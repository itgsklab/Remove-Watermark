# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **fail** · IoU: 0.643 · Precision: 0.937 · Recall: 0.673
Correction reduction: 0.730 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8
Candidate gate: TP 7 · TN 8 · FP 0 · FN 1 · Precision 1.000 · Recall 0.875

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| holdout-as17-148-22727-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-as17-148-22727-positive | positive | corner_badge | 0.000 | 136 | 11000 | 0.000 |
| holdout-0202487-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-0202487-positive | positive | translucent_text | 0.626 | 2554 | 1425 | 0.442 |
| holdout-iss040e063570-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-iss040e063570-positive | positive | corner_badge | 0.675 | 136 | 3580 | 0.000 |
| holdout-as17-140-21497-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-as17-140-21497-positive | positive | translucent_text | 0.817 | 2607 | 640 | 0.755 |
| holdout-0701891-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-0701891-positive | positive | corner_badge | 0.995 | 136 | 53 | 0.610 |
| holdout-iss041e045376-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-iss041e045376-positive | positive | translucent_text | 0.722 | 2606 | 1164 | 0.553 |
| holdout-as17-145-22162-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-as17-145-22162-positive | positive | corner_badge | 0.791 | 136 | 2304 | 0.000 |
| holdout-iss073e0008524-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-iss073e0008524-positive | positive | translucent_text | 0.736 | 2592 | 1067 | 0.588 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
