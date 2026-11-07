"""One-time demo accounts: private, limited, and not reusable by the same visitor."""
from datetime import datetime, timedelta, timezone

from synthetic import make_png


def _guest(client, ip):
    client.cookies.clear()
    return client.post("/api/auth/guest", headers={"X-Forwarded-For": f"{ip}, 10.0.0.1"})


def _upload(client, auth):
    return client.post("/api/analyses", headers=auth, files={"file": ("f.png", make_png(), "image/png")})


def test_guest_is_one_time_per_browser_and_ip(client):
    first = _guest(client, "203.0.113.7")
    assert first.status_code == 201, first.text
    assert "ss_demo_used" in first.cookies
    assert first.json()["max_analyses"] == 2

    # Same browser (cookie still set) is refused...
    again = client.post("/api/auth/guest", headers={"X-Forwarded-For": "198.51.100.1"})
    assert again.status_code == 429 and "already used" in again.json()["detail"]
    # ...and so is the same connection from a private window (no cookie).
    assert _guest(client, "203.0.113.7").status_code == 429
    # A different visitor still gets a demo.
    assert _guest(client, "203.0.113.99").status_code == 201
    client.cookies.clear()


def test_guest_quota_privacy_and_expiry(client, auth):
    data = _guest(client, "192.0.2.10").json()
    guest = {"Authorization": f"Bearer {data['access_token']}"}
    me = client.get("/api/auth/me", headers=guest).json()
    assert me["is_guest"] and me["guest_analyses_left"] == 2 and me["email"].endswith("@guest.shotsense.app")

    assert _upload(client, guest).status_code == 201
    assert _upload(client, guest).status_code == 201
    third = _upload(client, guest)
    assert third.status_code == 403 and "used them all" in third.json()["detail"]
    assert client.get("/api/auth/me", headers=guest).json()["guest_analyses_left"] == 0

    # Guests only see their own work; regular users never see guests' uploads.
    guest_ids = {a["id"] for a in client.get("/api/analyses", headers=guest).json()}
    assert len(guest_ids) == 2
    assert not guest_ids & {a["id"] for a in client.get("/api/analyses", headers=auth).json()}

    # Expire the demo: the token stops working and cleanup removes the uploads.
    from app.db import SessionLocal
    from app.models import Analysis, GuestSession, User
    from app.routers.auth import cleanup_guests
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == me["email"]).one()
        user.guest.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        expired = client.get("/api/auth/me", headers=guest)
        assert expired.status_code == 401 and "demo has ended" in expired.json()["detail"]
        cleanup_guests(db)
        assert db.query(Analysis).filter(Analysis.user_id == user.id).count() == 0
        assert db.query(GuestSession).filter(GuestSession.user_id == user.id).count() == 1  # IP limit remembered
    client.cookies.clear()


def test_guest_domain_cannot_be_registered(client):
    r = client.post("/api/auth/register", json={"email": "guest-abc@guest.shotsense.app", "password": "password123"})
    assert r.status_code == 422
