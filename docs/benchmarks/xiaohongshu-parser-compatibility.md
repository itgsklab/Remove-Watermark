# Xiaohongshu parser compatibility audit

This offline audit uses repository-generated HTML only. It performs no network access
and records no share links, page text, media URLs or user content in the report.

- Parser version: `xhs-html-meta-v2`
- Cases: `5`
- Matched expectations: `5`
- Mismatches: `0`
- Status: `pass`

| Case | Structure | Candidates | Diagnostics | Result |
|---|---|---:|---|---|
| complete-gallery | matched | 2 | none | pass |
| duplicate-gallery-entry | matched | 1 | XHS_MEDIA_DUPLICATES_COLLAPSED | pass |
| missing-dimensions | partial | 1 | XHS_MEDIA_DIMENSIONS_MISSING | pass |
| unrecognized-page-structure | changed | 0 | XHS_PAGE_STRUCTURE_UNRECOGNIZED | pass |
| media-outside-allowlist | changed | 0 | XHS_PAGE_MEDIA_UNUSABLE | pass |
