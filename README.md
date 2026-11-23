# Aurelia Studios — digital event experience platform

**One event. One platform. One link. Everything organised.**

A complete web application for creating, publishing and managing event websites in South Africa
(prices in ZAR): a marketing site, an event creation wizard, 11 event website templates, guest RSVPs,
guest list, seating chart, menus, programme, emails, WhatsApp sharing, reports, payments and an admin
dashboard.

The brand is "Aurelia Studios". Change it with `BRAND_NAME` in `.env`.

## Run it

Only Python 3.9 or later is needed. There are no packages to install.

```bash
cd aurelia
python3 run.py --seed        # loads demo data, then serves http://127.0.0.1:8040
```

| Demo login (development only) | Email | Password |
|---|---|---|
| Event host with 3 events | `thandi@demo.aurelia.example` | `Demo-Host-2026` |
| Platform admin | `admin@demo.aurelia.example` | `Demo-Admin-2026` |

Every demo row has `is_demo = 1` and an `@demo.aurelia.example` address. Admin totals leave demo rows out,
and running the seed again replaces them. To create a real administrator, run
`python3 run.py --create-admin you@example.com`.

Run the tests:

```bash
python3 -m unittest discover -s tests -t .     # 97 tests
```

## The customer journey

1. **Choose.** `/create`: pick the occasion (14 categories in 4 groups) and a template, or start from any
   template's "Use this template" button.
2. **Account.** If you aren't signed in, you register and land back on step 1 with your choices kept.
3. **Set up in 10 steps**, each saved as a private draft (`/dashboard/events/<uid>/setup/1..10`): event
   details, venue, design (with a live preview that updates as you go), guests, programme, food, seating,
   extras (dress code, registry, contacts, accommodation, gallery), review, then package.
4. **Pay.** Checkout creates an order. The website goes live **only** when the gateway's server-to-server
   notification is verified. Returning to the site from the gateway changes nothing.
5. **Share** one link: copy it, send it on WhatsApp, use the ready-made message, or download the QR code
   (PNG/SVG). Each guest can also get a personal link that greets them and shows their table.
6. **Manage**: RSVPs, guest list (with CSV import), drag-and-drop seating, menus and meal choices,
   programme, guest emails (always previewed before sending), and seven reports as PDF or
   Excel-friendly CSV, including the final event administration report.

## Architecture

The brief preferred Next.js, TypeScript and PostgreSQL. This Mac has no Node.js, and the decision was to
build on Python only, so the app uses the Python standard library: `http.server`, `sqlite3`, `hashlib`,
`smtplib` and `urllib`. The structure maps one-to-one onto a later move: routes become route handlers, the
SQL schema becomes Prisma models, and the services keep the same interfaces.

```
aurelia/
  run.py                      server entry point (ThreadingHTTPServer) and CLI
  app/
    app.py                    request dispatch: sessions, CSRF, flash messages, error pages, security headers
    web.py                    Request/Response, router, multipart parsing, static files
    db.py, migrations/        SQLite with numbered SQL migrations (foreign keys, WAL)
    auth.py                   PBKDF2 passwords, DB sessions, CSRF, reset/verify tokens, rate limits, access checks
    catalog.py                categories, templates, packages, feature gating (has_feature / limit)
    events.py, notify.py      event model helpers; organiser notifications; publish/unpublish
    eventsite/                website generator: themes.py (palettes, fonts), designs.py (11 layouts), render.py, demo.py
    services/
      email.py                provider interface: outbox (dev) | Resend | SMTP; editable templates; delivery log
      payments.py             gateway interface: sandbox (dev) | PayFast; verified notifications only
      storage.py              upload interface (local disk; byte-sniffed images, random names)
      pdf.py, qr.py           hand-written PDF writer and QR encoder (PNG + SVG)
      reports.py              guest, RSVP, seating, dietary, meal, outstanding and final reports (CSV/PDF)
      scheduler.py            summaries, reminders, post-event report, hosting expiry, cleanup
    views/                    marketing, accounts, wizard, dashboard, manage, public_event, payments, admin
  static/css/app.css          design system (from docs/website-style-playbook.md plus the glass layer)
  static/css/eventsite.css    event website designs; admin.css
  static/js/                  app.js (UI behaviour), seating.js (seating editor), eventsite.js (countdown, RSVP)
  tests/                      in-process test client and 97 tests
```

**Data model:** users, sessions, user_tokens, categories, templates, packages, events, event_admins,
event_functions, schedule_items, menus, menu_items, guests, guest_functions, rsvp_responses,
seating_tables, seat_assignments, uploads, orders, payments, email_templates, email_logs, sent_markers,
support_requests, report_runs, audit_log. See `app/migrations/001_init.sql`.

**Design:** the marketing site and dashboards follow the STS playbook's structure (one signal colour,
Geist with tight tracking, hairline grids, a glass header) in a pastel palette: lilac as the signal colour
with blush, mint, peach and sky washes, glossy pastel buttons with dark text, and deeper lilac for small
text and checked controls so contrast stays AA. Footer and menu drawer are deep plum. Aurelia adds a
glossy, transparent layer (frosted glass panels with a specular edge) and an Instrument Serif keyword.
All colours are tokens at the top of `static/css/app.css`.
Event websites have their own identities. Each of the 11 templates has a different layout, not just
different colours: Atelier, Folio, Bloom, Heritage, Champagne, Linea, Confetti, Pulse, Aurora, Laureate
and Cradle. Light and dark themes are supported, and motion turns off under reduced-motion settings.

## Security and privacy

