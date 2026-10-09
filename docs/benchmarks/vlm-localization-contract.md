# VLM watermark-localization benchmark

This is a geometry contract fixture, not a model performance result.

Metric gate: **pass** · Precision: 1.000 · Recall: 1.000 · F1: 1.000 · Mean matched IoU: 0.901

| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |
|---|---|---:|---:|---:|---:|---:|---:|
| real-horizon-corner | positive | 1 | 1 | 1 | 0 | 0 | 0.887 |
| real-horizon-translucent | positive | 1 | 1 | 1 | 0 | 0 | 0.893 |
| real-night-multiline | positive | 1 | 1 | 1 | 0 | 0 | 0.923 |
| clean-horizon-negative | negative | 0 | 0 | 0 | 0 | 0 | — |
| clean-night-negative | negative | 0 | 0 | 0 | 0 | 0 | — |

A release claim is allowed only when `evaluation_kind` is `model` and the metric gate passes.
