# Box-guided mask-refinement benchmark

This is a scoring-contract fixture, not a model performance result.

Metric gate: **pass** · IoU: 1.000 · Precision: 1.000 · Recall: 1.000
Correction reduction: 1.000 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| holdout-as17-148-22727-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-as17-148-22727-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| holdout-0202487-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-0202487-positive | positive | translucent_text | 1.000 | 2554 | 0 | 1.000 |
| holdout-iss040e063570-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-iss040e063570-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| holdout-as17-140-21497-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-as17-140-21497-positive | positive | translucent_text | 1.000 | 2607 | 0 | 1.000 |
| holdout-0701891-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-0701891-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| holdout-iss041e045376-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-iss041e045376-positive | positive | translucent_text | 1.000 | 2606 | 0 | 1.000 |
| holdout-as17-145-22162-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| holdout-as17-145-22162-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| holdout-iss073e0008524-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| holdout-iss073e0008524-positive | positive | translucent_text | 1.000 | 2592 | 0 | 1.000 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
