.PHONY: backend-install backend-check frontend-install frontend-check browser-install browser-check web-build web-run image-benchmark mobile-watermark-benchmark mobile-selection-corpus vlm-localization-corpus vlm-model-fetch vlm-localization-contract vlm-localization-model vlm-photo-gate vlm-localization-model-photo-gated mask-refinement-corpus mask-refinement-contract mask-refinement-model-env mask-refinement-model-fetch mask-refinement-model mask-refinement-photo-corpus mask-refinement-photo-model mask-refinement-photo-model-cpu mask-refinement-candidate-gate-mps mask-refinement-candidate-gate-cpu model-supply-chain-review complexity-calibration codecv-corpus codecv-real-corpus pdf-redaction-probe pdf-ocr-probe pdf-redaction-corpus release-metadata release-metadata-check wheel-check release-check stable-release-policy-check check

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

backend-check:
	cd backend && .venv/bin/ruff check . && .venv/bin/pytest --cov=wmrm

frontend-install:
	cd frontend && npm install

frontend-check:
	cd frontend && npm run typecheck && npm run build

browser-install:
	cd frontend && npm ci && npx playwright install chromium

browser-check:
	cd frontend && npm run e2e

web-build:
	cd frontend && npm ci && npm run build

web-run:
	backend/.venv/bin/wmrm-web --frontend-dir frontend/dist

image-benchmark:
	cd backend && .venv/bin/python -m wmrm.benchmarks.image_quality \
		--output ../work/image-benchmark \
		--report-json ../docs/benchmarks/opencv-telea-baseline.json \
		--report-md ../docs/benchmarks/opencv-telea-baseline.md

mobile-watermark-benchmark:
	cd backend && .venv/bin/python -m wmrm.benchmarks.mobile_watermark \
		--output ../work/mobile-watermark \
		--report-json ../docs/benchmarks/mobile-watermark-baseline.json \
		--report-md ../docs/benchmarks/mobile-watermark-baseline.md \
		--strict

mobile-selection-corpus:
	cd backend && .venv/bin/python -m wmrm.benchmarks.mobile_selection_corpus \
		--manifest tests/fixtures/mobile_selection_corpus/manifest.json \
		--report-json ../docs/benchmarks/mobile-selection-corpus.json \
		--report-md ../docs/benchmarks/mobile-selection-corpus.md \
		--strict

vlm-model-fetch:
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_fetch \
		--manifest ../docs/models/florence-2-base.json \
		--destination ../work/models/florence-2-base

vlm-localization-corpus:
	cd backend && .venv/bin/python tests/fixtures/vlm_localization/build_corpus.py

vlm-localization-contract:
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_localization \
		--manifest tests/fixtures/vlm_localization/manifest.json \
		--predictions tests/fixtures/vlm_localization/contract-predictions.json \
		--report-json ../docs/benchmarks/vlm-localization-contract.json \
		--report-md ../docs/benchmarks/vlm-localization-contract.md

vlm-localization-model:
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_predict \
		--manifest tests/fixtures/vlm_localization/manifest.json \
		--model-dir ../work/models/florence-2-base \
		--model-manifest ../docs/models/florence-2-base.json \
		--output ../work/vlm-localization-predictions.json
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_localization \
		--manifest tests/fixtures/vlm_localization/manifest.json \
		--predictions ../work/vlm-localization-predictions.json \
		--report-json ../work/vlm-localization-model.json \
		--report-md ../work/vlm-localization-model.md \
		--require-model-output --strict

vlm-photo-gate:
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_photo_gate \
		--manifest tests/fixtures/vlm_localization/manifest.json \
		--predictions ../work/vlm-localization-predictions.json \
		--gated-predictions ../work/vlm-photo-gated-predictions.json \
		--localization-report-json ../docs/benchmarks/vlm-photo-gated-localization.json \
		--localization-report-md ../docs/benchmarks/vlm-photo-gated-localization.md \
		--gate-report-json ../docs/benchmarks/vlm-photo-gate.json \
		--gate-report-md ../docs/benchmarks/vlm-photo-gate.md

