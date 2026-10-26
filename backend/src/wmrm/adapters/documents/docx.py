import hashlib
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile, ZipInfo

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from wmrm.application.assets import AssetError

VML = "urn:schemas-microsoft-com:vml"
HEADER_FOOTER_PATTERN = re.compile(r"^word/(?:header|footer)\d+\.xml$")
WATERMARK_SHAPE_TYPE = "#_x0000_t136"
IMAGE_RELATIONSHIP_SUFFIX = "/image"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _browser_image_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@dataclass(frozen=True, slots=True)
class DocxCandidate:
    candidate_id: str
    classification: str
    kind: str
    content: str | None
    evidence: str
    part_name: str
    shape_index: int | None = None
    shape_id: str | None = None
    shape_type: str | None = None
    style: str | None = None
    drawing_index: int | None = None
    relationship_id: str | None = None
    media_part_name: str | None = None
    media_sha256: str | None = None
    preview_media_type: str | None = None
    allowed_strategies: tuple[str, ...] = ("object",)


@dataclass(frozen=True, slots=True)
class DocxInspection:
    candidates: tuple[DocxCandidate, ...]
    inspected_parts: tuple[str, ...]
    warnings: tuple[str, ...]


class DocxInspector:
    def __init__(self, max_entries: int, max_uncompressed_bytes: int) -> None:
        self.max_entries = max_entries
        self.max_uncompressed_bytes = max_uncompressed_bytes

    def inspect(
        self,
        path: Path,
        asset_sha256: str,
        watermark_text: str | None = None,
    ) -> DocxInspection:
        try:
            with ZipFile(path) as package:
                infos = package.infolist()
                self._validate_package(infos)
                names = {info.filename for info in infos}
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise AssetError("INVALID_DOCX", "文件不是有效的 DOCX 文档。", 422)
                parts = tuple(sorted(name for name in names if HEADER_FOOTER_PATTERN.match(name)))
                candidates: list[DocxCandidate] = []
                warnings: list[str] = []
                for part_name in parts:
                    try:
                        root = fromstring(package.read(part_name))
                    except DefusedXmlException as exc:
                        raise AssetError(
                            "INVALID_DOCX",
                            f"{part_name} 包含不安全的 XML 内容。",
                            422,
                        ) from exc
                    except ParseError as exc:
                        warnings.append(f"无法解析 {part_name}：{exc}")
                        continue
                    candidates.extend(
                        self._inspect_part(root, part_name, asset_sha256, watermark_text)
                    )
                    image_candidates, image_warnings = self._inspect_drawing_images(
                        package,
                        names,
                        root,
                        part_name,
                        asset_sha256,
                        watermark_text,
                    )
                    candidates.extend(image_candidates)
                    warnings.extend(image_warnings)
                return DocxInspection(
                    candidates=tuple(candidates),
                    inspected_parts=parts,
                    warnings=tuple(warnings),
                )
        except BadZipFile as exc:
            raise AssetError("INVALID_DOCX", "DOCX 压缩包结构无效。", 422) from exc

    def _validate_package(self, infos: list[ZipInfo]) -> None:
        if len(infos) > self.max_entries:
            raise AssetError("RESOURCE_LIMIT", "DOCX 内部文件数量超过限制。", 413)
        total_size = 0
        for info in infos:
            if info.flag_bits & 0x1:
                raise AssetError("PASSWORD_REQUIRED", "不支持加密的 DOCX 内部文件。", 422)
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise AssetError("INVALID_DOCX", "DOCX 包含不安全的内部路径。", 422)
            total_size += info.file_size
            if total_size > self.max_uncompressed_bytes:
                raise AssetError("RESOURCE_LIMIT", "DOCX 解压后体积超过限制。", 413)

    def _inspect_part(
        self,
        root,
        part_name: str,
        asset_sha256: str,
        watermark_text: str | None,
    ) -> list[DocxCandidate]:
        results: list[DocxCandidate] = []
        for shape_index, shape in enumerate(root.iter(f"{{{VML}}}shape")):
            textpaths = list(shape.iter(f"{{{VML}}}textpath"))
            if not textpaths:
                continue
            shape_type = shape.attrib.get("type")
            shape_id = shape.attrib.get("id")
            style = shape.attrib.get("style")
            content = " ".join(
                value.strip()
                for textpath in textpaths
                if (value := textpath.attrib.get("string")) and value.strip()
            ) or None
            known_shape = shape_type == WATERMARK_SHAPE_TYPE
            text_matches = bool(
                watermark_text
                and content
                and content.casefold() == watermark_text.strip().casefold()
            )
            classification = "confirmed" if known_shape and text_matches else "ambiguous"
            evidence_bits = ["页眉或页脚中包含 VML textpath 文字形状"]
            if known_shape:
                evidence_bits.append("使用 Word 内置文字水印形状类型")
            if text_matches:
                evidence_bits.append("文字与用户指定目标完全一致")
            digest = hashlib.sha256(
                f"{asset_sha256}|{part_name}|{shape_index}|{content or ''}".encode()
            ).hexdigest()[:20]
            results.append(
                DocxCandidate(
                    candidate_id=f"docx-{digest}",
                    classification=classification,
                    kind="text",
                    content=content,
                    evidence="；".join(evidence_bits),
                    part_name=part_name,
                    shape_index=shape_index,
                    shape_id=shape_id,
                    shape_type=shape_type,
                    style=style,
                )
            )
        return results

    def _inspect_drawing_images(
        self,
        package: ZipFile,
        names: set[str],
        root,
        part_name: str,
        asset_sha256: str,
        watermark_text: str | None,
    ) -> tuple[list[DocxCandidate], list[str]]:
        relationship_part = _relationship_part_name(part_name)
        drawings = [
            element for element in root.iter() if _local_name(element.tag) in {"anchor", "inline"}
        ]
        if not drawings:
            return [], []
        relationships, warnings = _image_relationships(package, names, part_name, relationship_part)
        results: list[DocxCandidate] = []
        for drawing_index, drawing in enumerate(drawings):
            blip = next(
                (element for element in drawing.iter() if _local_name(element.tag) == "blip"),
                None,
            )
            relationship_id = _attribute_by_local_name(blip, "embed") if blip is not None else None
            if not relationship_id:
                warnings.append(
                    f"{part_name} 中第 {drawing_index + 1} 个 DrawingML 对象"
                    "没有嵌入图片关系，已跳过。"
                )
                continue
            media_part_name = relationships.get(relationship_id)
            if media_part_name is None:
                warnings.append(
                    f"{part_name} 中第 {drawing_index + 1} 个 DrawingML 图片关系"
                    "无法安全解析，已跳过。"
                )
                continue
            media = package.read(media_part_name)
            media_sha256 = hashlib.sha256(media).hexdigest()
            preview_media_type = _browser_image_type(media)
            metadata = _drawing_metadata(drawing)
            label = metadata or "嵌入图片"
            evidence_bits = ["页眉或页脚中包含 DrawingML 嵌入图片"]
            if _local_name(drawing.tag) == "anchor":
                evidence_bits.append("图片使用浮动锚点")
                if drawing.attrib.get("behindDoc") in {"1", "true"}:
                    evidence_bits.append("图片位于正文后方")
            target = watermark_text.strip().casefold() if watermark_text else ""
            if target and target in label.casefold():
                evidence_bits.append("图片名称或说明包含用户指定目标")
            if preview_media_type is None:
                evidence_bits.append("图片格式不能在浏览器中安全预览")
            digest = hashlib.sha256(
                (
                    f"{asset_sha256}|{part_name}|drawing|{drawing_index}|"
                    f"{relationship_id}|{media_sha256}"
                ).encode()
            ).hexdigest()[:20]
            results.append(
                DocxCandidate(
                    candidate_id=f"docx-{digest}",
                    classification="ambiguous",
                    kind="image",
                    content=label,
                    evidence="；".join(evidence_bits),
                    part_name=part_name,
                    style=_drawing_style(drawing),
                    drawing_index=drawing_index,
                    relationship_id=relationship_id,
                    media_part_name=media_part_name,
                    media_sha256=media_sha256,
                    preview_media_type=preview_media_type,
                    allowed_strategies=("object",) if preview_media_type else (),
                )
            )
        return results, warnings


