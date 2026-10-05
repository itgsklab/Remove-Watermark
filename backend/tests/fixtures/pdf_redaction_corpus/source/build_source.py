# ruff: noqa: E501

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent


def main() -> None:
    (ROOT / "producer-source.html").write_text(_html(), encoding="utf-8")
    with ZipFile(ROOT / "producer-source.docx", "w", ZIP_DEFLATED) as archive:
        _write(archive, "[Content_Types].xml", _content_types())
        _write(archive, "_rels/.rels", _package_relationships())
        _write(archive, "word/document.xml", _document())


def _write(archive: ZipFile, name: str, content: str) -> None:
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, content.encode("utf-8"))


def _html() -> str:
    return """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Watermark remover PDF compatibility source</title>
<style>
  @page { size: Letter; margin: 1in; }
  body { margin: 0; font: 16pt Arial, sans-serif; color: #172033; }
  .page { position: relative; height: 9in; break-after: page; }
  .page:last-child { break-after: auto; }
  .keep-before { position: absolute; top: 0.45in; left: 0.25in; }
  .remove { position: absolute; top: 3.6in; left: 1.65in; color: #777; font-size: 28pt; }
  .keep-after { position: absolute; top: 7.5in; left: 0.25in; }
</style>
<body>
  <section class="page">
    <div class="keep-before">KEEP-BEFORE</div>
    <div class="remove">REMOVE-ME</div>
    <div class="keep-after">KEEP-AFTER</div>
  </section>
  <section class="page"><div>UNCHANGED-PAGE</div></section>
</body>
</html>
"""


def _content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""


def _package_relationships() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


def _paragraph(text: str, *, size: int = 32, before: int = 0, after: int = 160) -> str:
    return f"""<w:p><w:pPr><w:spacing w:before="{before}" w:after="{after}"/></w:pPr>
      <w:r><w:rPr><w:sz w:val="{size}"/></w:rPr><w:t>{text}</w:t></w:r></w:p>"""


def _document() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {_paragraph("KEEP-BEFORE", before=360)}
    {_paragraph("REMOVE-ME", size=56, before=3600)}
    {_paragraph("KEEP-AFTER", before=2500)}
    <w:p><w:r><w:br w:type="page"/></w:r></w:p>
    {_paragraph("UNCHANGED-PAGE", before=360)}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


if __name__ == "__main__":
    main()
