# Aurelia Studios: launch on Railway with your own domain

The full platform: accounts and "My events", guest RSVPs, seating, WhatsApp invitations, PayFast
checkout that publishes the website by itself, emails and the admin area. Follow the parts in order.
Menu names can shift slightly when Railway, Cloudflare or Resend update their dashboards; look for the
closest match, or send me a screenshot.

**Monthly cost, roughly:** Railway Hobby about US$5 (card needed) · domain: a yearly fee at a South
African registrar · Cloudflare DNS: free · Resend email: free plan to start (check its daily limit) ·
PayFast: a fee per transaction.

---

## Part 1: GitHub (where the code lives)

1. Sign up at **github.com** (free).
2. **New repository** → name it e.g. `aurelia-studio` → **Private** → leave "Add a README" unticked →
   **Create repository**.
3. Let Claude reach it: open **https://claude.ai/connect-github**, connect your GitHub account and
   install the **Claude GitHub App** on the `aurelia-studio` repository (same page).
4. Send me the name, e.g. `yourname/aurelia-studio`. I upload the code there, and every future change
   I make goes there too.

## Part 2: Railway (the server)

1. Sign up at **railway.com** with your GitHub account, choose the **Hobby** plan and add a card.
2. **New Project → Deploy from GitHub repo** → pick `aurelia-studio`. Railway reads `railway.json` and
   builds from the `Dockerfile`; nothing to configure for the build. The first build takes a few minutes.
3. **A web address:** click the service → **Settings → Networking → Generate Domain**. If it asks for a
   port, enter **8040**.
4. **Add a volume** (the disk for the database and photos): on the project canvas, add a Volume and
   attach it to the service with mount path **`/data`**. Without it, everything is lost on each update.
5. **Variables** (service → Variables → Raw Editor), paste and fill in:

```ini
PORT=8040
ADMIN_EMAIL=<your email>
ADMIN_PASSWORD=<a strong password for your admin login>
ALLOW_SANDBOX_PAYMENTS=1
```

   That's all. The web address comes from Railway, a secret key is created on the volume the first time
   the app starts, and the proxy setting is switched on by itself. Railway redeploys after the change.
6. Open the address. Sign in at `/login` with your `ADMIN_EMAIL` and `ADMIN_PASSWORD`, then go to
   `/admin`. The **Launch checks** box at the top lists what's left, starting with deleting the
   `ADMIN_PASSWORD` variable (your account keeps the password).
