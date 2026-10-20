# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **pass** · IoU: 0.806 · Precision: 0.942 · Recall: 0.848
Correction reduction: 0.852 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 32 · Negatives: 16 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 16 · Paired scenes: 16
Candidate gate: TP 15 · TN 16 · FP 0 · FN 1 · Precision 1.000 · Recall 0.938

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| paired-as11-40-5878-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-as11-40-5878-positive | positive | translucent_text | 0.654 | 2536 | 1474 | 0.419 |
| paired-commons-144326190-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-144326190-positive | positive | corner_badge | 0.996 | 136 | 41 | 0.699 |
| paired-commons-14666867-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-14666867-positive | positive | corner_badge | 0.984 | 136 | 178 | 0.000 |
| paired-commons-201054816-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-201054816-positive | positive | translucent_text | 0.845 | 2534 | 561 | 0.779 |
| paired-commons-38778875-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-38778875-positive | positive | corner_badge | 0.980 | 136 | 225 | 0.000 |
| paired-commons-59873545-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-59873545-positive | positive | translucent_text | 0.660 | 2564 | 1301 | 0.493 |
| paired-commons-74184357-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-74184357-positive | positive | translucent_text | 0.670 | 2560 | 1362 | 0.468 |
| paired-iss042e097549-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-iss042e097549-positive | positive | corner_badge | 0.987 | 137 | 147 | 0.000 |
| paired-photo-horizon-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-photo-horizon-positive | positive | corner_badge | 0.973 | 136 | 298 | 0.000 |
| paired-photo-night-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-photo-night-positive | positive | translucent_text | 0.501 | 2580 | 1668 | 0.353 |
| paired-pia00254-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia00254-positive | positive | corner_badge | 0.996 | 136 | 46 | 0.662 |
| paired-pia11141-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11141-positive | positive | translucent_text | 0.725 | 2592 | 1137 | 0.561 |
| paired-pia11727-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11727-positive | positive | translucent_text | 0.483 | 2549 | 2039 | 0.200 |
| paired-pia17792-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia17792-positive | positive | corner_badge | 0.000 | 136 | 11000 | 0.000 |
| paired-pia20284-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia20284-positive | positive | translucent_text | 0.638 | 2536 | 1753 | 0.309 |
| paired-pia24642-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia24642-positive | positive | corner_badge | 0.996 | 136 | 39 | 0.713 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