vlm-localization-model-photo-gated:
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_predict \
		--manifest tests/fixtures/vlm_localization/manifest.json \
		--model-dir ../work/models/florence-2-base \
		--model-manifest ../docs/models/florence-2-base.json \
		--output ../work/vlm-photo-gated-predictions.json \
		--photo-scene-gate

mask-refinement-corpus:
	cd backend && .venv/bin/python tests/fixtures/mask_refinement/build_corpus.py

mask-refinement-contract:
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/mask_refinement/manifest.json \
		--predictions tests/fixtures/mask_refinement/contract-predictions.json \
		--report-json ../docs/benchmarks/mask-refinement-contract.json \
		--report-md ../docs/benchmarks/mask-refinement-contract.md

mask-refinement-model-fetch:
	cd backend && .venv/bin/python -m wmrm.benchmarks.vlm_fetch \
		--manifest ../docs/models/sam2-hiera-tiny.json \
		--destination ../work/models/sam2-hiera-tiny

mask-refinement-model-env:
	python3 -m venv work/segmentation-eval/.venv
	work/segmentation-eval/.venv/bin/pip install --requirement backend/requirements-segmentation-eval.txt
	work/segmentation-eval/.venv/bin/pip install --no-deps --editable backend

mask-refinement-model:
	cd backend && ../work/segmentation-eval/.venv/bin/python -m wmrm.benchmarks.mask_refinement_predict \
		--manifest tests/fixtures/mask_refinement/manifest.json \
		--model-dir ../work/models/sam2-hiera-tiny \
		--model-manifest ../docs/models/sam2-hiera-tiny.json \
		--output ../work/mask-refinement-sam2/predictions.json
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/mask_refinement/manifest.json \
		--predictions ../work/mask-refinement-sam2/predictions.json \
		--report-json ../work/mask-refinement-sam2/report.json \
		--report-md ../work/mask-refinement-sam2/report.md \
		--require-model-output

mask-refinement-photo-corpus:
	backend/.venv/bin/python backend/tests/fixtures/vlm_localization/build_mask_refinement_corpus.py
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--predictions tests/fixtures/vlm_localization/mask-refinement-photo-contract-predictions.json \
		--report-json ../docs/benchmarks/mask-refinement-photo-contract.json \
		--report-md ../docs/benchmarks/mask-refinement-photo-contract.md \
		--min-sample-count 32 --min-negative-count 16 --min-category-count 4

mask-refinement-photo-model:
	cd backend && ../work/segmentation-eval/.venv/bin/python -m wmrm.benchmarks.mask_refinement_predict \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--model-dir ../work/models/sam2-hiera-tiny \
		--model-manifest ../docs/models/sam2-hiera-tiny.json \
		--output ../work/mask-refinement-sam2-photo-mps/predictions.json --device mps
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--predictions ../work/mask-refinement-sam2-photo-mps/predictions.json \
		--report-json ../work/mask-refinement-sam2-photo-mps/report.json \
		--report-md ../work/mask-refinement-sam2-photo-mps/report.md \
		--require-model-output \
		--min-sample-count 32 --min-negative-count 16 --min-category-count 4

mask-refinement-photo-model-cpu:
	cd backend && ../work/segmentation-eval/.venv/bin/python -m wmrm.benchmarks.mask_refinement_predict \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--model-dir ../work/models/sam2-hiera-tiny \
		--model-manifest ../docs/models/sam2-hiera-tiny.json \
		--output ../work/mask-refinement-sam2-photo-cpu/predictions.json --device cpu
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--predictions ../work/mask-refinement-sam2-photo-cpu/predictions.json \
		--report-json ../work/mask-refinement-sam2-photo-cpu/report.json \
		--report-md ../work/mask-refinement-sam2-photo-cpu/report.md \
		--require-model-output \
		--min-sample-count 32 --min-negative-count 16 --min-category-count 4

