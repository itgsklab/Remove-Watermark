from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wmrm.api.app import create_app
from wmrm.settings import Settings


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            max_upload_bytes=1024 * 1024,
            docx_preview_enabled=False,
            pdf_preview_enabled=False,
            worker_start_method="forkserver",
        )
    )
    with TestClient(app) as test_client:
        yield test_client
