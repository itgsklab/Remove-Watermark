# Image inspection, masks and OpenCV repair

PNG, JPEG and WebP assets use the explicit `image` analysis preset. This stage validates the uploaded bytes with Pillow and records the encoded size, display size after EXIF orientation, format, color mode, frame count, alpha-channel presence, ICC-profile presence and a transform ID tied to the asset digest and geometry.

## Resource limits

The default limits are 20,000 pixels per edge, 40 million pixels per frame and 100 animation frames. They can be changed with `WMRM_MAX_IMAGE_DIMENSION`, `WMRM_MAX_IMAGE_PIXELS` and `WMRM_MAX_IMAGE_FRAMES`. Corrupt payloads, format mismatches and decompression-bomb warnings are rejected before a mask can be created.

## Coordinate contract

The editor uses top-left-origin display pixels after applying EXIF orientation:

- `x0`, `y0` are the left and top edges;
- `x1`, `y1` are the right and bottom edges;
- all values must remain within `display_width × display_height`;
- every region carries the server-issued `transform_id`.

`POST /api/v1/image-masks/preview` rejects stale transforms, non-finite values, empty rectangles and out-of-bounds regions. It calculates the exact union area of all rectangles, so overlapping masks are not counted twice. Covering more than 25% of the image requires explicit acknowledgement in the processing plan.

The same preview measures the pixels around each mask and returns an explainable complexity assessment. It reports normalized texture, edge-density, periodicity and long-structure scores for every region. The selected pixels are excluded from feature extraction, so the watermark itself does not inflate the assessment. Smooth backgrounds are marked `low`; moderate texture is marked `review`; repeated patterns, dense detail or long crossing edges are marked `high`. High-complexity plans require explicit acknowledgement before a task can be created.

The preview also evaluates selection risk derived from the mobile benchmark. A combined mask covering at least 10% of the image requires acknowledgement. For every region, the service compares mean luminance inside the selection with a nearby context ring; a normalized difference below 4% is treated as a low-contrast selection that may contain a translucent watermark and also requires acknowledgement. This is a conservative heuristic rather than an opacity detector. The Vue workspace displays the measured difference, reason and large-selection state before plan creation.

## OpenCV baseline

`POST /api/v1/image-plans/validate` persists a static-image plan using OpenCV's Telea algorithm and a radius from 1 to 10 pixels. The task runs in the same isolated worker system as document jobs and always writes a new PNG artifact. The source file is never overwritten.

Before accepting the artifact, the worker:

- applies the recorded EXIF display orientation;
- decodes the output again as a single-frame PNG;
- verifies the output dimensions;
- compares every pixel outside the rasterized mask with the normalized source;
- rejects the task if any pixel outside the mask changed.

The PNG output intentionally omits EXIF, ICC and other source metadata. Alpha channels are repaired inside the mask with the same algorithm and remain byte-identical outside it.

## Current boundary

The source image is served through the controlled asset-content endpoint and remains unchanged. Animated WebP files can be inspected, but cannot enter processing until per-frame mask behavior is defined.

The OpenCV baseline works best for small watermarks surrounded by simple, continuous texture. The preflight is a deterministic risk estimate rather than a perceptual quality predictor: it cannot see the unknown pixels behind a watermark or guarantee a natural reconstruction. The generated benchmark provides offline regression evidence rather than a guarantee for arbitrary user images. Model weights and their licenses must be audited before a model-backed adapter is distributed.

The generated five-scenario benchmark and its current measurements are stored in [`docs/benchmarks/opencv-telea-baseline.md`](benchmarks/opencv-telea-baseline.md). Run `make image-benchmark` to recreate clean targets, watermarked inputs, masks, repaired outputs and both report formats. The corpus is fully procedural and uses no external image assets.

The portrait-oriented mobile benchmark adds a small corner badge, translucent center text and a multi-line lower overlay. It records risk classification, low-contrast and large-selection decisions, mask coverage, target-aware quality metrics and whether repair improved or degraded the known clean image. The current baseline shows that the small smooth-background badge improves strongly, while the translucent mark becomes worse after Telea removal despite its absolute error receiving a `good` grade. This is why [`mobile-watermark-baseline.md`](benchmarks/mobile-watermark-baseline.md) reports quality outcome separately from grade. Run `make mobile-watermark-benchmark` to reproduce all source, mask, result and report artifacts.

The companion [`mobile-selection-corpus.md`](benchmarks/mobile-selection-corpus.md) checks the 4% low-contrast and 10% large-selection rules on portrait derivatives of two provenance-recorded NASA photographs. Source and derived SHA-256 digests, crop and overlay transformations, attribution, usage terms and manual-review state are pinned in the fixture manifest. The underlying pixels are real photographs, while all watermark overlays are generated by this repository; these samples are not presented as native social-platform exports. Run `make mobile-selection-corpus` for the strict audit.

The current measurements support automatic use on flat and smoothly varying backgrounds only. Periodic stripes, crossing geometry and high-detail texture require visual review. The LaMa packaging decision and conditions for reconsideration are documented in [`docs/LAMA_EVALUATION.md`](LAMA_EVALUATION.md).

The complexity thresholds are also audited against two provenance-recorded NASA photos and one browser screenshot generated by this repository. Eighteen semantically labeled regions provide six balanced examples for each risk level and cover smooth space, curved horizons, cloud and city texture, reflected light, thin planetary limbs, typography and UI edges. Periodicity only raises high risk when the context also contains measurable texture, preventing unstable correlations in nearly flat areas from creating false alarms. Each expected level carries a visible-semantic rationale independent of the measured score values, so the audit detects disagreement instead of treating current output as ground truth. Exact source bytes, SHA-256 values, attribution, expected labels and measured scores are recorded in [`docs/benchmarks/image-complexity-calibration.md`](benchmarks/image-complexity-calibration.md). Run `make complexity-calibration`; strict mode fails when any pinned region changes risk level.
