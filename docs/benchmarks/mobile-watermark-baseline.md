# Mobile watermark benchmark

All portrait images and watermark overlays are generated deterministically by this repository; no external assets or user data are used.

Status: **pass** · Scenarios: 3 · Failed checks: 0 · Outside-mask integrity: 3/3

| Scenario | Mask | Risk | Low contrast | Large | MAE | Improvement | Outcome | Grade | Checks |
|---|---:|---|---|---|---:|---:|---|---|---|
| 右上角小水印 | 2.33% | low | false | false | 1.93 | 97.14% | improved | excellent | pass |
| 中央半透明水印 | 10.13% | review | true | true | 14.62 | -167.62% | degraded | good | pass |
| 底部多行文字覆盖 | 19.13% | high | false | true | 25.52 | 61.92% | improved | review | pass |

The benchmark covers a small corner badge, translucent center text and a multi-line lower overlay on portrait images. Quality grades describe the OpenCV baseline and are not perceptual guarantees.

Keep automatic OpenCV use limited to small masks on smooth backgrounds. Require before/after review for translucent marks and large structured overlays because removal can damage more pixels than the watermark changed.
