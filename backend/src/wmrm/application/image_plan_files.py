from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wmrm.adapters.images.complexity import ImageComplexityInspector
from wmrm.adapters.images.metadata import ImageInspector
from wmrm.adapters.images.plan_risk import build_image_plan_warnings
from wmrm.adapters.images.selection_risk import (
    LARGE_SELECTION_THRESHOLD,
    ImageSelectionRiskInspector,
)
from wmrm.api.schemas import (
    ImageComplexityResponse,
    ImageMaskRegion,
    ImageMetadataResponse,
    ImageRegionComplexity,
    ImageRegionSelectionRisk,
    ImageSelectionRiskResponse,
    PlanWarning,
)
from wmrm.application.assets import AssetError, detect_kind
from wmrm.application.image_masks import rectangle_union_area
from wmrm.settings import Settings

MAX_PLAN_BYTES = 1024 * 1024


class ImagePlanFileError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ImagePlanFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    kind: Literal["image_inpaint"] = "image_inpaint"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_size_bytes: int = Field(gt=0)
    source_kind: Literal["png", "jpeg", "webp"]
    metadata: ImageMetadataResponse
    regions: list[ImageMaskRegion] = Field(min_length=1, max_length=100)
    radius: int = Field(ge=1, le=10)
    covered_pixels: float = Field(gt=0)
    coverage_ratio: float = Field(gt=0, le=1)
    complexity: ImageComplexityResponse
    selection_risk: ImageSelectionRiskResponse
    warnings: list[PlanWarning]
    required_acknowledgements: list[str]
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")


def create_image_plan(
    source: Path,
    raw_regions: list[dict[str, float]],
    radius: int,
    *,
    settings: Settings | None = None,
) -> ImagePlanFile:
    config = settings or Settings()
    if not 1 <= radius <= 10:
        raise ImagePlanFileError("IMAGE_RADIUS_INVALID", "Radius must be between 1 and 10.")
    try:
        size_bytes = source.stat().st_size
        if size_bytes <= 0 or size_bytes > config.max_upload_bytes:
            raise ImagePlanFileError(
                "IMAGE_RESOURCE_LIMIT",
                f"Image must contain 1 to {config.max_upload_bytes} bytes.",
            )
        digest = _sha256(source)
        with source.open("rb") as handle:
            asset_kind, _ = detect_kind(handle.read(32), source.name)
        if asset_kind.value not in {"png", "jpeg", "webp"}:
            raise ImagePlanFileError(
                "IMAGE_INPUT_INVALID", "Input must be PNG, JPEG or WebP."
            )
        inspection = ImageInspector(
            config.max_image_dimension,
            config.max_image_pixels,
            config.max_image_frames,
        ).inspect(source, digest, asset_kind.value)
    except ImagePlanFileError:
        raise
    except AssetError as exc:
        raise ImagePlanFileError(exc.code, str(exc)) from exc
    except OSError as exc:
        raise ImagePlanFileError("IMAGE_INPUT_INVALID", "Image could not be read.") from exc

    if inspection.animated:
        raise ImagePlanFileError(
            "IMAGE_ANIMATION_UNSUPPORTED",
            "Animated images cannot be used in an inpainting plan.",
        )
    regions = _validated_regions(raw_regions, inspection)
    covered_pixels = rectangle_union_area(regions)
    coverage_ratio = covered_pixels / (
        inspection.display_width * inspection.display_height
    )
    complexity_items = ImageComplexityInspector().inspect(source, regions)
    risk_order = {"low": 0, "review": 1, "high": 2}
    complexity_level = max(
        (item.risk for item in complexity_items), key=risk_order.__getitem__
    )
    complexity = ImageComplexityResponse(
        level=complexity_level,
        regions=[ImageRegionComplexity(**asdict(item)) for item in complexity_items],
    )
    selection_items = ImageSelectionRiskInspector().inspect(source, regions)
    large_selection = coverage_ratio >= LARGE_SELECTION_THRESHOLD
    selection_risk = ImageSelectionRiskResponse(
        level=(
            "review"
            if large_selection or any(item.low_contrast for item in selection_items)
            else "normal"
        ),
        large_selection=large_selection,
        regions=[ImageRegionSelectionRisk(**asdict(item)) for item in selection_items],
    )
    warnings = [
        PlanWarning(
            code=item.code,
            message=item.message,
            requires_acknowledgement=item.requires_acknowledgement,
        )
        for item in build_image_plan_warnings(
            coverage_ratio, selection_items, complexity_level
        )
    ]
    metadata = ImageMetadataResponse(
        **{
            key: value
            for key, value in asdict(inspection).items()
            if key not in {"inspected_parts", "warnings"}
        }
    )
    payload = {
        "schema_version": 1,
        "kind": "image_inpaint",
        "source_sha256": digest,
        "source_size_bytes": size_bytes,
        "source_kind": asset_kind.value,
        "metadata": metadata.model_dump(mode="json"),
        "regions": [item.model_dump(mode="json") for item in regions],
        "radius": radius,
        "covered_pixels": covered_pixels,
        "coverage_ratio": coverage_ratio,
        "complexity": complexity.model_dump(mode="json"),
        "selection_risk": selection_risk.model_dump(mode="json"),
        "warnings": [item.model_dump(mode="json") for item in warnings],
        "required_acknowledgements": [
            item.code for item in warnings if item.requires_acknowledgement
        ],
    }
    return ImagePlanFile(**payload, plan_id=_payload_digest(payload))


