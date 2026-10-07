# PDF OCR probe

- Passed: `true`
- Fixture: repository-generated synthetic image-only PDF
- Tesseract: `tesseract 5.5.3`
- Languages: `chi_sim+eng`

| Check | Result |
|---|---|
| `source_is_image_only` | pass |
| `ocr_page_reported` | pass |
| `no_unsearchable_pages` | pass |
| `english_text_searchable` | pass |
| `chinese_text_searchable` | pass |
| `masked_text_omitted` | pass |
| `masked_pixels_repaired` | pass |
| `page_count_preserved` | pass |
| `strict_reopen` | pass |