7. **Test the whole journey** as a client: create an event, pay with the built-in test checkout
   (no real money; it's allowed because of `ALLOW_SANDBOX_PAYMENTS=1`), see it go live, RSVP as a guest.

## Part 3: your domain, aureliastudios.co.za (registered at GoDaddy)

GoDaddy's DNS can't point the bare domain (`aureliastudios.co.za`, without www) at Railway, so the
domain's DNS moves to Cloudflare, which is free and can. The domain stays registered at GoDaddy: you
keep renewing it there, and nothing else at GoDaddy changes.

1. **Cloudflare.** Sign up at **cloudflare.com** → **Add a domain** → `aureliastudios.co.za` → choose the
   **Free** plan → continue past the record scan. Cloudflare then shows **two nameservers** (they end in
   `ns.cloudflare.com`). Keep that tab open.
2. Still in Cloudflare → **DNS → Records**: delete the records it copied for `aureliastudios.co.za` (`@`)
   and `www`. They point at GoDaddy's "parked" page.
3. **GoDaddy.** Sign in → **My Products** → next to `aureliastudios.co.za`, **DNS** (or *Manage DNS*) →
   **Nameservers** → **Change nameservers** → **I'll use my own nameservers** → enter Cloudflare's two →
   **Save**. If GoDaddy shows **DNSSEC** as on, turn it off first.
   Cloudflare emails you when the domain is active: often within an hour, sometimes up to a day.
4. In Railway: click the service → **Settings → Networking → Custom Domain** → add `aureliastudios.co.za`,
   then add `www.aureliastudios.co.za` too. For each one Railway shows a **target** (it ends in
   `.up.railway.app`), and sometimes a TXT record to prove you own the domain.
5. In Cloudflare → **DNS → Records → Add record**, create exactly what Railway shows:

   | Type  | Name  | Target / content                                    | Proxy status         |
   | ----- | ----- | --------------------------------------------------- | -------------------- |
   | CNAME | `@`   | the target Railway shows for `aureliastudios.co.za`  | **DNS only** (grey)  |
   | CNAME | `www` | the target Railway shows for `www.aureliastudios.co.za` | **DNS only** (grey) |
   | TXT   | as Railway shows | as Railway shows (only if Railway lists one) | n/a            |

   "DNS only" matters: it lets Railway issue the HTTPS certificate.
6. Wait until Railway shows both domains with a green tick. That usually takes minutes, sometimes an hour.
7. Railway → **Variables** → add **`BASE_URL=https://aureliastudios.co.za`**. After the redeploy:
   - links in emails, receipts and payment returns use `https://aureliastudios.co.za`;
   - anyone who opens `www.aureliastudios.co.za` or the `.up.railway.app` address is sent to
     `https://aureliastudios.co.za` automatically. Only page views move; payment notifications, forms
     and the health check are never redirected.
8. Ask Claude to check the domain: it opens the site, the www redirect and a sample page.

## Part 4: email (Resend)

Railway's Hobby plan blocks ordinary email sending (SMTP), so the platform sends through Resend's
secure web connection instead.

1. Sign up at **resend.com** → **Domains → Add domain** → `aureliastudios.co.za`.
2. Add the DNS records Resend lists in Cloudflare (DNS only). Wait for Resend to show "Verified".
3. **API Keys → Create** (sending access) and copy it.
4. Railway variables:

```ini
EMAIL_PROVIDER=resend
RESEND_API_KEY=<the key from Resend>
EMAIL_FROM=Aurelia Studios <invites@aureliastudios.co.za>
EMAIL_REPLY_TO=invitesaurelia@gmail.com
```

5. Test: `/admin/emails` → open any template → **Send test to me**.

## Part 5: PayFast (real payments)

1. Open and verify a PayFast merchant account (see `GO-LIVE-GUIDE.md`, Part 2, for documents).
2. In PayFast, set a **passphrase** (developer or integration settings) and copy your merchant ID and key.
3. Railway variables, first against PayFast's sandbox:

```ini
PAYMENT_GATEWAY=payfast
PAYFAST_MERCHANT_ID=<id>
PAYFAST_MERCHANT_KEY=<key>
PAYFAST_PASSPHRASE=<passphrase>
PAYFAST_SANDBOX=1
PAYFAST_CHECK_IP=1
```

   PayFast tells the platform about each payment at `BASE_URL/webhooks/payments/payfast`; there's
   nothing to set up for that in PayFast.
4. Test a payment, see the order in `/admin/orders`, then switch to live: `PAYFAST_SANDBOX=0` and your
   live merchant details. **Delete `ALLOW_SANDBOX_PAYMENTS`** so nobody can publish without paying.

## Part 6: before you announce it

- [ ] Your domain opens with the padlock (HTTPS), and `BASE_URL` is that address
- [ ] `ADMIN_PASSWORD` and `ALLOW_SANDBOX_PAYMENTS` variables deleted
- [ ] `/admin` → **Launch checks** shows nothing left to fix
- [ ] A test email arrived; a PayFast payment published an event by itself
- [ ] Company address, VAT number and information officer set (`COMPANY_ADDRESS`, `VAT_NUMBER`,
      `INFORMATION_OFFICER_EMAIL`)
- [ ] Legal pages reviewed (`/privacy`, `/terms`, `/refunds`)
- [ ] Optional: `WHATSAPP_NUMBER`, `SOCIAL_INSTAGRAM`, `SOCIAL_FACEBOOK`, `SOCIAL_TIKTOK`
- [ ] A first backup downloaded: `/admin` → **Download a backup**. Do this weekly and keep the files
      somewhere safe (e.g. Google Drive)

## Updates

I push changes to GitHub; Railway rebuilds and redeploys by itself in a few minutes. Your data on the
`/data` volume stays. Database changes apply automatically on start.

## If something goes wrong

- Railway → service → **Deployments → View logs** shows what the app printed.
- The health check is `/healthz` (answers "ok" when the app and database are up).
- To restore a backup: stop the service, replace `aurelia.sqlite3` and the `uploads` folder on the volume
  with the ones from the zip, start it again. Ask me and I'll walk you through it.
