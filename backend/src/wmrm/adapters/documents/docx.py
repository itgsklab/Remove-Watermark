import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from wmrm.application.assets import AssetError

VML = "urn:schemas-microsoft-com:vml"
HEADER_FOOTER_PATTERN = re.compile(r"^word/(?:header|footer)\d+\.xml$")
WATERMARK_SHAPE_TYPE = "#_x0000_t136"


@dataclass(frozen=True, slots=True)
class DocxCandidate:
    candidate_id: str
    classification: str
    kind: str
    content: str | None
    evidence: str
    part_name: str
    shape_index: int
    shape_id: str | None
    shape_type: str | None
    style: str | None
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
