# Aurelia project log

Decisions, changes and open items, newest first. The baseline is `AURELIA-COMPLETE.md` as shared on
2026-11-16 (67 files, 70 tests passing).

## 2026-11-16 (later): making it as easy as possible for the client

The 21 pain points from the journey review, fixed in both the hosted app and the Netlify site unless noted.

**Decisions (from you)**
- Hosting: a site never goes offline before one month after the event date (package months still count
  from publishing).
- "We'll set it up for you": a free request; the team replies with a quote. No price on the site yet.
- WhatsApp support button: built, hidden until a number is set (`WHATSAPP_NUMBER`).
- Payments: PayFast.

**Changes**
- Booking on the Netlify site sends itself (details, guest list, photos) through Netlify Forms, shows
  "Sent", and offers "Send my changes" after edits. Falls back to "copy and email" if sending fails.
  Contact and set-up help forms send for real too.
- "Pay now" per package from a PayFast link or a pasted PayFast "Pay Now" button (PayFast addresses only).
- Continue on another device (link carries the draft; photos stay on the first device) and a shareable
  preview link for family (no contact details or guest list). App: signed draft preview link.
- Package chosen on the first screen, "Planning with" switcher on every step, locked steps marked,
  and warnings on the review and package steps when a package wouldn't show something already filled in.
- Quick path: steps 4 to 8 optional with "Skip for now" and "Save and go to review".
- First screen: occasion, matching templates only (a matching one pre-selected), package. No name box;
  the event name fills in from the names ("Lerato & Sipho's wedding").
- Ready-made wording (2 per occasion), "Try another look", sample programme per occasion timed from the
  start time, paste a caterer's menu, paste a guest list (Excel/Sheets/notes; duplicates skipped).
  Guest list options folded under "More options".
- Seating: "Set up my tables now" is optional; the seating editor seats everyone automatically, keeping
  families and groups together, and reports anyone who doesn't fit.
- Review step: checklist (needed vs nice to have) with links.
- App sign-up: name and email on the create page, no password needed; sign-in links by email; password
  optional on registration (migration `002_login_links.sql`).
- App: WhatsApp invitation and reminder queue (one guest at a time, progress, skip, broadcast-list guide);
  "Next steps" cards on the event overview; reminders on WhatsApp from the RSVPs page.
- Trust: demo testimonials removed (section hidden until real reviews exist), social links and WhatsApp
  shown only when set, "We'll set it up for you" page linked from home, create, pricing, package step and
  footer.
- Bug fixes found on the way: blank starter rows in Programme and Menu counted as items and blocked
  saving (app and static); a contact form button stayed disabled after a validation error (static); a
  test used SQL syntax older SQLite rejects.
- `GO-LIVE-GUIDE.md`: Netlify (forms, email notifications) and PayFast (account, buttons, requests).

**Checked**
- 89 tests pass on Python 3.11 and 3.13.
- Static site, in a browser against a stand-in for Netlify Forms: 25 checks covering the whole journey,
  booking with photo and guest list received, continue and preview links on a second device, broken
  link message, both forms, "Pay now" button. No script errors.
- App: 110 page loads (marketing, sign-in, wizard steps, share, WhatsApp queue, seating, guests, RSVPs)
  on desktop and phone, no errors, no sideways scrolling.

**Open**
- PayFast account and buttons (see `GO-LIVE-GUIDE.md`), then rebuild with them.
- On Netlify: enable form detection and add an email notification (guide, part 1).
- WhatsApp number and social links, when you have them.
- Legal review, company details, real reviews (unchanged from before).

## 2026-11-16: first public hosting (static site on Netlify)

**Decisions**
- Host the **newer static site** built from the project (`tools/export_preview.py`), not the older
  brochure-only zip (`aurelia-website.zip`), whose "Create your event" only said "email us". The static
  site includes the full 10-step create journey, package choice and booking request.
- Host on **Netlify Drop** (free, https, own domain can be added later).
- The full platform app (accounts, RSVPs, dashboards, emails, PayFast) stays for a later phase on a
  paid host with a disk (Railway, Render or a VPS).

**Changes**
- `tools/export_preview.py`: new `--standalone` option writes `index.html` as a complete HTML
  document (doctype, charset, viewport, description, favicon, `<body class="site">`). Without it the
  page was a fragment meant for a Claude Artifact, and on a normal host the `site` body class was
  never set (script ran before `<body>` existed).
- `tools/make_bundle.py`: skips `dist/` and `preview_build/` so build output never enters the bundle.
- `.gitignore`: `dist/`. `README.md`: how to build for a static host.
- Added this log.

**Checked**
- 70 tests pass.
- Static build: all main pages load with no script errors on desktop and phone (no sideways scroll);
  the create journey runs from step 1 to "Booking request ready".

**Open**
- Payment link per package (`preview_site/payment_links.json`): empty, so the booking page says
  "Online payment opens soon". Add the links and rebuild to show "Pay now".
- Items listed under "Still to confirm before launch" in `README.md` (brand, domain, company
  details, legal review, testimonials, social links, package limits).
