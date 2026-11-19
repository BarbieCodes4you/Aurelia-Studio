#!/usr/bin/env python3
"""Run the Aurelia platform.

    python3 run.py                 # serve on 127.0.0.1:8040 (PORT env or --port to change)
    python3 run.py --seed          # load clearly-labelled demo data, then serve
    python3 run.py --seed-only     # load demo data and exit
    python3 run.py --create-admin you@example.com   # make (or promote) an administrator
    python3 run.py --jobs-once     # run reminders/summaries once (use from cron with wsgi.py)

Only the Python 3.9+ standard library is needed.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import config, db, icons  # noqa: E402
from app.app import App, bootstrap  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    server_version = "Aurelia/1.0"
    protocol_version = "HTTP/1.1"
    app: App = None

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > config.MAX_BODY_BYTES:
            self.send_error(413, "Request too large")
            return
        body = self.rfile.read(length) if length else b""
        ip = self.client_address[0]
        if config.TRUST_PROXY and self.headers.get("X-Forwarded-For"):
            ip = self.headers["X-Forwarded-For"].split(",")[-1].strip()     # added by the proxy; earlier entries come from the client
        resp = self.app.handle(self.command, self.path, dict(self.headers.items()), body, ip)
        self.send_response(resp.status)
        for k, v in resp.headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp.body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(resp.body)

    do_GET = do_POST = do_HEAD = _handle

    def log_message(self, fmt, *args):
        if config.DEBUG:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8040)))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--seed-only", action="store_true")
    ap.add_argument("--create-admin", metavar="EMAIL")
    ap.add_argument("--jobs-once", action="store_true", help="run the background jobs once and exit (for cron)")
    args = ap.parse_args()

    icons.write_css()
    bootstrap()
    if args.jobs_once:
        from app.services import scheduler
        print(scheduler.run_once())
        return
    if args.create_admin:
        from app import auth
        email = args.create_admin.strip().lower()
        row = db.one("SELECT * FROM users WHERE email = ?", (email,))
        if row:
            db.run("UPDATE users SET role = 'admin' WHERE id = ?", (row["id"],))
            print(f"{email} is now an administrator.")
        else:
            pw = getpass.getpass("Password for the new admin: ")
            problems = auth.password_problems(pw, email)
            if problems:
                sys.exit("; ".join(problems))
            db.insert("users", {"email": email, "name": "Administrator", "password_hash": auth.hash_password(pw),
                                "role": "admin", "email_verified_at": db.now(), "created_at": db.now()})
            print(f"Created administrator {email}.")
        return
    if args.seed or args.seed_only:
        from app import seed
        seed.run()
        if args.seed_only:
            return

    Handler.app = App()
    if config.SCHEDULER_ENABLED:
        from app.services import scheduler
        threading.Thread(target=scheduler.loop, daemon=True, name="scheduler").start()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print(f"{config.BRAND_NAME} running at http://{args.host}:{args.port}  (env: {config.APP_ENV}, "
          f"email: {config.EMAIL_PROVIDER}, payments: {config.PAYMENT_GATEWAY})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
