import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader, Transformation
from pypdf.errors import PyPdfError
from pypdf.generic import ContentStream, IndirectObject, NameObject

from wmrm.application.assets import AssetError

WATERMARK_WORDS = {"watermark", "draft", "confidential", "sample", "水印", "草稿", "机密"}


@dataclass(frozen=True, slots=True)
class GeneralPdfCandidate:
    candidate_id: str
    classification: str
    kind: str
    content: str | None
    evidence: str
    page_number: int | None
    resource_name: str | None = None
    object_number: int | None = None
    generation_number: int | None = None
    operation_index: int | None = None
    annotation_index: int | None = None
    style: str | None = None
    region: dict[str, Any] | None = None
    overlaps_protected_content: bool | None = None
    allowed_strategies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeneralPdfInspection:
    candidates: tuple[GeneralPdfCandidate, ...]
    inspected_parts: tuple[str, ...]
    warnings: tuple[str, ...]
    match_status: str
    pdf_pages: tuple[dict[str, Any], ...]
    protected_content: tuple[dict[str, Any], ...]


@dataclass(slots=True)
class _TextFragment:
    page_number: int
    occurrence: int
    text: str
    font_size: float
    matrix: tuple[float, ...]
    region: dict[str, Any]


@dataclass(slots=True)
class _ObjectOccurrence:
    page_number: int
    operation_index: int
    resource_name: str
    subtype: str
    reference: Any
    obj: Any
    region: dict[str, Any] | None
    nesting_depth: int = 0


