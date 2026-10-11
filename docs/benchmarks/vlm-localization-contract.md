# VLM watermark-localization benchmark

This is a geometry contract fixture, not a model performance result.

Metric gate: **pass** · Precision: 1.000 · Recall: 1.000 · F1: 1.000 · Mean matched IoU: 0.982
Evidence gate: **pass** · Samples: 48 · Negatives: 24 · Scenes: 4 · Pairs: 21

## Scene breakdown

| Scene | Samples | Positives | Negatives | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| document | 2 | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| natural_scene | 37 | 19 | 18 | 19 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| ordinary_ui | 7 | 3 | 4 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| typography | 2 | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |

## Paired-scene diagnostics

| Pair | Scene | Clean negative | Mark detected | Pair pass |
|---|---|---:|---:|---:|
| as11-40-5878 | natural_scene | yes | yes | yes |
| code-editor | ordinary_ui | yes | yes | yes |
| commons-144326190 | natural_scene | yes | yes | yes |
| commons-14666867 | natural_scene | yes | yes | yes |
| commons-201054816 | natural_scene | yes | yes | yes |
| commons-38778875 | natural_scene | yes | yes | yes |
| commons-59873545 | natural_scene | yes | yes | yes |
| commons-74184357 | natural_scene | yes | yes | yes |
| dashboard | ordinary_ui | yes | yes | yes |
| document | document | yes | yes | yes |
| iss042e097549 | natural_scene | yes | yes | yes |
| mobile-feed | ordinary_ui | yes | yes | yes |
| photo-horizon | natural_scene | yes | yes | yes |
| photo-night | natural_scene | yes | yes | yes |
| pia00254 | natural_scene | yes | yes | yes |
| pia11141 | natural_scene | yes | yes | yes |
| pia11727 | natural_scene | yes | yes | yes |
| pia17792 | natural_scene | yes | yes | yes |
| pia20284 | natural_scene | yes | yes | yes |
| pia24642 | natural_scene | yes | yes | yes |
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
| paired-pia24642-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia24642-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-as11-40-5878-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-as11-40-5878-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-iss042e097549-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-iss042e097549-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-pia11141-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia11141-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-pia00254-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia00254-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-pia20284-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia20284-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-pia17792-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia17792-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-pia11727-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-pia11727-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-commons-38778875-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-commons-38778875-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-commons-59873545-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-commons-59873545-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-commons-14666867-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-commons-14666867-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-commons-74184357-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-commons-74184357-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-commons-144326190-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-commons-144326190-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
| paired-commons-201054816-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| paired-commons-201054816-positive | positive | 1 | 1 | 1 | 0 | 0 | 1.000 |
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
