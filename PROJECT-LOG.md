# Aurelia project log

Decisions, changes and open items, newest first. The baseline is `AURELIA-COMPLETE.md` as shared on
2026-11-16 (67 files, 70 tests passing).

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