mask-refinement-candidate-gate-mps:
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement_gate \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--localization-predictions ../docs/benchmarks/vlm-photo-gated-predictions.json \
		--segmentation-predictions ../work/mask-refinement-sam2-photo-mps/predictions.json \
		--output ../work/mask-refinement-sam2-photo-mps-gated/predictions.json
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--predictions ../work/mask-refinement-sam2-photo-mps-gated/predictions.json \
		--report-json ../work/mask-refinement-sam2-photo-mps-gated/report.json \
		--report-md ../work/mask-refinement-sam2-photo-mps-gated/report.md \
		--require-model-output \
		--min-sample-count 32 --min-negative-count 16 --min-category-count 4

mask-refinement-candidate-gate-cpu:
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement_gate \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--localization-predictions ../docs/benchmarks/vlm-photo-gated-predictions.json \
		--segmentation-predictions ../work/mask-refinement-sam2-photo-cpu/predictions.json \
		--output ../work/mask-refinement-sam2-photo-cpu-gated/predictions.json
	cd backend && .venv/bin/python -m wmrm.benchmarks.mask_refinement \
		--manifest tests/fixtures/vlm_localization/mask-refinement-photo-manifest.json \
		--predictions ../work/mask-refinement-sam2-photo-cpu-gated/predictions.json \
		--report-json ../work/mask-refinement-sam2-photo-cpu-gated/report.json \
		--report-md ../work/mask-refinement-sam2-photo-cpu-gated/report.md \
		--require-model-output \
		--min-sample-count 32 --min-negative-count 16 --min-category-count 4

model-supply-chain-review:
	cd backend && .venv/bin/python -m wmrm.benchmarks.model_supply_chain \
		--manifest ../docs/models/sam2-hiera-tiny.json \
		--report-json ../docs/benchmarks/sam2-hiera-tiny-supply-chain.json \
		--report-md ../docs/benchmarks/sam2-hiera-tiny-supply-chain.md

complexity-calibration:
	cd backend && .venv/bin/python -m wmrm.benchmarks.complexity_calibration \
		--manifest tests/fixtures/image_complexity/manifest.json \
		--report-json ../docs/benchmarks/image-complexity-calibration.json \
		--report-md ../docs/benchmarks/image-complexity-calibration.md \
		--strict

codecv-corpus:
	cd backend && .venv/bin/python -m wmrm.benchmarks.codecv_corpus \
		--manifest tests/fixtures/codecv_corpus/manifest.json \
		--report-json ../docs/benchmarks/codecv-corpus-harness.json \
		--report-md ../docs/benchmarks/codecv-corpus-harness.md \
		--strict

codecv-real-corpus:
	cd backend && .venv/bin/python -m wmrm.benchmarks.codecv_corpus \
		--manifest private-fixtures/codecv/manifest.json \
		--report-json ../work/codecv-real-corpus.json \
		--report-md ../work/codecv-real-corpus.md \
		--strict --require-real

pdf-redaction-probe:
	cd backend && .venv/bin/python -m wmrm.benchmarks.pdf_redaction_probe \
		--report-json ../work/pdf-redaction-probe.json \
		--output-pdf ../work/pdf-redaction-probe.pdf \
		--strict

pdf-ocr-probe:
	cd backend && .venv/bin/python -m wmrm.benchmarks.pdf_ocr_probe \
		--report-json ../docs/benchmarks/pdf-ocr-probe.json \
		--report-md ../docs/benchmarks/pdf-ocr-probe.md \
		--output-pdf ../work/pdf-ocr-probe.pdf \
		--strict

pdf-redaction-corpus:
	cd backend && .venv/bin/python -m wmrm.benchmarks.pdf_redaction_corpus \
		--manifest tests/fixtures/pdf_redaction_corpus/manifest.json \
		--report-json ../docs/benchmarks/pdf-redaction-producer-corpus.json \
		--report-md ../docs/benchmarks/pdf-redaction-producer-corpus.md \
		--strict

release-metadata:
	python3 packaging/generate_release_metadata.py

release-metadata-check:
	python3 packaging/generate_release_metadata.py --check

wheel-check:
	python3 packaging/verify_wheel_install.py

release-check: release-metadata-check wheel-check

stable-release-policy-check:
	python3 packaging/verify_stable_release.py

check: backend-check frontend-check
