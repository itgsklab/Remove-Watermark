# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **fail** · IoU: 0.714 · Precision: 0.908 · Recall: 0.770
Correction reduction: 0.777 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8
Candidate gate: TP 7 · TN 8 · FP 0 · FN 1 · Precision 1.000 · Recall 0.875

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| confirmation-third-pia00123-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia00123-positive | positive | corner_badge | 0.871 | 136 | 1417 | 0.000 |
| confirmation-third-pia00122-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-pia00122-positive | positive | translucent_text | 0.854 | 2562 | 529 | 0.794 |
| confirmation-third-pia13474-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia13474-positive | positive | corner_badge | 0.976 | 137 | 262 | 0.000 |
| confirmation-third-pia00134-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-pia00134-positive | positive | translucent_text | 0.770 | 2592 | 940 | 0.637 |
| confirmation-third-pia00232-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia00232-positive | positive | corner_badge | 0.000 | 136 | 11000 | 0.000 |
| confirmation-third-twin-jet-nebula-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-twin-jet-nebula-positive | positive | translucent_text | 0.691 | 2625 | 1414 | 0.461 |
| confirmation-third-pia04200-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia04200-positive | positive | corner_badge | 0.996 | 136 | 46 | 0.662 |
| confirmation-third-pia04225-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-pia04225-positive | positive | translucent_text | 0.623 | 2575 | 1924 | 0.253 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
