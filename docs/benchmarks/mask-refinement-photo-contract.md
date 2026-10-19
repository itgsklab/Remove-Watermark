# Box-guided mask-refinement benchmark

This is a scoring-contract fixture, not a model performance result.

Metric gate: **pass** · IoU: 1.000 · Precision: 1.000 · Recall: 1.000
Correction reduction: 1.000 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 32 · Negatives: 16 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 16 · Paired scenes: 16

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| paired-as11-40-5878-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-as11-40-5878-positive | positive | translucent_text | 1.000 | 2536 | 0 | 1.000 |
| paired-commons-144326190-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-144326190-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| paired-commons-14666867-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-14666867-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| paired-commons-201054816-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-201054816-positive | positive | translucent_text | 1.000 | 2534 | 0 | 1.000 |
| paired-commons-38778875-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-commons-38778875-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| paired-commons-59873545-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-59873545-positive | positive | translucent_text | 1.000 | 2564 | 0 | 1.000 |
| paired-commons-74184357-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-commons-74184357-positive | positive | translucent_text | 1.000 | 2560 | 0 | 1.000 |
| paired-iss042e097549-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-iss042e097549-positive | positive | corner_badge | 1.000 | 137 | 0 | 1.000 |
| paired-photo-horizon-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-photo-horizon-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| paired-photo-night-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-photo-night-positive | positive | translucent_text | 1.000 | 2580 | 0 | 1.000 |
| paired-pia00254-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia00254-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| paired-pia11141-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11141-positive | positive | translucent_text | 1.000 | 2592 | 0 | 1.000 |
| paired-pia11727-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia11727-positive | positive | translucent_text | 1.000 | 2549 | 0 | 1.000 |
| paired-pia17792-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia17792-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| paired-pia20284-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| paired-pia20284-positive | positive | translucent_text | 1.000 | 2536 | 0 | 1.000 |
| paired-pia24642-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| paired-pia24642-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
