"""A small WSGI-free web layer on the standard library.

`App.handle(method, path, headers, body, ip)` turns a raw request into (status, headers, body)
so the same code serves http.server in run.py and the in-process test client in tests/.
"""
from __future__ import annotations

import email.parser
import email.policy
import html
import json
import mimetypes
import re
import traceback
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, quote, unquote, urlencode

from . import config


class HTTPError(Exception):
    def __init__(self, status: int, message: str = ""):
        super().__init__(message or HTTPStatus(status).phrase)
        self.status = status
        self.message = message or HTTPStatus(status).phrase


class Redirect(Exception):
    def __init__(self, location: str, status: int = 303):
        super().__init__(location)
        self.location = location
        self.status = status


class UploadedFile:
    def __init__(self, filename: str, content_type: str, data: bytes):
        self.filename = filename
        self.content_type = content_type
        self.data = data

    @property
    def size(self) -> int:
        return len(self.data)


class Request:
    def __init__(self, method: str, target: str, headers: dict, body: bytes, ip: str = ""):
        self.method = method.upper()
        path, _, query = target.partition("?")
        self.path = unquote(path) or "/"
        self.query_string = query
        self.query = {k: v for k, v in parse_qs(query, keep_blank_values=True).items()}
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = body
        self.ip = ip
        self.cookies = {}
        raw = self.headers.get("cookie", "")
        if raw:
            c = SimpleCookie()
            try:
                c.load(raw)
            except Exception:
                pass
            self.cookies = {k: m.value for k, m in c.items()}
        self.form: dict[str, list[str]] = {}
        self.files: dict[str, list[UploadedFile]] = {}
        self._json = None
        self._parse_body()
        # filled by middleware
        self.session: Optional[dict] = None
        self.user = None
        self.params: dict = {}

    # -- body parsing --------------------------------------------------------------
    def _parse_body(self) -> None:
        if not self.body:
            return
        ctype = self.headers.get("content-type", "")
        if ctype.startswith("application/x-www-form-urlencoded"):
            self.form = parse_qs(self.body.decode("utf-8", "replace"), keep_blank_values=True)
        elif ctype.startswith("multipart/form-data"):
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                b"Content-Type: " + ctype.encode("latin-1") + b"\r\n\r\n" + self.body)
            if msg.is_multipart():
                for part in msg.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    if not name:
                        continue
                    filename = part.get_filename()
                    payload = part.get_payload(decode=True) or b""
                    if filename is not None:
                        if payload:
                            self.files.setdefault(name, []).append(
                                UploadedFile(filename, part.get_content_type(), payload))
                    else:
                        charset = part.get_content_charset() or "utf-8"
                        self.form.setdefault(name, []).append(payload.decode(charset, "replace"))

    @property
    def json(self) -> Any:
        if self._json is None:
            try:
                self._json = json.loads(self.body.decode("utf-8") or "null")
            except ValueError:
                raise HTTPError(400, "Invalid JSON")
        return self._json

    # -- accessors -----------------------------------------------------------------
    def arg(self, key: str, default: str = "") -> str:
        v = self.query.get(key)
        return v[0] if v else default

    def get(self, key: str, default: str = "") -> str:
        """Form value, stripped."""
        v = self.form.get(key)
        return v[0].strip() if v else default

    def getlist(self, key: str) -> list[str]:
        return [x.strip() for x in self.form.get(key, [])]

    def has(self, key: str) -> bool:
        return key in self.form

    def file(self, key: str) -> Optional[UploadedFile]:
        f = self.files.get(key)
        return f[0] if f else None

    # Fields that always carry a value (hidden ids and drop-downs), so they don't make a row "filled in".
    ROW_DEFAULTS = frozenset({"id", "kind", "function", "course"})

    def rows(self, prefix: str, fields: list[str]) -> list[dict]:
        """Collect repeatable rows posted as prefix-<i>-<field>. Rows with nothing typed in are dropped."""
        idx = set()
        pat = re.compile(rf"^{re.escape(prefix)}-(\d+)-")
        for k in self.form:
            m = pat.match(k)
            if m:
                idx.add(int(m.group(1)))
        out = []
        for i in sorted(idx):
            row = {f: self.get(f"{prefix}-{i}-{f}") for f in fields}
            if any(v for k, v in row.items() if k not in self.ROW_DEFAULTS):
                out.append(row)
        return out

    @property
    def is_htmx(self) -> bool:
        return self.headers.get("x-requested-with") == "fetch"

    @property
    def wants_json(self) -> bool:
        return "application/json" in self.headers.get("accept", "")

    @property
    def full_path(self) -> str:
        return self.path + (("?" + self.query_string) if self.query_string else "")


