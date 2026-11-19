# Aurelia Studio: launch on Railway with your own domain

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

## Part 3: your domain

1. **Buy the domain** at a South African registrar (for a `.co.za`, e.g. Domains.co.za, Afrihost or
   Xneelo). Compare yearly prices; you only need the domain, not their hosting or email.
2. **Cloudflare (free) for DNS.** Railway needs a DNS provider that can point the bare domain
   (`aureliastudio.co.za`, without www) at it; Cloudflare can. Sign up at **cloudflare.com** → **Add a
   site** → your domain → Free plan. Cloudflare gives you two **nameservers**.
3. At your registrar, replace the domain's nameservers with Cloudflare's two. This can take a few hours.
4. In Railway: service → Settings → Networking → **Custom Domain** → add `aureliastudio.co.za`, then add
   `www.aureliastudio.co.za` too. For each, Railway shows the DNS record to create.
5. In Cloudflare → DNS → **Add record** exactly as Railway shows (usually a CNAME; for the bare domain use
   name `@`). Set the cloud icon to **DNS only** (grey) so Railway can issue the HTTPS certificate.
6. When Railway shows both domains as active, add the variable **`BASE_URL=https://aureliastudio.co.za`**, so
   links in emails and payment returns use your domain.

## Part 4: email (Resend)

Railway's Hobby plan blocks ordinary email sending (SMTP), so the platform sends through Resend's
secure web connection instead.

1. Sign up at **resend.com** → **Domains → Add domain** → your domain.
2. Add the DNS records Resend lists in Cloudflare (DNS only). Wait for Resend to show "Verified".
3. **API Keys → Create** (sending access) and copy it.
4. Railway variables:

```ini
EMAIL_PROVIDER=resend
RESEND_API_KEY=<the key from Resend>
EMAIL_FROM=Aurelia Studio <invites@aureliastudio.co.za>
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
