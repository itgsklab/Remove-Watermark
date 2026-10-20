# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **pass** · IoU: 0.827 · Precision: 0.913 · Recall: 0.897
Correction reduction: 0.864 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 32 · Negatives: 16 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 16 · Paired scenes: 16
Candidate gate: TP 15 · TN 16 · FP 0 · FN 1 · Precision 1.000 · Recall 0.938

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| paired-as11-40-5878-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-as11-40-5878-positive | positive | translucent_text | 0.767 | 2536 | 985 | 0.612 |
| paired-commons-144326190-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-144326190-positive | positive | corner_badge | 0.999 | 136 | 14 | 0.897 |
| paired-commons-14666867-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-14666867-positive | positive | corner_badge | 0.999 | 136 | 14 | 0.897 |
| paired-commons-201054816-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-201054816-positive | positive | translucent_text | 0.746 | 2534 | 1110 | 0.562 |
| paired-commons-38778875-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-38778875-positive | positive | corner_badge | 0.999 | 136 | 7 | 0.949 |
| paired-commons-59873545-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-59873545-positive | positive | translucent_text | 0.689 | 2564 | 1408 | 0.451 |
| paired-commons-74184357-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-74184357-positive | positive | translucent_text | 0.787 | 2560 | 856 | 0.666 |
| paired-iss042e097549-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-iss042e097549-positive | positive | corner_badge | 1.000 | 137 | 3 | 0.978 |
| paired-photo-horizon-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-photo-horizon-positive | positive | corner_badge | 1.000 | 136 | 3 | 0.978 |
| paired-photo-night-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-photo-night-positive | positive | translucent_text | 0.664 | 2580 | 1514 | 0.413 |
| paired-pia00254-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia00254-positive | positive | corner_badge | 0.999 | 136 | 8 | 0.941 |
| paired-pia11141-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11141-positive | positive | translucent_text | 0.618 | 2592 | 1981 | 0.236 |
| paired-pia11727-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11727-positive | positive | translucent_text | 0.729 | 2549 | 1194 | 0.532 |
| paired-pia17792-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia17792-positive | positive | corner_badge | 0.000 | 136 | 11000 | 0.000 |
| paired-pia20284-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia20284-positive | positive | translucent_text | 0.708 | 2536 | 1341 | 0.471 |
| paired-pia24642-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia24642-positive | positive | corner_badge | 0.999 | 136 | 8 | 0.941 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
