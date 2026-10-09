# VLM watermark-localization benchmark

This is a geometry contract fixture, not a model performance result.

Metric gate: **pass** · Precision: 1.000 · Recall: 1.000 · F1: 1.000 · Mean matched IoU: 0.857
Evidence gate: **fail** · Samples: 6 · Negatives: 3

| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |
|---|---|---:|---:|---:|---:|---:|---:|
| real-horizon-corner | positive | 1 | 1 | 1 | 0 | 0 | 0.887 |
| real-horizon-translucent | positive | 1 | 1 | 1 | 0 | 0 | 0.762 |
| real-night-multiline | positive | 1 | 1 | 1 | 0 | 0 | 0.923 |
| clean-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-project-ui-negative | negative | 0 | 0 | 0 | 0 | 0 | — |

A release claim is allowed only for real model output when both metric and minimum-evidence gates pass.
