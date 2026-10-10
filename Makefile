.PHONY: backend-install backend-check frontend-install frontend-check web-build web-run image-benchmark mobile-watermark-benchmark mobile-selection-corpus vlm-localization-corpus vlm-model-fetch vlm-localization-contract vlm-localization-model complexity-calibration codecv-corpus codecv-real-corpus pdf-redaction-probe pdf-ocr-probe pdf-redaction-corpus release-metadata release-metadata-check wheel-check release-check check

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

backend-check:
	cd backend && .venv/bin/ruff check . && .venv/bin/pytest --cov=wmrm

frontend-install:
	cd frontend && npm install

frontend-check:
	cd frontend && npm run typecheck && npm run build

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

check: backend-check frontend-check
