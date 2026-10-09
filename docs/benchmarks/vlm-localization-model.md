# VLM watermark-localization benchmark

This report contains real model output.

Metric gate: **fail** · Precision: 0.400 · Recall: 0.667 · F1: 0.500 · Mean matched IoU: 0.879

| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |
|---|---|---:|---:|---:|---:|---:|---:|
| real-horizon-corner | positive | 1 | 1 | 1 | 0 | 0 | 0.833 |
| real-horizon-translucent | positive | 1 | 1 | 0 | 1 | 1 | — |
| real-night-multiline | positive | 1 | 1 | 1 | 0 | 0 | 0.925 |
| clean-horizon-negative | negative | 0 | 1 | 0 | 1 | 0 | — |
| clean-night-negative | negative | 0 | 1 | 0 | 1 | 0 | — |

A release claim is allowed only when `evaluation_kind` is `model` and the metric gate passes.
