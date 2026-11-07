import json

import numpy as np
from PIL import Image

from synthetic import CUTS, make_png, make_video


def test_health_and_model(client):
    assert client.get("/api/health").json() == {"status": "ok", "model_loaded": True}
    info = client.get("/api/model").json()
    assert info["loaded"] and info["dummy"]
    assert [lab["abbr"] for lab in info["labels"]] == ["ECU", "CU", "MCU", "MS", "FS", "LS", "ELS"]


def test_public_config(client):
    cfg = client.get("/api/config").json()
    assert cfg["guest_enabled"] and cfg["guest_max_analyses"] == 2 and cfg["llm_enabled"] is False
    assert "demo_password" not in cfg


def test_auth_flow(client, token, auth):
    assert client.get("/api/auth/me", headers=auth).json()["email"] == "tester@example.com"
    dup = client.post("/api/auth/register", json={"email": "tester@example.com", "password": "password123"})
    assert dup.status_code == 409
    bad = client.post("/api/auth/login", json={"email": "tester@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    short = client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"})
    assert short.status_code == 422
    form = client.post("/api/auth/token", data={"username": "tester@example.com", "password": "password123"})
    assert form.status_code == 200


def test_requires_auth(client):
    assert client.get("/api/analyses").status_code == 401
    assert client.get("/api/analyses", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_image_analysis(client, auth):
    r = client.post("/api/analyses", headers=auth, data={"title": "Still", "notes": "a lone astronaut"},
                    files={"file": ("frame.png", make_png(), "image/png")})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["source_type"] == "image" and a["shot_count"] == 1 and a["width"] == 1280
    shot = a["shots"][0]
    assert len(shot["top3"]) == 3 and shot["thumbnail"].startswith("data:image/jpeg;base64,")
    assert a["breakdown_source"] == "template" and "a lone astronaut" in shot["prompt"]


def test_video_analysis_and_history(client, auth, tmp_path):
    path = tmp_path / "clip.mp4"
    make_video(str(path))
    with open(path, "rb") as fh:
        r = client.post("/api/analyses", headers=auth, files={"file": ("clip.mp4", fh, "video/mp4")})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["source_type"] == "video" and a["shot_count"] == 4, [(s["start_sec"], s["end_sec"]) for s in a["shots"]]
    starts = [s["start_sec"] for s in a["shots"][1:]]
    assert all(abs(s - c) <= 0.25 for s, c in zip(starts, CUTS)), starts
    assert abs(a["duration_sec"] - 12) < 0.5
    assert a["summary"].startswith("4 shots covering")

    listing = client.get("/api/analyses", headers=auth).json()
    assert listing[0]["id"] == a["id"] and listing[0]["cover"] and sum(listing[0]["label_counts"].values()) == 4
    assert client.get(f"/api/analyses/{a['id']}", headers=auth).json()["shot_count"] == 4

    other = client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123"}).json()
    other_auth = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/api/analyses/{a['id']}", headers=other_auth).status_code == 404
    assert client.delete(f"/api/analyses/{a['id']}", headers=other_auth).status_code == 404

    assert client.delete(f"/api/analyses/{a['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/analyses/{a['id']}", headers=auth).status_code == 404


def test_bad_uploads(client, auth):
    r = client.post("/api/analyses", headers=auth, files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post("/api/analyses", headers=auth, files={"file": ("empty.mp4", b"", "video/mp4")})
    assert r.status_code == 400
    r = client.post("/api/analyses", headers=auth, files={"file": ("broken.mp4", b"not a video" * 100, "video/mp4")})
    assert r.status_code == 422
    r = client.post("/api/analyses", headers=auth, files={"file": ("broken.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422


def test_llm_breakdown_is_merged(monkeypatch):
    from app.config import Settings
    from app.services import llm

    shots = [llm.ShotFacts(1, 0.0, 2.0, "closeUp", 0.9, "data:image/jpeg;base64,AAAA"),
             llm.ShotFacts(2, 2.0, 5.0, "longShot", 0.8, "data:image/jpeg;base64,AAAA")]
    reply = "```json\n" + json.dumps({
        "summary": "Moody and intimate.", "pacing": "Quick then slower.",
        "shots": [{"index": 1, "description": "A face in the rain.", "prompt": "Close-up of a face in rain, 85mm."}],
    }) + "\n```"
    monkeypatch.setattr(llm, "_call_anthropic", lambda *a, **k: reply)
    out = llm.build_breakdown(Settings(anthropic_api_key="test"), shots, "noir")
    assert out.source == "anthropic"
    assert out.prompts[1] == "Close-up of a face in rain, 85mm."
    assert out.prompts[2].startswith("Long Shot with the same subject") and "Project style: noir." in out.prompts[2]  # missing shot falls back to the template
    assert "Moody and intimate." in out.summary and out.pacing == "Quick then slower."

    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(llm, "_call_anthropic", boom)
    assert llm.build_breakdown(Settings(anthropic_api_key="test"), shots).source == "template"


def test_letterbox_keeps_framing():
    from app.services.preprocess import INPUT_H, INPUT_W, letterbox, to_tensor

    wide = Image.new("RGB", (2390, 1000), (255, 255, 255))
    boxed = np.asarray(letterbox(wide))
    assert boxed.shape == (INPUT_H, INPUT_W, 3)
    assert boxed[0].max() == 0 and boxed[INPUT_H // 2].min() == 255  # black bars top, picture in the middle
    assert to_tensor(wide).shape == (3, INPUT_H, INPUT_W)