class Response:
    def __init__(self, body: Any = b"", status: int = 200, content_type: str = "text/html; charset=utf-8",
                 headers: Optional[list] = None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body: bytes = body
        self.status = status
        self.headers: list[tuple[str, str]] = list(headers or [])
        if content_type:
            self.headers.append(("Content-Type", content_type))

    def header(self, name: str, value: str) -> "Response":
        self.headers.append((name, value))
        return self

    def set_cookie(self, name: str, value: str, max_age: Optional[int] = None, path: str = "/",
                   http_only: bool = True, same_site: str = "Lax") -> "Response":
        parts = [f"{name}={value}", f"Path={path}", f"SameSite={same_site}"]
        if max_age is not None:
            parts.append(f"Max-Age={max_age}")
        if http_only:
            parts.append("HttpOnly")
        if config.SECURE_COOKIES:
            parts.append("Secure")
        self.headers.append(("Set-Cookie", "; ".join(parts)))
        return self


def redirect(location: str, status: int = 303) -> Response:
    r = Response(b"", status=status, content_type="")
    r.header("Location", location)
    return r


def json_response(data: Any, status: int = 200) -> Response:
    return Response(json.dumps(data, ensure_ascii=False), status=status, content_type="application/json")


def download(data: bytes | str, filename: str, content_type: str) -> Response:
    if isinstance(data, str):
        data = data.encode("utf-8")
    r = Response(data, content_type=content_type)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename)
    r.header("Content-Disposition", f'attachment; filename="{safe}"')
    r.header("Cache-Control", "no-store")
    return r


# --- routing ------------------------------------------------------------------------------
Handler = Callable[..., Any]
_CONVERTERS = {"str": r"[^/]+", "int": r"\d+", "path": r".+", "slug": r"[a-z0-9][a-z0-9-]*"}


class Route:
    def __init__(self, methods: tuple, pattern: str, handler: Handler, csrf: bool, name: str):
        self.methods = methods
        self.handler = handler
        self.csrf = csrf
        self.name = name
        self.pattern = pattern
        regex = "^"
        self.casts = {}
        for part in re.split(r"(<[^>]+>)", pattern):
            if part.startswith("<") and part.endswith(">"):
                conv, _, key = part[1:-1].rpartition(":")
                conv = conv or "str"
                regex += f"(?P<{key}>{_CONVERTERS[conv]})"
                if conv == "int":
                    self.casts[key] = int
            else:
                regex += re.escape(part)
        self.regex = re.compile(regex + "$")


class Router:
    def __init__(self):
        self.routes: list[Route] = []

    def route(self, pattern: str, methods=("GET",), csrf: bool = True, name: str = ""):
        def deco(fn):
            self.routes.append(Route(tuple(m.upper() for m in methods), pattern, fn, csrf, name or fn.__name__))
            return fn
        return deco

    def get(self, pattern: str, **kw):
        return self.route(pattern, methods=("GET",), **kw)

    def post(self, pattern: str, **kw):
        return self.route(pattern, methods=("POST",), **kw)

    def match(self, method: str, path: str):
        allowed = False
        for r in self.routes:
            m = r.regex.match(path)
            if not m:
                continue
            if method in r.methods or (method == "HEAD" and "GET" in r.methods):
                params = {k: r.casts.get(k, str)(v) for k, v in m.groupdict().items()}
                return r, params
            allowed = True
        return None, ("405" if allowed else None)


router = Router()


# --- static files -------------------------------------------------------------------------
def serve_file(root: Path, rel: str, cache: str = "public, max-age=3600") -> Response:
    try:
        target = (root / rel).resolve()
        target.relative_to(root.resolve())
    except (ValueError, OSError):
        raise HTTPError(404)
    if not target.is_file():
        raise HTTPError(404)
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
        ctype += "; charset=utf-8"
    r = Response(target.read_bytes(), content_type=ctype)
    r.header("Cache-Control", cache)
    return r


# --- helpers ------------------------------------------------------------------------------
def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def url(path: str, **query) -> str:
    q = {k: v for k, v in query.items() if v not in (None, "")}
    return path + ("?" + urlencode(q) if q else "")


def safe_next(target: str, default: str = "/dashboard") -> str:
    """Only allow same-site relative redirects."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return default


def qp(value: str) -> str:
    return quote(value, safe="")


SECURITY_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
]
