#!/bin/sh
set -eu

rm -rf ../work/e2e-data
../backend/.venv/bin/python e2e/build_fixtures.py
npm run build

export WMRM_DOCX_PREVIEW_ENABLED=false
export WMRM_PDF_PREVIEW_ENABLED=false
exec ../backend/.venv/bin/python -m wmrm.web \
  --frontend-dir dist \
  --port 8766 \
  --data-dir ../work/e2e-data