- Passwords are hashed with PBKDF2-SHA256 (310k iterations). Sessions are HttpOnly and SameSite=Lax, and
  marked Secure when `BASE_URL` is https. Every form POST is CSRF-protected; payment webhooks are
  authenticated by signature instead. Login, registration, reset and
  RSVP are rate-limited.
- Every dashboard route checks event ownership or co-admin access on the server and returns 404 for other
  people's events. Admin routes require the admin role on the server.
- Guests never see other guests. Personal links reveal only that guest's own RSVP and table. Event pages
  send `noindex`.
- Uploads are checked by their file signature, size-limited and stored under random names. Media is served
  only for live events or to the event's managers.
- POPIA: there is a privacy notice, an information officer contact, an unsubscribe link in every guest
  email, data download and account deletion on `/account`, and an audit log of admin and payment actions.

## Configuration

Copy `.env.example` to `.env`. Nothing secret is in the code.

| To switch on | Set |
|---|---|
| Real email with Resend | `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM` (verified domain) |
| Real email with SMTP | `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| PayFast sandbox | `PAYMENT_GATEWAY=payfast`, `PAYFAST_MERCHANT_ID`, `PAYFAST_MERCHANT_KEY`, `PAYFAST_PASSPHRASE`, `PAYFAST_SANDBOX=1`, and a public `BASE_URL` PayFast can reach for `/webhooks/payments/payfast` |
| PayFast live | the same, with live credentials and `PAYFAST_SANDBOX=0` |
| Production | `APP_ENV=production`, a long random `SECRET_KEY`, https `BASE_URL`, `ADMIN_EMAIL`/`ADMIN_PASSWORD` for the first admin |

In development, emails are written to `data/outbox/` (admins can read them at `/admin/outbox`). Payments
use the built-in sandbox checkout, which is labelled on every screen. Sandbox orders never count as revenue.

The PayFast integration builds the MD5 signature, checks the ITN signature, source IP and amount, and
confirms each notification with PayFast's validate endpoint. It has been unit-tested for signatures but
**not yet run against the PayFast sandbox**, because that needs merchant credentials and a public URL.

## Still to confirm before launch

- Brand name, company address, VAT number, information officer (the domain is aureliastudios.co.za) (support email is invitesaurelia@gmail.com; no phone number is shown)
  (`.env`; placeholders are marked `[TBC]`).
- Legal pages (`/privacy`, `/terms`, `/refunds`) are drafts marked for legal review.
- Customer reviews: the home page section stays hidden until real reviews are added (`TESTIMONIALS`).
- WhatsApp support number and social links: hidden until set (`WHATSAPP_NUMBER`, `SOCIAL_*` in `.env`).
- Package limits (email allowance, hosting months, functions, admins, gallery photos) are proposals.
  Edit them at `/admin/packages`.
- Custom domain support (Signature) is listed as a feature, but domain mapping needs hosting-level setup
  (DNS and TLS) that isn't automated yet.
- Cloud storage for uploads: the interface is in `services/storage.py`, but only the local-disk backend
  exists.

## Next phases

1. **Hosting**: deploy behind a reverse proxy with TLS, back up `data/`, and run a PayFast sandbox
   end-to-end test on a public URL.
2. **Scale-up path**: move to PostgreSQL (mostly ANSI SQL already: `INTEGER PRIMARY KEY` becomes
   `BIGSERIAL`, JSON text columns become `JSONB`), then to Next.js and Prisma if the team wants a
   JavaScript stack.
3. **Approved WhatsApp Business API** for automated invitations. Today WhatsApp is share-only, by design.
4. **Custom PDF invitation designs** (Signature) and S3/R2 storage.

## Launch the full platform

`DEPLOY-RAILWAY.md`: GitHub, Railway, your domain (Cloudflare DNS), email (Resend) and PayFast, step by step.

## Go live now (static site)

`GO-LIVE-GUIDE.md` covers putting the static site on Netlify (with bookings, contact messages and
set-up requests arriving through Netlify Forms) and taking payment with PayFast.

## Shareable preview site (no server)

`python3 tools/export_preview.py OUT_DIR` builds a static version of the site that runs anywhere,
including a Claude Artifact link. It includes the full customer journey in the browser:
occasion and template, all 10 set-up steps with photo uploads and a live preview
(`preview_site/eventrender.js` is a JavaScript port of the Python renderer), "My events" saved in
the visitor's browser, links to continue on another device or show a draft to family, and package
choice. On a `--standalone` build hosted on Netlify, the booking (with photos and guest list), the
contact form and the set-up help form send themselves through Netlify Forms; anywhere else they fall
back to "copy and email us". Put a PayFast link or a pasted PayFast "Pay Now" button per package in
`preview_site/payment_links.json` and rebuild: the booking page then shows "Pay now". Accounts and
RSVPs still need the hosted app.

To host the static version on its own (Netlify, Cloudflare Pages, GitHub Pages), add `--standalone`:
`python3 tools/export_preview.py dist/aurelia-site --standalone` writes `index.html` as a complete HTML
document. Upload the `aurelia-site` folder as it is.

## Hosting

`AURELIA-COMPLETE.md` (made by `python3 tools/make_bundle.py`) holds the full hosting guide and every
source file. Hosting files: `Dockerfile`, `wsgi.py` (for WSGI servers), `deploy/Caddyfile` (HTTPS),
`deploy/aurelia.service` (systemd) and `deploy/backup.sh` (nightly backups). In production the built-in
test checkout is refused unless `ALLOW_SANDBOX_PAYMENTS=1`.

## Preview from this Mac

The Claude preview server can't read the Desktop, so it runs a copy in the session scratchpad
(`.claude/launch.json` → `aurelia`). Bash can run `python3 run.py` here directly.
