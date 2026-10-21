# Box-guided mask-refinement benchmark

This is a scoring-contract fixture, not a model performance result.

Metric gate: **pass** · IoU: 1.000 · Precision: 1.000 · Recall: 1.000
Correction reduction: 1.000 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| confirmation-fourth-pia07882-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia07882-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-fourth-pia15691-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia15691-positive | positive | translucent_text | 1.000 | 2534 | 0 | 1.000 |
| confirmation-fourth-pia24921-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia24921-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-fourth-pia02210-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia02210-positive | positive | translucent_text | 1.000 | 2592 | 0 | 1.000 |
| confirmation-fourth-pia02215-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia02215-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-fourth-pia18182-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia18182-positive | positive | translucent_text | 1.000 | 2534 | 0 | 1.000 |
| confirmation-fourth-pia00346-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia00346-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-fourth-pia01481-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia01481-positive | positive | translucent_text | 1.000 | 2581 | 0 | 1.000 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
