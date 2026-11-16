"""Passwords, sessions, CSRF, one-time tokens, rate limiting and access checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config, db
from .web import HTTPError, Redirect, url

SESSION_COOKIE = "aur_sid"
CSRF_COOKIE = "aur_csrf"
FLASH_COOKIE = "aur_flash"
PBKDF2_ITERATIONS = 310_000


# --- passwords ----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


def password_problems(password: str, email: str = "") -> list[str]:
    problems = []
    if len(password) < 10:
        problems.append("Use at least 10 characters.")
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        problems.append("Mix upper- and lower-case letters and at least one number.")
    if email and email.split("@")[0].lower() in password.lower() and len(email.split("@")[0]) > 3:
        problems.append("Don't include your email name in the password.")
    return problems


# --- signing ------------------------------------------------------------------------------
def sign(value: str, purpose: str) -> str:
    mac = hmac.new(config.SECRET_KEY.encode(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{value}.{mac}"


def unsign(signed: str, purpose: str) -> Optional[str]:
    value, _, mac = (signed or "").rpartition(".")
    if not value:
        return None
    expected = sign(value, purpose).rpartition(".")[2]
    return value if hmac.compare_digest(mac, expected) else None


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- sessions -----------------------------------------------------------------------------
def create_session(user_id: int, ip: str = "", ua: str = "") -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)
    db.insert("sessions", {
        "id": _sha(token), "user_id": user_id, "csrf": secrets.token_hex(16), "data": "{}",
        "ip": ip[:64], "user_agent": ua[:250], "created_at": db.now(),
        "expires_at": expires.replace(microsecond=0).isoformat(),
    })
    db.run("UPDATE users SET last_login_at = ? WHERE id = ?", (db.now(), user_id))
    return token


def load_user(token: str):
    if not token:
        return None
    row = db.one("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                    WHERE s.id = ? AND s.expires_at > ?""", (_sha(token), db.now()))
    if row is None or row["status"] != "active":
        return None
    return row


def destroy_session(token: str) -> None:
    if token:
        db.run("DELETE FROM sessions WHERE id = ?", (_sha(token),))


def destroy_user_sessions(user_id: int) -> None:
    db.run("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# --- flash messages (signed cookie) -------------------------------------------------------
def encode_flash(items: list) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(items).encode()).decode().rstrip("=")
    return sign(raw, "flash")


def decode_flash(cookie: str) -> list:
    raw = unsign(cookie, "flash")
    if not raw:
        return []
    try:
        return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        return []


# --- one-time tokens (email verification, password reset) --------------------------------
def issue_token(user_id: int, kind: str, hours: int) -> str:
    token = secrets.token_urlsafe(32)
    db.run("UPDATE user_tokens SET used_at = ? WHERE user_id = ? AND kind = ? AND used_at IS NULL",
           (db.now(), user_id, kind))
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    db.insert("user_tokens", {"user_id": user_id, "kind": kind, "token_hash": _sha(token),
                              "expires_at": expires.replace(microsecond=0).isoformat(), "created_at": db.now()})
    return token


def consume_token(token: str, kind: str) -> Optional[int]:
    row = db.one("SELECT * FROM user_tokens WHERE token_hash = ? AND kind = ?", (_sha(token or ""), kind))
    if not row or row["used_at"] or row["expires_at"] < db.now():
        return None
    db.run("UPDATE user_tokens SET used_at = ? WHERE id = ?", (db.now(), row["id"]))
    return row["user_id"]


def peek_token(token: str, kind: str) -> Optional[int]:
    row = db.one("SELECT * FROM user_tokens WHERE token_hash = ? AND kind = ?", (_sha(token or ""), kind))
    if not row or row["used_at"] or row["expires_at"] < db.now():
        return None
    return row["user_id"]


# --- rate limiting (in memory, per process) ----------------------------------------------
_hits: dict[str, list[float]] = {}
_hits_lock = threading.Lock()


def rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    """Record a hit for `key`; True when the key has gone over `limit` in the window."""
    now = time.time()
    with _hits_lock:
        bucket = [t for t in _hits.get(key, []) if now - t < window_seconds]
        bucket.append(now)
        _hits[key] = bucket
        return len(bucket) > limit


def reset_rate(key: str) -> None:
    with _hits_lock:
        _hits.pop(key, None)


# --- access checks ------------------------------------------------------------------------
def require_user(req):
    if req.user is None:
        raise Redirect(url("/login", next=req.full_path))
    return req.user


def require_admin(req):
    user = require_user(req)
    if user["role"] != "admin":
        raise HTTPError(403, "This area is for platform administrators.")
    return user


def can_manage_event(user, event) -> bool:
    if user is None or event is None:
        return False
    if user["role"] == "admin" or event["owner_id"] == user["id"]:
        return True
    return db.one("SELECT 1 FROM event_admins WHERE event_id = ? AND user_id = ?",
                  (event["id"], user["id"])) is not None


def event_for(req, uid: str):
    """Load an event the signed-in user may manage, or 404 (never reveal other events)."""
    user = require_user(req)
    event = db.one("SELECT * FROM events WHERE uid = ?", (uid,))
    if not can_manage_event(user, event):
        raise HTTPError(404)
    return event


def audit(actor_id, action: str, target: str = "", **meta) -> None:
    db.insert("audit_log", {"actor_id": actor_id, "action": action, "target": target,
                            "meta": db.dumps(meta), "created_at": db.now()})
