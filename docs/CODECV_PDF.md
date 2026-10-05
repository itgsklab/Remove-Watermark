# CodeCV PDF preset

## Current scope

The CodeCV preset scans PDF structure and can generate a cleaned PDF copy after candidate selection. It does not overwrite the source, rasterize pages or delete every `/Pattern` resource.

Clients must explicitly send `preset: "codecv"` when creating an analysis for a PDF. This prevents a generic PDF from being silently treated as a CodeCV export.

## Match evidence

The inspector parses page content streams with `pypdf` and looks for this complete operation sequence:

1. Set stroking and non-stroking color spaces to `/Pattern` with `CS` and `cs`.
2. Select the same named pattern for stroking and filling with `SCN` and `scn`.
3. Optionally apply an extended graphics state with `gs`.
4. Create a rectangle with `re` and fill it with `f` or `f*`.
5. Resolve the named resource from the page `/Resources` `/Pattern` dictionary and verify `/PatternType 1`.

The resource name is evidence only. It is never assumed to have a fixed value. Each candidate records the one-based page number, content operation index, resource name, indirect object and generation number, plus selected tiling pattern properties.

This signature was checked against the behavior described by the public [peakxy/remove_codecv_watermark](https://github.com/peakxy/remove_codecv_watermark) project. This project implements its own structural parser and editor and does not import that repository's source code.

The public reference repository contains the script and documentation but no PDF export corpus. Its behavior description therefore informs the signature shape, but does not count as compatibility evidence for any CodeCV template version.

## Safety limits

- Encrypted PDFs return `PASSWORD_REQUIRED`.
- Malformed or truncated PDFs return `INVALID_PDF`.
- Page count and decoded content streams have configurable limits.
- A partial sequence does not become a candidate.
- A complete sequence without a resolvable tiling pattern is marked ambiguous.
- A scan with no match reports `not_found`; it does not claim the document has no watermark.

## Editing and validation

The editor rechecks every selected page, operation index and resource name against the source digest locked into the plan. It removes only the matched operation slice and leaves the pattern resource dictionary intact, which avoids deleting unrelated uses of the same resource.

After writing the copy, the service reopens it in strict mode and verifies:

- encryption state and page count;
- media box, crop box and rotation for every page;
- direct page-content text-showing operations;
- the exact reduction in matching CodeCV operation sequences;
- output size and SHA-256 digest.

Poppler renders source and result pages for visual comparison when available. Preview failure does not discard an otherwise validated output PDF.

## Validation state

Automated tests use generated PDFs with both matching and ordinary page content. The generated matching fixture is rendered with Poppler during development to verify that it is a valid visible tiling pattern.

`make codecv-corpus` runs the export-corpus audit against three repository-generated fixtures. They cover a basic fill, a two-page signature with optional `gs` and `f*`, and a negative PDF that contains an unrelated Pattern resource. The audit pins source and extracted-text SHA-256 values, candidate counts and pages, then removes every confirmed candidate, verifies page/text preservation and requires a clean rescan to return `not_found`.

The generated report deliberately uses status `generated_only`; it proves the harness works but is not real-template compatibility evidence. See [`benchmarks/codecv-corpus-harness.md`](benchmarks/codecv-corpus-harness.md).

## Adding private real exports

Real resumes can contain personal information and are not committed by default. `backend/private-fixtures/` is ignored by Git. To create a manifest entry without manually calculating hashes:

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.codecv_probe \
  private-fixtures/codecv/resume-export.pdf \
  --id template-export-date \
  --template-version "visible template/version" \
  --provenance private_export \
  --output private-fixtures/codecv/probed-entry.json
```

The probe sets `review_required: true`. Review ownership or permission, template identity, candidate pages and expected cleanup behavior before copying the entry into `private-fixtures/codecv/manifest.json` and setting `review_required` to `false`. A complete example is stored in [`examples/codecv-corpus-manifest.json`](examples/codecv-corpus-manifest.json).

Run `make codecv-real-corpus`. This command uses `--require-real`, so generated fixtures alone cannot produce a passing real-export report.

The preset still needs provenance-cleared CodeCV exports from multiple template versions before it can move beyond experimental status. Until then, the UI exposes the structural evidence and requires the user to select candidates explicitly.
