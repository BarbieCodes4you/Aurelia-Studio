"""Request dispatch: sessions, CSRF, flash messages, error pages, security headers."""
from __future__ import annotations

import hmac
import secrets
import sys
import traceback

from . import auth, config, db
from .web import (SECURITY_HEADERS, HTTPError, Redirect, Request, Response, json_response, router,
                  serve_file)


def _load_views() -> None:
    # Importing a views module registers its routes on the shared router.
    from .views import (accounts, admin, dashboard, marketing, media, payments_views,  # noqa: F401
                        public_event, wizard, manage)


class App:
    def __init__(self):
        _load_views()

    def handle(self, method: str, target: str, headers: dict, body: bytes = b"", ip: str = ""):
        req = Request(method, target, headers, body, ip)
        req.flash_out = None            # list to write back, or None for "unchanged"
        req.flash_in = auth.decode_flash(req.cookies.get(auth.FLASH_COOKIE, ""))
        req.flash = lambda kind, msg: _add_flash(req, kind, msg)
        req.take_flashes = lambda: _take_flashes(req)
        req.new_csrf = None
        token = req.cookies.get(auth.CSRF_COOKIE, "")
        if len(token) != 32:
            token = secrets.token_hex(16)
            req.new_csrf = token
        req.csrf = token
        try:
            resp = self._dispatch(req)
        except Redirect as r:
            resp = Response(b"", status=r.status, content_type="")
            resp.header("Location", r.location)
        except HTTPError as e:
            resp = self._error(req, e.status, e.message)
        except Exception:  # pragma: no cover - logged and shown as a 500 page
            traceback.print_exc(file=sys.stderr)
            resp = self._error(req, 500, "Something went wrong on our side. Please try again.")
        for name, value in SECURITY_HEADERS:
            resp.header(name, value)
        if not any(h[0].lower() == "x-frame-options" for h in resp.headers):
            resp.header("X-Frame-Options", "SAMEORIGIN")
        if req.new_csrf:
            resp.set_cookie(auth.CSRF_COOKIE, req.new_csrf, max_age=60 * 60 * 24 * 30)
        if req.flash_out is not None:
            if req.flash_out:
                resp.set_cookie(auth.FLASH_COOKIE, auth.encode_flash(req.flash_out), max_age=300)
            else:
                resp.set_cookie(auth.FLASH_COOKIE, "", max_age=0)
        if method.upper() == "HEAD":
            resp.body = b""
        return resp

    def _dispatch(self, req: Request) -> Response:
        if req.path.startswith("/static/"):
            cache = "no-cache" if config.DEBUG else "public, max-age=86400"
            return serve_file(config.STATIC_DIR, req.path[len("/static/"):], cache)
        if req.path in ("/favicon.ico", "/favicon.svg"):
            return serve_file(config.STATIC_DIR, "img/favicon.svg")
        req.user = auth.load_user(req.cookies.get(auth.SESSION_COOKIE, ""))
        route, params = router.match(req.method, req.path)
        if route is None:
            if params == "405":
                raise HTTPError(405)
            # tolerate a trailing slash
            if req.path.endswith("/") and len(req.path) > 1:
                alt, _ = router.match(req.method, req.path.rstrip("/"))
                if alt is not None:
                    raise Redirect(req.path.rstrip("/") + (("?" + req.query_string) if req.query_string else ""), 301)
            raise HTTPError(404)
        if req.method == "POST" and route.csrf:
            sent = req.get("_csrf") or req.headers.get("x-csrf-token", "")
            if not sent or not hmac.compare_digest(sent, req.csrf):
                raise HTTPError(403, "Your form expired. Go back, refresh the page and try again.")
        req.params = params
        result = route.handler(req, **params)
        if isinstance(result, Response):
            return result
        if isinstance(result, (dict, list)):
            return json_response(result)
        return Response(result or "")

    def _error(self, req: Request, status: int, message: str) -> Response:
        if req.wants_json or req.path.startswith("/api/"):
            return json_response({"ok": False, "error": message}, status=status)
        from .views.layout import error_page
        try:
            return Response(error_page(req, status, message), status=status)
        except Exception:  # pragma: no cover
            traceback.print_exc(file=sys.stderr)
            return Response(f"<h1>{status}</h1><p>{message}</p>", status=status)


def _add_flash(req, kind: str, msg: str) -> None:
    if req.flash_out is None:
        req.flash_out = []
    req.flash_out.append([kind, msg])


def _take_flashes(req) -> list:
    items = list(req.flash_in) + list(req.flash_out or [])
    req.flash_in = []
    req.flash_out = []          # clears the cookie on this response
    return items


def bootstrap() -> None:
    """Create tables, seed catalogue rows and the first admin (from env) if missing."""
    db.migrate()
    from . import catalog
    catalog.ensure_catalog()
    from .services import email as email_service
    email_service.ensure_templates()
    if config.ADMIN_EMAIL and config.ADMIN_PASSWORD:
        if not db.one("SELECT 1 FROM users WHERE email = ?", (config.ADMIN_EMAIL,)):
            db.insert("users", {"email": config.ADMIN_EMAIL, "name": "Platform admin",
                                "password_hash": auth.hash_password(config.ADMIN_PASSWORD),
                                "role": "admin", "email_verified_at": db.now(), "created_at": db.now()})
