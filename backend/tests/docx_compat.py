from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

TRANSITIONAL_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STRICT_WORD_NS = "http://purl.oclc.org/ooxml/wordprocessingml/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(frozen=True, slots=True)
class CompatibilityProfile:
    id: str
    word_namespace: str
    part_kind: str
    part_number: int
    word_prefix: str
    vml_prefix: str
    leading_shape: bool = False

    @property
    def part_name(self) -> str:
        return f"word/{self.part_kind}{self.part_number}.xml"


PROFILES = (
    CompatibilityProfile(
        id="word-transitional-header",
        word_namespace=TRANSITIONAL_WORD_NS,
        part_kind="header",
        part_number=1,
        word_prefix="w",
        vml_prefix="v",
    ),
    CompatibilityProfile(
        id="word-strict-alternate-prefix",
        word_namespace=STRICT_WORD_NS,
        part_kind="header",
        part_number=2,
        word_prefix="wx",
        vml_prefix="vx",
        leading_shape=True,
    ),
    CompatibilityProfile(
        id="wps-style-footer",
        word_namespace=TRANSITIONAL_WORD_NS,
        part_kind="footer",
        part_number=1,
        word_prefix="word",
        vml_prefix="shape",
    ),
)


def make_compatibility_docx(
    profile: CompatibilityProfile,
    watermark_texts: tuple[str, ...],
) -> bytes:
    word = profile.word_prefix
    vml = profile.vml_prefix
    root_tag = "hdr" if profile.part_kind == "header" else "ftr"
    relation_tag = "headerReference" if profile.part_kind == "header" else "footerReference"
    relation_type = "header" if profile.part_kind == "header" else "footer"
    leading_shape = ""
    if profile.leading_shape:
        leading_shape = (
            f'<{vml}:shape id="DecorativeObject" type="#_x0000_t75">'
            f"<{vml}:imagedata/>"
            f"</{vml}:shape>"
        )
    watermarks = "".join(
        (
            f'<{vml}:shape id="PowerPlusWaterMarkObject{index}" '
            'type="#_x0000_t136" style="rotation:315;position:absolute">'
            f'<{vml}:textpath string={quoteattr(text)}/>'
            f"</{vml}:shape>"
        )
        for index, text in enumerate(watermark_texts, start=1)
    )
    part_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<{word}:{root_tag} xmlns:{word}="{profile.word_namespace}" '
        f'xmlns:{vml}="urn:schemas-microsoft-com:vml">'
        f"<{word}:p><{word}:r><{word}:pict>"
        f"{leading_shape}{watermarks}"
        f"</{word}:pict></{word}:r></{word}:p>"
        f"</{word}:{root_tag}>"
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{profile.word_namespace}" xmlns:r="{OFFICE_REL_NS}">'
        f'<w:body><w:p/><w:sectPr><w:{relation_tag} r:id="rId1"/>'
        "</w:sectPr></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        f'<Override PartName="/{profile.part_name}" '
        f'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{relation_type}+xml"/>'
        "</Types>"
    )
    root_relationships = (
        f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rId1" Type="{OFFICE_REL_NS}/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    document_relationships = (
        f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rId1" Type="{OFFICE_REL_NS}/{relation_type}" '
        f'Target="{profile.part_kind}{profile.part_number}.xml"/></Relationships>'
    )

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", root_relationships)
        package.writestr("word/document.xml", document_xml)
        package.writestr("word/_rels/document.xml.rels", document_relationships)
        package.writestr(profile.part_name, part_xml)
    return output.getvalue()
