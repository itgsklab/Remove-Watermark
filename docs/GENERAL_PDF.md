# General PDF inspection

## Current scope

The general PDF preset is a read-only candidate inventory. Clients create an analysis with `preset: "general"`; they may also provide target watermark text. The resulting candidates have no allowed processing strategy, so they cannot enter a destructive plan.

This stage deliberately separates detection from deletion. Repeated text may be a header, repeated images may be a logo, Pattern resources may be ordinary backgrounds and Stamp annotations may be valid review marks.

## Candidate types

The inspector currently reports:

- text fragments that contain user-supplied target text;
- identical short text repeated on at least two pages and at least half of the document;
- Image and Form XObject calls, recursively expanding nested Forms and marking cross-page reuse for review;
- Pattern resources selected by `SCN` or `scn` operations;
- `/Watermark` and `/Stamp` annotations;
- optional content groups, with name checks for the target and common watermark terms.

Explicit `/Watermark` annotations are classified as `confirmed`. Target text, repeated text, repeated objects, patterns, stamps and suspicious optional-content names remain `ambiguous`. A single-page image or Form call is returned as `content` so the UI can explain why it was not promoted to a watermark candidate.

## Location evidence

PDF locations use `pdf_points` in the page crop-box coordinate system. Each available region records page number, XYXY bounds, crop-box origin, page dimensions, rotation, transform ID and whether the bounds are approximate.

Image and Form bounds come from the current transformation matrix at the `Do` operation. Form bounds use the Form `/BBox` and optional `/Matrix`; nested resource paths are retained in names such as `/FmOuter>/ImInner`. Text bounds are approximate because reliable glyph boxes require font metrics and shaping details that are not always embedded. Candidates also retain operation index, resource name and indirect object identity when available.

## Safety boundaries

- General candidates have an empty `allowed_strategies` list.
- Plan validation rejects `general` analyses.
- Region previews validate the saved page transform before calculating overlap.
- Encrypted, malformed and over-limit PDFs use the same safety checks as CodeCV inspection.
- Digital signature fields produce a warning because writing a new PDF normally invalidates existing signatures.
- Form XObjects are recursively inventoried to a maximum depth of eight. Cycles or deeper trees produce an explicit incomplete-scan warning; recursive editing is not implemented.
- No OCR is attempted, so image-only and scanned text watermarks are outside this stage.

The current UI renders pages with PDF.js and converts drag selections back to crop-box-relative PDF points. Numeric coordinates remain visible and editable for inspection. The backend then reports overlap with inventoried text, images, Forms, vector graphics, links and annotations.

PDF.js is dynamically imported only when the visual editor is opened, keeping the initial application bundle separate from the PDF parser and worker. A reviewed rectangle can now enter a persisted PyMuPDF redaction plan; any inventoried overlap requires explicit acknowledgement before the isolated worker generates a new PDF.

Object deletion will only be enabled for additional structures after each locator can be revalidated and output preservation has regression coverage.
