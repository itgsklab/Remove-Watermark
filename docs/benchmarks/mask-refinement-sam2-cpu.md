# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **fail** · IoU: 0.230 · Precision: 0.231 · Recall: 0.981
Correction reduction: 0.654 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 8 · Negatives: 4 · Categories: 8
Timing gate: **fail** · Timed workflows: 0

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| positive-translucent-text | positive | translucent_text | 0.325 | 1872 | 1101 | 0.412 |
| positive-timestamp | positive | timestamp | 0.714 | 936 | 154 | 0.835 |
| positive-stamp | positive | stamp | 0.987 | 1078 | 5 | 0.995 |
| positive-signature | positive | signature | 0.786 | 1586 | 68 | 0.957 |
| negative-face | negative | face | 0.000 | 2162 | 1125 | 0.480 |
| negative-content-signature | negative | normal_signature | 0.000 | 2128 | 309 | 0.855 |
| negative-brand | negative | brand | 0.000 | 1296 | 637 | 0.508 |
| negative-body-text | negative | body_text | 0.000 | 3760 | 1730 | 0.540 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
