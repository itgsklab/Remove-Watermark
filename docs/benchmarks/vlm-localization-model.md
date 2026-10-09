# VLM watermark-localization benchmark

This report contains real model output.

Metric gate: **pass** · Precision: 0.750 · Recall: 1.000 · F1: 0.857 · Mean matched IoU: 0.839
Evidence gate: **fail** · Samples: 6 · Negatives: 3

| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |
|---|---|---:|---:|---:|---:|---:|---:|
| real-horizon-corner | positive | 1 | 1 | 1 | 0 | 0 | 0.833 |
| real-horizon-translucent | positive | 1 | 1 | 1 | 0 | 0 | 0.760 |
| real-night-multiline | positive | 1 | 1 | 1 | 0 | 0 | 0.925 |
| clean-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-project-ui-negative | negative | 0 | 1 | 0 | 1 | 0 | — |

A release claim is allowed only for real model output when both metric and minimum-evidence gates pass.
