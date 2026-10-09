from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox

MAX_CANDIDATE_COVERAGE = 0.30


class Florence2ConfigurationError(RuntimeError):
    """The optional local model is unavailable or violates its pinned manifest."""


@dataclass(frozen=True, slots=True)
class VerifiedModel:
    model_id: str
    revision: str
    directory: Path


class Florence2Runtime(Protocol):
    def predict(
        self, image: Image.Image, prompt: str
    ) -> tuple[dict[str, Any], ...]: ...


def verify_model_directory(model_dir: Path, manifest_path: Path) -> VerifiedModel:
    """Verify the exact local files allowed by the reviewed Florence-2 manifest."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Florence2ConfigurationError("Cannot read the Florence-2 model manifest.") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise Florence2ConfigurationError("Unsupported Florence-2 model manifest.")
    policy = manifest.get("runtime_policy")
    if not isinstance(policy, dict) or any(
        policy.get(field) is not expected
        for field, expected in {
            "automatic_download": False,
            "allow_remote_code": False,
            "allow_pickle_weights": False,
            "require_exact_revision": True,
            "require_sha256_verification": True,
        }.items()
    ):
        raise Florence2ConfigurationError("The model manifest weakens the local runtime policy.")
    if policy.get("required_weight_format") != "safetensors":
        raise Florence2ConfigurationError("Only Safetensors model weights are allowed.")

    root = model_dir.expanduser().resolve()
    if not root.is_dir():
        raise Florence2ConfigurationError(f"Local model directory does not exist: {root}")
    allowed_files = manifest.get("allowed_files")
    if not isinstance(allowed_files, list) or not allowed_files:
        raise Florence2ConfigurationError("The model manifest has no allowed files.")
    expected_names: set[str] = set()
    for record in allowed_files:
        if not isinstance(record, dict):
            raise Florence2ConfigurationError("Invalid model file record.")
        relative = record.get("path")
        size = record.get("size_bytes")
        digest = record.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise Florence2ConfigurationError("Invalid model file record.")
        expected_names.add(relative)
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise Florence2ConfigurationError(f"Missing regular model file: {relative}")
        if path.stat().st_size != size:
            raise Florence2ConfigurationError(f"Model file size mismatch: {relative}")
        if _sha256(path) != digest:
            raise Florence2ConfigurationError(f"Model file SHA-256 mismatch: {relative}")

    forbidden = {"pytorch_model.bin", "modeling_florence2.py", "processing_florence2.py"}
    present_forbidden = sorted(name for name in forbidden if (root / name).exists())
    if present_forbidden:
        raise Florence2ConfigurationError(
            f"Forbidden model files are present: {', '.join(present_forbidden)}"
        )
    if "model.safetensors" not in expected_names:
        raise Florence2ConfigurationError(
            "Pinned Safetensors weights are missing from the manifest."
        )
    return VerifiedModel(
        model_id=_required_text(manifest, "model_id"),
        revision=_required_text(manifest, "revision"),
        directory=root,
    )


class Florence2Localizer:
    """Optional Florence-2 locator that only opens a verified local model directory."""

    def __init__(
        self,
        model_dir: Path,
        manifest_path: Path,
        *,
        device: str = "auto",
        runtime: Florence2Runtime | None = None,
    ) -> None:
        verified = verify_model_directory(model_dir, manifest_path)
        self.model_id = verified.model_id
        self.model_revision = verified.revision
        self._runtime = runtime or _TransformersFlorence2Runtime(verified.directory, device)
        self.runtime_metadata = getattr(self._runtime, "metadata", {"kind": "injected"})

    def localize(self, image_path: Path, prompt: str) -> tuple[LocalizationBox, ...]:
        if not prompt.strip():
            raise ValueError("Florence-2 localization prompt must not be empty.")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        width, height = image.size
        boxes = []
        for candidate in self._runtime.predict(image, prompt.strip()):
            try:
                bbox = candidate["bbox"]
                if not isinstance(bbox, list | tuple) or len(bbox) != 4:
                    raise ValueError
                box = LocalizationBox(
                    x0=float(bbox[0]),
                    y0=float(bbox[1]),
                    x1=float(bbox[2]),
                    y1=float(bbox[3]),
                    label=str(candidate.get("label", "watermark")),
                    # Florence-2 generation does not expose calibrated box confidence.
                    confidence=1.0,
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise Florence2ConfigurationError("Florence-2 returned an invalid box.") from exc
            if box.x1 > width or box.y1 > height:
                raise Florence2ConfigurationError("Florence-2 returned an out-of-bounds box.")
            coverage = (box.x1 - box.x0) * (box.y1 - box.y0) / (width * height)
            if coverage > MAX_CANDIDATE_COVERAGE:
                continue
            boxes.append(box)
        return tuple(boxes)


class _TransformersFlorence2Runtime:
    task = "<OPEN_VOCABULARY_DETECTION>"

    def __init__(self, model_dir: Path, device: str) -> None:
        try:
            import torch
            import transformers

            from wmrm.vendor.florence2.modeling_florence2 import (
                Florence2ForConditionalGeneration,
            )
            from wmrm.vendor.florence2.processing_florence2 import Florence2Processor
        except ImportError as exc:
            raise Florence2ConfigurationError(
                "Florence-2 is optional. Install the 'vlm' extra before enabling it."
            ) from exc
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        if device not in {"cpu", "mps", "cuda"}:
            raise Florence2ConfigurationError("Florence-2 device must be auto, cpu, mps, or cuda.")
        if device == "cuda" and not torch.cuda.is_available():
            raise Florence2ConfigurationError("CUDA was requested but is unavailable.")
        if device == "mps" and not torch.backends.mps.is_available():
            raise Florence2ConfigurationError("MPS was requested but is unavailable.")
        try:
            self._processor = Florence2Processor.from_pretrained(
                model_dir, local_files_only=True
            )
            self._model = Florence2ForConditionalGeneration.from_pretrained(
                model_dir,
                local_files_only=True,
                use_safetensors=True,
                attn_implementation="eager",
            ).to(device)
        except Exception as exc:
            raise Florence2ConfigurationError(
                "Cannot load the verified local Florence-2 model."
            ) from exc
        self._model.eval()
        self._device = device
        self._torch = torch
        self.metadata = {
            "kind": "local-vendored-florence2",
            "device": device,
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "maximum_candidate_coverage": MAX_CANDIDATE_COVERAGE,
        }

    def predict(self, image: Image.Image, prompt: str) -> tuple[dict[str, Any], ...]:
        task_prompt = f"{self.task}{prompt}"
        inputs = self._processor(text=task_prompt, images=image, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        with self._torch.inference_mode():
            generated_ids = self._model.generate(
                **inputs, max_new_tokens=1024, num_beams=3, do_sample=False
            )
        generated_text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=False
        )[0]
        result = self._processor.post_process_generation(
            generated_text, task=self.task, image_size=image.size
        ).get(self.task, {})
        bboxes = result.get("bboxes", [])
        labels = result.get("bboxes_labels", result.get("labels", []))
        if (
            not isinstance(bboxes, list)
            or not isinstance(labels, list)
            or len(bboxes) != len(labels)
        ):
            raise Florence2ConfigurationError("Florence-2 returned an unsupported result shape.")
        return tuple(
            {"bbox": bbox, "label": label}
            for bbox, label in zip(bboxes, labels, strict=True)
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise Florence2ConfigurationError(f"Missing model manifest field: {field}")
    return value
