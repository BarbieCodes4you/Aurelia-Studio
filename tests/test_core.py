"""Accounts, marketing pages, the create flow, the wizard and payments."""
import json
import re
import unittest

from tests.helpers import Client, fresh_app, find, login, make_user  # noqa: F401  (helpers sets env first)

from app import auth, catalog, config, db, events
from app.services import payments


class AccountsTest(unittest.TestCase):
    def setUp(self):
        self.app = fresh_app("accounts")
        self.c = Client(self.app)

    def test_marketing_pages_render(self):
        for path in ["/", "/weddings", "/baby-celebrations", "/parties", "/celebrations", "/templates",
                     "/templates/atelier", "/pricing", "/how-it-works", "/faq", "/contact", "/privacy", "/terms",
                     "/refunds", "/create", "/login", "/register", "/forgot-password"]:
            r = self.c.get(path)
            self.assertEqual(r.status, 200, path)
            self.assertIn("<h1", r.text, path)
        self.assertEqual(self.c.get("/templates/does-not-exist").status, 404)

    def test_pricing_reads_packages_from_db(self):
        db.run("UPDATE packages SET price_cents = 1234500 WHERE code = 'premium'")
        self.assertIn("R12,345", self.c.get("/pricing").text)

    def test_register_login_logout(self):
        r = self.c.post("/register", {"name": "Lerato Dube", "email": "lerato@example.com", "password": "Sunrise-2027a",
                                      "password_confirm": "Sunrise-2027a", "terms": "1"})
        self.assertEqual(r.status, 303)
        self.assertIn("aur_sid", self.c.cookies)
        sent = db.q("SELECT template_key FROM email_logs WHERE to_email = 'lerato@example.com'")
        self.assertEqual({s["template_key"] for s in sent}, {"welcome", "verify_email"})
        self.assertEqual(self.c.get("/dashboard/billing").status, 200)
        self.c.post("/logout")
        self.assertEqual(self.c.get("/dashboard/billing").status, 303)
        r = self.c.post("/login", {"email": "lerato@example.com", "password": "wrong-password-1A"})
        self.assertIn("match an account", r.text)
        login(self.c, "lerato@example.com", "Sunrise-2027a")

    def test_register_validation(self):
        r = self.c.post("/register", {"name": "A", "email": "bad", "password": "short", "password_confirm": "x"})
        self.assertEqual(r.status, 200)
        self.assertIn("form-errors", r.text)
        self.assertEqual(db.val("SELECT COUNT(*) FROM users"), 0)

    def test_csrf_required(self):
        make_user()
        self.c.get("/login")
        r = self.c.request("POST", "/login", data={"email": "organiser@example.com", "password": "Correct-Horse-9", "_csrf": "x" * 32})
        self.assertEqual(r.status, 403)

    def test_password_reset_flow(self):
        make_user()
        self.c.post("/forgot-password", {"email": "organiser@example.com"})
        log = db.one("SELECT * FROM email_logs WHERE template_key = 'password_reset'")
        self.assertIsNotNone(log)
        # pull the token from the outbox file
        html = (config.OUTBOX_DIR / f"{log['outbox_file']}.html").read_text()
        token = find(r"/reset-password/([A-Za-z0-9_-]+)", html)
        r = self.c.post(f"/reset-password/{token}", {"password": "New-Password-77", "password_confirm": "New-Password-77"})
        self.assertEqual(r.status, 303)
        login(self.c, password="New-Password-77")
        self.assertIn("expired", self.c.get(f"/reset-password/{token}").text)   # single use

    def test_unknown_email_reset_gives_same_answer(self):
        r = self.c.post("/forgot-password", {"email": "nobody@example.com"})
        self.assertIn("Check your email", r.text)
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs"), 0)

    def test_contact_creates_support_request(self):
        r = self.c.post("/contact", {"name": "Sam", "email": "sam@example.com", "topic": "general", "message": "Hello, a question about pricing."})
        self.assertIn("reference is S-", r.text)
        self.assertEqual(db.val("SELECT COUNT(*) FROM support_requests"), 1)