class GeneralPdfInspector:
    """Inventory likely watermark structures without enabling destructive operations."""

    def __init__(self, max_pages: int, max_content_bytes: int) -> None:
        self.max_pages = max_pages
        self.max_content_bytes = max_content_bytes

    def inspect(
        self,
        path: Path,
        asset_sha256: str,
        watermark_text: str | None = None,
    ) -> GeneralPdfInspection:
        try:
            reader = PdfReader(str(path), strict=False)
            if reader.is_encrypted:
                raise AssetError("PASSWORD_REQUIRED", "PDF 已加密，需要先移除密码保护。", 422)
            if len(reader.pages) > self.max_pages:
                raise AssetError(
                    "RESOURCE_LIMIT", f"PDF 页数超过 {self.max_pages} 页限制。", 413
                )
            content_bytes = 0
            text_fragments: list[_TextFragment] = []
            object_occurrences: list[_ObjectOccurrence] = []
            candidates: list[GeneralPdfCandidate] = []
            inspected_parts: list[str] = []
            pdf_pages: list[dict[str, Any]] = []
            protected_content: list[dict[str, Any]] = []
            incomplete_form_scan = False
            for page_number, page in enumerate(reader.pages, start=1):
                inspected_parts.append(f"page:{page_number}")
                page_width, page_height, rotation = _page_geometry(page)
                crop_x, crop_y = _crop_origin(page)
                transform_id = _transform_id(
                    page_number, page_width, page_height, rotation, crop_x, crop_y
                )
                pdf_pages.append(
                    {
                        "page_number": page_number,
                        "width": page_width,
                        "height": page_height,
                        "rotation": rotation,
                        "crop_x": crop_x,
                        "crop_y": crop_y,
                        "transform_id": transform_id,
                    }
                )
                page_fragments = self._text_fragments(page, page_number)
                text_fragments.extend(page_fragments)
                protected_content.extend(
                    {
                        "content_id": "protected-text-"
                        + _candidate_digest(
                            asset_sha256, page_number, item.occurrence, item.text
                        ),
                        "kind": "text",
                        "summary": item.text[:120],
                        "region": item.region,
                    }
                    for item in page_fragments
                )
                contents = page.get_contents()
                if contents is not None:
                    stream = ContentStream(contents, reader)
                    content_bytes += len(stream.get_data())
                    if content_bytes > self.max_content_bytes:
                        raise AssetError(
                            "RESOURCE_LIMIT",
                            "PDF 解码后的页面内容流超过安全限制。",
                            413,
                        )
                    objects, patterns, graphics, nested_bytes, form_scan_incomplete = (
                        self._page_operations(page, stream.operations, page_number, reader)
                    )
                    content_bytes += nested_bytes
                    if content_bytes > self.max_content_bytes:
                        raise AssetError(
                            "RESOURCE_LIMIT",
                            "PDF 解码后的页面内容流超过安全限制。",
                            413,
                        )
                    object_occurrences.extend(objects)
                    protected_content.extend(
                        {
                            "content_id": "protected-object-"
                            + _candidate_digest(
                                asset_sha256,
                                item.page_number,
                                item.operation_index,
                                item.resource_name,
                            ),
                            "kind": "image" if item.subtype == "/Image" else "form",
                            "summary": f"{item.subtype[1:] or 'XObject'} {item.resource_name}",
                            "region": item.region,
                        }
                        for item in objects
                        if item.region is not None
                    )
                    protected_content.extend(
                        {
                            "content_id": "protected-graphic-"
                            + _candidate_digest(
                                asset_sha256, page_number, item["operation_index"]
                            ),
                            "kind": "graphic",
                            "summary": "矢量图形",
                            "region": item["region"],
                        }
                        for item in graphics
                    )
                    candidates.extend(
                        self._pattern_candidates(patterns, page, asset_sha256)
                    )
                    incomplete_form_scan = incomplete_form_scan or form_scan_incomplete
                candidates.extend(
                    self._annotation_candidates(page, page_number, asset_sha256)
                )
                protected_content.extend(
                    self._protected_annotations(page, page_number, asset_sha256)
                )

            candidates.extend(
                self._text_candidates(
                    text_fragments,
                    len(reader.pages),
                    asset_sha256,
                    watermark_text,
                )
            )
            candidates.extend(
                self._object_candidates(object_occurrences, asset_sha256)
            )
            ocg_candidates = self._optional_content_candidates(
                reader, asset_sha256, watermark_text
            )
            candidates.extend(ocg_candidates)
            if ocg_candidates:
                inspected_parts.append("catalog:optional-content")
            warnings = [
                "通用 PDF 扫描只提供候选证据，不会自动删除对象；文字相同或跨页重复不等于水印。"
            ]
            if incomplete_form_scan:
                warnings.append(
                    "部分 Form XObject 因循环引用或递归层级限制未能完全展开。"
                )
            if self._has_signatures(reader):
                warnings.append("PDF 包含数字签名字段；生成新文件通常会使现有签名失效。")
            reviewable = [item for item in candidates if item.classification != "content"]
            return GeneralPdfInspection(
                candidates=tuple(candidates),
                inspected_parts=tuple(inspected_parts),
                warnings=tuple(warnings),
                match_status="needs_review" if reviewable else "not_found",
                pdf_pages=tuple(pdf_pages),
                protected_content=tuple(protected_content),
            )
        except AssetError:
            raise
        except (PyPdfError, OSError, TypeError, ValueError) as exc:
            raise AssetError("INVALID_PDF", "文件不是可安全解析的 PDF。", 422) from exc

    def _text_fragments(self, page: Any, page_number: int) -> list[_TextFragment]:
        fragments: list[_TextFragment] = []
        page_width, page_height, rotation = _page_geometry(page)
        crop_x, crop_y = _crop_origin(page)

        def visitor(text: str, cm: list[float], tm: list[float], _font: Any, size: float):
            clean = " ".join(text.split())
            if not clean or len(clean) > 200:
                return
            combined = Transformation(tuple(float(item) for item in tm)).transform(
                Transformation(tuple(float(item) for item in cm))
            )
            width = max(float(size), len(clean) * float(size) * 0.5)
            points = [
                combined.apply_on((0, 0)),
                combined.apply_on((width, 0)),
                combined.apply_on((0, float(size))),
                combined.apply_on((width, float(size))),
            ]
            fragments.append(
                _TextFragment(
                    page_number=page_number,
                    occurrence=len(fragments),
                    text=clean,
                    font_size=float(size),
                    matrix=tuple(float(item) for item in combined.ctm),
                    region=_region(
                        points,
                        page_number,
                        page_width,
                        page_height,
                        rotation,
                        True,
                        crop_x,
                        crop_y,
                    ),
                )
            )

        page.extract_text(visitor_text=visitor)
        return fragments

    def _text_candidates(
        self,
        fragments: list[_TextFragment],
        page_count: int,
        asset_sha256: str,
        target: str | None,
    ) -> list[GeneralPdfCandidate]:
        normalized = [_normalize(item.text) for item in fragments]
        page_sets: dict[str, set[int]] = defaultdict(set)
        for item, value in zip(fragments, normalized, strict=True):
            page_sets[value].add(item.page_number)
        target_value = _normalize(target or "")
        results: list[GeneralPdfCandidate] = []
        for item, value in zip(fragments, normalized, strict=True):
            target_match = bool(target_value and target_value in value)
            repeated_pages = len(page_sets[value])
            repeated = repeated_pages >= 2 and repeated_pages / max(page_count, 1) >= 0.5
            if not target_match and not repeated:
                continue
            evidence = []
            if target_match:
                evidence.append("文字包含用户指定目标")
            if repeated:
                evidence.append(f"相同文字出现在 {repeated_pages} 页")
            evidence.append("文字和位置仅作为候选线索，不能据此自动删除")
            digest = _candidate_digest(
                asset_sha256, "text", item.page_number, item.occurrence, item.text
            )
            results.append(
                GeneralPdfCandidate(
                    candidate_id=f"pdf-text-{digest}",
                    classification="ambiguous",
                    kind="text",
                    content=item.text,
                    evidence="；".join(evidence),
                    page_number=item.page_number,
                    operation_index=item.occurrence,
                    style=json.dumps(
                        {"font_size": item.font_size, "matrix": item.matrix},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    region=item.region,
                    overlaps_protected_content=True,
                )
            )
        return results

    def _page_operations(
        self,
        page: Any,
        operations: list[tuple[list[Any], bytes]],
        page_number: int,
        reader: PdfReader,
    ) -> tuple[
        list[_ObjectOccurrence], list[tuple[int, str]], list[dict[str, Any]], int, bool
    ]:
        page_width, page_height, rotation = _page_geometry(page)
        crop_x, crop_y = _crop_origin(page)
        counter = [0]
        return self._walk_operations(
            operations=operations,
            resources=page.get("/Resources"),
            page_number=page_number,
            reader=reader,
            page_width=page_width,
            page_height=page_height,
            rotation=rotation,
            crop_x=crop_x,
            crop_y=crop_y,
            initial_ctm=Transformation(),
            resource_path="",
            depth=0,
            active_forms=set(),
            counter=counter,
        )

    def _walk_operations(
        self,
        *,
        operations: list[tuple[list[Any], bytes]],
        resources: Any,
        page_number: int,
        reader: PdfReader,
        page_width: float,
        page_height: float,
        rotation: int,
        crop_x: float,
        crop_y: float,
        initial_ctm: Transformation,
        resource_path: str,
        depth: int,
        active_forms: set[str],
        counter: list[int],
    ) -> tuple[
        list[_ObjectOccurrence], list[tuple[int, str]], list[dict[str, Any]], int, bool
    ]:
        xobjects = resources.get("/XObject") if resources else None
        ctm = initial_ctm
        stack: list[Transformation] = []
        objects: list[_ObjectOccurrence] = []
        patterns: list[tuple[int, str]] = []
        seen_patterns: set[str] = set()
        graphics: list[dict[str, Any]] = []
        path_points: list[tuple[float, float]] = []
        nested_bytes = 0
        incomplete = False
        for operands, operator in operations:
            index = counter[0]
            counter[0] += 1
            if operator == b"q":
                stack.append(ctm)
            elif operator == b"Q":
                ctm = stack.pop() if stack else Transformation()
            elif operator == b"cm" and len(operands) == 6:
                incoming = Transformation(tuple(float(item) for item in operands))
                ctm = incoming.transform(ctm)
            elif operator == b"m" and len(operands) >= 2:
                path_points = [ctm.apply_on((float(operands[0]), float(operands[1])))]
            elif operator == b"l" and len(operands) >= 2:
                path_points.append(
                    ctm.apply_on((float(operands[0]), float(operands[1])))
                )
            elif operator == b"c" and len(operands) >= 6:
                path_points.extend(
                    ctm.apply_on((float(operands[offset]), float(operands[offset + 1])))
                    for offset in (0, 2, 4)
                )
            elif operator in {b"v", b"y"} and len(operands) >= 4:
                path_points.extend(
                    ctm.apply_on((float(operands[offset]), float(operands[offset + 1])))
                    for offset in (0, 2)
                )
            elif operator == b"re" and len(operands) >= 4:
                x, y, width, height = (float(value) for value in operands[:4])
                path_points.extend(
                    ctm.apply_on(point)
                    for point in (
                        (x, y),
                        (x + width, y),
                        (x, y + height),
                        (x + width, y + height),
                    )
                )
            elif operator in {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"n"}:
                if path_points and operator != b"n":
                    graphic_region = _region(
                        path_points,
                        page_number,
                        page_width,
                        page_height,
                        rotation,
                        True,
                        crop_x,
                        crop_y,
                    )
                    graphics.append(
                        {"operation_index": index, "region": _expand_region(graphic_region, 5)}
                    )
                path_points = []
            elif operator == b"Do" and operands and xobjects:
                name = str(operands[0])
                reference, obj = _resolve_resource(xobjects, name)
                if obj is None:
                    continue
                subtype = str(obj.get("/Subtype", ""))
                full_name = f"{resource_path}>{name}" if resource_path else name
                object_ctm = ctm
                bounds = (0.0, 0.0, 1.0, 1.0)
                if subtype == "/Form":
                    matrix = obj.get("/Matrix", [1, 0, 0, 1, 0, 0])
                    if len(matrix) == 6:
                        object_ctm = Transformation(
                            tuple(float(value) for value in matrix)
                        ).transform(ctm)
                    bbox = obj.get("/BBox", [0, 0, 1, 1])
                    if len(bbox) == 4:
                        bounds = tuple(float(value) for value in bbox)
                x0, y0, x1, y1 = bounds
                points = [
                    object_ctm.apply_on((x0, y0)),
                    object_ctm.apply_on((x1, y0)),
                    object_ctm.apply_on((x0, y1)),
                    object_ctm.apply_on((x1, y1)),
                ]
                objects.append(
                    _ObjectOccurrence(
                        page_number=page_number,
                        operation_index=index,
                        resource_name=full_name,
                        subtype=subtype,
                        reference=reference,
                        obj=obj,
                        region=_region(
                            points,
                            page_number,
                            page_width,
                            page_height,
                            rotation,
                            False,
                            crop_x,
                            crop_y,
                        ),
                        nesting_depth=depth,
                    )
                )
                if subtype == "/Form":
                    form_key = _resource_key(reference, obj)
                    if depth >= 8 or form_key in active_forms:
                        incomplete = True
                        continue
                    try:
                        form_stream = ContentStream(obj, reader)
                        form_data = form_stream.get_data()
                    except (PyPdfError, TypeError, ValueError):
                        incomplete = True
                        continue
                    nested_bytes += len(form_data)
                    form_resources = obj.get("/Resources") or resources
                    nested = self._walk_operations(
                        operations=form_stream.operations,
                        resources=form_resources,
                        page_number=page_number,
                        reader=reader,
                        page_width=page_width,
                        page_height=page_height,
                        rotation=rotation,
                        crop_x=crop_x,
                        crop_y=crop_y,
                        initial_ctm=object_ctm,
                        resource_path=full_name,
                        depth=depth + 1,
                        active_forms=active_forms | {form_key},
                        counter=counter,
                    )
                    nested_objects, _, nested_graphics, child_bytes, child_incomplete = nested
                    objects.extend(nested_objects)
                    graphics.extend(nested_graphics)
                    nested_bytes += child_bytes
                    incomplete = incomplete or child_incomplete
            elif operator in {b"SCN", b"scn"}:
                name = next(
                    (str(value) for value in operands if isinstance(value, NameObject)), None
                )
                if depth == 0 and name and name not in seen_patterns:
                    patterns.append((index, name))
                    seen_patterns.add(name)
        return objects, patterns, graphics, nested_bytes, incomplete

    def _object_candidates(
        self, occurrences: list[_ObjectOccurrence], asset_sha256: str
    ) -> list[GeneralPdfCandidate]:
        keys = [_object_key(item) for item in occurrences]
        page_sets: dict[str, set[int]] = defaultdict(set)
        for item, key in zip(occurrences, keys, strict=True):
            page_sets[key].add(item.page_number)
        results: list[GeneralPdfCandidate] = []
        for item, key in zip(occurrences, keys, strict=True):
            repeated_pages = len(page_sets[key])
            reviewable = repeated_pages >= 2
            subtype_label = "图片" if item.subtype == "/Image" else "Form XObject"
            evidence = f"页面内容流调用{subtype_label}资源"
            if reviewable:
                evidence += f"；同一对象跨 {repeated_pages} 页重复调用"
            else:
                evidence += "；仅单页出现，默认视为正文内容"
            reference = item.reference
            object_number = reference.idnum if isinstance(reference, IndirectObject) else None
            generation = reference.generation if isinstance(reference, IndirectObject) else None
            details = {
                "subtype": item.subtype,
                "width": int(item.obj.get("/Width", 0)),
                "height": int(item.obj.get("/Height", 0)),
                "filter": str(item.obj.get("/Filter", "")),
                "nesting_depth": item.nesting_depth,
            }
            digest = _candidate_digest(
                asset_sha256,
                item.subtype,
                item.page_number,
                item.operation_index,
                item.resource_name,
            )
            results.append(
                GeneralPdfCandidate(
                    candidate_id=f"pdf-object-{digest}",
                    classification="ambiguous" if reviewable else "content",
                    kind="image" if item.subtype == "/Image" else "other",
                    content=f"{subtype_label}（资源 {item.resource_name}）",
                    evidence=evidence,
                    page_number=item.page_number,
                    resource_name=item.resource_name,
                    object_number=object_number,
                    generation_number=generation,
                    operation_index=item.operation_index,
                    style=json.dumps(details, ensure_ascii=False, separators=(",", ":")),
                    region=item.region,
                    overlaps_protected_content=None,
                )
            )
        return results

    def _pattern_candidates(
        self,
        patterns: list[tuple[int, str]],
        page: Any,
        asset_sha256: str,
    ) -> list[GeneralPdfCandidate]:
        resources = page.get("/Resources")
        pattern_resources = resources.get("/Pattern") if resources else None
        page_number = int(page.page_number) + 1
        results = []
        for operation_index, name in patterns:
            reference, pattern = _resolve_resource(pattern_resources, name)
            pattern_type = int(pattern.get("/PatternType", 0)) if pattern else 0
            object_number = reference.idnum if isinstance(reference, IndirectObject) else None
            generation = reference.generation if isinstance(reference, IndirectObject) else None
            digest = _candidate_digest(
                asset_sha256, "pattern", page_number, operation_index, name
            )
            results.append(
                GeneralPdfCandidate(
                    candidate_id=f"pdf-pattern-{digest}",
                    classification="ambiguous",
                    kind="pattern",
                    content=f"Pattern 资源 {name}",
                    evidence="页面内容流使用 Pattern；普通背景和水印都可能采用该结构，需要人工复核",
                    page_number=page_number,
                    resource_name=name,
                    object_number=object_number,
                    generation_number=generation,
                    operation_index=operation_index,
                    style=json.dumps(
                        {"pattern_type": pattern_type}, separators=(",", ":")
                    ),
                )
            )
        return results

    def _annotation_candidates(
        self, page: Any, page_number: int, asset_sha256: str
    ) -> list[GeneralPdfCandidate]:
        annotations = page.get("/Annots") or []
        page_width, page_height, rotation = _page_geometry(page)
        crop_x, crop_y = _crop_origin(page)
        results = []
        for index, reference in enumerate(annotations):
            annotation = reference.get_object()
            subtype = str(annotation.get("/Subtype", ""))
            if subtype not in {"/Watermark", "/Stamp"}:
                continue
            rect = [float(item) for item in annotation.get("/Rect", [])]
            region = None
            if len(rect) == 4:
                region = _region(
                    [(rect[0], rect[1]), (rect[2], rect[3])],
                    page_number,
                    page_width,
                    page_height,
                    rotation,
                    False,
                    crop_x,
                    crop_y,
                )
            contents = str(annotation.get("/Contents", "")).strip() or None
            digest = _candidate_digest(
                asset_sha256, "annotation", page_number, index, subtype
            )
            results.append(
                GeneralPdfCandidate(
                    candidate_id=f"pdf-annotation-{digest}",
                    classification="confirmed" if subtype == "/Watermark" else "ambiguous",
                    kind="other",
                    content=contents or f"{subtype[1:]} annotation",
                    evidence=(
                        "PDF 明确标记为 Watermark annotation"
                        if subtype == "/Watermark"
                        else "PDF Stamp annotation 可能是印章、水印或有效正文标记"
                    ),
                    page_number=page_number,
                    object_number=(
                        reference.idnum if isinstance(reference, IndirectObject) else None
                    ),
                    generation_number=(
                        reference.generation
                        if isinstance(reference, IndirectObject)
                        else None
                    ),
                    annotation_index=index,
                    style=json.dumps({"subtype": subtype}, separators=(",", ":")),
                    region=region,
                )
            )
        return results

    def _protected_annotations(
        self, page: Any, page_number: int, asset_sha256: str
    ) -> list[dict[str, Any]]:
        annotations = page.get("/Annots") or []
        page_width, page_height, rotation = _page_geometry(page)
        crop_x, crop_y = _crop_origin(page)
        results = []
        for index, reference in enumerate(annotations):
            annotation = reference.get_object()
            subtype = str(annotation.get("/Subtype", ""))
            if subtype not in {"/Link", "/Watermark", "/Stamp"}:
                continue
            rect = [float(item) for item in annotation.get("/Rect", [])]
            if len(rect) != 4:
                continue
            kind = "link" if subtype == "/Link" else "annotation"
            summary = str(annotation.get("/Contents", "")).strip() or subtype[1:]
            results.append(
                {
                    "content_id": "protected-annotation-"
                    + _candidate_digest(asset_sha256, page_number, index, subtype),
                    "kind": kind,
                    "summary": summary[:120],
                    "region": _region(
                        [(rect[0], rect[1]), (rect[2], rect[3])],
                        page_number,
                        page_width,
                        page_height,
                        rotation,
                        False,
                        crop_x,
                        crop_y,
                    ),
                }
            )
        return results

    def _optional_content_candidates(
        self, reader: PdfReader, asset_sha256: str, target: str | None
    ) -> list[GeneralPdfCandidate]:
        root = reader.trailer.get("/Root")
        properties = root.get("/OCProperties") if root else None
        groups = properties.get("/OCGs", []) if properties else []
        target_value = _normalize(target or "")
        results = []
        for index, reference in enumerate(groups):
            group = reference.get_object()
            name = str(group.get("/Name", "")).strip()
            normalized = _normalize(name)
            suspicious = bool(
                (target_value and target_value in normalized)
                or any(word in normalized for word in WATERMARK_WORDS)
            )
            digest = _candidate_digest(asset_sha256, "ocg", index, name)
            results.append(
                GeneralPdfCandidate(
                    candidate_id=f"pdf-ocg-{digest}",
                    classification="ambiguous" if suspicious else "content",
                    kind="other",
                    content=name or "未命名可选内容组",
                    evidence=(
                        "可选内容组名称与目标或常见水印词匹配"
                        if suspicious
                        else "PDF 可选内容组；名称没有水印特征，默认视为内容"
                    ),
                    page_number=None,
                    object_number=(
                        reference.idnum if isinstance(reference, IndirectObject) else None
                    ),
                    generation_number=(
                        reference.generation
                        if isinstance(reference, IndirectObject)
                        else None
                    ),
                    style=json.dumps({"optional_content": True}, separators=(",", ":")),
                )
            )
        return results

    @staticmethod
    def _has_signatures(reader: PdfReader) -> bool:
        root = reader.trailer.get("/Root")
        form = root.get("/AcroForm") if root else None
        fields = form.get("/Fields", []) if form else []
        return any(str(reference.get_object().get("/FT", "")) == "/Sig" for reference in fields)


def _resolve_resource(resources: Any, name: str) -> tuple[Any | None, Any | None]:
    if not resources:
        return None, None
    try:
        reference = resources.raw_get(NameObject(name))
    except (AttributeError, KeyError):
        return None, None
    try:
        return reference, reference.get_object()
    except (AttributeError, PyPdfError):
        return reference, None


def _object_key(item: _ObjectOccurrence) -> str:
    if isinstance(item.reference, IndirectObject):
        return f"{item.reference.idnum}:{item.reference.generation}"
    return f"direct:{item.subtype}:{item.resource_name}:{id(item.obj)}"


def _resource_key(reference: Any, obj: Any) -> str:
    if isinstance(reference, IndirectObject):
        return f"{reference.idnum}:{reference.generation}"
    return f"direct:{id(obj)}"


def _page_geometry(page: Any) -> tuple[float, float, int]:
    return float(page.cropbox.width), float(page.cropbox.height), int(page.get("/Rotate", 0))


def _crop_origin(page: Any) -> tuple[float, float]:
    return float(page.cropbox.left), float(page.cropbox.bottom)


def _region(
    points: list[tuple[float, float]],
    page_number: int,
    page_width: float,
    page_height: float,
    rotation: int,
    approximate: bool,
    crop_x: float = 0,
    crop_y: float = 0,
) -> dict[str, Any]:
    xs = [float(point[0]) - crop_x for point in points]
    ys = [float(point[1]) - crop_y for point in points]
    x0, x1 = max(0.0, min(xs)), min(page_width, max(xs))
    y0, y1 = max(0.0, min(ys)), min(page_height, max(ys))
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return {
        "coordinate_space": "pdf_points",
        "page_number": page_number,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "page_width": page_width,
        "page_height": page_height,
        "rotation": rotation,
        "transform_id": _transform_id(
            page_number, page_width, page_height, rotation, crop_x, crop_y
        ),
        "approximate": approximate,
    }


def _expand_region(region: dict[str, Any], amount: float) -> dict[str, Any]:
    expanded = dict(region)
    expanded["x0"] = max(0.0, float(region["x0"]) - amount)
    expanded["y0"] = max(0.0, float(region["y0"]) - amount)
    expanded["x1"] = min(float(region["page_width"]), float(region["x1"]) + amount)
    expanded["y1"] = min(float(region["page_height"]), float(region["y1"]) + amount)
    expanded["approximate"] = True
    return expanded


def _transform_id(
    page_number: int,
    page_width: float,
    page_height: float,
    rotation: int,
    crop_x: float = 0,
    crop_y: float = 0,
) -> str:
    value = (
        f"{page_number}|{page_width:.6f}|{page_height:.6f}|{rotation}|"
        f"{crop_x:.6f}|{crop_y:.6f}"
    )
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _candidate_digest(asset_sha256: str, *parts: object) -> str:
    value = "|".join([asset_sha256, *(str(part) for part in parts)])
    return hashlib.sha256(value.encode()).hexdigest()[:20]
