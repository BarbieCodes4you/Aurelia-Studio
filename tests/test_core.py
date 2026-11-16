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
        db.run("UPDATE packages SET price_cents = 1_234_500 WHERE code = 'premium'")
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

    def create(self, category="white-wedding", template="atelier"):
        r = self.c.post("/create", {"category": category, "template": template, "name": "Our wedding"})
        self.assertEqual(r.status, 303, r.text[:400])
        uid = find(r"/dashboard/events/([0-9a-f]+)/setup/1", r.location)
        return uid

    def test_create_requires_login_and_preserves_choice(self):
        anon = Client(self.app)
        r = anon.post("/create", {"category": "baby-shower", "template": "bloom", "name": "Shower"})
        self.assertEqual(r.status, 303)
        self.assertIn("/register?next=", r.location)
        self.assertIn("baby-shower", r.location)

    def test_full_wizard(self):
        uid = self.create()
        base = f"/dashboard/events/{uid}/setup"
        self.assertEqual(self.c.get(base + "/1").status, 200)
        r = self.c.post(base + "/1", {"name": "Our wedding", "category": "white-wedding", "hosts": "Lerato & Sipho",
                                      "event_date": "2027-03-14", "start_time": "14:00", "end_time": "23:00", "nav": "next"})
        self.assertEqual(r.location, base + "/2")
        ev = events.get(uid)
        self.assertEqual(ev["slug"], "lerato-and-sipho")
        r = self.c.post(base + "/2", {"venue_name": "Avianto", "address": "Muldersdrift, Gauteng", "nav": "next"})
        self.assertEqual(r.status, 303)
        r = self.c.post(base + "/3", {"template": "atelier", "palette": "stone", "font_pair": "cormorant-jost", "background": "paper",
                                      "monogram": "L&S", "w_welcome": "Together with their families", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.get(uid)["design"]["palette"], "stone")
        r = self.c.post(base + "/4", {"estimated": "150", "categories": ["Family", "Friends"], "categories_other": "Choir",
                                      "plus_one_policy": "per_guest", "plus_ones_default": "1", "rsvp_deadline": "2027-02-01",
                                      "children_allowed": "1", "max_children": "2", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertIn("Choir", events.get(uid)["guest_settings"]["categories"])
        r = self.c.post(base + "/5", {"fn-0-name": "Ceremony", "fn-0-start": "14:00", "fn-1-name": "Reception", "fn-1-start": "17:00",
                                      "si-0-time": "14:00", "si-0-title": "Ceremony begins", "si-0-kind": "ceremony",
                                      "si-1-time": "18:30", "si-1-title": "Dinner", "si-1-kind": "meal", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(len(events.functions(events.get(uid)["id"])), 2)
        self.assertEqual(len(events.schedule(events.get(uid)["id"])), 2)
        r = self.c.post(base + "/6", {"menu_name": "Reception menu", "mi-0-course": "Main", "mi-0-name": "Lamb", "mi-0-selectable": "1",
                                      "mi-1-course": "Main", "mi-1-name": "Butternut risotto", "mi-1-tags": "Vegetarian", "mi-1-selectable": "1",
                                      "dietary_options": ["Vegetarian", "Halal"], "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(len(events.meal_options(events.get(uid)["id"])), 2)
        r = self.c.post(base + "/7", {"table_count": "15", "capacity": "10", "shape": "round", "apply_capacity": "1",
                                      "table_names": "Head table\nProtea", "nav": "next"})
        self.assertEqual(r.status, 303)
        tables = events.tables(events.get(uid)["id"])
        self.assertEqual(len(tables), 15)
        self.assertEqual(tables[0]["name"], "Head table")
        r = self.c.post(base + "/8", {"dress_code": "Black tie", "rg-0-name": "Yuppiechef", "rg-0-url": "yuppiechef.com",
                                      "ct-0-name": "Zanele", "ct-0-phone": "+27 82 000 0000", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.get(uid)["info"]["registry"][0]["url"], "https://yuppiechef.com")
        self.assertEqual(self.c.get(base + "/9").status, 200)
        self.assertEqual(self.c.get(base + "/10").status, 200)
        self.assertEqual(set(events.get(uid)["wizard_done"]), set(range(1, 9)))

    def test_step1_validation(self):
        uid = self.create()
        r = self.c.post(f"/dashboard/events/{uid}/setup/1", {"name": "", "category": "nope", "event_date": "2001-01-01", "nav": "next"})
        self.assertEqual(r.status, 200)
        self.assertIn("form-errors", r.text)

    def test_essential_limits_functions(self):
        uid = self.create()
        events.touch(events.get(uid)["id"], selected_package="essential")
        r = self.c.post(f"/dashboard/events/{uid}/setup/5", {"fn-0-name": "A", "fn-1-name": "B", "nav": "next"})
        self.assertIn("includes 1 event function", r.text)

    def test_image_upload_checks_content(self):
        uid = self.create()
        r = self.c.multipart(f"/dashboard/events/{uid}/setup/3", {"template": "atelier", "nav": "stay"},
                             {"hero": ("evil.png", b"<script>alert(1)</script>", "image/png")})
        self.assertIn("Upload a JPG, PNG, WebP or GIF", r.text)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        r = self.c.multipart(f"/dashboard/events/{uid}/setup/3", {"template": "atelier", "nav": "stay"}, {"hero": ("ok.png", png, "image/png")})
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
        self.assertIn("/setup/10", r.location)
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
        self.assertTrue({"payment_confirmation", "website_published", "event_link", "setup_instructions"} <= keys)
        self.assertIn("Payment confirmed", self.c.get(f"/dashboard/events/{self.ev['uid']}/payment/{order_uid}").text)
        self.assertEqual(self.c.get(f"/dashboard/orders/{order_uid}/receipt").status, 200)

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
        self.assertIn("/setup/10", r.location)

    def test_payfast_signature(self):
        sig = payments.PayFastGateway.signature([("merchant_id", "10000100"), ("amount", "100.00"), ("item_name", "Test item"), ("empty", "")], "pass phrase")
        self.assertEqual(len(sig), 32)
        self.assertNotEqual(sig, payments.PayFastGateway.signature([("merchant_id", "10000100"), ("amount", "100.01"), ("item_name", "Test item")], "pass phrase"))

    def test_production_refuses_sandbox_checkout(self):
        old = config.ALLOW_SANDBOX_PAYMENTS
        config.ALLOW_SANDBOX_PAYMENTS = False
        try:
            r = self.c.post(f"/dashboard/events/{self.ev['uid']}/checkout", {"package": "premium", "accept": "1"})
            self.assertIn("/setup/10", r.location)
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
