# PDF region redaction

## Implemented preview contract

`POST /api/v1/redactions/preview` accepts an asset ID, a persisted `general` PDF analysis and up to 100 rectangles. Each rectangle contains a one-based page number, crop-box-relative PDF-point XYXY bounds and the `transform_id` returned for that page.

The Vue workspace loads the source through the controlled asset-content endpoint and renders the selected page with PDF.js. Pointer coordinates are converted through the PDF.js viewport, adjusted for the crop-box origin and submitted with the server-issued transform ID. The editor supports page rotation because conversion uses the rendered page viewport rather than hand-written screen-axis formulas.

The backend rejects:

- analyses belonging to another asset or digest;
- CodeCV and non-PDF analyses;
- missing pages, non-finite values and reversed or out-of-page coordinates;
- transforms that no longer match the scanned page geometry.

For each accepted rectangle, the response lists intersections with inventoried text, images, Form XObjects, vector graphics, links and annotations. Text and vector bounds are marked approximate where PDF font metrics, stroke width, clipping or nested graphics can make an exact box unavailable.

The response sets `executable` from the installed PyMuPDF backend probe. A validated preview can be submitted to `POST /api/v1/redaction-plans/validate`; overlaps require the `PDF_REDACTION_OVERLAP` acknowledgement before a persisted task plan is created.

## Why applied redaction is required

Adding a white rectangle or an unapplied redaction annotation does not remove underlying PDF content. Text can remain extractable and graphics can remain recoverable, so the project will not label either technique as deletion.

PyMuPDF provides applied redactions that physically remove affected content. The project is licensed under `AGPL-3.0-only`, uses PyMuPDF's AGPL distribution path and includes it as a runtime dependency. `WMRM_PYMUPDF_LICENSE_MODE=commercial` only records a separately obtained PyMuPDF commercial license mode; it does not relicense this project's source code.

The license and redaction semantics are documented by the [PyMuPDF licensing page](https://pymupdf.io/licensing) and [`Page.apply_redactions()` API](https://pymupdf.readthedocs.io/en/latest/page.html#Page.apply_redactions). pypdf remains the permissively licensed structural parser and output verifier; qpdf's documented transformations preserve page content and therefore do not replace an applied-redaction engine.

## Backend and proof

The repository contains a PyMuPDF adapter and a deterministic conformance probe. The adapter refuses to run unless its caller explicitly supplies `agpl` or `commercial` as the license mode. It converts the application's crop-box-relative, bottom-left coordinates to PyMuPDF's unrotated top-left coordinates, applies transparent redactions, saves with full garbage collection, and strictly reopens the result with pypdf.

Install and run the isolated proof with:

```bash
cd backend
.venv/bin/pip install -e .
cd ..
make pdf-redaction-probe
```

The probe covers target-text removal, outside-text preservation, image-pixel clearing, overlapping-vector removal, overlapping-link removal, unchanged-page text, page count, geometry and strict reopening. It writes disposable evidence under `work/`. Production tasks run the same adapter in the existing isolated worker and use the existing Poppler before/after preview pipeline.

## Application-exported compatibility corpus

`make pdf-redaction-corpus` runs the production adapter against PDFs exported from project-authored source documents by three installed applications:

- Google Chrome 154.0.8037.93;
- LibreOfficeDev 26.8.0.0.alpha0;
- Microsoft Word for Mac 16.110.

The manifest pins the producer and version, export note, source record, PDF SHA-256 digest, reviewed region and expected preserved text. The audit requires the target text to disappear, all control text to remain, unaffected page text to stay identical, page count and geometry validation to pass, and the result to reopen in strict mode. The committed report is [benchmarks/pdf-redaction-producer-corpus.md](benchmarks/pdf-redaction-producer-corpus.md).

These fixtures test distinct application export paths with controlled project content. WPS is not represented because no verifiable WPS installation was available on the test machine. Broader malformed-content behavior and third-party documents with documented redistribution rights are still required before calling the feature stable.