class WizardTest(unittest.TestCase):
    def setUp(self):
        self.app = fresh_app("wizard")
        self.c = Client(self.app)
        self.user = make_user()
        login(self.c)

    def create(self, category="white-wedding", template="atelier", hosts="Lerato & Sipho"):
        r = self.c.post("/create", {"category": category, "template": template, "hosts": hosts})
        self.assertEqual(r.status, 303, r.text[:400])
        uid = find(r"/dashboard/events/([0-9a-f]+)/setup/1", r.location)
        return uid

    def test_create_asks_for_names(self):
        r = self.c.post("/create", {"category": "white-wedding", "template": "atelier"})
        self.assertEqual(r.status, 200)
        self.assertIn("Add the names", r.text)
        uid = self.create()
        ev = events.get(uid)
        self.assertEqual((ev["hosts"], ev["name"], ev["slug"]), ("Lerato & Sipho", "Lerato & Sipho's wedding", "lerato-and-sipho"))
        self.assertNotIn("Which package", self.c.get("/create").text)

    def test_create_without_account_needs_name_email_and_password(self):
        anon = Client(self.app)
        r = anon.post("/create", {"category": "baby-shower", "template": "bloom", "hosts": "Amahle"})
        self.assertEqual(r.status, 200)
        self.assertIn("Your name", r.text)
        r = anon.post("/create", {"category": "baby-shower", "template": "bloom", "hosts": "Amahle", "package": "essential",
                                  "contact_name": "Amahle Zulu", "contact_email": "amahle@example.com", "terms": "1"})
        self.assertEqual(r.status, 200)
        self.assertIn("Choose a password", r.text)
        r = anon.post("/create", {"category": "baby-shower", "template": "bloom", "hosts": "Amahle", "package": "essential",
                                  "contact_name": "Amahle Zulu", "contact_email": "amahle@example.com", "terms": "1",
                                  "password": "Nursery-2027b", "password_confirm": "Nursery-2027b"})
        self.assertEqual(r.status, 303, r.text[:300])
        self.assertIn("/setup/1", r.location)
        user = db.one("SELECT * FROM users WHERE email = ?", ("amahle@example.com",))
        self.assertNotEqual(user["password_hash"], "")
        ev = db.one("SELECT * FROM events WHERE owner_id = ?", (user["id"],))
        self.assertEqual((ev["selected_package"], ev["name"]), ("essential", "Amahle's baby shower"))
        self.assertEqual(anon.get(r.location).status, 200)      # signed in straight away

    def test_create_with_existing_email_sends_sign_in_link(self):
        anon = Client(self.app)
        r = anon.post("/create", {"category": "birthday", "template": "pulse", "hosts": "Kagiso's 40th", "contact_name": "Thandi",
                                  "contact_email": "organiser@example.com", "terms": "1"})
        self.assertEqual(r.status, 200)
        self.assertIn("sign-in link", r.text)
        log = db.one("SELECT * FROM email_logs WHERE to_email = ? AND template_key = 'login_link' ORDER BY id DESC", ("organiser@example.com",))
        self.assertIsNotNone(log)

    def test_full_wizard(self):
        uid = self.create()
        base = f"/dashboard/events/{uid}/setup"
        self.assertEqual(self.c.get(base + "/1").status, 200)
        r = self.c.post(base + "/1", {"hosts": "Lerato & Sipho", "event_date": "2027-03-14", "start_time": "14:00", "end_time": "23:00",
                                      "venue_name": "Avianto", "address": "Muldersdrift, Gauteng", "nav": "next"})
        self.assertEqual(r.location, base + "/2")
        ev = events.get(uid)
        self.assertEqual((ev["slug"], ev["venue"]["name"]), ("lerato-and-sipho", "Avianto"))
        r = self.c.post(base + "/2", {"template": "atelier", "palette": "stone", "font_pair": "cormorant-jost", "background": "paper",
                                      "monogram": "L&S", "w_welcome": "Together with their families", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.get(uid)["design"]["palette"], "stone")
        r = self.c.post(base + "/3", {"estimated": "150", "categories": ["Family", "Friends"], "categories_other": "Choir",
                                      "plus_one_policy": "per_guest", "plus_ones_default": "1", "rsvp_deadline": "2027-02-01",
                                      "children_allowed": "1", "max_children": "2", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertIn("Choir", events.get(uid)["guest_settings"]["categories"])
        # two days, each with its own items
        r = self.c.post(base + "/4", {"fn-0-name": "Ceremony", "fn-0-start": "14:00", "fn-1-name": "Reception", "fn-1-date": "2027-03-15",
                                      "si-0-time": "14:00", "si-0-title": "Ceremony begins", "si-0-day": "0",
                                      "si-1-time": "18:30", "si-1-title": "Dinner", "si-1-day": "1", "nav": "next"})
        self.assertEqual(r.status, 303, r.text[:500])
        eid = events.get(uid)["id"]
        funcs = events.functions(eid)
        self.assertEqual([f["name"] for f in funcs], ["Ceremony", "Reception"])
        self.assertEqual(funcs[0]["func_date"], "2027-03-14")                 # day 1 defaults to the event date
        sched = events.schedule(eid)
        self.assertEqual([(x["title"], x["function_name"], x["kind"]) for x in sched],
                         [("Ceremony begins", "Ceremony", "ceremony"), ("Dinner", "Reception", "meal")])
        r = self.c.post(base + "/5", {"menu_name": "Reception menu", "mi-0-course": "Main", "mi-0-name": "Lamb", "mi-0-selectable": "1",
                                      "mi-1-course": "Main", "mi-1-name": "Butternut risotto", "mi-1-tags": "Vegetarian", "mi-1-selectable": "1",
                                      "dietary_options": ["Vegetarian", "Halal"], "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(len(events.meal_options(eid)), 2)
        r = self.c.post(base + "/6", {"top_table": "head", "guest_tables": "mixed", "capacity": "10", "table_count": "15", "plan_now": "1", "nav": "next"})
        self.assertEqual(r.status, 303)
        tables = events.tables(eid)
        self.assertEqual(len(tables), 16)
        self.assertEqual((tables[0]["name"], tables[0]["shape"], tables[0]["notes"]), ("Head table", "long", "Top table"))
        self.assertEqual(sum(1 for t in tables if t["shape"] == "long"), 6)  # head table + every third guest table
        r = self.c.post(base + "/7", {"dress_code": "Black tie", "rg-0-name": "Yuppiechef", "rg-0-url": "yuppiechef.com",
                                      "ct-0-name": "Zanele", "ct-0-phone": "+27 82 000 0000", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(r.location, base + "/8")
        self.assertEqual(events.get(uid)["info"]["registry"][0]["url"], "https://yuppiechef.com")
        page8 = self.c.get(base + "/8").text
        self.assertIn("Pay R12,999", page8)
        self.assertIn("Show someone before you pay", page8)
        self.assertEqual(self.c.get(base + "/10").location, base + "/8")       # old links still land on the last step
        self.assertEqual(set(events.get(uid)["wizard_done"]), set(range(1, 8)))

    def test_single_day_programme_has_no_days(self):
        uid = self.create()
        r = self.c.post(f"/dashboard/events/{uid}/setup/4", {"fn-0-id": "", "si-0-time": "14:00", "si-0-title": "Speeches", "si-0-day": "0",
                                                             "si-1-time": "", "si-1-title": "", "si-1-day": "0", "nav": "next"})
        self.assertEqual(r.status, 303, r.text[:400])
        eid = events.get(uid)["id"]
        self.assertEqual(events.functions(eid), [])
        self.assertEqual([(x["title"], x["kind"], x["function_id"]) for x in events.schedule(eid)], [("Speeches", "speech", None)])

    def test_step1_validation(self):
        uid = self.create()
        r = self.c.post(f"/dashboard/events/{uid}/setup/1", {"hosts": "", "category": "nope", "event_date": "2001-01-01", "nav": "next"})
        self.assertEqual(r.status, 200)
        self.assertIn("form-errors", r.text)

    def test_essential_limits_days(self):
        uid = self.create()
        events.touch(events.get(uid)["id"], selected_package="essential")
        r = self.c.post(f"/dashboard/events/{uid}/setup/4", {"fn-0-name": "A", "fn-1-name": "B", "nav": "next"})
        self.assertIn("includes 1 day", r.text)

    def test_image_upload_checks_content(self):
        uid = self.create()
        r = self.c.multipart(f"/dashboard/events/{uid}/setup/2", {"template": "atelier", "nav": "stay"},
                             {"hero": ("evil.png", b"<script>alert(1)</script>", "image/png")})
        self.assertIn("Upload a JPG, PNG, WebP or GIF", r.text)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        r = self.c.multipart(f"/dashboard/events/{uid}/setup/2", {"template": "atelier", "nav": "stay"}, {"hero": ("ok.png", png, "image/png")})
        self.assertEqual(r.status, 303)
        self.assertEqual(len(events.uploads(events.get(uid)["id"], "hero")), 1)

    def test_other_users_cannot_open_event(self):
        uid = self.create()
        make_user("other@example.com")
        other = Client(self.app)
        login(other, "other@example.com")
        self.assertEqual(other.get(f"/dashboard/events/{uid}/setup/1").status, 404)
        self.assertEqual(other.post(f"/dashboard/events/{uid}/setup/1", {"name": "Hijack"}).status, 404)


class PaymentsTest(unittest.TestCase):
    def setUp(self):
        self.app = fresh_app("payments")
        self.c = Client(self.app)
        self.user = make_user()
        login(self.c)
        self.ev = events.create(self.user["id"], "white-wedding", "atelier", "Wedding", "Ayanda & Kabelo")
        events.touch(self.ev["id"], event_date="2027-06-01")

    def checkout(self, pkg="premium"):
        r = self.c.post(f"/dashboard/events/{self.ev['uid']}/checkout", {"package": pkg, "accept": "1"})
        self.assertEqual(r.status, 303, r.text[:300])
        self.assertTrue(r.location.startswith("/pay/sandbox/"))
        return r.location.rsplit("/", 1)[1]

    def test_checkout_requires_terms(self):
        r = self.c.post(f"/dashboard/events/{self.ev['uid']}/checkout", {"package": "premium"})
        self.assertIn("/setup/8", r.location)
        self.assertEqual(db.val("SELECT COUNT(*) FROM orders"), 0)

    def test_return_page_alone_does_not_pay(self):
        order_uid = self.checkout()
        r = self.c.get(f"/dashboard/events/{self.ev['uid']}/payment/{order_uid}")
        self.assertIn("Waiting for the payment gateway", r.text)
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (order_uid,)), "pending")
        self.assertIsNone(events.get(self.ev["uid"])["paid_package"])
        self.assertEqual(Client(self.app).get(f"/events/{events.get(self.ev['uid'])['slug']}").status, 404)

    def test_sandbox_approve_publishes(self):
        order_uid = self.checkout()
        r = self.c.post(f"/pay/sandbox/{order_uid}", {"decision": "approve"})
        self.assertEqual(r.status, 303)
        order = db.one("SELECT * FROM orders WHERE uid = ?", (order_uid,))
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["mode"], "sandbox")
        self.assertEqual(order["amount_cents"], 1_299_900)
        self.assertTrue(order["invoice_no"].startswith("INV-"))
        ev = events.get(self.ev["uid"])
        self.assertEqual(ev["paid_package"], "premium")
        self.assertEqual(ev["status"], "published")
        self.assertTrue(ev["hosting_until"])
        keys = {r["template_key"] for r in db.q("SELECT template_key FROM email_logs")}
        self.assertTrue({"payment_confirmation", "website_published"} <= keys)
        self.assertFalse({"event_link", "setup_instructions"} & keys)        # one "is live" email; next steps come later
        self.assertIn("Payment confirmed", self.c.get(f"/dashboard/events/{self.ev['uid']}/payment/{order_uid}").text)
        self.assertEqual(self.c.get(f"/dashboard/orders/{order_uid}/receipt").status, 200)

    def test_vat_only_when_registered(self):
        from app import config
        order_uid = self.checkout()
        self.c.post(f"/pay/sandbox/{order_uid}", {"decision": "approve"})
        db.run("UPDATE orders SET mode = 'live' WHERE uid = ?", (order_uid,))
        url = f"/dashboard/orders/{order_uid}/receipt"
        old = (config.VAT_NUMBER, config.VAT_REGISTERED)
        try:
            config.VAT_NUMBER, config.VAT_REGISTERED = "", False
            t = self.c.get(url).text
            self.assertNotIn("Tax invoice", t)
            self.assertNotIn("VAT", t)
            self.assertNotIn("VAT", self.c.get("/pricing").text)
            self.assertEqual(self.c.get(url + "?format=pdf").status, 200)
            config.VAT_NUMBER, config.VAT_REGISTERED = "4123456789", True
            t = self.c.get(url).text
            self.assertIn("Tax invoice", t)
            self.assertIn("4123456789", t)
            self.assertIn("VAT incl.", self.c.get("/pricing").text)
        finally:
            config.VAT_NUMBER, config.VAT_REGISTERED = old

    def test_decline_keeps_draft(self):
        order_uid = self.checkout()
        self.c.post(f"/pay/sandbox/{order_uid}", {"decision": "decline"})
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (order_uid,)), "failed")
        self.assertIsNone(events.get(self.ev["uid"])["paid_package"])

    def test_forged_and_mismatched_webhooks_rejected(self):
        order_uid = self.checkout()
        order = db.one("SELECT * FROM orders WHERE uid = ?", (order_uid,))
        gw = payments.SandboxGateway()
        body, sig = gw.build_notification(order, "approve")
        r = self.c.request("POST", "/webhooks/payments/sandbox", body=body, headers={"X-Aurelia-Signature": "0" * 64, "Content-Type": "application/json"})
        self.assertEqual(r.status, 400)
        data = json.loads(body)
        data["amount_cents"] = 100
        cheap = json.dumps(data, separators=(",", ":")).encode()
        r = self.c.request("POST", "/webhooks/payments/sandbox", body=cheap, headers={"X-Aurelia-Signature": gw.sign(cheap), "Content-Type": "application/json"})
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (order_uid,)), "pending")
        r = self.c.request("POST", "/webhooks/payments/sandbox", body=body, headers={"X-Aurelia-Signature": sig, "Content-Type": "application/json"})
        self.assertEqual(r.status, 200)
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (order_uid,)), "paid")
        # replay is recorded but not applied twice
        self.c.request("POST", "/webhooks/payments/sandbox", body=body, headers={"X-Aurelia-Signature": sig, "Content-Type": "application/json"})
        self.assertEqual(db.val("SELECT COUNT(*) FROM orders WHERE status = 'paid'"), 1)
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'payment_confirmation'"), 1)

    def test_upgrade_pays_difference(self):
        order_uid = self.checkout("essential")
        self.c.post(f"/pay/sandbox/{order_uid}", {"decision": "approve"})
        order_uid = self.checkout("signature")
        self.assertEqual(db.val("SELECT amount_cents FROM orders WHERE uid = ?", (order_uid,)), 1_799_900 - 899_900)
        r = self.c.post(f"/dashboard/events/{self.ev['uid']}/checkout", {"package": "essential", "accept": "1"})
        self.assertIn("/setup/8", r.location)

    def test_payfast_signature(self):
        sig = payments.PayFastGateway.signature([("merchant_id", "10000100"), ("amount", "100.00"), ("item_name", "Test item"), ("empty", "")], "pass phrase")
        self.assertEqual(len(sig), 32)
        self.assertNotEqual(sig, payments.PayFastGateway.signature([("merchant_id", "10000100"), ("amount", "100.01"), ("item_name", "Test item")], "pass phrase"))

    def test_production_refuses_sandbox_checkout(self):
        old = config.ALLOW_SANDBOX_PAYMENTS
        config.ALLOW_SANDBOX_PAYMENTS = False
        try:
            r = self.c.post(f"/dashboard/events/{self.ev['uid']}/checkout", {"package": "premium", "accept": "1"})
            self.assertIn("/setup/8", r.location)
            self.assertEqual(db.val("SELECT COUNT(*) FROM orders"), 0)
        finally:
            config.ALLOW_SANDBOX_PAYMENTS = old

    def test_someone_elses_order_is_hidden(self):
        order_uid = self.checkout()
        make_user("other@example.com")
        other = Client(self.app)
        login(other, "other@example.com")
        self.assertEqual(other.get(f"/pay/sandbox/{order_uid}").status, 404)
        self.assertEqual(other.post(f"/pay/sandbox/{order_uid}", {"decision": "approve"}).status, 404)
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (order_uid,)), "pending")


