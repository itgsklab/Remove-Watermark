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

The frontend contains no server shutdown action. Service lifecycle remains under the terminal or
process supervisor that launched FastAPI. Uploaded files, the SQLite database and generated outputs
remain in the configured local data directory.