def _relationship_part_name(part_name: str) -> str:
    owner = PurePosixPath(part_name)
    return (owner.parent / "_rels" / f"{owner.name}.rels").as_posix()


def _image_relationships(
    package: ZipFile,
    names: set[str],
    owner_part: str,
    relationship_part: str,
) -> tuple[dict[str, str], list[str]]:
    if relationship_part not in names:
        return {}, [f"{owner_part} 包含 DrawingML 对象，但缺少关系部件。"]
    try:
        root = fromstring(package.read(relationship_part))
    except (DefusedXmlException, ParseError):
        return {}, [f"无法安全解析 {relationship_part}，DrawingML 图片候选已跳过。"]
    relationships: dict[str, str] = {}
    warnings: list[str] = []
    owner_directory = PurePosixPath(owner_part).parent.as_posix()
    for relationship in root:
        if _local_name(relationship.tag) != "Relationship":
            continue
        relationship_id = relationship.attrib.get("Id")
        relationship_type = relationship.attrib.get("Type", "")
        if not relationship_id or not relationship_type.endswith(IMAGE_RELATIONSHIP_SUFFIX):
            continue
        if relationship.attrib.get("TargetMode", "").casefold() == "external":
            warnings.append(f"{relationship_part} 的外部图片关系 {relationship_id} 不会被读取。")
            continue
        target = unquote(relationship.attrib.get("Target", "")).split("#", 1)[0]
        if target.startswith("/"):
            resolved = posixpath.normpath(target.lstrip("/"))
        else:
            resolved = posixpath.normpath(posixpath.join(owner_directory, target))
        if resolved == ".." or resolved.startswith("../") or resolved not in names:
            warnings.append(f"{relationship_part} 的图片关系 {relationship_id} 指向无效目标。")
            continue
        relationships[relationship_id] = resolved
    return relationships, warnings


