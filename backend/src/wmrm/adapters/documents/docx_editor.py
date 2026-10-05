import hashlib
import os
import posixpath
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import CancelledError
from pathlib import Path
from urllib.parse import unquote
from xml.etree.ElementTree import Element, ParseError, tostring
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from wmrm.adapters.documents.docx import VML


class DocxEditError(Exception):
    pass


def _shape_text(shape: Element) -> str | None:
    values = []
    for textpath in shape.iter(f"{{{VML}}}textpath"):
        value = textpath.attrib.get("string")
        if value and value.strip():
            values.append(value.strip())
    return " ".join(values) or None


def _parse_xml(data: bytes) -> Element:
    return fromstring(data)


def remove_docx_candidates(
    source_path: Path,
    output_path: Path,
    candidates: list[dict],
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, str | int]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["source_locator"]["part_name"]].append(candidate)

    output_path.parent.mkdir(parents=True, exist_ok=False)
    temporary_path = output_path.with_suffix(".tmp")
    try:
        _raise_if_cancelled(should_cancel)
        with ZipFile(source_path) as source, ZipFile(
            temporary_path, "x", compression=ZIP_DEFLATED
        ) as output:
            names = set(source.namelist())
            if not set(grouped).issubset(names):
                raise DocxEditError("计划引用的 DOCX 部件不存在。")
            for info in source.infolist():
                _raise_if_cancelled(should_cancel)
                data = source.read(info.filename)
                part_candidates = grouped.get(info.filename)
                if part_candidates:
                    root = _parse_xml(data)
                    shapes = list(root.iter(f"{{{VML}}}shape"))
                    selected_shapes: list[Element] = []
                    parents = {child: parent for parent in root.iter() for child in parent}
                    for candidate in part_candidates:
                        locator = candidate["source_locator"]
                        index = locator["shape_index"]
                        if index >= len(shapes):
                            raise DocxEditError("水印形状位置已经变化，请重新扫描。")
                        shape = shapes[index]
                        if (
                            shape.attrib.get("id") != locator.get("shape_id")
                            or shape.attrib.get("type") != locator.get("shape_type")
                            or _shape_text(shape) != candidate.get("content")
                        ):
                            raise DocxEditError("水印形状内容已经变化，请重新扫描。")
                        selected_shapes.append(shape)
                    for shape in selected_shapes:
                        parent = parents.get(shape)
                        if parent is None:
                            raise DocxEditError("水印形状没有可删除的父节点。")
                        parent.remove(shape)
                    data = tostring(
                        root,
                        encoding="UTF-8",
                        xml_declaration=True,
                    )
                output.writestr(info, data)
        _raise_if_cancelled(should_cancel)
        os.replace(temporary_path, output_path)
        _validate_output(source_path, output_path, set(grouped))
        _raise_if_cancelled(should_cancel)
    except CancelledError:
        output_path.unlink(missing_ok=True)
        raise
    except DocxEditError:
        output_path.unlink(missing_ok=True)
        raise
    except (BadZipFile, DefusedXmlException, ParseError, OSError) as exc:
        output_path.unlink(missing_ok=True)
        raise DocxEditError(f"生成 DOCX 失败：{exc}") from exc
    finally:
        temporary_path.unlink(missing_ok=True)

    digest = hashlib.sha256()
    with output_path.open("rb") as output_file:
        for chunk in iter(lambda: output_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": output_path.stat().st_size,
        "removed_count": len(candidates),
    }


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise CancelledError("任务已取消。")


def _validate_output(source_path: Path, output_path: Path, changed_parts: set[str]) -> None:
    with ZipFile(source_path) as source, ZipFile(output_path) as output:
        source_names = source.namelist()
        if output.namelist() != source_names:
            raise DocxEditError("输出 DOCX 的内部文件列表发生异常变化。")
        required = {"[Content_Types].xml", "word/document.xml"}
        if not required.issubset(source_names):
            raise DocxEditError("输出文件缺少 DOCX 必需部件。")
        for name in source_names:
            output_data = output.read(name)
            if name not in changed_parts and output_data != source.read(name):
                raise DocxEditError(f"非目标部件 {name} 发生了变化。")
            if name in changed_parts:
                _parse_xml(output_data)
        _validate_relationships(output)


def _validate_relationships(package: ZipFile) -> None:
    names = set(package.namelist())
    for relationship_part in (name for name in names if name.endswith(".rels")):
        root = _parse_xml(package.read(relationship_part))
        owner_directory = Path(relationship_part).parent.parent.as_posix()
        if owner_directory == ".":
            owner_directory = ""
        for relationship in root:
            if not relationship.tag.endswith("Relationship"):
                continue
            if relationship.attrib.get("TargetMode", "").casefold() == "external":
                continue
            target = unquote(relationship.attrib.get("Target", "")).split("#", 1)[0]
            if not target:
                raise DocxEditError(f"关系部件 {relationship_part} 包含空目标。")
            if target.startswith("/"):
                resolved = posixpath.normpath(target.lstrip("/"))
            else:
                resolved = posixpath.normpath(posixpath.join(owner_directory, target))
            if resolved == ".." or resolved.startswith("../") or resolved not in names:
                raise DocxEditError(f"关系部件 {relationship_part} 引用了无效目标。")
