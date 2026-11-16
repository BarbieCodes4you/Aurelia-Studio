"""WSGI entry point, for hosts that run Python web apps through a WSGI server
(gunicorn, uWSGI, mod_wsgi, PythonAnywhere).

    gunicorn --workers 1 --threads 8 --bind 0.0.0.0:8040 wsgi:application

Use ONE worker process: SQLite and the in-memory rate limiter are per process. Threads are fine.
Background jobs don't start here by default (several workers would each start them); run
`python3 run.py --jobs-once` from cron every 5 minutes, or set SCHEDULER_IN_WSGI=1 when you
are sure there is exactly one process.
"""
from __future__ import annotations

import os
import sys
import threading
from http import HTTPStatus
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import config, icons  # noqa: E402
from app.app import App, bootstrap  # noqa: E402

icons.write_css()
bootstrap()
_app = App()

if config.env_bool("SCHEDULER_IN_WSGI", False):
    from app.services import scheduler
    threading.Thread(target=scheduler.loop, daemon=True, name="scheduler").start()


def application(environ, start_response):
    raw = environ.get("RAW_URI") or environ.get("REQUEST_URI")
    if not raw:
        path = environ.get("PATH_INFO", "/").encode("latin-1").decode("utf-8", "replace")
        raw = quote(path, safe="/:@!$&'()*+,;=-._~")
        if environ.get("QUERY_STRING"):
            raw += "?" + environ["QUERY_STRING"]
    headers = {k[5:].replace("_", "-").title(): v for k, v in environ.items() if k.startswith("HTTP_")}
    if environ.get("CONTENT_TYPE"):
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > config.MAX_BODY_BYTES:
        start_response("413 Request Entity Too Large", [("Content-Type", "text/plain")])
        return [b"Request too large"]
    body = environ["wsgi.input"].read(length) if length else b""
    ip = environ.get("REMOTE_ADDR", "")
    if config.TRUST_PROXY and environ.get("HTTP_X_FORWARDED_FOR"):
        ip = environ["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
    resp = _app.handle(environ.get("REQUEST_METHOD", "GET"), raw, headers, body, ip)
    try:
        phrase = HTTPStatus(resp.status).phrase
    except ValueError:
        phrase = ""
    out_headers = list(resp.headers) + [("Content-Length", str(len(resp.body)))]
    start_response(f"{resp.status} {phrase}", out_headers)
    return [resp.body]
