# VLM watermark-localization benchmark

This report contains real model output.

Metric gate: **fail** · Precision: 0.300 · Recall: 0.600 · F1: 0.400 · Mean matched IoU: 0.825
Evidence gate: **pass** · Samples: 20 · Negatives: 10 · Scenes: 4 · Pairs: 7

## Scene breakdown

| Scene | Samples | Positives | Negatives | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| document | 2 | 1 | 1 | 0 | 2 | 1 | 0.000 | 0.000 | 0.000 |
| natural_scene | 9 | 5 | 4 | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| ordinary_ui | 7 | 3 | 4 | 1 | 10 | 2 | 0.091 | 0.333 | 0.143 |
| typography | 2 | 1 | 1 | 0 | 2 | 1 | 0.000 | 0.000 | 0.000 |

## Paired-scene diagnostics

| Pair | Scene | Clean negative | Mark detected | Pair pass |
|---|---|---:|---:|---:|
| code-editor | ordinary_ui | no | yes | no |
| dashboard | ordinary_ui | no | no | no |
| document | document | no | no | no |
| mobile-feed | ordinary_ui | no | no | no |
| photo-horizon | natural_scene | yes | yes | yes |
| photo-night | natural_scene | yes | yes | yes |
| poster | typography | no | no | no |

## Samples

| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |
|---|---|---:|---:|---:|---:|---:|---:|
| real-horizon-corner | positive | 1 | 1 | 1 | 0 | 0 | 0.833 |
| real-horizon-translucent | positive | 1 | 1 | 1 | 0 | 0 | 0.760 |
| real-night-multiline | positive | 1 | 1 | 1 | 0 | 0 | 0.925 |
| clean-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-project-ui-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-photo-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-photo-horizon-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.871 |
| paired-photo-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-photo-night-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.704 |
| paired-dashboard-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-dashboard-positive | positive | 1 | 1 | 0 | 1 | 1 | — |
| paired-document-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-document-positive | positive | 1 | 1 | 0 | 1 | 1 | — |
| paired-code-editor-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-code-editor-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.856 |
| paired-poster-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-poster-positive | positive | 1 | 1 | 0 | 1 | 1 | — |
| paired-mobile-feed-negative | negative | 0 | 3 | 0 | 3 | 0 | — |
| paired-mobile-feed-positive | positive | 1 | 3 | 0 | 3 | 1 | — |

A release claim is allowed only for real model output when both metric and minimum-evidence gates pass.