def _attribute_by_local_name(element, name: str) -> str | None:
    if element is None:
        return None
    return next(
        (value for key, value in element.attrib.items() if _local_name(key) == name),
        None,
    )


def _drawing_metadata(drawing) -> str | None:
    values: list[str] = []
    for element in drawing.iter():
        if _local_name(element.tag) not in {"docPr", "cNvPr"}:
            continue
        for key in ("title", "descr", "name"):
            value = element.attrib.get(key)
            if value and value.strip() and value.strip() not in values:
                values.append(value.strip())
    return " · ".join(values[:3]) or None


def _drawing_style(drawing) -> str | None:
    bits = [_local_name(drawing.tag)]
    extent = next(
        (element for element in drawing.iter() if _local_name(element.tag) == "extent"),
        None,
    )
    if extent is not None and extent.attrib.get("cx") and extent.attrib.get("cy"):
        bits.append(f"extent={extent.attrib['cx']}x{extent.attrib['cy']}")
    if drawing.attrib.get("behindDoc") in {"1", "true"}:
        bits.append("behindDoc=true")
    return ";".join(bits)


def read_docx_image_preview(
    path: Path,
    media_part_name: str,
    expected_sha256: str,
    expected_media_type: str,
) -> bytes:
    safe_name = PurePosixPath(media_part_name)
    if safe_name.is_absolute() or ".." in safe_name.parts:
        raise AssetError("PREVIEW_NOT_AVAILABLE", "图片预览位置无效。", 404)
    try:
        with ZipFile(path) as package:
            if media_part_name not in package.namelist():
                raise AssetError("PREVIEW_NOT_AVAILABLE", "图片预览已不存在。", 404)
            data = package.read(media_part_name)
    except BadZipFile as exc:
        raise AssetError("INVALID_DOCX", "DOCX 压缩包结构无效。", 422) from exc
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise AssetError("PREVIEW_STALE", "图片预览与扫描结果不一致，请重新扫描。", 409)
    if _browser_image_type(data) != expected_media_type:
        raise AssetError("PREVIEW_NOT_AVAILABLE", "该图片格式不能安全预览。", 415)
    return data
