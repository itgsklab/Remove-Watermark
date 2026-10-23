# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **pass** · IoU: 0.909 · Precision: 0.914 · Recall: 0.995
Correction reduction: 0.928 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8
Candidate gate: TP 8 · TN 8 · FP 0 · FN 0 · Precision 1.000 · Recall 1.000

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| confirmation-fourth-pia07882-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia07882-positive | positive | corner_badge | 0.991 | 136 | 95 | 0.301 |
| confirmation-fourth-pia15691-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia15691-positive | positive | translucent_text | 0.744 | 2534 | 1128 | 0.555 |
| confirmation-fourth-pia24921-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia24921-positive | positive | corner_badge | 0.994 | 136 | 61 | 0.551 |
| confirmation-fourth-pia02210-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia02210-positive | positive | translucent_text | 0.622 | 2592 | 1945 | 0.250 |
| confirmation-fourth-pia02215-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia02215-positive | positive | corner_badge | 0.998 | 136 | 19 | 0.860 |
| confirmation-fourth-pia18182-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia18182-positive | positive | translucent_text | 0.758 | 2534 | 1046 | 0.587 |
| confirmation-fourth-pia00346-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-fourth-pia00346-positive | positive | corner_badge | 0.998 | 136 | 22 | 0.838 |
| confirmation-fourth-pia01481-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-fourth-pia01481-positive | positive | translucent_text | 0.705 | 2581 | 1337 | 0.482 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
