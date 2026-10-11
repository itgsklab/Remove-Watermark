from __future__ import annotations

import importlib.util
import json
import math
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from sqlalchemy.orm import Session

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.adapters.images.florence2 import (
    Florence2ConfigurationError,
    Florence2Localizer,
    VerifiedModel,
    verify_model_directory,
)
from wmrm.adapters.images.photo_scene import PhotoSceneGate
from wmrm.api.schemas import (
    AnalysisResponse,
    ImageMaskRegion,
    OptionalModelCapability,
    PhotoSceneAssessmentResponse,
    VlmSuggestionRequest,
    VlmSuggestionResponse,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.persistence.database import AnalysisRecord

LocalizerFactory = Callable[[Path, Path, str], Florence2Localizer]


class VlmSuggestionService:
    """Expose a local, opt-in locator as review-only image mask suggestions."""

    def __init__(
        self,
        assets: AssetService,
        *,
        enabled: bool,
        model_dir: Path | None,
        model_manifest: Path | None,
        device: str,
        localizer_factory: LocalizerFactory | None = None,
    ) -> None:
        self.assets = assets
        self.enabled = enabled
        self.model_dir = model_dir
        self.model_manifest = model_manifest
        self.device = device
        self._factory = localizer_factory or self._create_localizer
        self._factory_is_injected = localizer_factory is not None
        self._localizer: Florence2Localizer | None = None
        self._verified_model: VerifiedModel | None = None
        self._lock = Lock()

    def capability(self) -> OptionalModelCapability:
        if not self.enabled:
            return OptionalModelCapability(
                enabled=False,
                available=False,
                status="disabled",
                message="本地图片模型未启用；可以继续手工框选。",
            )
        try:
            verified = self._verify_configuration()
        except Florence2ConfigurationError:
            return OptionalModelCapability(
                enabled=True,
                available=False,
                status="configuration_invalid",
                message="本地模型文件或固定清单校验失败；可以继续手工框选。",
            )
        if not self._factory_is_injected and not self._runtime_installed():
            return OptionalModelCapability(
                enabled=True,
                available=False,
                status="runtime_missing",
                model_id=verified.model_id,
                message="未安装可选 VLM 运行依赖；可以继续手工框选。",
            )
        return OptionalModelCapability(
            enabled=True,
            available=True,
            status="ready",
            model_id=verified.model_id,
            message="本地照片水印候选建议已就绪，建议结果仍需人工检查。",
        )

    def suggest(
        self, session: Session, request: VlmSuggestionRequest
    ) -> VlmSuggestionResponse:
        capability = self.capability()
        if not capability.available:
            raise AssetError("VLM_NOT_AVAILABLE", capability.message, 409)

        asset = self.assets.get(session, request.asset_id)
        if asset.kind not in {"png", "jpeg", "webp"}:
            raise AssetError("VLM_NOT_AVAILABLE", "模型候选建议仅支持静态图片。", 409)
        record = session.get(AnalysisRecord, request.analysis_id)
        if record is None:
            raise AssetError("ANALYSIS_NOT_FOUND", "找不到该扫描结果。", 404)
        analysis = AnalysisResponse.model_validate(json.loads(record.result_json))
        metadata = analysis.image_metadata
        if analysis.preset != "image" or metadata is None:
            raise AssetError("VLM_NOT_AVAILABLE", "模型候选建议需要图片检查结果。", 409)
        if analysis.asset_id != asset.id or analysis.asset_sha256 != asset.sha256:
            raise AssetError("PLAN_STALE", "图片检查结果已经失效，请重新检查。", 409)
        if metadata.animated:
            raise AssetError("VLM_NOT_AVAILABLE", "动态图不支持模型候选建议。", 409)

        path = self.assets.path_for(asset)
        assessment = PhotoSceneGate().assess(path)
        photo_scene = PhotoSceneAssessmentResponse(
            eligible=assessment.eligible,
            matched_routes=list(assessment.matched_routes),
            reasons=list(assessment.reasons),
        )
        if not assessment.eligible:
            return VlmSuggestionResponse(
                asset_id=asset.id,
                analysis_id=analysis.id,
                status="photo_gate_rejected",
                regions=[],
                photo_scene=photo_scene,
                warnings=["图片未通过照片场景门禁，模型没有运行；请继续手工框选。"],
            )

        try:
            boxes = self._get_localizer().localize(path, "watermark")
            regions = self._validate_regions(
                boxes,
                width=metadata.display_width,
                height=metadata.display_height,
                transform_id=metadata.transform_id,
            )
        except (Florence2ConfigurationError, OSError, RuntimeError, ValueError) as exc:
            raise AssetError(
                "VLM_INFERENCE_FAILED",
                "本地模型未能生成候选区域；请继续手工框选。",
                503,
            ) from exc
        status = "suggested" if regions else "no_candidates"
        warning = (
            "模型候选只是蒙版草稿；请逐个检查、调整并验证后再处理。"
            if regions
            else "模型没有提出候选区域；请继续手工框选。"
        )
        return VlmSuggestionResponse(
            asset_id=asset.id,
            analysis_id=analysis.id,
            status=status,
            regions=regions,
            photo_scene=photo_scene,
            warnings=[warning],
        )

    def _verify_configuration(self) -> VerifiedModel:
        if self._verified_model is not None:
            return self._verified_model
        if self.model_dir is None or self.model_manifest is None:
            raise Florence2ConfigurationError("Local model paths are not configured.")
        self._verified_model = verify_model_directory(self.model_dir, self.model_manifest)
        return self._verified_model

    def _get_localizer(self) -> Florence2Localizer:
        if self._localizer is None:
            with self._lock:
                if self._localizer is None:
                    if self.model_dir is None or self.model_manifest is None:
                        raise Florence2ConfigurationError("Local model paths are not configured.")
                    self._localizer = self._factory(
                        self.model_dir, self.model_manifest, self.device
                    )
        return self._localizer

    @staticmethod
    def _create_localizer(
        model_dir: Path, model_manifest: Path, device: str
    ) -> Florence2Localizer:
        return Florence2Localizer(model_dir, model_manifest, device=device)

    @staticmethod
    def _validate_regions(
        boxes: tuple[LocalizationBox, ...], *, width: int, height: int, transform_id: str
    ) -> list[ImageMaskRegion]:
        if len(boxes) > 100:
            raise Florence2ConfigurationError("The local model returned too many boxes.")
        regions = []
        for box in boxes:
            coordinates = (box.x0, box.y0, box.x1, box.y1)
            if (
                not all(math.isfinite(value) for value in coordinates)
                or box.x0 < 0
                or box.y0 < 0
                or box.x0 >= box.x1
                or box.y0 >= box.y1
                or box.x1 > width
                or box.y1 > height
            ):
                raise Florence2ConfigurationError("The local model returned an invalid box.")
            coverage = (box.x1 - box.x0) * (box.y1 - box.y0) / (width * height)
            if coverage > 0.30:
                continue
            regions.append(
                ImageMaskRegion(
                    x0=box.x0,
                    y0=box.y0,
                    x1=box.x1,
                    y1=box.y1,
                    transform_id=transform_id,
                )
            )
        return regions

    @staticmethod
    def _runtime_installed() -> bool:
        packages = ("einops", "safetensors", "timm", "torch", "transformers")
        return all(importlib.util.find_spec(name) is not None for name in packages)
