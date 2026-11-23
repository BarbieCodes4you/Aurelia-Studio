# Aurelia Studios: go-live guide (Netlify + PayFast)

This is for the version of the site that runs on Netlify today: the marketing pages, templates and the
full "Create your event" journey. Bookings, contact messages and set-up requests arrive through Netlify
Forms. Payments use PayFast. The full platform (accounts, RSVPs, dashboards) comes later; see
`AURELIA-COMPLETE.md`, section 3.

Menu names below can change slightly when Netlify or PayFast update their dashboards. If a name doesn't
match, look for the closest one, or send me a screenshot.

---

## Part 1: put the site on Netlify

1. Sign in at **app.netlify.com** (free; Google sign-in works).
2. Unzip `aurelia-site-netlify.zip`. You get a folder called `aurelia-site`.
3. Go to **app.netlify.com/drop** and drag the `aurelia-site` folder onto the page.
4. Rename the site: **Site configuration → Change site name**, e.g. `aurelia-invites`. Your address becomes
   `https://aurelia-invites.netlify.app`.

### Switch on the forms (once)

Netlify only collects form submissions when form detection is on.

1. Open your site → **Forms** (left menu).
2. If you see **Enable form detection**, click it.
3. Upload the folder again (**Deploys** → drag the `aurelia-site` folder onto the page), so Netlify finds
   the forms. Afterwards **Forms** lists four: `booking`, `booking-photos`, `contact` and `setup-help`.

### Get an email for every booking (once)

1. **Site configuration → Notifications → Emails and webhooks → Form submission notifications**.
2. **Add notification → Email notification**, choose "Any form", and enter `invitesaurelia@gmail.com`.

Each booking includes: reference (e.g. `AUR-7K2QD`), package and amount, the client's name, email and
mobile, every detail they entered, their guest list, and their photos as attachments. Gallery photos come
as separate `booking-photos` submissions with the same reference.

**Limits:** Netlify's free plan caps form submissions and uploaded files per month. Check
**Forms → Usage** after your first few bookings. If you get close, upgrade the Netlify plan.

### Test it yourself

Make a booking on your live site with your own email. You should see "Sent. We have your booking." and
receive the notification email. Also send yourself a message from **Contact** and a request from
**We'll set it up for you**.

---

## Part 2: PayFast

### What you need

- A PayFast account: **payfast.io → Sign up**. You can register as an individual (sole proprietor) or a
  company. Opening an account is free; PayFast charges a fee per transaction.
- Verification documents (FICA). PayFast shows the exact list for your account type during sign-up.
  Typically: ID, proof of address (less than three months old) and a bank confirmation letter; companies
  also need registration documents. Clear scans with matching names and addresses avoid delays.
- Upload them in the dashboard (**Account → Verification documents**). PayFast says verification takes
  about two business days once the documents are complete. You can't receive payments until then.

### Option A (recommended): a "Pay now" button for each package

The booking page then shows **Pay R12,999 securely**, and clients pay straight away.

1. In the PayFast dashboard, find **Pay Now buttons** and click **Generate** (or Create).
2. Make one button per package, with a fixed amount:

   | Package | Item name | Amount |
   |---|---|---|
   | Essential | Aurelia Studios Essential | 8999.00 |
   | Premium | Aurelia Studios Premium | 12999.00 |
   | Signature | Aurelia Studios Signature | 17999.00 |

3. If it asks for return or cancel pages, use your site address, e.g. `https://aurelia-invites.netlify.app/`.
4. Click **Create button** and copy the code it shows. If PayFast also gives you a link for the button,
   that works too.
5. Send me the three codes or links in this chat, or paste each into `preview_site/payment_links.json`
   (one per package). The button code and links contain only your public merchant ID.
   **Never paste your merchant key or passphrase in a chat.**
6. I rebuild the site, and you drag the new `aurelia-site` folder onto **Deploys** in Netlify. The address
   stays the same.

The site accepts only PayFast addresses, and keeps only the hidden payment fields from a pasted button.

### Option B: a payment request per client (works today, no changes)

Without buttons, the booking page tells the client you'll email a payment link. For each booking:

1. In the PayFast dashboard, open **Request money / Payment request**.
2. Enter the client's email (from the booking notification), the package amount, and the booking
   reference (e.g. `AUR-7K2QD`) in the description.
3. PayFast emails the client a secure link. You get an email when they pay.

### Knowing who has paid

PayFast emails you for every payment and lists it in the dashboard. Match the amount and the client's
email (or the reference) to the booking email from Netlify, then build and send their event website.

### Test first

Make one real payment for a small amount (e.g. a R5 test button) and refund it from the dashboard, or
use PayFast's sandbox (`sandbox.payfast.co.za`) to see the flow without real money.

---

## Part 3: later, on the full platform

When the full app is hosted (accounts, RSVPs, dashboards), PayFast connects directly: payment is
confirmed server-to-server and the website publishes itself. That needs your merchant ID, merchant key
and passphrase in the server settings (`AURELIA-COMPLETE.md`, section 5). They go in the hosting
settings, never in the code or a chat.

---

## Optional settings (full platform)

| Setting | What it does |
|---|---|
| `WHATSAPP_NUMBER` | Shows a "Chat on WhatsApp" button on every page and in the footer |
| `SOCIAL_INSTAGRAM`, `SOCIAL_FACEBOOK`, `SOCIAL_TIKTOK` | Footer icons, each shown only when set |

For the Netlify site, send me the WhatsApp number or social links and I'll rebuild with them.
