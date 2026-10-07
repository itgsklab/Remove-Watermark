# Command line interface

The `wmrm` entry point runs locally and never overwrites an input file. It exposes the mature
general-PDF backends plus reviewable plan workflows for images, DOCX and CodeCV PDFs.

## Runtime check

```bash
wmrm doctor
wmrm doctor --json
```

`doctor` reports the package version, PyMuPDF license modes and whether a local Tesseract executable
was found. JSON mode emits exactly one success object to standard output or one error object to
standard error.

## PDF Deep repair

```bash
wmrm pdf-deep source.pdf cleaned.pdf \
  --region 1:80:660:235:715 \
  --license-mode agpl \
  --dpi 144 \
  --radius 3 \
  --ocr-languages chi_sim+eng \
  --acknowledge-rasterization \
  --json
```

Regions use `PAGE:X0:Y0:X1:Y1` in crop-box-relative PDF points with a bottom-left origin. Repeat
`--region` for multiple selections. `--acknowledge-rasterization` is mandatory because selected
pages lose links, forms and editable vector objects.

## Object-level PDF removal

```bash
wmrm pdf-redact source.pdf cleaned.pdf \
  --region 1:80:660:235:715 \
  --license-mode agpl \
  --acknowledge-content-removal \
  --json
```

`--acknowledge-content-removal` confirms that intersecting text, image pixels, vectors and links may
be removed. Existing output files are rejected unless `--force` is supplied. Even with `--force`,
the CLI rejects an output path that resolves to the input or is a symbolic link. Replacement is
atomic: the previous output remains intact until the new PDF has passed backend validation.

## Image plan and execution

Create a JSON plan without modifying the image:

```bash
wmrm image-plan source.png watermark-plan.json \
  --region 120:80:260:145 \
  --radius 3 \
  --json
```

Image regions use display pixels with a top-left origin. The plan records the source SHA-256,
orientation transform, exact regions, mask coverage, background-complexity scores, low-contrast
assessment, warnings and a deterministic plan ID. Review `required_acknowledgements` before running:

```bash
wmrm image-apply source.png watermark-plan.json cleaned.png \
  --acknowledge IMAGE_COMPLEXITY_HIGH \
  --acknowledge IMAGE_MASK_OVER_10_PERCENT \
  --json
```

Only warning codes listed in the plan are accepted. Before processing, `image-apply` verifies the
plan ID, source digest, image orientation and a freshly computed risk assessment. Changed images or
edited plans are rejected. Results are lossless PNG files with original EXIF and ICC metadata removed.
As with PDF output, `--force` performs an atomic replacement after successful validation.

## DOCX candidate plan and execution

Scan header and footer parts without changing the document:

```bash
wmrm docx-plan source.docx docx-plan.json \
  --watermark-text DRAFT \
  --json
```

The saved plan records the source digest, inspected parts, every VML text-shape candidate, its exact
package locator, classification and evidence. `--watermark-text` is optional, but an exact match to
Word's built-in watermark shape turns that candidate from `ambiguous` into `confirmed`.

Select candidate IDs from the plan and create a new DOCX:

```bash
wmrm docx-apply source.docx docx-plan.json cleaned.docx \
  --candidate docx-0123456789abcdef0123 \
  --json
```

An ambiguous candidate requires its own warning code, for example
`--acknowledge AMBIGUOUS_CANDIDATE:docx-0123456789abcdef0123`. The editor changes only the selected
VML shapes, checks all untouched package parts byte-for-byte and validates package relationships.

## CodeCV candidate plan and execution

```bash
wmrm codecv-plan resume.pdf codecv-plan.json --json
wmrm codecv-apply resume.pdf codecv-plan.json cleaned.pdf \
  --candidate codecv-0123456789abcdef0123 \
  --json
```

The CodeCV plan reports `matched`, `needs_review` or `not_found` and preserves the page, content
operation, Pattern resource and indirect-object evidence for each candidate. Execution removes only
the selected operation sequence. It then verifies page count, page boxes, rotation, direct text
operations and the expected reduction in matching CodeCV sequences.

Both document apply commands recompute the complete scan before processing. A changed source,
edited plan, moved candidate or mismatched plan kind is rejected. Repeat `--candidate` and
`--acknowledge` for multiple selections. Output replacement with `--force` is atomic.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Command completed successfully. |
| `2` | Command syntax or region format is invalid. |
| `3` | Input or output path validation failed. |
| `4` | A required processing-risk acknowledgement is missing. |
| `5` | The processing backend or output write failed. |

The JSON envelope is stable for automation:

```json
{"ok": true, "command": "doctor", "result": {}}
```

Errors use `{"ok": false, "error": {"code": "...", "message": "..."}, "exit_code": 4}`.
