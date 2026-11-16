#!/usr/bin/env python3
"""Write AURELIA-COMPLETE.md: the whole project in one Markdown file.

It holds the hosting guide, configuration, architecture, the route map and the exact
contents of every source file, plus a script that unpacks it back into a working project.

    python3 tools/make_bundle.py            # writes ./AURELIA-COMPLETE.md
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "AURELIA-COMPLETE.md")
SKIP_DIRS = {"data", "__pycache__", ".git", ".claude", "dist", "preview_build"}
SKIP_FILES = {".DS_Store", "AURELIA-COMPLETE.md"}
LANG = {".py": "python", ".sql": "sql", ".css": "css", ".js": "javascript", ".md": "markdown", ".svg": "xml",
        ".sh": "sh", ".json": "json", ".service": "ini", ".toml": "toml"}


def project_files() -> list[str]:
    out = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(d, f), ROOT))
    return sorted(out, key=lambda p: (p.count("/") > 0, p))


def fence_for(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def routes_table() -> str:
    sys.path.insert(0, ROOT)
    import tempfile
    os.environ.setdefault("AURELIA_DATA_DIR", tempfile.mkdtemp())
    os.environ.setdefault("SCHEDULER_ENABLED", "0")
    from app.app import App
    from app.web import router
    App()
    rows = ["| Method | Path | Module |", "|---|---|---|"]
    for r in router.routes:
        rows.append(f"| {', '.join(r.methods)} | `{r.pattern}` | {r.handler.__module__.replace('app.views.', '')} |")
    return "\n".join(rows)


UNPACK = r'''#!/usr/bin/env python3
"""Unpack AURELIA-COMPLETE.md into a project folder.
    python3 unpack.py AURELIA-COMPLETE.md aurelia
"""
import hashlib, os, re, sys

src, dest = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "aurelia")
text = open(src, encoding="utf-8").read()
pat = re.compile(r'<!-- FILE: (?P<path>[^ ]+) sha256=(?P<sha>[0-9a-f]{64}) nl=(?P<nl>[01]) -->\n'
                 r'(?P<fence>`{3,})[a-z]*\n(?:(?P<body>.*?)\n)??(?P=fence)\n', re.S)
count = 0
for m in pat.finditer(text):
    body = (m.group("body") or "") + ("\n" if m.group("nl") == "1" else "")
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != m.group("sha"):
        sys.exit(f"Checksum mismatch for {m.group('path')}: the Markdown was altered.")
    path = os.path.normpath(os.path.join(dest, m.group("path")))
    if not path.startswith(os.path.normpath(dest)):
        sys.exit(f"Refusing to write outside {dest}: {m.group('path')}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    if path.endswith(".sh"):
        os.chmod(path, 0o755)
    count += 1
print(f"Wrote {count} files to {dest}/")
'''

GUIDE = r"""
## 1. What this is

**Aurelia** is a complete digital event platform for South Africa (prices in ZAR). It is not a mock-up:
every button and form works and saves data.

- **Marketing website:** home, four occasion pages, template gallery with desktop/mobile preview,
  pricing with full comparison, how it works, FAQ, contact/support form, privacy (POPIA), terms, refunds.
- **Accounts:** register, log in/out, password reset, email confirmation, profile, data download,
  account deletion.
- **10-step event set-up wizard:** event details, venue, design (live preview), guests, programme,
  food and drinks, seating, extras (dress code, registry, contacts, accommodation, gallery), review,
  package and payment. Saved as a private draft at every step.
- **Event website generator:** 11 templates with different layouts (Atelier, Folio, Bloom, Heritage,
  Champagne, Linea, Confetti, Pulse, Aurora, Laureate, Cradle), each with palettes, font pairs,
  backgrounds, photos and custom wording. One public link per event, plus a personal link per guest.
- **Guest experience:** welcome, invitation, countdown, venue and Google Maps, programme, menu, dress
  code, RSVP (plus-ones, children, meals, dietary needs, several functions), personal table,
  accommodation, registry, gallery, contacts, add-to-calendar, email unsubscribe.
- **Organiser dashboard:** overview stats, guests (add, edit, CSV import, categories, families, VIP,
  check-in), RSVPs, drag-and-drop seating chart, menus, programme, guest emails with preview, sharing
  (link, WhatsApp, invitation message, QR code), 7 reports as PDF or Excel-friendly CSV (including the
  final event administration report), settings (sections, link, publish, co-admins, delete).
