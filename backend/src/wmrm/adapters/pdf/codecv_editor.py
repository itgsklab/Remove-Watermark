import hashlib
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError
from pypdf.generic import ContentStream, DecodedStreamObject

from wmrm.adapters.pdf.codecv import CodeCvPdfInspector


class CodeCvEditError(Exception):
    pass


def remove_codecv_candidates(
    source_path: Path,
    output_path: Path,
    candidates: list[dict[str, Any]],
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, object]:
    _raise_if_cancelled(should_cancel)
    try:
        source = PdfReader(str(source_path), strict=False)
        if source.is_encrypted:
            raise CodeCvEditError("PDF 已加密，无法处理。")
        before_boxes = [_page_boxes(page) for page in source.pages]
        before_text_ops = [_direct_text_operations(page, source) for page in source.pages]
        before_matches = _count_matches(source)

        selected = _group_candidates(candidates, len(source.pages))
        writer = PdfWriter(clone_from=source)
        removed_count = 0
        changed_pages: list[int] = []
        for page_number, page_candidates in sorted(selected.items()):
            _raise_if_cancelled(should_cancel)
            page = writer.pages[page_number - 1]
            contents = page.get_contents()
            if contents is None:
                raise CodeCvEditError(f"第 {page_number} 页缺少候选对应的内容流。")
            stream = ContentStream(contents, writer)
            operations = stream.operations
            for candidate in sorted(
                page_candidates,
                key=lambda item: int(item["source_locator"]["operation_index"]),
                reverse=True,
            ):
                locator = candidate["source_locator"]
                operation_index = int(locator["operation_index"])
                matched_count, pattern_name = CodeCvPdfInspector._match_pattern_fill(
                    operations, operation_index
                )
                if not matched_count or pattern_name != locator["resource_name"]:
                    raise CodeCvEditError(
                        f"第 {page_number} 页的候选定位已变化，请重新扫描。"
                    )
                del operations[operation_index : operation_index + matched_count]
                removed_count += 1
            replacement = DecodedStreamObject()
            replacement.set_data(stream.get_data())
            page.replace_contents(replacement)
            changed_pages.append(page_number)

        if removed_count != len(candidates):
            raise CodeCvEditError("实际删除数量与处理计划不一致。")
        _raise_if_cancelled(should_cancel)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as output:
            writer.write(output)

        _raise_if_cancelled(should_cancel)
        result = PdfReader(str(output_path), strict=True)
        if result.is_encrypted or len(result.pages) != len(source.pages):
            raise CodeCvEditError("输出 PDF 的加密状态或页数发生异常变化。")
        if [_page_boxes(page) for page in result.pages] != before_boxes:
            raise CodeCvEditError("输出 PDF 的页面尺寸发生变化。")
        if [_direct_text_operations(page, result) for page in result.pages] != before_text_ops:
            raise CodeCvEditError("输出 PDF 的正文文字操作发生变化。")
        if _count_matches(result) != before_matches - removed_count:
            raise CodeCvEditError("输出 PDF 中的目标操作数量未按计划减少。")

        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return {
            "removed_count": removed_count,
            "changed_pages": changed_pages,
            "size_bytes": output_path.stat().st_size,
            "sha256": digest,
        }
    except CancelledError:
        output_path.unlink(missing_ok=True)
        raise
    except (CodeCvEditError, PyPdfError, OSError, TypeError, ValueError) as exc:
        output_path.unlink(missing_ok=True)
        if isinstance(exc, CodeCvEditError):
            raise
        raise CodeCvEditError(f"PDF 处理或校验失败：{exc}") from exc


def _group_candidates(
    candidates: list[dict[str, Any]], page_count: int
) -> dict[int, list[dict[str, Any]]]:
    if not candidates:
        raise CodeCvEditError("处理计划未包含候选。")
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    positions: set[tuple[int, int]] = set()
    for candidate in candidates:
        locator = candidate.get("source_locator", {})
        pages = locator.get("page_numbers") or []
        operation_index = locator.get("operation_index")
        resource_name = locator.get("resource_name")
        if len(pages) != 1 or operation_index is None or not resource_name:
            raise CodeCvEditError("候选缺少 PDF 页码、操作位置或图案资源定位。")
        page_number = int(pages[0])
        position = (page_number, int(operation_index))
        if page_number < 1 or page_number > page_count or position in positions:
            raise CodeCvEditError("候选页码或操作位置无效。")
        positions.add(position)
        grouped[page_number].append(candidate)
    return grouped


def _count_matches(reader: PdfReader) -> int:
    count = 0
    for page in reader.pages:
        contents = page.get_contents()
        if contents is None:
            continue
        operations = ContentStream(contents, reader).operations
        index = 0
        while index < len(operations):
            matched_count, _ = CodeCvPdfInspector._match_pattern_fill(operations, index)
            if matched_count:
                count += 1
                index += matched_count
            else:
                index += 1
    return count


def _page_boxes(page: Any) -> tuple[tuple[float, ...], tuple[float, ...], int]:
    return (
        tuple(float(item) for item in page.mediabox),
        tuple(float(item) for item in page.cropbox),
        int(page.get("/Rotate", 0)),
    )


def _direct_text_operations(page: Any, pdf: Any) -> tuple[tuple[bytes, str], ...]:
    contents = page.get_contents()
    if contents is None:
        return ()
    text_operators = {b"Tj", b"TJ", b"'", b'"'}
    return tuple(
        (operator, repr(operands))
        for operands, operator in ContentStream(contents, pdf).operations
        if operator in text_operators
    )


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise CancelledError("任务已取消。")
