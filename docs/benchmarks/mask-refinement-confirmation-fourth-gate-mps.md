# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **pass** · IoU: 0.861 · Precision: 0.943 · Recall: 0.909
Correction reduction: 0.894 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8
Candidate gate: TP 8 · TN 8 · FP 0 · FN 0 · Precision 1.000 · Recall 1.000

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| confirmation-fourth-pia07882-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia07882-positive | positive | corner_badge | 0.982 | 136 | 197 | 0.000 |
| confirmation-fourth-pia15691-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia15691-positive | positive | translucent_text | 0.767 | 2534 | 982 | 0.612 |
| confirmation-fourth-pia24921-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia24921-positive | positive | corner_badge | 0.622 | 136 | 4155 | 0.000 |
| confirmation-fourth-pia02210-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia02210-positive | positive | translucent_text | 0.776 | 2592 | 907 | 0.650 |
| confirmation-fourth-pia02215-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia02215-positive | positive | corner_badge | 0.980 | 136 | 221 | 0.000 |
| confirmation-fourth-pia18182-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia18182-positive | positive | translucent_text | 0.717 | 2534 | 1275 | 0.497 |
| confirmation-fourth-pia00346-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia00346-positive | positive | corner_badge | 0.978 | 136 | 238 | 0.000 |
| confirmation-fourth-pia01481-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia01481-positive | positive | translucent_text | 0.889 | 2581 | 378 | 0.854 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