- **Payments:** PayFast integration with signature, source-IP and server validation, plus a built-in
  sandbox checkout for development. Only a verified server-to-server notification marks an order paid.
  VAT receipts.
- **Emails:** 25 editable templates for organisers and guests, sent through Resend, any SMTP server,
  or a development outbox. Delivery log, unsubscribe links, per-package allowance.
- **Admin dashboard:** analytics and revenue (sandbox payments kept separate), customers, events
  (suspend, publish, extend hosting), orders (record refunds), hosting periods, packages (prices,
  features, limits), templates, categories, email templates, email log, support, audit log.
- **Background jobs:** RSVP summaries, deadline reminders, automatic guest reminders, event reminders,
  post-event report, hosting expiry, cleanup.

Packages (editable in the admin): Essential R8,999 · Premium R12,999 · Signature R17,999.

**Technology:** Python 3.9+ standard library only (no `pip install`), SQLite, plain HTML/CSS/JS. It
runs anywhere Python runs.

## 2. Rebuild the project from this file

1. Save this file as `AURELIA-COMPLETE.md`.
2. Copy the script below into a file called `unpack.py`, in the same folder.
3. Run it:

```bash
python3 unpack.py AURELIA-COMPLETE.md aurelia
cd aurelia
python3 -m unittest discover -s tests -t .
python3 run.py --seed
```

Open http://127.0.0.1:8040. The demo logins are in `app/seed.py` (development only). Every file
carries a SHA-256 checksum, so the unpacker refuses a copy that was altered.

`unpack.py`:

```python
""" + UNPACK + r"""```

To produce this file again after changes: `python3 tools/make_bundle.py`.

## 3. Hosting

The app is one Python process plus a `data/` folder (the SQLite database, uploaded photos, the
email outbox and a generated secret key). Whatever host you choose needs:

- Python 3.9 or newer (or Docker),
- **a persistent disk** for `data/` (the database lives there),
- **HTTPS** on your domain,
- **one** running instance (SQLite and the login rate limiter are per process).

At roughly 100 events and 20,000 guests a year, a small server (1 vCPU, 1 GB RAM) is plenty.

### Option A: your own server (recommended): Ubuntu, Caddy, systemd

Any VPS works, such as Hetzner, DigitalOcean, Linode or a South African host like Xneelo or Afrihost.
Use Ubuntu 22.04 or 24.04.

1. Point your domain's DNS **A record** (for example `aurelia.co.za` or `www.aurelia.co.za`) at the
   server's IP address.
2. On the server:

```bash
sudo apt update && sudo apt install -y python3 caddy ufw
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw --force enable
sudo useradd --system --create-home --home-dir /opt/aurelia --shell /usr/sbin/nologin aurelia
# upload AURELIA-COMPLETE.md and unpack.py (scp or sftp), then:
sudo -u aurelia python3 unpack.py AURELIA-COMPLETE.md /opt/aurelia
sudo -u aurelia cp /opt/aurelia/.env.example /opt/aurelia/.env
sudo -u aurelia nano /opt/aurelia/.env
```

3. In `.env`, set at least:

```ini
APP_ENV=production
BASE_URL=https://your-domain.co.za
SECRET_KEY=<paste the output of: python3 -c "import secrets;print(secrets.token_hex(32))">
TRUST_PROXY=1
SUPPORT_EMAIL=invitesaurelia@gmail.com
```

   Add the email and payment settings from sections 4 and 5.

4. Create the first administrator:

```bash
cd /opt/aurelia && sudo -u aurelia python3 run.py --create-admin you@example.com
```

5. Run the app as a service:

```bash
sudo cp /opt/aurelia/deploy/aurelia.service /etc/systemd/system/aurelia.service
sudo systemctl daemon-reload && sudo systemctl enable --now aurelia
sudo systemctl status aurelia        # should say "active (running)"
```

6. Put it behind HTTPS: edit `/opt/aurelia/deploy/Caddyfile` with your domain, then:

```bash
sudo cp /opt/aurelia/deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

   Caddy obtains and renews the certificate itself. Open `https://your-domain.co.za`.

7. Add nightly backups:

```bash
sudo crontab -u aurelia -e
# add this line:
15 2 * * * /opt/aurelia/deploy/backup.sh /opt/aurelia/data /opt/aurelia/backups
```

   Copy the backups off the server now and then (for example to cloud storage).

