# Image complexity calibration

This audit checks the production preflight against provenance-recorded photos and a repository-owned browser screenshot. Exact source bytes are pinned by SHA-256.

Status: **pass** · Samples: 3 · Regions: 18 · Matches: 18 · Mismatches: 0 · Match rate: 100.00%

OpenCV: `5.0.0` · NumPy: `2.5.3` · Pillow: `12.3.0`

Labeling protocol: Expected risk is justified from visible background semantics rather than derived from numeric thresholds: low for locally smooth fill, review for irregular texture without a dominant crossing boundary, and high for repeated patterns or long structural edges likely to break during inpainting.

Thresholds: periodicity high `0.8` · periodicity minimum texture `0.1` · structure high `0.3` · edge high `0.2` · texture review `0.35` · edge review `0.08`

| Sample | Type | Region | Expected | Actual | Texture | Edge | Periodic | Structure |
|---|---|---|---|---|---:|---:|---:|---:|
| nasa-earth-horizon-2026 | photo | 平滑太空背景 | low | low | 0.0000 | 0.0000 | 0.5120 | 0.0000 |
| nasa-earth-horizon-2026 | photo | 地球弧线与大气层 | high | high | 0.3000 | 0.0666 | 0.8029 | 0.0985 |
| nasa-earth-horizon-2026 | photo | 云层与海面纹理 | review | review | 0.3667 | 0.1099 | 0.7583 | 0.2091 |
| nasa-earth-horizon-2026 | photo | 暗空中的柔和光斑 | low | low | 0.0000 | 0.0000 | 0.7066 | 0.0000 |
| nasa-earth-horizon-2026 | photo | 海面反光与云纹 | review | review | 0.4000 | 0.1034 | 0.6277 | 0.2402 |
| nasa-earth-horizon-2026 | photo | 云海长边界 | high | high | 0.3333 | 0.1109 | 0.6586 | 0.3065 |
| nasa-earth-night-2015 | photo | 暗色太空背景 | low | low | 0.2000 | 0.0357 | 0.6038 | 0.1235 |
| nasa-earth-night-2015 | photo | 空间站机械结构 | review | review | 0.6333 | 0.1037 | 0.7387 | 0.0589 |
| nasa-earth-night-2015 | photo | 城市灯光纹理 | review | review | 0.6000 | 0.1067 | 0.6292 | 0.0000 |
| nasa-earth-night-2015 | photo | 右侧稀疏星空 | low | low | 0.1000 | 0.0100 | 0.5417 | 0.0000 |
| nasa-earth-night-2015 | photo | 密集城市灯光 | review | review | 0.6667 | 0.1175 | 0.6237 | 0.1203 |
| nasa-earth-night-2015 | photo | 绿色地球边缘 | high | high | 0.7667 | 0.1206 | 0.7114 | 0.3240 |
| wmrm-home-desktop | screenshot | 空白页面背景 | low | low | 0.0000 | 0.0044 | 0.6777 | 0.0402 |
| wmrm-home-desktop | screenshot | 标题笔画结构 | high | high | 1.0000 | 0.0461 | 0.7523 | 0.5524 |
| wmrm-home-desktop | screenshot | 上传卡片边缘 | high | high | 0.8000 | 0.0621 | 0.6325 | 1.0000 |
| wmrm-home-desktop | screenshot | 右侧浅色留白 | low | low | 0.0000 | 0.0020 | 0.5572 | 0.0000 |
| wmrm-home-desktop | screenshot | 标题字间纹理 | review | review | 0.6000 | 0.0260 | 0.6461 | 0.1324 |
| wmrm-home-desktop | screenshot | 说明文字行结构 | high | high | 0.2667 | 0.0331 | 0.5004 | 0.3408 |

## Label rationale

