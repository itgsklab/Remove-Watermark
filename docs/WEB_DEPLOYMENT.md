# Web deployment

Watermark Remover uses a Vue browser interface and a Python/FastAPI service. The supported production
shape is one local origin: FastAPI serves both the compiled Vue files and `/api/v1`. The project does
not publish or support native desktop application bundles.

From a source checkout, install the backend once and build the pinned frontend dependencies:

```bash
make backend-install
make web-build
```

Start the production Web service:

```bash
make web-run
```

Then open `http://127.0.0.1:8765/`. Stop it with `Ctrl+C` in the launching terminal. The equivalent
explicit command is:

```bash
backend/.venv/bin/wmrm-web --frontend-dir frontend/dist
```

`wmrm-web --help` documents overrides for the frontend build, port and data directory. The
`WMRM_FRONTEND_DIR`, `WMRM_PORT` and `WMRM_DATA_DIR` environment variables are also supported. The
production entry point rejects non-loopback `WMRM_HOST` values, disables development CORS, verifies
that `index.html` and the asset directory exist, provides SPA history fallback and applies same-origin
CSP, frame, referrer and content-type protections.

The optional local Florence-2 photo suggestion path remains disabled unless
`WMRM_VLM_ENABLED=true`, `WMRM_VLM_MODEL_DIR` and `WMRM_VLM_MODEL_MANIFEST` are all set by the
local operator. It never downloads model files during Web requests. See
[`VLM_LOCALIZATION.md`](VLM_LOCALIZATION.md) for the reviewed model setup and manual-review contract.

The frontend contains no server shutdown action. Service lifecycle remains under the terminal or
process supervisor that launched FastAPI. Uploaded files, the SQLite database and generated outputs
remain in the configured local data directory.

## Release bundle

Release maintainers can combine an audited wheel, source distribution and compiled Vue build into a
reproducible Web archive:

```bash
python packaging/build_web_bundle.py \
  --version 0.1.0 \
  --wheel work/release/wmrm-0.1.0-py3-none-any.whl \
  --sdist work/release/wmrm-0.1.0.tar.gz \
  --frontend-dir frontend/dist \
  --source-date-epoch "$(git show -s --format=%ct HEAD)" \
  --output work/release/remove-watermark-web-0.1.0.tar.gz
```

The archive uses normalized ownership, modes and timestamps, rejects symlinks, contains the project
license and an internal `SHA256SUMS`, and includes startup instructions for Unix and Windows.

Verify the archive before extracting it. Supplying the published SHA-256 binds the check to the
downloaded release asset as well as its internal manifest:

```bash
python packaging/verify_web_bundle.py \
  --bundle work/release/remove-watermark-web-0.1.0.tar.gz \
  --version 0.1.0 \
  --expected-sha256 PUBLISHED_64_CHARACTER_SHA256 \
  --extract-to work/release/extracted \
  --report-json work/release/web-bundle-verification.json
```

The verifier rejects duplicate or escaping paths, links and special files, unexpected ownership,
permissions or timestamps, missing runtime files, unlisted payloads and checksum mismatches. Release
readiness CI independently builds the archive twice, requires byte-for-byte reproducibility, safely
extracts it, installs the bundled wheel in a clean environment, and starts the extracted Vue/FastAPI
service before publishing the archive as a workflow artifact.
