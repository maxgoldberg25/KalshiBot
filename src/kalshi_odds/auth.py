"""
Lightweight auth: PBKDF2-SHA256 password hashing + opaque session tokens.

No extra dependencies — uses only the Python stdlib (`hashlib`, `hmac`, `secrets`).
Sessions live in the configured database (SQLite or Postgres) and are sent to the browser via
an HTTP-only cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Optional

from fastapi import Cookie, Depends, HTTPException, Request, Response, status

from kalshi_odds.db import AnyRepository

SESSION_COOKIE_NAME = "kb_session"
SESSION_TTL_DAYS = 14
PBKDF2_ITERATIONS = 240_000

IP_HASH_SECRET = os.environ.get(
    "KALSHI_ODDS_IP_HASH_SECRET",
    "kalshi-bot-default-ip-salt-change-me-in-prod",
)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be 3-32 chars: letters, numbers, '.', '_' or '-'.",
        )
    return username


def validate_email(email: Optional[str]) -> Optional[str]:
    if email is None:
        return None
    email = email.strip().lower()
    if not email:
        return None
    if not _EMAIL_RE.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address."
        )
    return email


def validate_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )
    if len(password) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password too long."
        )
    return password


def hash_password(password: str) -> tuple[str, str]:
    """Return (salt_hex, hash_hex) using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return salt.hex(), derived.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(derived, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)


def set_session_cookie(
    response: Response,
    token: str,
    *,
    secure: bool = False,
    samesite: str = "lax",
) -> None:
    ss = (samesite or "lax").lower()
    if ss not in {"lax", "strict", "none"}:
        ss = "lax"
    # SameSite=None requires Secure to be accepted by modern browsers.
    if ss == "none" and not secure:
        ss = "lax"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        samesite=ss,
        secure=secure,
        path="/",
    )


def clear_session_cookie(
    response: Response, *, secure: bool = False, samesite: str = "lax"
) -> None:
    ss = (samesite or "lax").lower()
    if ss not in {"lax", "strict", "none"}:
        ss = "lax"
    if ss == "none" and not secure:
        ss = "lax"
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=ss,
        secure=secure,
    )


def hash_ip(ip: str) -> str:
    """Hash a client IP with an HMAC secret so we never store raw IPs."""
    return hmac.new(
        IP_HASH_SECRET.encode("utf-8"), (ip or "").encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def client_ip(request: Request) -> str:
    """Best-effort client IP extraction; only trusts the first X-Forwarded-For hop."""
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return (request.client.host if request.client else "") or "0.0.0.0"


class _RateLimiter:
    """Simple in-process sliding-window limiter. Single-worker deployments only."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self._max = max_events
        self._window = window_seconds
        self._events: dict[str, Deque[float]] = {}

    def check(self, key: str) -> bool:
        now = time.monotonic()
        dq = self._events.setdefault(key, deque())
        while dq and (now - dq[0]) > self._window:
            dq.popleft()
        if len(dq) >= self._max:
            return False
        dq.append(now)
        return True


# Module-level limiters keyed by route + ip.
LOGIN_LIMITER = _RateLimiter(max_events=10, window_seconds=60.0)
REGISTER_LIMITER = _RateLimiter(max_events=5, window_seconds=300.0)
WAITLIST_LIMITER = _RateLimiter(max_events=5, window_seconds=3600.0)


def rate_limit_or_raise(limiter: _RateLimiter, *, key: str) -> None:
    if not limiter.check(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
        )


class AuthDeps:
    """Holds a reference to the persistent DB repository so request deps can access it."""

    def __init__(self) -> None:
        self._repo: Optional[AnyRepository] = None

    def bind(self, repo: AnyRepository) -> None:
        self._repo = repo

    def unbind(self) -> None:
        self._repo = None

    @property
    def repo(self) -> AnyRepository:
        if self._repo is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth database is not ready yet.",
            )
        return self._repo


auth_deps = AuthDeps()


async def get_optional_user(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Optional[dict]:
    _ = request
    if not session_token:
        return None
    return await auth_deps.repo.get_session_user(session_token)


async def require_user(
    user: Optional[dict] = Depends(get_optional_user),
) -> dict:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


async def require_admin(
    user: dict = Depends(require_user),
) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
