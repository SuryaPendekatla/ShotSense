import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..config import get_settings
from ..db import get_db
from ..models import Analysis, GuestSession, User
from ..schemas import Credentials, GuestToken, Token, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

GUEST_DOMAIN = "guest.shotsense.app"
DEMO_COOKIE = "ss_demo_used"
DEMO_USED = "You've already used the free demo. Create a free account to keep using ShotSense."


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return user


def client_ip(request: Request) -> str:
    """Best-effort visitor IP behind Render's proxy. A deterrent, not a security boundary."""
    for header in ("cf-connecting-ip", "true-client-ip"):
        if value := request.headers.get(header):
            return value.strip()
    if forwarded := request.headers.get("x-forwarded-for"):
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ip_hash(ip: str) -> str:
    """Store a keyed hash, never the raw IP address."""
    return hmac.new(get_settings().secret_key.encode(), ip.encode(), hashlib.sha256).hexdigest()


def cleanup_guests(db: Session) -> None:
    """Delete expired guests' uploads, and guest accounts older than the IP window."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expired = select(GuestSession.user_id).where(GuestSession.expires_at <= now)
    for analysis in db.scalars(select(Analysis).where(Analysis.user_id.in_(expired))):
        db.delete(analysis)
    stale = now - timedelta(hours=settings.guest_ip_window_hours)
    for user in db.scalars(select(User).join(GuestSession).where(GuestSession.created_at < stale)):
        db.delete(user)
    db.commit()


def user_out(user: User) -> UserOut:
    out = UserOut(id=user.id, email=user.email, created_at=user.created_at)
    if user.guest is not None:
        out.is_guest = True
        out.guest_expires_at = user.guest.expires_at
        out.guest_analyses_left = max(0, get_settings().guest_max_analyses - user.guest.analyses_used)
    return out


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, db: Session = Depends(get_db)) -> Token:
    email = body.email.lower()
    if email.endswith("@" + GUEST_DOMAIN):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use your own email address")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
def login(body: Credentials, db: Session = Depends(get_db)) -> Token:
    user = _authenticate(db, body.email, body.password)
    return Token(access_token=create_access_token(user.id))


@router.post("/guest", response_model=GuestToken, status_code=status.HTTP_201_CREATED)
def start_guest(request: Request, response: Response, db: Session = Depends(get_db)) -> GuestToken:
    """Start a one-time demo: a private, temporary account with a small quota."""
    settings = get_settings()
    if not settings.guest_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The demo is turned off")
    cleanup_guests(db)
    if request.cookies.get(DEMO_COOKIE):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, DEMO_USED)

    now = datetime.now(timezone.utc)
    hashed = ip_hash(client_ip(request))
    since = now - timedelta(hours=settings.guest_ip_window_hours)
    used = db.scalar(select(func.count()).select_from(GuestSession)
                     .where(GuestSession.ip_hash == hashed, GuestSession.created_at >= since))
    if used >= settings.guest_per_ip:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, DEMO_USED)

    expires = now + timedelta(hours=settings.guest_session_hours)
    user = User(email=f"guest-{secrets.token_hex(6)}@{GUEST_DOMAIN}", password_hash="!guest")
    user.guest = GuestSession(ip_hash=hashed, expires_at=expires)
    db.add(user)
    db.commit()

    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(DEMO_COOKIE, "1", max_age=settings.guest_ip_window_hours * 3600,
                        httponly=True, samesite="lax", secure=https)
    return GuestToken(access_token=create_access_token(user.id, expires), expires_at=expires,
                      max_analyses=settings.guest_max_analyses)


@router.post("/token", response_model=Token, include_in_schema=True)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    """OAuth2 password flow, used by the interactive API docs' Authorize button."""
    user = _authenticate(db, form.username, form.password)
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)
