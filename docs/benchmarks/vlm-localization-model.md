# VLM watermark-localization benchmark

This report contains real model output.

Metric gate: **fail** · Precision: 0.419 · Recall: 0.722 · F1: 0.531 · Mean matched IoU: 0.795
Evidence gate: **pass** · Samples: 36 · Negatives: 18 · Scenes: 4 · Pairs: 15

## Scene breakdown

| Scene | Samples | Positives | Negatives | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| document | 2 | 1 | 1 | 0 | 2 | 1 | 0.000 | 0.000 | 0.000 |
| natural_scene | 25 | 13 | 12 | 12 | 4 | 1 | 0.750 | 0.923 | 0.828 |
| ordinary_ui | 7 | 3 | 4 | 1 | 10 | 2 | 0.091 | 0.333 | 0.143 |
| typography | 2 | 1 | 1 | 0 | 2 | 1 | 0.000 | 0.000 | 0.000 |

## Paired-scene diagnostics

| Pair | Scene | Clean negative | Mark detected | Pair pass |
|---|---|---:|---:|---:|
| as11-40-5878 | natural_scene | no | yes | no |
| code-editor | ordinary_ui | no | yes | no |
| dashboard | ordinary_ui | no | no | no |
| document | document | no | no | no |
| iss042e097549 | natural_scene | no | yes | no |
| mobile-feed | ordinary_ui | no | no | no |
| photo-horizon | natural_scene | yes | yes | yes |
| photo-night | natural_scene | yes | yes | yes |
| pia00254 | natural_scene | yes | yes | yes |
| pia11141 | natural_scene | yes | yes | yes |
| pia11727 | natural_scene | yes | yes | yes |
| pia17792 | natural_scene | no | no | no |
| pia20284 | natural_scene | yes | yes | yes |
| pia24642 | natural_scene | yes | yes | yes |
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
| paired-pia24642-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia24642-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.849 |
| paired-as11-40-5878-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-as11-40-5878-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.672 |
| paired-iss042e097549-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-iss042e097549-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.884 |
| paired-pia11141-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia11141-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.734 |
| paired-pia00254-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia00254-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.884 |
| paired-pia20284-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia20284-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.709 |
| paired-pia17792-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| paired-pia17792-positive | positive | 1 | 1 | 0 | 1 | 1 | — |
| paired-pia11727-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia11727-positive | positive | 1 | 1 | 1 | 0 | 0 | 0.653 |
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
