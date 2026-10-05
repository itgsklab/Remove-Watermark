# OpenCV Telea synthetic benchmark

All images are generated procedurally by this repository; no external assets are used.

Seed: `20260928` · Radius: `3` · OpenCV: `5.0.0` · NumPy: `2.5.3` · Pillow: `12.3.0`

| Case | Mask MAE | PSNR dB | Boundary MAE | Improvement | Grade |
|---|---:|---:|---:|---:|---|
| 纯色背景 | 1.86 | 40.94 | 0.52 | 97.71% | excellent |
| 平滑渐变 | 3.44 | 34.72 | 1.11 | 94.95% | excellent |
| 周期条纹 | 55.42 | 10.82 | 41.16 | 0.03% | poor |
| 跨蒙版结构线 | 32.61 | 11.81 | 10.34 | 61.51% | poor |
| 固定随机纹理 | 24.76 | 18.83 | 24.22 | 55.11% | review |

Mean masked MAE: **23.62**. Mean improvement: **61.86%**. Outside-mask integrity: **5/5** cases.

Keep OpenCV Telea as the lightweight baseline for small masks on simple backgrounds; require visual review for structured or textured regions.

Grades are internal regression bands, not perceptual-quality guarantees. Inspect the generated images before changing product behavior.
