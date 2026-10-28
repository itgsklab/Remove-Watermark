from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

OUTPUT = Path(__file__).resolve().parent / ".generated"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "browser-watermark.docx").write_bytes(_docx())
    _write_pdf(OUTPUT / "browser-watermark.pdf")
    codecv_path = OUTPUT / "browser-codecv.pdf"
    codecv_path.write_bytes(_codecv_pdf())
    _add_test_signature(codecv_path)
    _write_image(OUTPUT / "browser-watermark.png")


def _docx() -> bytes:
    image_buffer = BytesIO()
    image = Image.new("RGB", (120, 48), "#d8c6a8")
    draw = ImageDraw.Draw(image)
    draw.text((28, 15), "DRAFT", fill="#4b5a60")
    image.save(image_buffer, format="PNG", optimize=False)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types '
            'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        package.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        package.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>KEEP-ME</w:t></w:r></w:p></w:body></w:document>',
        )
        package.writestr(
            "word/header1.xml",
            '<?xml version="1.0"?><w:hdr '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:v="urn:schemas-microsoft-com:vml" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<w:p><w:r><w:pict>'
            '<v:shape id="PowerPlusWaterMarkObject1" type="#_x0000_t136" '
            'style="rotation:315;position:absolute"><v:textpath string="DRAFT"/>'
            '</v:shape></w:pict></w:r><w:r><w:drawing><wp:anchor behindDoc="1">'
            '<wp:extent cx="1143000" cy="457200"/>'
            '<wp:docPr id="2" name="Browser watermark" descr="DRAFT image"/>'
            '<a:graphic><a:graphicData><pic:pic><pic:nvPicPr>'
            '<pic:cNvPr id="3" name="browser-watermark.png"/>'
            '</pic:nvPicPr><pic:blipFill><a:blip r:embed="rIdImage"/>'
            '</pic:blipFill></pic:pic></a:graphicData></a:graphic>'
            '</wp:anchor></w:drawing></w:r></w:p></w:hdr>',
        )
        package.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" '
            'Target="header1.xml"/></Relationships>',
        )
        package.writestr(
            "word/_rels/header1.xml.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdImage" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="media/browser-watermark.png"/></Relationships>',
        )
        package.writestr("word/media/browser-watermark.png", image_buffer.getvalue())
    return output.getvalue()


def _write_pdf(path: Path) -> None:
    document = pymupdf.open()
    for page_number in (1, 2):
        page = document.new_page(width=612, height=792)
        page.insert_text(
            (100, 100),
            f"REMOVE-ME-{page_number}",
            fontsize=24,
            color=(0.45, 0.45, 0.45),
        )
        page.insert_text(
            (100, 210),
            f"KEEP-ME-{page_number}",
            fontsize=16,
            color=(0.1, 0.1, 0.1),
        )
    document.set_metadata({"title": "Generated browser PDF fixture"})
    document.save(path)
    document.close()
    _add_test_signature(path)


def _add_test_signature(path: Path) -> None:
    source = PdfReader(BytesIO(path.read_bytes()), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(source)
    signature = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Sig"),
            NameObject("/Filter"): NameObject("/Adobe.PPKLite"),
            NameObject("/SubFilter"): NameObject("/adbe.pkcs7.detached"),
            NameObject("/ByteRange"): ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(0), NumberObject(0)]
            ),
            NameObject("/Contents"): ByteStringObject(b"browser-test-signature"),
        }
    )
    signature_field = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Sig"),
            NameObject("/T"): TextStringObject("Browser approval"),
            NameObject("/V"): writer._add_object(signature),
        }
    )
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject(
        {NameObject("/Fields"): ArrayObject([writer._add_object(signature_field)])}
    )
    output = BytesIO()
    writer.write(output)
    path.write_bytes(output.getvalue())


def _codecv_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    pattern = DecodedStreamObject()
    pattern.set_data(b"0.92 g 0 0 30 30 re f\n")
    pattern.update(
        {
            NameObject("/Type"): NameObject("/Pattern"),
            NameObject("/PatternType"): NumberObject(1),
            NameObject("/PaintType"): NumberObject(1),
            NameObject("/TilingType"): NumberObject(1),
            NameObject("/BBox"): ArrayObject(
                [FloatObject(0), FloatObject(0), FloatObject(30), FloatObject(30)]
            ),
            NameObject("/XStep"): FloatObject(30),
            NameObject("/YStep"): FloatObject(30),
            NameObject("/Resources"): DictionaryObject(),
        }
    )
    pattern_ref = writer._add_object(pattern)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Pattern"): DictionaryObject(
                {NameObject("/Watermark1"): pattern_ref}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(
        b"/Pattern CS /Pattern cs /Watermark1 SCN /Watermark1 scn "
        b"0 0 612 792 re f\n"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _write_image(path: Path) -> None:
    image = Image.new("RGB", (100, 60), "#d8c6a8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 20, 54, 34), fill="#4b5a60")
    draw.text((29, 22), "WM", fill="white")
    image.save(path, format="PNG", optimize=False)


if __name__ == "__main__":
    main()
