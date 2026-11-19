# Aurelia project log

Decisions, changes and open items, newest first. The baseline is `AURELIA-COMPLETE.md` as shared on
2026-11-16 (67 files, 70 tests passing).

## 2026-11-19 (later): moved into the GitHub repository

**Changes**
- The project and its full history are now on GitHub at `BarbieCodes4you/Aurelia-Studio`, and work
  continues from there. `START-HERE.md` lists the links, the guides and the launch checklist.

**Checked**
- 106 tests pass after the move.

**Waiting on**
- Railway: deploy from the repository (`DEPLOY-RAILWAY.md`, Part 2).

## 2026-11-19: fewer Railway settings, launch checks

**Changes**
- On Railway the app takes its web address from Railway's generated domain (`RAILWAY_PUBLIC_DOMAIN`)
  and trusts Railway's proxy by itself; the secret key is created once on the `/data` volume. The
  Railway variables come down to `PORT`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `ALLOW_SANDBOX_PAYMENTS`.
  `BASE_URL` is only needed once your own domain is connected.
- The client address behind a proxy is now the last `X-Forwarded-For` entry (the one the proxy adds),
  so a visitor can't fake their address to get around rate limits.
- `/admin` shows **Launch checks**: missing volume, web address, `ADMIN_PASSWORD` still set, emails
  not connected, test-mode payments, company details. Each says what to do.
- `DEPLOY-RAILWAY.md` updated: connect GitHub to Claude, generate the domain before adding the volume
  and variables, the shorter variable list.

**Checked**
- 106 tests pass on Python 3.12 and 3.11.
- The production image run the way Railway runs it (volume at `/data`, Railway variables): health
  check ok, the app runs as the `aurelia` user, the secret key is created on the volume, admin sign-in
  works and the launch checks list the remaining steps. Without a volume, the first check warns.

**Waiting on**
- GitHub: connect it to Claude (https://claude.ai/connect-github, install the Claude GitHub App on the
  repository) and send the repository name; then the code goes up and Railway can deploy it.

## 2026-11-17 (later): what the client sees after paying