**Updating later:** unpack the new bundle into the same folder (`data/` and `.env` are never
overwritten, because they aren't in the bundle). Then run `sudo systemctl restart aurelia`. Database
migrations run automatically on start.

**Logs:** `sudo journalctl -u aurelia -f`.

### Option B: a Docker host (Railway, Render, Fly.io, any VPS with Docker)

The included `Dockerfile` runs the app on port 8040, with its data in `/data`.

- **Every platform:** create a persistent **volume mounted at `/data`**, run exactly **1 instance**,
  and set the environment variables from `.env.example` (at least `BASE_URL`, `SECRET_KEY`,
  `APP_ENV=production` and `TRUST_PROXY=1`). The platform provides HTTPS; attach your domain in its
  dashboard.
- **Railway:** New project → Deploy from GitHub repo (or `railway up`) → add a Volume at `/data` →
  Variables → Settings → Networking → generate a domain or add your own.
- **Render:** New Web Service → Docker → instance type with a **Persistent Disk** (mount path `/data`;
  free instances have no disk) → Environment.
- **Fly.io:** `fly launch --no-deploy`, then `fly volumes create aurelia_data --size 1`, then add the
  mount below to `fly.toml`, set `internal_port = 8040`, and run `fly secrets set SECRET_KEY=... BASE_URL=...`
  and `fly deploy`:

```toml
[mounts]
  source = "aurelia_data"
  destination = "/data"
```

- Create the admin by opening the platform's shell: `python3 run.py --create-admin you@example.com`.
  Alternatively, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` once, start the app, then remove them.

Background jobs run inside the process, so no extra worker is needed.

### Option C: hosts that run Python through WSGI (PythonAnywhere, cPanel "Python App", uWSGI, gunicorn)

Point the host at `wsgi.py` and its `application` object, for example
`gunicorn --workers 1 --threads 8 --bind 0.0.0.0:8040 wsgi:application`. Use **one worker**.

Background jobs don't run under WSGI. Schedule `python3 /path/to/run.py --jobs-once` every 5 to 15
minutes with the host's scheduled-task feature. Set the same environment variables.

PythonAnywhere: a paid account is needed for a custom domain and for outgoing connections to Resend and
PayFast.

## 4. Email (invitations, RSVPs, reports)

In development, emails are written to `data/outbox/` and can be read at `/admin/outbox`. For real
delivery, choose one of these:

- **Gmail SMTP (simplest, low volume, sends as invitesaurelia@gmail.com):** turn on 2-step verification
  on the Google account, create an **App password**, then set:

```ini
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=invitesaurelia@gmail.com
SMTP_PASSWORD=<the 16-character app password>
EMAIL_FROM=Aurelia <invitesaurelia@gmail.com>
```

  Gmail allows about 500 messages a day, which suits launch volumes.

- **Resend (better delivery at volume):** create an account, add and verify your own domain (Resend
  shows the DNS records to add), create an API key, then set:

```ini
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_...
EMAIL_FROM=Aurelia <invites@your-domain.co.za>
EMAIL_REPLY_TO=invitesaurelia@gmail.com
```

  Resend can't send *from* a Gmail address; replies can still go to Gmail.

Each package includes a guest-email allowance (editable in the admin). Sharing the link itself is
unlimited.

## 5. Payments (PayFast)

1. Open a PayFast merchant account. For testing first, use a PayFast **sandbox** account at
   sandbox.payfast.co.za.
2. In the PayFast dashboard, copy the **Merchant ID** and **Merchant Key**, and set a **passphrase**
   under the developer/integration settings.
3. Set:

```ini
PAYMENT_GATEWAY=payfast
PAYFAST_MERCHANT_ID=...
PAYFAST_MERCHANT_KEY=...
PAYFAST_PASSPHRASE=...
PAYFAST_SANDBOX=1        # 0 when you go live with real credentials
PAYFAST_CHECK_IP=1
```

4. `BASE_URL` must be your public **https** address. Each payment tells PayFast to notify
   `BASE_URL/webhooks/payments/payfast`; no dashboard setting is needed for that.
5. Test the full journey with the sandbox: choose a package, pay, and watch the event publish. Then
   check the order in `/admin/orders`. Switch to live credentials with `PAYFAST_SANDBOX=0`.

Safety: in production, the built-in test checkout is refused, so nobody can publish without paying.
Only a private staging or demo copy should set `ALLOW_SANDBOX_PAYMENTS=1`.

## 6. Go-live checklist

- [ ] Domain and HTTPS working; `BASE_URL` is the https address
- [ ] `APP_ENV=production`, a long random `SECRET_KEY`, `TRUST_PROXY=1` behind a proxy
- [ ] An admin account created with a strong password; demo data **not** loaded (`--seed` is for development)
- [ ] Email provider set and a test sent from `/admin/emails/<template>` → "Send test to me"
- [ ] PayFast sandbox journey passes, then live credentials with `PAYFAST_SANDBOX=0`
- [ ] Company address, VAT number and information officer set in `.env`
- [ ] Legal pages (`/privacy`, `/terms`, `/refunds`) reviewed by a lawyer; edit them in `app/views/marketing.py`
- [ ] Footer social links (currently `#`) set in `app/views/layout.py`
- [ ] Demonstration testimonials on the home page replaced or removed (`TESTIMONIALS` in `app/views/marketing.py`)
- [ ] Package prices, features and limits confirmed in `/admin/packages`
- [ ] Nightly backups running and copied off the server

## 7. Configuration reference (`.env`)

| Setting | Default | Purpose |
|---|---|---|
| `APP_ENV` | development | `production` turns off debug behaviour and the test checkout |
| `BASE_URL` | http://127.0.0.1:8040 | Public address used in emails, links and payment callbacks |
| `SECRET_KEY` | generated into `data/` | Signs cookies and test notifications; set a long random value |
| `AURELIA_DATA_DIR` | `./data` | Database, uploads, outbox, reports |
| `DATABASE_PATH` | `data/aurelia.sqlite3` | SQLite file |
| `HOST`, `PORT` | 127.0.0.1, 8040 | Listening address for `run.py` |
| `TRUST_PROXY` | 0 | Use `X-Forwarded-For` for client IPs (only behind your proxy) |
| `SECURE_COOKIES` | on if https | Secure flag on cookies |
| `SESSION_DAYS` | 14 | Login lifetime |
| `MAX_BODY_BYTES`, `MAX_UPLOAD_BYTES` | 25 MB, 6 MB | Request and image size limits |
| `BRAND_NAME`, `BRAND_TAGLINE` | Aurelia | Name and tagline everywhere |
| `SUPPORT_EMAIL` | invitesaurelia@gmail.com | Contact address on the site and in emails |
| `COMPANY_ADDRESS`, `VAT_NUMBER`, `INFORMATION_OFFICER_EMAIL` | placeholders | Footer, receipts, POPIA |
| `VAT_RATE` | 0.15 | VAT split on receipts (prices include VAT) |
| `EMAIL_PROVIDER` | outbox | `outbox`, `smtp` or `resend` |
| `EMAIL_FROM`, `EMAIL_REPLY_TO` | | Sender and reply address |
| `RESEND_API_KEY` | | Resend |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | 587, on | SMTP |
| `PAYMENT_GATEWAY` | sandbox | `sandbox` or `payfast` |
| `PAYFAST_MERCHANT_ID`, `PAYFAST_MERCHANT_KEY`, `PAYFAST_PASSPHRASE` | | PayFast credentials |
| `PAYFAST_SANDBOX` | 1 | Use sandbox.payfast.co.za |
| `PAYFAST_CHECK_IP` | 1 | Accept notifications only from PayFast's servers |
| `ALLOW_SANDBOX_PAYMENTS` | on in development | Allow the built-in test checkout (never on a live site) |
| `SCHEDULER_ENABLED`, `SCHEDULER_INTERVAL_SECONDS` | 1, 300 | In-process background jobs (`run.py`) |
| `SCHEDULER_IN_WSGI` | 0 | Start jobs inside `wsgi.py` (single process only) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | | Create the first admin on start |

## 8. Command line

| Command | Does |
|---|---|
| `python3 run.py` | Serve the app |
| `python3 run.py --seed` | Load demo data (flagged `is_demo`), then serve. Development only |
| `python3 run.py --seed-only` | Load demo data and exit |
| `python3 run.py --create-admin EMAIL` | Create or promote an administrator |
| `python3 run.py --jobs-once` | Run background jobs once (cron with WSGI hosting) |
| `python3 -m unittest discover -s tests -t .` | Run the test suite |
| `python3 tools/make_bundle.py` | Rebuild this Markdown file |
| `deploy/backup.sh DATA DEST` | Back up the database and uploads |

## 9. How it's built

- `run.py`: the threaded HTTP server and the CLI. `wsgi.py`: the same app for WSGI servers.
- `app/app.py`: request dispatch, sessions, CSRF (double-submit cookie), flash messages, error pages,
  security headers.
- `app/web.py`: request and response objects, router, multipart uploads, static files.
- `app/db.py` + `app/migrations/*.sql`: SQLite (WAL, foreign keys) with numbered migrations that apply
  on start.
- `app/auth.py`: PBKDF2-SHA256 passwords (310,000 iterations), database sessions, reset and
  verification tokens, rate limits, ownership checks.
- `app/catalog.py`: categories, templates, packages and feature gating (`has_feature`, `limit`).
- `app/events.py`, `app/notify.py`: event helpers, organiser notifications, publish and unpublish.
- `app/eventsite/`: the website generator (`themes.py` palettes and fonts, `designs.py` 11 layouts,
  `render.py`, `demo.py` sample content).
- `app/services/`: `email.py` (providers and templates), `payments.py` (gateways), `storage.py`
  (uploads), `pdf.py` and `qr.py` (written from scratch), `reports.py`, `scheduler.py`.
- `app/views/`: marketing, accounts, wizard, dashboard, manage (organiser tools), public_event, media,
  payments, admin, plus the `layout`, `shell` and `forms` helpers.
- `static/`: `css/app.css` (the design system: pastel tokens at the top), `css/eventsite.css` (event
  templates), `css/admin.css`, `css/icons.css` (generated), `js/app.js`, `js/seating.js`,
  `js/eventsite.js`, `img/favicon.svg`.
- `tests/`: an in-process test client and 70 tests.
- `deploy/`: Caddyfile, systemd unit and backup script. `Dockerfile` and `.dockerignore` for container
  hosts.

**Data model:** users, sessions, user_tokens, categories, templates, packages, events, event_admins,
event_functions, schedule_items, menus, menu_items, guests, guest_functions, rsvp_responses,
seating_tables, seat_assignments, uploads, orders, payments, email_templates, email_logs, sent_markers,
support_requests, report_runs, audit_log (`app/migrations/001_init.sql`).

**Security:** every dashboard route checks ownership on the server (other people's events return
404). Admin routes require the admin role. Guests never see other guests. Uploads are checked by
content and stored under random names. Media is served only for live events or to their managers.
Event pages are `noindex`. Admin and payment actions are written to an audit log.

**Growing later:** move SQLite to PostgreSQL (`INTEGER PRIMARY KEY` becomes `BIGSERIAL`, JSON text
becomes `JSONB`) when you need several app servers. Add an S3 or R2 backend to
`app/services/storage.py` for uploads. Add the WhatsApp Business API for automated messages (sharing
is manual today, by design).

## 10. Known limits

- PayFast is implemented and unit-tested, but it has not yet been run against the PayFast sandbox:
  that needs your merchant credentials and a public https address (section 5).
- Custom domains for individual events (Signature package) need DNS and TLS setup per domain; this
  isn't automated.
- Uploads are stored on the server's disk; back them up (section 3, step 7).
"""


def main():
    files = project_files()
    parts = [f"# Aurelia: complete project and hosting guide\n\n"
             f"Generated {date.today().isoformat()} from the working project. **{len(files)} files**, each included in full "
             f"under section 12, with a checksum. Nothing else is needed to rebuild and host the website.\n\n"
             "## Contents\n\n1. What this is\n2. Rebuild the project from this file\n3. Hosting\n4. Email\n5. Payments (PayFast)\n"
             "6. Go-live checklist\n7. Configuration reference\n8. Command line\n9. How it's built\n10. Known limits\n"
             "11. Every page and endpoint\n12. Source files\n",
             GUIDE,
             "\n## 11. Every page and endpoint\n\n" + routes_table() + "\n",
             "\n## 12. Source files\n\n" + "\n".join(f"- `{p}`" for p in files) + "\n"]
    for rel in files:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        nl = text.endswith("\n")
        body = text[:-1] if nl else text
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        fence = fence_for(text)
        lang = LANG.get(os.path.splitext(rel)[1], "")
        if rel == "Dockerfile":
            lang = "dockerfile"
        parts.append(f"\n### `{rel}`\n\n<!-- FILE: {rel} sha256={sha} nl={1 if nl else 0} -->\n"
                     f"{fence}{lang}\n{body + chr(10) if body else ''}{fence}\n")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print(f"Wrote {OUT} ({os.path.getsize(OUT) // 1024} KB, {len(files)} files)")


if __name__ == "__main__":
    main()
