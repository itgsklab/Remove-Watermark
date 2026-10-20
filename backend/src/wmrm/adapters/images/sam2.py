from __future__ import annotations

import platform
from pathlib import Path
from typing import Literal, Protocol

import numpy as np
from PIL import Image, ImageOps

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.adapters.images.segmentation import SegmentationMask
from wmrm.benchmarks.model_supply_chain import audit_model_manifest


class Sam2ConfigurationError(RuntimeError):
    """The evaluation-only SAM2 runtime is unavailable or violates its manifest."""


class Sam2Runtime(Protocol):
    metadata: dict[str, object]

    def predict(self, image: Image.Image, boxes: tuple[LocalizationBox, ...]) -> np.ndarray: ...


class Sam2MaskRefiner:
    """Evaluation-only box-prompted SAM2 refiner using verified local files."""

    def __init__(
        self,
        model_dir: Path,
        manifest_path: Path,
        *,
        device: str = "auto",
        mask_selection: Literal["single", "highest-iou"] = "single",
        runtime: Sam2Runtime | None = None,
    ) -> None:
        if mask_selection not in {"single", "highest-iou"}:
            raise ValueError("SAM2 mask selection must be single or highest-iou.")
        report = audit_model_manifest(manifest_path, model_dir=model_dir)
        self.model_id = str(report["model_id"])
        self.model_revision = str(report["revision"])
        self.mask_selection = mask_selection
        self._runtime = runtime or _TransformersSam2Runtime(
            model_dir.resolve(),
            device,
            mask_selection,
        )
        self.runtime_metadata = dict(self._runtime.metadata)
        self.runtime_metadata.setdefault("mask_selection", mask_selection)

    def refine(
        self,
        image_path: Path,
        boxes: tuple[LocalizationBox, ...],
    ) -> SegmentationMask:
        if not boxes:
            raise ValueError("SAM2 refinement requires at least one candidate box.")
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = image.size
        for box in boxes:
            if box.x1 > width or box.y1 > height:
                raise ValueError("SAM2 candidate box leaves image bounds.")
        predicted = np.asarray(self._runtime.predict(image, boxes), dtype=bool)
        if predicted.shape != (height, width):
            raise Sam2ConfigurationError("SAM2 returned a mask with incorrect dimensions.")
        candidate_union = np.zeros((height, width), dtype=bool)
        for box in boxes:
            x0, y0 = int(np.floor(box.x0)), int(np.floor(box.y0))
            x1, y1 = int(np.ceil(box.x1)), int(np.ceil(box.y1))
            candidate_union[y0:y1, x0:x1] = True
        predicted &= candidate_union
        return SegmentationMask(width, height, predicted.astype(np.uint8).tobytes())


class _TransformersSam2Runtime:
    def __init__(
        self,
        model_dir: Path,
        device: str,
        mask_selection: Literal["single", "highest-iou"],
    ) -> None:
        try:
            import torch
            import transformers
            from transformers import AutoConfig, Sam2Model, Sam2Processor
        except ImportError as exc:
            raise Sam2ConfigurationError(
                "SAM2 evaluation requires the isolated segmentation environment."
            ) from exc
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        if device not in {"cpu", "mps", "cuda"}:
            raise Sam2ConfigurationError("SAM2 device must be auto, cpu, mps, or cuda.")
        if device == "cuda" and not torch.cuda.is_available():
            raise Sam2ConfigurationError("CUDA was requested but is unavailable.")
        if device == "mps" and not torch.backends.mps.is_available():
            raise Sam2ConfigurationError("MPS was requested but is unavailable.")
        try:
            source_config = AutoConfig.from_pretrained(model_dir, local_files_only=True)
            self._processor = Sam2Processor.from_pretrained(
                model_dir,
                local_files_only=True,
            )
            self._model, loading_info = Sam2Model.from_pretrained(
                model_dir,
                local_files_only=True,
                use_safetensors=True,
                output_loading_info=True,
            )
            loading_issues = sum(
                len(loading_info.get(name, ()))
                for name in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
            )
            if loading_issues:
                raise Sam2ConfigurationError(
                    "SAM2 checkpoint does not exactly match the image runtime."
                )
            self._model = self._model.to(device)
        except Exception as exc:
            raise Sam2ConfigurationError("Cannot load the verified local SAM2 model.") from exc
        self._model.eval()
        self._device = device
        self._torch = torch
        self._mask_selection = mask_selection
        self.metadata = {
            "kind": "local-transformers-sam2",
            "device": device,
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "platform": platform.system().lower(),
            "architecture": platform.machine().lower(),
            "source_config_model_type": source_config.model_type,
            "runtime_model_class": type(self._model).__name__,
            "checkpoint_load_issues": loading_issues,
            "candidate_box_clipping": True,
            "mask_selection": mask_selection,
            "multimask_output": mask_selection == "highest-iou",
        }

    def predict(self, image: Image.Image, boxes: tuple[LocalizationBox, ...]) -> np.ndarray:
        input_boxes = [
            [[box.x0, box.y0, box.x1, box.y1] for box in boxes]
        ]
        inputs = self._processor(
            images=image,
            input_boxes=input_boxes,
            return_tensors="pt",
        ).to(self._device)
        original_sizes = inputs["original_sizes"].cpu()
        with self._torch.inference_mode():
            outputs = self._model(
                **inputs,
                multimask_output=self._mask_selection == "highest-iou",
            )
        masks = self._processor.post_process_masks(
            outputs.pred_masks.cpu(),
            original_sizes,
        )[0]
        values = masks.detach().cpu().numpy().astype(bool)
        scores = outputs.iou_scores.detach().cpu().numpy()
        selected = _select_predicted_masks(
            values,
            scores,
            box_count=len(boxes),
            mask_selection=self._mask_selection,
        )
        return np.logical_or.reduce(selected, axis=0)


def _select_predicted_masks(
    values: np.ndarray,
    scores: np.ndarray,
    *,
    box_count: int,
    mask_selection: Literal["single", "highest-iou"],
) -> np.ndarray:
    """Select one SAM2 mask per box without consulting evaluation ground truth."""
    while values.ndim > 4 and values.shape[0] == 1:
        values = values[0]
    if values.ndim == 3:
        values = values[:, None, :, :]
    if values.ndim != 4 or values.shape[0] != box_count:
        raise Sam2ConfigurationError("SAM2 returned an unsupported mask tensor.")

    while scores.ndim > 2 and scores.shape[0] == 1:
        scores = scores[0]
    if scores.ndim == 1:
        scores = scores[:, None]
    if scores.shape != values.shape[:2]:
        raise Sam2ConfigurationError("SAM2 returned incompatible mask scores.")
    if mask_selection == "single":
        if values.shape[1] != 1:
            raise Sam2ConfigurationError("SAM2 single-mask mode returned multiple masks.")
        return values[:, 0]
    indices = np.argmax(scores, axis=1)
    return values[np.arange(box_count), indices]
