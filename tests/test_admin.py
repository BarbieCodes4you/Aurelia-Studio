"""Admin dashboard permissions and actions, plus the background scheduler."""
from __future__ import annotations

import itertools
import unittest
from datetime import date, timedelta

from tests.helpers import Client, fresh_app, make_user

from app import config, auth, catalog, db, events
from app.services import scheduler
from app.views import admin as admin_views

_n = itertools.count(1)

ADMIN_GETS = ["/admin", "/admin/customers", "/admin/events", "/admin/orders", "/admin/hosting", "/admin/packages",
              "/admin/packages/premium", "/admin/templates", "/admin/templates/atelier", "/admin/categories",
              "/admin/categories/white-wedding", "/admin/emails", "/admin/emails/welcome", "/admin/emails/welcome/preview",
              "/admin/outbox", "/admin/support", "/admin/audit"]


def signed_in(app, user) -> Client:
    c = Client(app)
    c.cookies[auth.SESSION_COOKIE] = auth.create_session(user["id"])
    c.csrf  # prime the CSRF cookie before the first POST
    return c


def new_user(role="customer"):
    k = next(_n)
    return make_user(email=f"user{k}@example.com", name=f"User {k}", role=role)


def live_event(owner, **over):
    ev = events.create(owner["id"], "white-wedding", "atelier", "Test Wedding", "Sarah and John")
    fields = {"status": "published", "paid_package": "premium", "published_at": db.now(),
              "hosting_until": (date.today() + timedelta(days=200)).isoformat(),
              "event_date": (date.today() + timedelta(days=60)).isoformat()}
    fields.update(over)
    events.touch(ev["id"], **fields)
    return events.by_id(ev["id"])


def add_order(owner, ev, mode, status="paid", cents=1_299_900):
    uid = f"ord_{next(_n)}"
    db.insert("orders", {"uid": uid, "user_id": owner["id"], "event_id": ev["id"], "package_code": "premium",
                         "description": "Premium Experience", "amount_cents": cents, "currency": "ZAR", "status": status,
                         "gateway": "sandbox" if mode == "sandbox" else "payfast", "mode": mode,
                         "created_at": db.now(), "updated_at": db.now(), "paid_at": db.now() if status == "paid" else None})
    return uid


def add_guest(ev, email, consent=1, unsubscribed=None, status="pending"):
    return db.insert("guests", {"event_id": ev["id"], "token": events.new_guest_token(), "first_name": "Guest",
                                "email": email, "email_consent": consent, "unsubscribed_at": unsubscribed, "status": status,
                                "created_at": db.now(), "updated_at": db.now()})


def sent(key, event_id=None):
    if event_id is None:
        return db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = ? AND status = 'sent'", (key,), 0)
    return db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = ? AND status = 'sent' AND event_id = ?",
                  (key, event_id), 0)


class AdminPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("admin-perm")

    def test_customer_gets_403_everywhere(self):
        c = signed_in(self.app, new_user())
        for path in ADMIN_GETS:
            r = c.get(path)
            self.assertEqual(r.status, 403, path)
        r = c.post("/admin/packages/premium", {"name": "Hacked", "price": "1"})
        self.assertEqual(r.status, 403)
        self.assertNotEqual(catalog.package("premium")["name"], "Hacked")

    def test_visitor_redirected_to_login(self):
        r = Client(self.app).get("/admin")
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith("/login"))

    def test_admin_pages_render(self):
        admin = new_user("admin")
        owner = new_user()
        ev = live_event(owner)
        uid = add_order(owner, ev, "live")
        db.insert("support_requests", {"name": "A", "email": "a@example.com", "message": "Help", "created_at": db.now(),
                                       "updated_at": db.now()})
        c = signed_in(self.app, admin)
        for path in ADMIN_GETS + [f"/admin/events/{ev['uid']}", f"/admin/orders/{uid}", f"/admin/customers/{owner['id']}",
                                  "/admin/support/1"]:
            r = c.get(path)
            self.assertEqual(r.status, 200, (path, r.text[:300]))
        preview = c.get("/admin/emails/welcome/preview")
        self.assertIn("sandbox", preview.header("Content-Security-Policy"))


class AdminActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("admin-actions")

    def setUp(self):
        self.admin = new_user("admin")
        self.c = signed_in(self.app, self.admin)

    def test_launch_checks_list_what_is_left(self):
        from unittest import mock
        r = self.c.get("/admin")
        self.assertIn("Launch checks", r.text)
        self.assertIn("Emails aren", r.text)                      # outbox in tests
        self.assertIn("Payments are in test mode", r.text)
        from app.views import admin as admin_view
        with mock.patch.object(config, "ON_RAILWAY", True), mock.patch("os.path.ismount", return_value=False):
            self.assertTrue(any("No volume is attached" in t for _, t in admin_view.launch_checks()))
        with mock.patch.object(config, "BASE_URL", "https://aurelia.up.railway.app"):
            self.assertTrue(any("Railway's address" in t for _, t in admin_view.launch_checks()))

    def test_launch_checks_catch_example_values_and_missing_keys(self):
        from unittest import mock
        from app.views import admin as admin_view
        secret = "<id>"
        env = {"PAYFAST_MERCHANT_ID": secret, "RESEND_API_KEY": "re_...", "EMAIL_FROM": "Aurelia <invites@your-domain.co.za>"}
        with mock.patch.dict("os.environ", env), mock.patch.object(config, "PAYMENT_GATEWAY", "payfast"), \
                mock.patch.object(config, "PAYFAST_MERCHANT_ID", secret), mock.patch.object(config, "PAYFAST_MERCHANT_KEY", ""), \
                mock.patch.object(config, "EMAIL_PROVIDER", "resend"), mock.patch.object(config, "RESEND_API_KEY", "re_..."):
            texts = [t for _, t in admin_view.launch_checks()]
        for key in env:
            self.assertTrue(any(t.startswith(key + " still holds example text") for t in texts), key)
        self.assertTrue(any("no RESEND_API_KEY" in t for t in texts))
        self.assertTrue(any("merchant ID or key is missing" in t for t in texts))
        self.assertFalse(any(secret in t for t in texts))                  # values are never shown
        with mock.patch.object(config, "ON_RAILWAY", True), mock.patch.object(config, "APP_ENV", "development"), \
                mock.patch("os.path.ismount", return_value=True):
            self.assertTrue(any("APP_ENV isn't production" in t for _, t in admin_view.launch_checks()))

    def test_edit_package_price(self):
        p = catalog.package("essential")
        data = {"name": p["name"], "tagline": p["tagline"], "price": "9 499.00", "rank": "1", "active": "1",
                "features": db.loads(p["features"], []), "bullets": "Line one\nLine two",
                **{f"limit_{k}": v for k, v in db.loads(p["limits"], {}).items()}}
        r = self.c.post("/admin/packages/essential", data)
        self.assertEqual(r.status, 303, r.text[:500])
        p = catalog.package("essential")
        self.assertEqual(p["price_cents"], 949_900)
        self.assertEqual(db.loads(p["bullets"]), ["Line one", "Line two"])
        self.assertTrue(db.val("SELECT COUNT(*) FROM audit_log WHERE action = 'package.update'"))

    def test_bad_price_rejected(self):
        r = self.c.post("/admin/packages/premium", {"name": "Premium", "price": "abc", "rank": "2"})
        self.assertEqual(r.status, 400)
        self.assertEqual(catalog.package("premium")["price_cents"], 1_299_900)

    def test_suspend_makes_event_not_live(self):
        ev = live_event(new_user())
        self.assertTrue(events.is_live(ev))
        r = self.c.post(f"/admin/events/{ev['uid']}/suspend", {"reason": "Payment dispute"})
        self.assertEqual(r.status, 303)
        ev = events.get(ev["uid"])
        self.assertEqual(ev["status"], "suspended")
        self.assertFalse(events.is_live(ev))
        self.c.post(f"/admin/events/{ev['uid']}/reactivate")
        self.assertEqual(events.get(ev["uid"])["status"], "published")

    def test_revenue_excludes_sandbox(self):
        owner = new_user()
        ev = live_event(owner)
        before = admin_views.revenue_stats()
        add_order(owner, ev, "live", cents=1_299_900)
        add_order(owner, ev, "sandbox", cents=1_799_900)
        add_order(owner, ev, "live", status="pending", cents=899_900)
        after = admin_views.revenue_stats()
        self.assertEqual(after["live"]["cents"] - before["live"]["cents"], 1_299_900)
        self.assertEqual(after["sandbox"]["cents"] - before["sandbox"]["cents"], 1_799_900)

    def test_admin_cannot_mark_order_paid(self):
        owner = new_user()
        ev = live_event(owner)
        uid = add_order(owner, ev, "live", status="pending")
        for path, data in [(f"/admin/orders/{uid}/refund", {}), (f"/admin/orders/{uid}/paid", {}),
                           (f"/admin/orders/{uid}", {"status": "paid"})]:
            self.c.post(path, data)
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (uid,)), "pending")
        paid_uid = add_order(owner, ev, "live")
        self.c.post(f"/admin/orders/{paid_uid}/refund", {"note": "Customer cancelled"})
        self.assertEqual(db.val("SELECT status FROM orders WHERE uid = ?", (paid_uid,)), "refunded")

    def test_cannot_demote_self(self):
        self.c.post(f"/admin/customers/{self.admin['id']}/role", {"role": "customer"})
        self.assertEqual(db.val("SELECT role FROM users WHERE id = ?", (self.admin["id"],)), "admin")

    def test_suspend_customer_ends_sessions(self):
        cust = new_user()
        other = signed_in(self.app, cust)
        self.assertEqual(other.get("/dashboard/billing").status in (200, 404, 303), True)
        self.c.post(f"/admin/customers/{cust['id']}/status", {"status": "suspended"})
        self.assertEqual(db.val("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (cust["id"],)), 0)

    def test_email_template_edit(self):
        r = self.c.post("/admin/emails/welcome", {"subject": "Hello {{first_name}}", "body": "Body text", "active": "1"})
        self.assertEqual(r.status, 303)
        self.assertEqual(db.val("SELECT subject FROM email_templates WHERE key = 'welcome'"), "Hello {{first_name}}")
        self.c.post("/admin/emails/welcome/reset")
        self.assertNotEqual(db.val("SELECT subject FROM email_templates WHERE key = 'welcome'"), "Hello {{first_name}}")


class Scheduler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("scheduler")

    def monday(self):
        d = date.today()
        return d + timedelta(days=(7 - d.weekday()) % 7 or 7)

    def test_weekly_summary_sent_once(self):
        owner = new_user()
        ev = live_event(owner, event_date=(date.today() + timedelta(days=90)).isoformat())
        events.save_json(ev["id"], "report_prefs", {"summary": "weekly", "new_rsvp": True, "auto_reminders": False})
        mon = self.monday()
        scheduler.run_once(mon)
        self.assertEqual(sent("rsvp_summary", ev["id"]), 1)
        scheduler.run_once(mon)
        self.assertEqual(sent("rsvp_summary", ev["id"]), 1)
        scheduler.run_once(mon + timedelta(days=1))  # Tuesday: no weekly summary
        self.assertEqual(sent("rsvp_summary", ev["id"]), 1)
        scheduler.run_once(mon + timedelta(days=7))  # next Monday: a new week
        self.assertEqual(sent("rsvp_summary", ev["id"]), 2)

    def test_hosting_expiry(self):
        ev = live_event(new_user(), hosting_until=(date.today() - timedelta(days=1)).isoformat())
        counts = scheduler.run_once()
        self.assertGreaterEqual(counts["hosting_expired"], 1)
        self.assertEqual(events.get(ev["uid"])["status"], "unpublished")

    def test_auto_reminders_respect_consent(self):
        deadline = date.today() + timedelta(days=5)
        ev = live_event(new_user())
        events.save_json(ev["id"], "report_prefs", {"summary": "none", "auto_reminders": True})
        gs = ev["guest_settings"]
        gs["rsvp_deadline"] = deadline.isoformat()
        events.save_json(ev["id"], "guest_settings", gs)
        ok = add_guest(ev, "yes@example.com")
        no_consent = add_guest(ev, "no@example.com", consent=0)
        unsub = add_guest(ev, "unsub@example.com", unsubscribed=db.now())
        replied = add_guest(ev, "done@example.com", status="attending")
        scheduler.run_once()
        scheduler.run_once()
        got = {r["guest_id"] for r in db.q("SELECT guest_id FROM email_logs WHERE template_key = 'guest_reminder' AND event_id = ?", (ev["id"],))}
        self.assertEqual(got, {ok})
        self.assertNotIn(no_consent, got)
        self.assertNotIn(unsub, got)
        self.assertNotIn(replied, got)

    def test_no_auto_reminders_on_essential(self):
        ev = live_event(new_user(), paid_package="essential")
        events.save_json(ev["id"], "report_prefs", {"summary": "none", "auto_reminders": True})
        gs = ev["guest_settings"]
        gs["rsvp_deadline"] = (date.today() + timedelta(days=3)).isoformat()
        events.save_json(ev["id"], "guest_settings", gs)
        add_guest(ev, "ess@example.com")
        scheduler.run_once()
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'guest_reminder' AND event_id = ?", (ev["id"],)), 0)

    def test_suspended_and_demo_events_get_no_email(self):
        owner = new_user()
        ev = live_event(owner, event_date=(date.today() + timedelta(days=7)).isoformat())
        events.touch(ev["id"], status="suspended")
        demo = live_event(owner, event_date=(date.today() + timedelta(days=7)).isoformat(), is_demo=1)
        scheduler.run_once()
        n = db.val("SELECT COUNT(*) FROM email_logs WHERE event_id IN (?, ?)", (ev["id"], demo["id"]), 0)
        self.assertEqual(n, 0)

    def test_next_steps_email_the_day_after_publishing_only_when_something_is_left(self):
        today = date.today()
        busy = live_event(new_user())
        add_guest(busy, "a@example.com")                      # guests added, invitations not sent yet
        done = live_event(new_user())
        events.save_json(done["id"], "venue", {"name": "Oakhaven", "address": "Helshoogte Road, Stellenbosch"})
        g = add_guest(done, "b@example.com", status="attending")
        db.run("UPDATE guests SET invited_at = ? WHERE id = ?", (db.now(), g))
        db.run("INSERT INTO seating_tables (event_id, name, capacity, shape, pos_x, pos_y, sort) VALUES (?, 'T1', 10, 'round', 50, 44, 0)", (done["id"],))
        db.run("INSERT INTO seat_assignments (guest_id, table_id, event_id, assigned_at) VALUES (?, last_insert_rowid(), ?, ?)", (g, done["id"], db.now()))
        scheduler.run_once(today)                             # publish day: nothing yet
        self.assertEqual(sent("setup_instructions", busy["id"]), 0)
        scheduler.run_once(today + timedelta(days=1))
        scheduler.run_once(today + timedelta(days=2))
        self.assertEqual(sent("setup_instructions", busy["id"]), 1)     # once
        self.assertEqual(sent("setup_instructions", done["id"]), 0)     # nothing left to do: no email
        html = db.val("SELECT subject FROM email_logs WHERE template_key = 'setup_instructions' AND event_id = ?", (busy["id"],))
        self.assertIn("Next steps", html)

    def test_event_reminder_and_post_event(self):
        ev = live_event(new_user(), event_date=(date.today() + timedelta(days=7)).isoformat())
        scheduler.run_once()
        scheduler.run_once()
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'event_reminder' AND event_id = ?", (ev["id"],)), 1)
        scheduler.run_once(date.today() + timedelta(days=8))
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'post_event' AND event_id = ?", (ev["id"],)), 1)


if __name__ == "__main__":
    unittest.main()


class BackupTest(unittest.TestCase):
    def test_admin_can_download_backup_others_cannot(self):
        import io
        import zipfile
        from tests.helpers import Client, fresh_app, login, make_user
        app = fresh_app("backup")
        make_user("boss@example.com", role="admin")
        make_user("guest@example.com")
        c = Client(app)
        login(c, "boss@example.com")
        r = c.get("/admin/backup")
        self.assertEqual(r.status, 200)
        names = zipfile.ZipFile(io.BytesIO(r.body)).namelist()
        self.assertIn("aurelia.sqlite3", names)
        self.assertIn("README.txt", names)
        other = Client(app)
        login(other, "guest@example.com")
        self.assertNotEqual(other.get("/admin/backup").status, 200)