if __name__ == "__main__":
    unittest.main()


class HostingRuleTest(unittest.TestCase):
    def test_site_never_ends_before_a_month_after_the_event(self):
        fresh_app("hosting")
        ev = {"event_date": "2028-06-01"}
        self.assertEqual(events.hosting_end(ev, 6, start=__import__("datetime").date(2026, 11, 16)), "2028-07-02")
        self.assertEqual(events.hosting_end({"event_date": "2027-01-10"}, 6, start=__import__("datetime").date(2026, 11, 16)), "2027-05-18")
        self.assertEqual(events.hosting_end({"event_date": ""}, 6, start=__import__("datetime").date(2026, 11, 16)), "2027-05-18")


class HostingDefaultsTest(unittest.TestCase):
    """On Railway the address and the proxy come from the platform, so the owner sets fewer variables."""

    def settings(self, **extra):
        import os
        import subprocess
        import sys
        import tempfile
        env = {k: v for k, v in os.environ.items()
               if k not in ("BASE_URL", "TRUST_PROXY", "SECRET_KEY") and not k.startswith("RAILWAY_")}
        env.update(extra, AURELIA_DATA_DIR=tempfile.mkdtemp())
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        code = "from app import config; print(config.BASE_URL, config.TRUST_PROXY, len(config.SECRET_KEY))"
        out = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, check=True)
        return out.stdout.split()

    def test_railway_needs_no_address_proxy_or_secret_settings(self):
        rw = {"RAILWAY_ENVIRONMENT_NAME": "production", "RAILWAY_PUBLIC_DOMAIN": "aurelia.up.railway.app"}
        self.assertEqual(self.settings(**rw), ["https://aurelia.up.railway.app", "True", "64"])
        self.assertEqual(self.settings(**rw, BASE_URL="https://aureliastudio.co.za")[0], "https://aureliastudio.co.za")
        self.assertEqual(self.settings()[:2], ["http://127.0.0.1:8040", "False"])     # elsewhere: nothing assumed
