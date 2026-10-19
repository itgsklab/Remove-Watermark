# Box-guided mask-refinement benchmark

This is a scoring-contract fixture, not a model performance result.

Metric gate: **pass** · IoU: 1.000 · Precision: 1.000 · Recall: 1.000
Correction reduction: 1.000 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 8 · Negatives: 4 · Categories: 8
Timing gate: **fail** · Timed workflows: 0

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| positive-translucent-text | positive | translucent_text | 1.000 | 1872 | 0 | 1.000 |
| positive-timestamp | positive | timestamp | 1.000 | 936 | 0 | 1.000 |
| positive-stamp | positive | stamp | 1.000 | 1078 | 0 | 1.000 |
| positive-signature | positive | signature | 1.000 | 1586 | 0 | 1.000 |
| negative-face | negative | face | 1.000 | 2162 | 0 | 1.000 |
| negative-content-signature | negative | normal_signature | 1.000 | 2128 | 0 | 1.000 |
| negative-brand | negative | brand | 1.000 | 1296 | 0 | 1.000 |
| negative-body-text | negative | body_text | 1.000 | 3760 | 0 | 1.000 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
