# Aurelia Studios: start here

Everything for Aurelia Studios now lives in this repository, and future work happens here.

## What this is

A platform where clients choose a template, add their event details, pay once through PayFast and get
an event website. It covers RSVPs, the guest list, seating, menus, the programme, WhatsApp invitations,
emails and reports, plus an admin area for us. It runs on Python's standard library, with no packages to
install, and stores data in SQLite on a disk mounted at `/data`.

## Links

| What | Where |
| --- | --- |
| Code (this repository) | https://github.com/BarbieCodes4you/Aurelia-Studio |
| Preview of the marketing site and templates | https://claude.ai/artifact/UNdUTWgjEoM9xw9M4dLCqT |
| What a client sees after paying (walkthrough) | https://claude.ai/artifact/17TyBLy7hTbFn9UbuMPuEi |
| Live site on Railway | https://aurelia-studio-production.up.railway.app |
| Own domain | **aureliastudios.co.za**, registered at GoDaddy (to connect: `DEPLOY-RAILWAY.md`, part 3) |

The two preview links are private until you share them from the page's Share menu.

## Guides in this repository

- `DEPLOY-RAILWAY.md`: **the launch guide**, covering Railway, domain, email and PayFast, step by step
- `PROJECT-LOG.md`: decisions, changes and open items, newest first
- `README.md`: how the code is organised, settings, and what's still to confirm
- `GO-LIVE-GUIDE.md`: an older, simpler route (static site on Netlify), kept for reference
- `AURELIA-COMPLETE.md`: the whole project bundled into one file

## Launch checklist

**1. Code on GitHub** ✅ done (19 Nov 2026)

**2. Railway: get it running** (see `DEPLOY-RAILWAY.md` Part 2)
- [x] New Project → Deploy from GitHub repo → **Aurelia-Studio**
- [x] Settings → Networking → **Generate Domain**. The domain's port must match `PORT` (8040);
      a mismatch shows "Application failed to respond".
- [x] Add a **Volume** with mount path **`/data`**. Without it, all data is lost on every update.
- [x] Variables → Raw Editor: `PORT=8040`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ALLOW_SANDBOX_PAYMENTS=1`
- [ ] Sign in at `/login`, open `/admin` and follow **Launch checks**. Delete `ADMIN_PASSWORD` afterwards.
- [ ] Test the full journey with the test checkout: create an event, pay, see it go live, RSVP as a guest

**3. Domain** (Part 3)
- [x] Domain bought: **aureliastudios.co.za** (GoDaddy)
- [ ] Move its DNS to Cloudflare (free; nameservers changed at GoDaddy), then add `aureliastudios.co.za` and `www.aureliastudios.co.za` as
      Custom Domains in Railway
- [ ] Set `BASE_URL=https://aureliastudios.co.za` once both show a green tick

**4. Email through Resend** (Part 4)
- [ ] Verify the domain in Resend and create an API key
- [ ] Set `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO`
- [ ] `/admin/emails` → **Send test to me**

**5. PayFast** (Part 5)
- [ ] Open and verify a merchant account; set a passphrase
- [ ] Test in sandbox (`PAYFAST_SANDBOX=1`), then switch to live (`PAYFAST_SANDBOX=0`)
- [ ] **Delete `ALLOW_SANDBOX_PAYMENTS`** so nobody can publish without paying

**6. Before announcing**
- [ ] Company address, VAT number, information officer (`COMPANY_ADDRESS`, `VAT_NUMBER`,
      `INFORMATION_OFFICER_EMAIL`)
- [ ] Legal pages reviewed by someone qualified: `/privacy`, `/terms`, `/refunds`
- [ ] Package limits checked at `/admin/packages`
- [ ] Optional: `WHATSAPP_NUMBER`, social links, real customer reviews
- [ ] First backup downloaded (`/admin` → **Download a backup**), then weekly

## Known gaps (from README)

- Custom domains for Signature clients are advertised, but connecting a client's domain is still manual.
- Uploads are stored on the Railway volume only. There is no cloud storage yet.
