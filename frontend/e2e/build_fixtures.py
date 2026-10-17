from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parent / ".generated"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "browser-watermark.docx").write_bytes(_docx())
    _write_pdf(OUTPUT / "browser-watermark.pdf")
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
    page = document.new_page(width=612, height=792)
    page.insert_text((100, 100), "REMOVE-ME", fontsize=24, color=(0.45, 0.45, 0.45))
    page.insert_text((100, 210), "KEEP-ME", fontsize=16, color=(0.1, 0.1, 0.1))
    document.set_metadata({"title": "Generated browser PDF fixture"})
    document.save(path)
    document.close()


def _write_image(path: Path) -> None:
    image = Image.new("RGB", (100, 60), "#d8c6a8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 20, 54, 34), fill="#4b5a60")
    draw.text((29, 22), "WM", fill="white")
    image.save(path, format="PNG", optimize=False)


if __name__ == "__main__":
    main()