- `nasa-earth-horizon-2026:smooth-space` (low): The selected area and its surrounding ring are visually uniform black space without a crossing boundary.
- `nasa-earth-horizon-2026:earth-horizon` (high): The curved atmospheric boundary is a long structure whose continuity must be reconstructed.
- `nasa-earth-horizon-2026:cloud-texture` (review): Irregular cloud and ocean detail requires review but has no single dominant crossing edge.
- `nasa-earth-horizon-2026:upper-lens-flare` (low): The surrounding black sky is smooth; the soft flare stays inside the selected area and does not create a crossing boundary.
- `nasa-earth-horizon-2026:sun-glint` (review): Irregular reflected light and cloud texture can expose fill artifacts but do not form one dominant crossing line.
- `nasa-earth-horizon-2026:cloud-ocean-boundary` (high): Several elongated cloud and ocean boundaries cross the context and should remain continuous after filling.
- `nasa-earth-night-2015:dark-space` (low): The surrounding dark sky is locally smooth with sparse points that do not define a structure.
- `nasa-earth-night-2015:station-arm` (review): Mechanical parts add irregular texture around the region without a single continuous boundary through the mask.
- `nasa-earth-night-2015:city-lights` (review): Dense, irregular city lights can blur during filling and require visual review.
- `nasa-earth-night-2015:right-starfield` (low): The surrounding sky is predominantly smooth and sparse stars do not form a continuous structure.
- `nasa-earth-night-2015:dense-city-core` (review): Dense stochastic lights make texture synthesis uncertain without a dominant geometric boundary.
- `nasa-earth-night-2015:green-earth-limb` (high): A thin, continuous planetary limb crosses the context and visible discontinuity would be obvious.
- `wmrm-home-desktop:empty-background` (low): The page fill is visually flat and contains no crossing UI boundary.
- `wmrm-home-desktop:headline-strokes` (high): Large glyph strokes create long, high-contrast structures near the selected region.
- `wmrm-home-desktop:upload-card-edge` (high): The card boundary is a long straight structure that must remain aligned.
- `wmrm-home-desktop:quiet-right-fill` (low): The selected area is a uniform page fill with no nearby control boundary crossing the mask.
- `wmrm-home-desktop:headline-interglyph-context` (review): Nearby antialiased glyph fragments create moderate texture, while no long stroke crosses the selected area.
- `wmrm-home-desktop:supporting-copy-structure` (high): Multiple aligned text strokes and baselines form long visual structures that should not be broken.

## Provenance

### nasa-earth-horizon-2026

- File: `nasa-earth-iss074e0089803.jpg` (`d88909464177af39f24ed97ae28f4eab383c2b477f4a7e00e716812252227d11`)
- Dimensions: 1279 × 718
- Attribution: NASA, image iss074e0089803
- Provenance: Downloaded from NASA's official image service. The record contains no third-party copyright notice, identifiable person, or NASA logo.
- References: [source record](https://images.nasa.gov/details/iss074e0089803); [usage terms](https://www.nasa.gov/nasa-brand-center/images-and-media/)

### nasa-earth-night-2015

- File: `nasa-earth-iss045e013851.jpg` (`cf7b480745b578ced3c8913761228fbff6660caf35b8301f7c232791ff504169`)
- Dimensions: 1279 × 851
- Attribution: NASA, image iss045e013851
- Provenance: Downloaded from NASA's official image service. The record contains no third-party copyright notice, identifiable person, or NASA logo.
- References: [source record](https://images.nasa.gov/details/iss045e013851); [usage terms](https://www.nasa.gov/nasa-brand-center/images-and-media/)

### wmrm-home-desktop

- File: `project-home-desktop.png` (`0639a998f0dfacac68eb9c6067348ea706b363bd5860d97e3041b89ee8ceafa2`)
- Dimensions: 1265 × 889
- Attribution: Generated from this repository's Vue application at 1280 × 900 browser viewport.
- Provenance: Captured locally from commit f18747a with an empty local data directory; contains no user data or third-party media.
- References: local project capture; repository-owned

## Interpretation

The labels describe expected preflight risk for the selected regions, not reconstruction quality. A passing audit shows that threshold behavior remains stable on these pinned samples; it does not establish accuracy on arbitrary photos.
