# PDF deep raster repair

The general-PDF workspace offers `raster_inpaint` for watermarks that cannot be removed as a
separate PDF object. The workflow remains local and always writes a new PDF.

## Processing contract

1. The user scans the PDF with the `general` preset and selects a crop-box-relative region.
2. The server repeats coordinate, digest, page-transform and protected-content checks.
3. The user acknowledges that each selected page will be rasterized and lose links, forms and
   editable vector objects.
4. A worker renders only the selected pages at 96–300 DPI, converts the regions to pixel masks and
   applies OpenCV Telea inpainting.
5. Unselected pages are copied from the source PDF without rasterization.
6. Words from the original text layer that do not intersect a mask are inserted invisibly over the
   repaired page. Masked words are intentionally omitted.
7. If a selected page has no source words and Tesseract is available, OCR TSV word boxes are mapped
   back into PDF points and inserted as the hidden searchable layer.
8. The result is reopened strictly and checked for encryption, page count, crop-box size and page
   rotation before it becomes downloadable.

The task result reports which pages used the source text layer, which used OCR and which remained
unsearchable. Page previews are generated through the existing Poppler comparison path.

## OCR boundary

Tesseract is optional and is never downloaded automatically. The default language is `eng`; the Vue
workspace accepts installed Tesseract language expressions such as `chi_sim+eng`. If Tesseract is
missing or OCR fails, born-digital pages can still reuse their original words, while image-only pages
are reported as unsearchable. Web and CLI launches check `PATH` plus conventional Homebrew, Unix and
Windows Tesseract install locations so macOS Finder launches can find Homebrew installations.

Run `make pdf-ocr-probe` to generate a synthetic image-only PDF and verify the installed Tesseract
binary end to end. The probe checks English text, Chinese text when `chi_sim` and a local CJK font are
available, removal of masked text, repaired pixels, strict reopening and OCR-page reporting. The
latest local evidence is stored in `docs/benchmarks/pdf-ocr-probe.{json,md}`.

## Current limits

- Deep repair supports crop boxes whose lower-left origin is `(0, 0)`. Offset crop boxes are rejected
  before editing and should use object-level redaction.
- Selected pages become lossless PNG backgrounds. Their links, annotations, forms, optional-content
  groups and editable vector objects are not retained.
- OpenCV Telea is intended for relatively small masks. Structured or large backgrounds still require
  manual before/after review.
- OCR quality depends on the locally installed Tesseract build, language data, render DPI and source
  page quality. The output is not claimed to reproduce reading order or typography exactly.
- PyMuPDF correctly extracts the probe's built-in CJK searchable layer. Some other PDF parsers,
  including the currently pinned pypdf version, may not decode that built-in CJK font mapping.
