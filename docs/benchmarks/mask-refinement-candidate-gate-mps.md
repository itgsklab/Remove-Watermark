# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **pass** · IoU: 0.795 · Precision: 0.958 · Recall: 0.823
Correction reduction: 0.846 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 32 · Negatives: 16 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 16 · Paired scenes: 16
Candidate gate: TP 15 · TN 16 · FP 0 · FN 1 · Precision 1.000 · Recall 0.938

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| paired-as11-40-5878-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-as11-40-5878-positive | positive | translucent_text | 0.710 | 2536 | 1071 | 0.578 |
| paired-commons-144326190-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-144326190-positive | positive | corner_badge | 0.993 | 136 | 77 | 0.434 |
| paired-commons-14666867-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-14666867-positive | positive | corner_badge | 0.980 | 136 | 222 | 0.000 |
| paired-commons-201054816-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-201054816-positive | positive | translucent_text | 0.835 | 2534 | 596 | 0.765 |
| paired-commons-38778875-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-38778875-positive | positive | corner_badge | 0.919 | 136 | 887 | 0.000 |
| paired-commons-59873545-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-59873545-positive | positive | translucent_text | 0.530 | 2564 | 1534 | 0.402 |
| paired-commons-74184357-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-74184357-positive | positive | translucent_text | 0.693 | 2560 | 1240 | 0.516 |
| paired-iss042e097549-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-iss042e097549-positive | positive | corner_badge | 0.959 | 137 | 449 | 0.000 |
| paired-photo-horizon-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-photo-horizon-positive | positive | corner_badge | 0.925 | 136 | 828 | 0.000 |
| paired-photo-night-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-photo-night-positive | positive | translucent_text | 0.501 | 2580 | 1668 | 0.353 |
| paired-pia00254-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia00254-positive | positive | corner_badge | 0.987 | 136 | 146 | 0.000 |
| paired-pia11141-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11141-positive | positive | translucent_text | 0.784 | 2592 | 804 | 0.690 |
| paired-pia11727-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11727-positive | positive | translucent_text | 0.483 | 2549 | 2039 | 0.200 |
| paired-pia17792-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia17792-positive | positive | corner_badge | 0.000 | 136 | 11000 | 0.000 |
| paired-pia20284-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia20284-positive | positive | translucent_text | 0.652 | 2536 | 1619 | 0.362 |
| paired-pia24642-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia24642-positive | positive | corner_badge | 0.992 | 136 | 86 | 0.368 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
