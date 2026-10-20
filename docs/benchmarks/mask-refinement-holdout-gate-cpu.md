# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **fail** · IoU: 0.705 · Precision: 0.855 · Recall: 0.801
Correction reduction: 0.758 · Outside-box pixels: 0
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
| holdout-0202487-positive | positive | translucent_text | 0.632 | 2554 | 1863 | 0.271 |
| holdout-iss040e063570-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-iss040e063570-positive | positive | corner_badge | 0.998 | 136 | 27 | 0.801 |
| holdout-as17-140-21497-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-as17-140-21497-positive | positive | translucent_text | 0.601 | 2607 | 2102 | 0.194 |
| holdout-0701891-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-0701891-positive | positive | corner_badge | 0.999 | 136 | 11 | 0.919 |
| holdout-iss041e045376-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-iss041e045376-positive | positive | translucent_text | 0.612 | 2606 | 1968 | 0.245 |
| holdout-as17-145-22162-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-as17-145-22162-positive | positive | corner_badge | 1.000 | 136 | 5 | 0.963 |
| holdout-iss073e0008524-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-iss073e0008524-positive | positive | translucent_text | 0.603 | 2592 | 2093 | 0.193 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
