# Box-guided mask-refinement benchmark

This report contains real model output.

Metric gate: **fail** · IoU: 0.730 · Precision: 0.955 · Recall: 0.756
Correction reduction: 0.798 · Outside-box pixels: 0
Evidence gate: **pass** · Samples: 16 · Negatives: 8 · Categories: 4
Timing gate: **fail** · Timed workflows: 0
Provenance gate: **pass** · Independent sources: 8 · Paired scenes: 8
Candidate gate: TP 7 · TN 8 · FP 0 · FN 1 · Precision 1.000 · Recall 0.875

## Samples

| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |
|---|---|---|---:|---:|---:|---:|
| confirmation-pia00342-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-pia00342-positive | positive | corner_badge | 0.000 | 136 | 11000 | 0.000 |
| confirmation-pia17542-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-pia17542-positive | positive | translucent_text | 0.630 | 2575 | 1304 | 0.494 |
| confirmation-pia14417-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-pia14417-positive | positive | corner_badge | 0.970 | 136 | 330 | 0.000 |
| confirmation-pia07902-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-pia07902-positive | positive | translucent_text | 0.674 | 2572 | 1433 | 0.443 |
| confirmation-pia24439-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-pia24439-positive | positive | corner_badge | 0.987 | 136 | 145 | 0.000 |
| confirmation-s69-16402-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-s69-16402-positive | positive | translucent_text | 0.786 | 2595 | 798 | 0.692 |
| confirmation-pia15658-negative | negative | clean_corner_badge_context | 1.000 | 11136 | 0 | 1.000 |
| confirmation-pia15658-positive | positive | corner_badge | 0.971 | 136 | 316 | 0.000 |
| confirmation-pia04227-negative | negative | clean_translucent_text_context | 1.000 | 5824 | 0 | 1.000 |
| confirmation-pia04227-positive | positive | translucent_text | 0.823 | 2563 | 593 | 0.769 |

A release claim requires real model output plus metric, evidence and human timing gates. Model output remains a review-only draft.
