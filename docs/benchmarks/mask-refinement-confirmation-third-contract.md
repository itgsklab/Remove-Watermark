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
| confirmation-third-pia00123-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia00123-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-third-pia00122-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-pia00122-positive | positive | translucent_text | 1.000 | 2562 | 0 | 1.000 |
| confirmation-third-pia13474-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia13474-positive | positive | corner_badge | 1.000 | 137 | 0 | 1.000 |
| confirmation-third-pia00134-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-pia00134-positive | positive | translucent_text | 1.000 | 2592 | 0 | 1.000 |
| confirmation-third-pia00232-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia00232-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-third-twin-jet-nebula-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-twin-jet-nebula-positive | positive | translucent_text | 1.000 | 2625 | 0 | 1.000 |
| confirmation-third-pia04200-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-third-pia04200-positive | positive | corner_badge | 1.000 | 136 | 0 | 1.000 |
| confirmation-third-pia04225-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-third-pia04225-positive | positive | translucent_text | 1.000 | 2575 | 0 | 1.000 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
