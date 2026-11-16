"""In-process test client. Import this before anything from `app` so data goes to a temp folder."""
from __future__ import annotations

import os
import re
import sys
import tempfile
from http.cookies import SimpleCookie
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_TMP = tempfile.mkdtemp(prefix="aurelia-test-")
os.environ.setdefault("AURELIA_DATA_DIR", _TMP)
os.environ.setdefault("SCHEDULER_ENABLED", "0")
os.environ.setdefault("EMAIL_PROVIDER", "outbox")
os.environ.setdefault("PAYMENT_GATEWAY", "sandbox")

from app import auth, config, db, icons  # noqa: E402
from app.app import App, bootstrap  # noqa: E402

_app = None
_counter = __import__("itertools").count(1)


def fresh_app(name: str = "test") -> App:
    """New empty database for each test case class."""
    global _app
    db.set_path(config.DATA_DIR / f"{name}-{os.getpid()}-{next(_counter)}.sqlite3")
    bootstrap()
    if _app is None:
        icons.write_css()
        _app = App()
    return _app


class Resp:
    def __init__(self, r):
        self.status = r.status
        self.headers = r.headers
        self.body = r.body
        self.text = r.body.decode("utf-8", "replace")

    def header(self, name):
        for k, v in self.headers:
            if k.lower() == name.lower():
                return v
        return None

    @property
    def location(self):
        return self.header("Location")


class Client:
    def __init__(self, app: App, ip: str = "127.0.0.1"):
        self.app = app
        self.cookies: dict[str, str] = {}
        self.ip = ip

    def _cookie_header(self):
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _store(self, resp):
        for k, v in resp.headers:
            if k.lower() == "set-cookie":
                c = SimpleCookie()
                c.load(v)
                for name, m in c.items():
                    if m.get("max-age") == "0":
                        self.cookies.pop(name, None)
                    else:
                        self.cookies[name] = m.value

    def request(self, method, path, data=None, headers=None, body=None, follow=False, json_body=None):
        if method == "POST" and "aur_csrf" not in self.cookies:
            self.get("/__csrf_probe")          # obtain the CSRF cookie before building headers
        h = {"Cookie": self._cookie_header(), "Host": "127.0.0.1"}
        if headers:
            h.update(headers)
        raw = b""
        if json_body is not None:
            import json
            raw = json.dumps(json_body).encode()
            h["Content-Type"] = "application/json"
            h.setdefault("X-CSRF-Token", self.csrf)
            h.setdefault("Accept", "application/json")
        elif body is not None:
            raw = body
        elif data is not None:
            data = dict(data)
            if method == "POST" and "_csrf" not in data:
                data["_csrf"] = self.csrf
            raw = urlencode(data, doseq=True).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        resp = Resp(self.app.handle(method, path, h, raw, self.ip))
        self._store(resp)
        hops = 0
        while follow and resp.status in (301, 302, 303, 307) and hops < 8:
            resp = self.get(resp.location)
            hops += 1
        return resp

    @property
    def csrf(self) -> str:
        if "aur_csrf" not in self.cookies:
            self.get("/__csrf_probe")
        return self.cookies.get("aur_csrf", "")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, data=None, **kw):
        return self.request("POST", path, data=data or {}, **kw)

    def multipart(self, path, fields: dict, files: dict):
        boundary = "----aurelia" + os.urandom(6).hex()
        parts = []
        fields = dict(fields)
        fields.setdefault("_csrf", self.csrf)
        for k, v in fields.items():
            for item in (v if isinstance(v, list) else [v]):
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{item}\r\n'.encode())
        for k, (fname, data, ctype) in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                         f'Content-Type: {ctype}\r\n\r\n'.encode() + data + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        return self.request("POST", path, body=body,
                            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})


def make_user(email="organiser@example.com", password="Correct-Horse-9", name="Thandi Mokoena", role="customer"):
    uid = db.insert("users", {"email": email, "name": name, "password_hash": auth.hash_password(password),
                              "role": role, "email_verified_at": db.now(), "created_at": db.now()})
    return db.one("SELECT * FROM users WHERE id = ?", (uid,))


def login(client: Client, email="organiser@example.com", password="Correct-Horse-9"):
    r = client.post("/login", {"email": email, "password": password})
    assert r.status == 303, (r.status, r.text[:500])
    return r


def find(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else ""
