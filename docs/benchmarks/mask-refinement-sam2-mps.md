# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **fail** · IoU: 0.223 · Precision: 0.228 · Recall: 0.917
Correction reduction: 0.664 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 8 · Negatives: 4 · Categories: 8
Timing gate: **fail** · Timed workflows: 0

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| positive-translucent-text | positive | translucent_text | 0.320 | 1872 | 1107 | 0.409 |
| positive-timestamp | positive | timestamp | 0.975 | 936 | 10 | 0.989 |
| positive-stamp | positive | stamp | 0.976 | 1078 | 9 | 0.992 |
| positive-signature | positive | signature | 0.632 | 1586 | 92 | 0.942 |
| negative-face | negative | face | 0.000 | 2162 | 1122 | 0.481 |
| negative-content-signature | negative | normal_signature | 0.000 | 2128 | 290 | 0.864 |
| negative-brand | negative | brand | 0.000 | 1296 | 637 | 0.508 |
| negative-body-text | negative | body_text | 0.000 | 3760 | 1711 | 0.545 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
