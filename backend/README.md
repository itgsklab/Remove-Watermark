# Backend

Python/FastAPI local service for Watermark Remover.

Install the development dependencies and start the API locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
wmrm-api
```

The service listens on `127.0.0.1:8765` by default. OpenAPI documentation is available at `/docs`
while it is running.