**Question (from you)**: what does the client face after purchasing? Answered with a walkthrough page
of real screens (pay, confirmation, emails, My events, dashboard, sharing, guest replies, next-morning
email, RSVPs, seating, the guest's table, reports), captured from the full platform in test mode.

**Changes made while walking through it**
- Checkout: Pay buttons sit right under the price on every package card; "VAT incl." no longer splits.
- Emails after paying: the receipt plus one "is live" email (link, Send your invitations, dashboard),
  instead of three overlapping emails at once. "Next steps" goes out the morning after publishing, only
  when something is left to do, using the same list as the dashboard (`scheduler._next_steps`).
  The Share page has "Email me this link" (sends the "Event website link" template on request).
- Invitation counts: guests who replied, or opened their personal link, count as having their
  invitation; reminders count only invited guests who haven't replied; the WhatsApp queue skips
  guests who replied.
- Guest list paste: "Thabo & Lindi Mokoena" becomes one invitation for two. The details step suggests
  an RSVP deadline, and changing it updates the invitation wording.
- Seating floor plan: `pos_y` is now pixels from the top (migration `003_floor_pixels.sql`); tables sit
  three across under the top table, new tables take free places, the floor grows to fit the lowest
  table (no more cut-off rows on big events), cards align by their tops, long names stay on one line
  inside the card (full name on hover), dragging keeps the card under the pointer. Auto-seat gives
  each family its own table first and creates the number of tables chosen during set-up.

**Checked**
- 104 tests pass on Python 3.12 and 3.11.
- Walkthrough in a browser with no script errors; a 60-party event seats into 17 tables with no
  overlapping or cut-off cards.

## 2026-11-17: full platform on Railway

**Decisions (from you)**
- Launch the full platform (not the Netlify static site) on **Railway**, code in a **private GitHub repo**.
- Template gallery photos from free sources.

**Changes**
- Railway-ready: no `VOLUME` line (Railway refuses it), `deploy/entrypoint.py` fixes ownership of the
  root-owned `/data` disk and then runs the app as a normal user, `railway.json` (Dockerfile build,
  `/healthz` health check, restart on failure), `/healthz` endpoint.
- Admin: **Download a backup** (database + uploaded photos in one zip).
- Sample galleries and main photos use real photos once added (`tools/add_photos.py` resizes and files
  them); the static bundle skips image files.
- Fixed: on the create page, changing the occasion caused a script error (data escaped twice).
- `DEPLOY-RAILWAY.md`: GitHub → Railway → domain via Cloudflare DNS → Resend email → PayFast → checklist.

**Checked**
- Production Docker image built and run like Railway (PORT from Railway, root-owned `/data`): health
  check ok, app runs as uid 1000, admin created from variables, client can create an event, payments stay
  in test mode until PayFast is set. 97 tests pass.

**Open**
- GitHub repo name from you → I push the code.
- Photos: Unsplash and Wikimedia both refuse automated downloads from this session's shared address;
  photos from you (zip) go in with `tools/add_photos.py`.

## 2026-11-16 (night): why digital, seating how-to, booking view, photo slots

**Changes**
- Home page: "Why send your invitations this way", just above "Finished event websites": printed
  cards versus one link for 300 guests (printing at about R30 to R50 a card, Bridebook ZA 2025).
- Seating step: "How you'll seat your guests" (replies come in → "Seat everyone automatically" →
  drag or tap to adjust, print or download).
- Full platform, event overview: "Your booking" card (package, amount and date paid, receipt,
  website link and status, online until).
- Photo slots (`app/stock.py`, `static/img/stock/`): weddings, traditional, baby, parties, other.
  Used on the home page occasion tiles and as the main photo in the template samples; the line
  drawings stay until photos are added.

**Open**
- Photos: Unsplash downloads are behind an anti-bot check from this session. Waiting on photos from
  you (see conversation). Unsplash hosts were added to the Default environment's network allowlist.
- 96 tests pass.

## 2026-11-16 (evening): smoother create-your-event, checkout on the site, Aurelia Studio

**Decisions (from you)**
- Name: **Aurelia Studio** (logo shows "Aurelia" with "Studio" set small beside it).
- Packages back at the end; the create page asks occasion, template and names.
- Fewer clicks, and checkout on the website itself, with no "send us your booking" step.
- Seating: keep the "Most hosts plan seating once replies are in…" note, add drawn table types.
- Programme: no "Type" or "Part of"; events over several days get a simple Day 1 / Day 2.
- Gallery: also for photos from the day, added after the event.

**Changes (app and website)**
- Set-up is 8 steps: Details (names, date, venue, extras folded away) · Design · Guests · Programme ·
  Food and drinks · Seating · Extras · Review and pay. Old links to steps 9 and 10 still work.
- No "Save draft" button: the website saves as you type; one "Continue" button per step.
- Guests: type a name and press Enter; add from phone contacts (Chrome on Android); upload Excel or
  CSV (Name/Surname/Mobile/Email/Family columns, or none); paste with "Mokoena family:" headings;
  remove with one tap; or skip and let guests add themselves when they reply.
- Programme: one list for a one-day event; "Add another day" for lobola, traditional and multi-day
  events, each day with its own date, optional venue and items. Item types are worked out from the
  wording (e.g. "Dinner" counts as a meal). The event website shows each day's date.
- Seating: drawn choices for the top table (sweetheart, head table, none) and guest tables (round,
  long, mix), a live room sketch, and the app builds tables from the layout (top table at the front,
  left out of automatic seating).
- Extras: "Someone guests can call on the day" explained and folded away; gallery framed for photos
  now or after the event; dashboard prompts "Share photos from the day" after the event.
- Review and pay: checklist, your details, a Pay button on each package (terms accepted by paying),
  draft link for family, everything else folded away. Website: Pay saves the booking in the background
  and goes straight to PayFast; without PayFast connected yet, a thank-you page says you'll be in touch.
- Bug fixed: spreadsheets with separate Name and Surname columns kept only the first name.

**Checked**
- 93 tests pass (Python 3.11 and 3.13). Website: full browser run-through of all 8 steps (Excel import,
  days, seating, pay with and without PayFast), phone widths for every step, no script errors. App:
  110 page loads on desktop and phone, no errors.

**Open**
- PayFast buttons (until then the website ends on the thank-you page).
- Hosting decision: real checkout that confirms payment and publishes automatically needs the full
  platform on a server (see the recommendation in this conversation).

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
