# VLM watermark-localization benchmark

This is a geometry contract fixture, not a model performance result.

Metric gate: **pass** · Precision: 1.000 · Recall: 1.000 · F1: 1.000 · Mean matched IoU: 0.957
Evidence gate: **pass** · Samples: 20 · Negatives: 10 · Scenes: 4 · Pairs: 7

## Scene breakdown

| Scene | Samples | Positives | Negatives | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| document | 2 | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| natural_scene | 9 | 5 | 4 | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| ordinary_ui | 7 | 3 | 4 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| typography | 2 | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |

## Paired-scene diagnostics

| Pair | Scene | Clean negative | Mark detected | Pair pass |
|---|---|---:|---:|---:|
| code-editor | ordinary_ui | yes | yes | yes |
| dashboard | ordinary_ui | yes | yes | yes |
| document | document | yes | yes | yes |
| mobile-feed | ordinary_ui | yes | yes | yes |
| photo-horizon | natural_scene | yes | yes | yes |
| photo-night | natural_scene | yes | yes | yes |
| poster | typography | yes | yes | yes |

## Samples

| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |
|---|---|---:|---:|---:|---:|---:|---:|
| real-horizon-corner | positive | 1 | 1 | 1 | 0 | 0 | 0.887 |
| real-horizon-translucent | positive | 1 | 1 | 1 | 0 | 0 | 0.762 |
| real-night-multiline | positive | 1 | 1 | 1 | 0 | 0 | 0.923 |
| clean-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-project-ui-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-photo-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-photo-horizon-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-photo-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-photo-night-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-dashboard-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-dashboard-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-document-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-document-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-code-editor-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-code-editor-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-poster-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-poster-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-mobile-feed-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-mobile-feed-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |

A release claim is allowed only for real model output when both metric and minimum-evidence gates pass.
