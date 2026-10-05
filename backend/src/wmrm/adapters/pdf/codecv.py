import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import ContentStream, IndirectObject, NameObject

from wmrm.application.assets import AssetError


@dataclass(frozen=True, slots=True)
class CodeCvCandidate:
    candidate_id: str
    classification: str
    kind: str
    content: str
    evidence: str
    page_number: int
    resource_name: str | None
    object_number: int | None
    generation_number: int | None
    operation_index: int
    style: str | None
    allowed_strategies: tuple[str, ...] = ("object",)


@dataclass(frozen=True, slots=True)
class CodeCvInspection:
    candidates: tuple[CodeCvCandidate, ...]
    inspected_parts: tuple[str, ...]
    warnings: tuple[str, ...]
    match_status: str


class CodeCvPdfInspector:
    """Read-only detector for CodeCV's tiled pattern-fill operation signature."""

    def __init__(self, max_pages: int, max_content_bytes: int) -> None:
        self.max_pages = max_pages
        self.max_content_bytes = max_content_bytes

    def inspect(self, path: Path, asset_sha256: str) -> CodeCvInspection:
        try:
            reader = PdfReader(str(path), strict=False)
            if reader.is_encrypted:
                raise AssetError("PASSWORD_REQUIRED", "PDF 已加密，需要先移除密码保护。", 422)
            if len(reader.pages) > self.max_pages:
                raise AssetError(
                    "RESOURCE_LIMIT",
                    f"PDF 页数超过 {self.max_pages} 页限制。",
                    413,
                )

            candidates: list[CodeCvCandidate] = []
            inspected_parts: list[str] = []
            content_bytes = 0
            for page_number, page in enumerate(reader.pages, start=1):
                inspected_parts.append(f"page:{page_number}")
                contents = page.get_contents()
                if contents is None:
                    continue
                stream = ContentStream(contents, reader)
                content_bytes += len(stream.get_data())
                if content_bytes > self.max_content_bytes:
                    raise AssetError(
                        "RESOURCE_LIMIT",
                        "PDF 解码后的页面内容流超过安全限制。",
                        413,
                    )
                candidates.extend(
                    self._inspect_operations(
                        stream.operations,
                        page,
                        page_number,
                        asset_sha256,
                    )
                )
        except AssetError:
            raise
        except (PyPdfError, OSError, ValueError, TypeError) as exc:
            raise AssetError("INVALID_PDF", "文件不是可安全解析的 PDF。", 422) from exc

        if any(item.classification == "confirmed" for item in candidates):
            warnings = (
                "已匹配 CodeCV 平铺水印操作签名；扫描只展示证据，创建任务后会生成新副本。",
            )
            match_status = "matched"
        elif candidates:
            warnings = (
                "发现相似的 Pattern 填充操作，但无法确认对应 tiling pattern 资源，需要人工复核。",
            )
            match_status = "needs_review"
        else:
            warnings = (
                "没有匹配 CodeCV 平铺水印操作签名；这不代表 PDF 中不存在其他类型水印。",
            )
            match_status = "not_found"
        return CodeCvInspection(
            candidates=tuple(candidates),
            inspected_parts=tuple(inspected_parts),
            warnings=warnings,
            match_status=match_status,
        )

    def _inspect_operations(
        self,
        operations: list[tuple[list[Any], bytes]],
        page: Any,
        page_number: int,
        asset_sha256: str,
    ) -> list[CodeCvCandidate]:
        results: list[CodeCvCandidate] = []
        for index in range(len(operations)):
            matched_count, pattern_name = self._match_pattern_fill(operations, index)
            if not matched_count or pattern_name is None:
                continue
            pattern_ref, pattern = self._resolve_pattern(page, pattern_name)
            is_tiling_pattern = pattern is not None and int(pattern.get("/PatternType", 0)) == 1
            classification = "confirmed" if is_tiling_pattern else "ambiguous"
            evidence = (
                "内容流连续设置描边和填充 Pattern 色彩空间，SCN/scn 使用同一资源，"
                "随后填充矩形"
            )
            if is_tiling_pattern:
                evidence += "；资源字典确认该对象为 tiling pattern"
            else:
                evidence += "；无法从资源字典确认 tiling pattern，需要人工复核"

            object_number = pattern_ref.idnum if isinstance(pattern_ref, IndirectObject) else None
            generation_number = (
                pattern_ref.generation if isinstance(pattern_ref, IndirectObject) else None
            )
            style = self._pattern_style(pattern)
            digest = hashlib.sha256(
                (
                    f"{asset_sha256}|{page_number}|{index}|{pattern_name}|"
                    f"{object_number}|{generation_number}"
                ).encode()
            ).hexdigest()[:20]
            results.append(
                CodeCvCandidate(
                    candidate_id=f"codecv-{digest}",
                    classification=classification,
                    kind="pattern",
                    content=f"CodeCV 平铺图案（资源 {pattern_name}）",
                    evidence=evidence,
                    page_number=page_number,
                    resource_name=pattern_name,
                    object_number=object_number,
                    generation_number=generation_number,
                    operation_index=index,
                    style=style,
                )
            )
        return results

    @staticmethod
    def _match_pattern_fill(
        operations: list[tuple[list[Any], bytes]], index: int
    ) -> tuple[int, str | None]:
        if index + 5 >= len(operations):
            return 0, None
        op0, op1, op2, op3 = operations[index : index + 4]
        uses_pattern_space = (
            op0[1] == b"CS"
            and op1[1] == b"cs"
            and len(op0[0]) == 1
            and len(op1[0]) == 1
            and CodeCvPdfInspector._is_name(op0[0][0], "/Pattern")
            and CodeCvPdfInspector._is_name(op1[0][0], "/Pattern")
        )
        if not uses_pattern_space or op2[1] != b"SCN" or op3[1] != b"scn":
            return 0, None
        stroke_pattern = CodeCvPdfInspector._first_name(op2[0])
        fill_pattern = CodeCvPdfInspector._first_name(op3[0])
        if stroke_pattern is None or stroke_pattern != fill_pattern:
            return 0, None

        fill_index = index + 4
        if fill_index < len(operations) and operations[fill_index][1] == b"gs":
            fill_index += 1
        if fill_index + 1 >= len(operations):
            return 0, None
        rect_op, fill_op = operations[fill_index : fill_index + 2]
        if rect_op[1] != b"re" or fill_op[1] not in {b"f", b"f*"}:
            return 0, None
        return fill_index + 2 - index, fill_pattern

    @staticmethod
    def _is_name(value: Any, expected: str) -> bool:
        return isinstance(value, NameObject) and str(value) == expected

    @staticmethod
    def _first_name(operands: list[Any]) -> str | None:
        return next((str(item) for item in operands if isinstance(item, NameObject)), None)

    @staticmethod
    def _resolve_pattern(page: Any, pattern_name: str) -> tuple[Any | None, Any | None]:
        resources = page.get("/Resources")
        patterns = resources.get("/Pattern") if resources else None
        if not patterns:
            return None, None
        key = NameObject(pattern_name)
        try:
            reference = patterns.raw_get(key)
        except (KeyError, AttributeError):
            return None, None
        try:
            return reference, reference.get_object()
        except (PyPdfError, AttributeError):
            return reference, None

    @staticmethod
    def _pattern_style(pattern: Any | None) -> str | None:
        if pattern is None:
            return None
        values: dict[str, Any] = {}
        for key in ("/PatternType", "/PaintType", "/TilingType", "/BBox", "/XStep", "/YStep"):
            if key not in pattern:
                continue
            value = pattern[key]
            if isinstance(value, (list, tuple)):
                values[key[1:]] = [float(item) for item in value]
            elif isinstance(value, (int, float)):
                values[key[1:]] = float(value)
            else:
                values[key[1:]] = str(value)
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))