def load_image_plan(path: Path) -> ImagePlanFile:
    try:
        if path.stat().st_size > MAX_PLAN_BYTES:
            raise ImagePlanFileError("IMAGE_PLAN_INVALID", "Image plan is too large.")
        plan = ImagePlanFile.model_validate_json(path.read_text(encoding="utf-8"))
    except ImagePlanFileError:
        raise
    except (OSError, UnicodeError, ValidationError, ValueError) as exc:
        raise ImagePlanFileError(
            "IMAGE_PLAN_INVALID", "Image plan is missing or malformed."
        ) from exc
    expected = _payload_digest(plan.model_dump(mode="json", exclude={"plan_id"}))
    if plan.plan_id != expected:
        raise ImagePlanFileError(
            "IMAGE_PLAN_INTEGRITY_FAILED", "Image plan content does not match its plan ID."
        )
    return plan


def revalidate_image_plan(source: Path, plan: ImagePlanFile) -> ImagePlanFile:
    fresh = create_image_plan(
        source,
        [
            {"x0": item.x0, "y0": item.y0, "x1": item.x1, "y1": item.y1}
            for item in plan.regions
        ],
        plan.radius,
    )
    if fresh.model_dump(mode="json") != plan.model_dump(mode="json"):
        raise ImagePlanFileError(
            "IMAGE_PLAN_STALE",
            "Image content, geometry or risk assessment has changed; create a new plan.",
        )
    return fresh


def serialize_image_plan(plan: ImagePlanFile) -> str:
    return json.dumps(
        plan.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"


def _validated_regions(raw_regions, inspection) -> list[ImageMaskRegion]:
    regions = []
    if not 1 <= len(raw_regions) <= 100:
        raise ImagePlanFileError("IMAGE_REGION_INVALID", "Provide 1 to 100 regions.")
    for item in raw_regions:
        values = (item["x0"], item["y0"], item["x1"], item["y1"])
        if (
            not all(math.isfinite(value) for value in values)
            or item["x0"] < 0
            or item["y0"] < 0
            or item["x1"] > inspection.display_width
            or item["y1"] > inspection.display_height
            or item["x0"] >= item["x1"]
            or item["y0"] >= item["y1"]
        ):
            raise ImagePlanFileError(
                "IMAGE_REGION_INVALID", "Image region is reversed or outside display bounds."
            )
        regions.append(ImageMaskRegion(**item, transform_id=inspection.transform_id))
    return regions


def _payload_digest(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
