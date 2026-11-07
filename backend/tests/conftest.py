import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))


@pytest.fixture(scope="session")
def tmp_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("shotsense")
    model_dir = root / "model"
    import make_dummy_model
    make_dummy_model.build(model_dir)
    os.environ["DATABASE_URL"] = f"sqlite:///{root / 'test.db'}"
    os.environ["MODEL_DIR"] = str(model_dir)
    os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes"
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["GUEST_MAX_ANALYSES"] = "2"
    os.environ["MAX_VIDEO_SECONDS"] = "60"
    return root


@pytest.fixture(scope="session")
def client(tmp_env):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def token(client):
    r = client.post("/api/auth/register", json={"email": "Tester@Example.com", "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}
