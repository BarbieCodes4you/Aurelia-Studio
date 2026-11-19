"""Runtime configuration.

Every secret and integration setting comes from environment variables (or a local `.env`
file next to run.py). Nothing secret is hard-coded. See `.env.example` for the full list.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # aurelia/
APP_DIR = ROOT / "app"
STATIC_DIR = ROOT / "static"


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=value lines, # comments, optional quotes. Real env wins."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(ROOT / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


DATA_DIR = Path(env("AURELIA_DATA_DIR", str(ROOT / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
OUTBOX_DIR = DATA_DIR / "outbox"
REPORT_DIR = DATA_DIR / "reports"
for _d in (UPLOAD_DIR, OUTBOX_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _secret_key() -> str:
    """SECRET_KEY from env; otherwise a random key, created once and kept in the data folder (on Railway,
    the /data volume), so sign-ins survive restarts and updates."""
    key = env("SECRET_KEY")
    if key:
        return key
    f = DATA_DIR / ".secret_key"
    if f.is_file():
        return f.read_text().strip()
    key = secrets.token_hex(32)
    f.write_text(key)
    try:
        f.chmod(0o600)
    except OSError:
        pass
    return key


# --- Brand ------------------------------------------------------------------------------
BRAND_NAME = env("BRAND_NAME", "Aurelia Studio")
BRAND_TAGLINE = env("BRAND_TAGLINE", "Affordable luxury. Everything for your event in one place.")
BRAND_LINE = "One event. One platform. One link. Everything organised."
SUPPORT_EMAIL = env("SUPPORT_EMAIL", "invitesaurelia@gmail.com")
COMPANY_ADDRESS = env("COMPANY_ADDRESS", "Johannesburg, South Africa")  # [TBC]
INFORMATION_OFFICER = env("INFORMATION_OFFICER_EMAIL", SUPPORT_EMAIL)   # POPIA contact
# Support on WhatsApp: set a number (e.g. 082 123 4567) to show a chat button on every page. Empty hides it.
WHATSAPP_NUMBER = env("WHATSAPP_NUMBER", "")
# Footer social links: full web addresses. Each one shows only when it is set.
SOCIAL_INSTAGRAM = env("SOCIAL_INSTAGRAM", "")
SOCIAL_FACEBOOK = env("SOCIAL_FACEBOOK", "")
SOCIAL_TIKTOK = env("SOCIAL_TIKTOK", "")


def whatsapp_link(text: str = "") -> str:
    """wa.me link to the support number (South African 0XX numbers become 27XX), or "" when none is set."""
    import re
    from urllib.parse import quote
    d = re.sub(r"\D", "", WHATSAPP_NUMBER)
    if d.startswith("0") and len(d) == 10:
        d = "27" + d[1:]
    if not d:
        return ""
    return f"https://wa.me/{d}" + (f"?text={quote(text)}" if text else "")
CURRENCY = "ZAR"
TIMEZONE = env("TIMEZONE", "Africa/Johannesburg")

# --- Server -----------------------------------------------------------------------------
APP_ENV = env("APP_ENV", "development")            # development | production
DEBUG = APP_ENV != "production"
# On Railway the web address and the proxy in front of the app are known, so they need no settings:
# BASE_URL falls back to the domain Railway generated (set BASE_URL once your own domain is connected).
ON_RAILWAY = any(env(k) for k in ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID"))
_RAILWAY_URL = f"https://{env('RAILWAY_PUBLIC_DOMAIN')}" if env("RAILWAY_PUBLIC_DOMAIN") else ""
BASE_URL = env("BASE_URL", _RAILWAY_URL or "http://127.0.0.1:8040").rstrip("/")
SECRET_KEY = _secret_key()
DATABASE_PATH = Path(env("DATABASE_PATH", str(DATA_DIR / "aurelia.sqlite3")))
SESSION_DAYS = env_int("SESSION_DAYS", 14)
MAX_BODY_BYTES = env_int("MAX_BODY_BYTES", 25 * 1024 * 1024)
MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 6 * 1024 * 1024)
SECURE_COOKIES = env_bool("SECURE_COOKIES", BASE_URL.startswith("https://"))
# Only trust X-Forwarded-For when a reverse proxy you control (Caddy, Nginx, the host's router) sets it.
# Railway always runs one in front of the app. The address that proxy adds (the last one) is used.
TRUST_PROXY = env_bool("TRUST_PROXY", ON_RAILWAY)

# --- Email ------------------------------------------------------------------------------
# EMAIL_PROVIDER: "outbox" (development: writes HTML files to data/outbox, nothing is sent),
# "resend" (needs RESEND_API_KEY) or "smtp" (needs SMTP_HOST etc.)
EMAIL_PROVIDER = env("EMAIL_PROVIDER", "outbox")
EMAIL_FROM = env("EMAIL_FROM", f"{BRAND_NAME} <no-reply@aurelia.example>")
EMAIL_REPLY_TO = env("EMAIL_REPLY_TO", SUPPORT_EMAIL)
RESEND_API_KEY = env("RESEND_API_KEY")
SMTP_HOST = env("SMTP_HOST")
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = env("SMTP_USER")
SMTP_PASSWORD = env("SMTP_PASSWORD")
SMTP_STARTTLS = env_bool("SMTP_STARTTLS", True)

# --- Payments ---------------------------------------------------------------------------
# PAYMENT_GATEWAY: "sandbox" (built-in test checkout, no money moves) or "payfast"
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "sandbox")
PAYFAST_MERCHANT_ID = env("PAYFAST_MERCHANT_ID")
PAYFAST_MERCHANT_KEY = env("PAYFAST_MERCHANT_KEY")
PAYFAST_PASSPHRASE = env("PAYFAST_PASSPHRASE")
PAYFAST_SANDBOX = env_bool("PAYFAST_SANDBOX", True)
# The built-in test checkout publishes events without real payment, so production refuses it
# unless this is set (use only on a private staging/demo copy).
ALLOW_SANDBOX_PAYMENTS = env_bool("ALLOW_SANDBOX_PAYMENTS", DEBUG)
VAT_RATE = float(env("VAT_RATE", "0.15"))
VAT_NUMBER = env("VAT_NUMBER", "")                 # [TBC] shown on receipts when set
# Only a VAT-registered business may charge VAT or issue tax invoices (SARS). Until VAT_NUMBER is set,
# prices and receipts say nothing about VAT and receipts are plain receipts, not tax invoices.
VAT_REGISTERED = bool(VAT_NUMBER)

# --- Background jobs --------------------------------------------------------------------
SCHEDULER_ENABLED = env_bool("SCHEDULER_ENABLED", True)
SCHEDULER_INTERVAL_SECONDS = env_int("SCHEDULER_INTERVAL_SECONDS", 300)

# --- Bootstrap admin (created on first run if no admin exists) --------------------------
ADMIN_EMAIL = env("ADMIN_EMAIL", "")
ADMIN_PASSWORD = env("ADMIN_PASSWORD", "")
