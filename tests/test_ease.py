"""Tests for the ease-of-use round (2026-11): sign-in links, draft previews, pasting guests and menus,
sample programmes, package gaps, the WhatsApp queue, next steps and the set-up help request."""
from __future__ import annotations

import re
import unittest

from tests.helpers import Client, fresh_app, make_user
from tests.test_manage import add_guest, make_event, session_for
from app import auth, db, events, suggestions


class EaseTests(unittest.TestCase):
    def setUp(self):
        self.app = fresh_app("ease")
        self.owner = make_user()
        self.client = Client(self.app)
        session_for(self.client, self.owner)
        self.ev = make_event(self.owner, package=None)
        events.touch(self.ev["id"], selected_package="premium")
        self.base = f"/dashboard/events/{self.ev['uid']}"

    # --- sign-in links ------------------------------------------------------------------------------
    def test_sign_in_link_logs_in_once(self):
        anon = Client(self.app)
        r = anon.post("/login/email", {"email": "organiser@example.com", "next": "/dashboard"})
        self.assertIn("Check your email", r.text)
        log = db.one("SELECT * FROM email_logs WHERE template_key = 'login_link' ORDER BY id DESC")
        self.assertIsNotNone(log)
        token = auth.issue_token(self.owner["id"], "login", 2)    # the emailed one is hashed; issue a fresh one
        r = anon.get(f"/login/link/{token}?next=/dashboard")
        self.assertEqual(r.status, 303)
        self.assertEqual(anon.get("/dashboard").status, 200)
        self.assertIn("expired", Client(self.app).get(f"/login/link/{token}").text)   # works once

    def test_unknown_email_gets_same_answer(self):
        r = Client(self.app).post("/login/email", {"email": "nobody@example.com"})
        self.assertIn("Check your email", r.text)
        self.assertIsNone(db.one("SELECT 1 FROM email_logs WHERE to_email = 'nobody@example.com'"))

    def test_register_without_password(self):
        anon = Client(self.app)
        r = anon.post("/register", {"name": "Naledi Khumalo", "email": "naledi@example.com", "terms": "1"})
        self.assertEqual(r.status, 303, r.text[:300])
        self.assertEqual(db.one("SELECT password_hash FROM users WHERE email = 'naledi@example.com'")["password_hash"], "")
        r = Client(self.app).post("/login", {"email": "naledi@example.com", "password": "anything"})
        self.assertIn("no password yet", r.text)

    # --- draft preview --------------------------------------------------------------------------------
    def test_draft_preview_link(self):
        ev = events.by_id(self.ev["id"])
        url = events.draft_url(ev).replace("http://127.0.0.1:8040", "").replace(events.config.BASE_URL, "")
        anon = Client(self.app)
        r = anon.get(url)
        self.assertEqual(r.status, 200)
        self.assertIn("Shared draft", r.text)
        self.assertIn("noindex", str(r.headers) + r.text)
        self.assertEqual(anon.get(url[:-3] + "abc").status, 404)
        self.assertEqual(anon.get(f"/events/{ev['slug']}").status in (200, 404), True)

    # --- wizard helpers ----------------------------------------------------------------------------------
    def test_guest_paste_in_step_4(self):
        r = self.client.post(self.base + "/setup/4", {"guest_paste": "Name\tPhone\nThandi Mokoena\t082 123 4567\nSipho Dlamini, sipho@example.com\nThandi Mokoena\t082 123 4567",
                                                      "plus_one_policy": "per_guest", "nav": "stay"})
        self.assertEqual(r.status, 303, r.text[:300])
        names = [g["first_name"] + " " + g["last_name"] for g in db.q("SELECT * FROM guests WHERE event_id = ? ORDER BY id", (self.ev["id"],))]
        self.assertEqual(names, ["Thandi Mokoena", "Sipho Dlamini"])
        # pasting the same people again adds nobody
        self.client.post(self.base + "/setup/4", {"guest_paste": "Sipho Dlamini, sipho@example.com", "nav": "stay"})
        self.assertEqual(db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (self.ev["id"],)), 2)

    def test_guest_paste_needs_premium(self):
        events.touch(self.ev["id"], selected_package="essential")
        r = self.client.post(self.base + "/setup/4", {"guest_paste": "Thandi Mokoena", "nav": "stay"})
        self.assertEqual(r.status, 200)
        self.assertIn("part of the Premium package", r.text)

    def test_sample_programme_and_menu_paste(self):
        r = self.client.post(self.base + "/setup/5", {"nav": "sample"})
        self.assertEqual(r.status, 303)
        items = events.schedule(self.ev["id"])
        self.assertEqual(items[1]["item_time"], "14:00")     # the ceremony starts at the event's start time
        self.assertEqual(items[1]["title"], "Ceremony")
        r = self.client.post(self.base + "/setup/6", {"menu_name": "Reception menu", "menu_paste": "Starters\nSoup\nMain: Lamb - jus\nDessert: Malva pudding",
                                                      "nav": "next"})
        self.assertEqual(r.status, 303)
        dishes = db.q("SELECT course, name, description FROM menu_items WHERE event_id = ? ORDER BY sort", (self.ev["id"],))
        self.assertEqual([(d["course"], d["name"]) for d in dishes], [("Starter", "Soup"), ("Main", "Lamb"), ("Dessert", "Malva pudding")])

    def test_blank_starter_rows_are_ignored(self):
        r = self.client.post(self.base + "/setup/5", {"si-0-kind": "other", "si-1-kind": "other", "si-0-function": "", "nav": "next"})
        self.assertEqual(r.status, 303, r.text[:400])
        r = self.client.post(self.base + "/setup/6", {"mi-0-course": "Main", "mi-1-course": "Main", "nav": "next"})
        self.assertEqual(r.status, 303, r.text[:400])

    def test_seating_step_can_wait_for_rsvps(self):
        r = self.client.post(self.base + "/setup/7", {"table_count": "12", "capacity": "10", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.tables(self.ev["id"]), [])

    def test_package_gaps_shown_on_review_and_package_steps(self):
        self.client.post(self.base + "/setup/5", {"nav": "sample"})
        self.assertEqual(events.package_gaps(events.by_id(self.ev["id"]), "premium"), [])
        self.assertIn("your programme", events.package_gaps(events.by_id(self.ev["id"]), "essential")[0])
        self.client.post(self.base + "/plan-package", {"package": "essential", "back": "9"})
        r = self.client.get(self.base + "/setup/9")
        self.assertIn("won't show your programme", r.text.replace("&#x27;", "'").replace("&#39;", "'"))
        self.assertIn("Show someone before you pay", r.text)
        r = self.client.get(self.base + "/setup/10")
        self.assertIn("Won't show your programme", r.text.replace("&#x27;", "'").replace("&#39;", "'"))

    def test_event_name_follows_names(self):
        r = self.client.post(self.base + "/setup/1", {"name": "", "category": "white-wedding", "hosts": "Lerato & Sipho", "event_date": "2027-03-14", "nav": "stay"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.by_id(self.ev["id"])["name"], "Lerato & Sipho's wedding")

    # --- after publishing ----------------------------------------------------------------------------------
    def test_whatsapp_queue(self):
        events.touch(self.ev["id"], paid_package="premium", status="published")
        a = add_guest(self.ev, "Ann", status="pending", phone="082 111 2222")
        add_guest(self.ev, "Ben", status="pending", phone="083 333 4444")
        add_guest(self.ev, "Cee", status="pending")                        # no number
        r = self.client.get(self.base + "/share/whatsapp")
        self.assertIn("1 of 2", r.text)
        self.assertIn("wa.me/27821112222", r.text)
        self.assertIn("1 guest has no mobile number", r.text)
        r = self.client.post(self.base + "/share/whatsapp", {"guest_id": str(a["id"]), "action": "sent", "mode": "invite"})
        self.assertEqual(r.status, 303)
        self.assertIsNotNone(db.one("SELECT invited_at FROM guests WHERE id = ?", (a["id"],))["invited_at"])
        r = self.client.get(r.location)
        self.assertIn("2 of 2", r.text)
        # reminders go to invited guests who haven't replied, once a day
        r = self.client.get(self.base + "/share/whatsapp?mode=remind")
        self.assertIn("a quick reminder", r.text)
        self.client.post(self.base + "/share/whatsapp", {"guest_id": str(a["id"]), "action": "sent", "mode": "remind"})
        self.assertIn("had a reminder today", self.client.get(self.base + "/share/whatsapp?mode=remind").text)

    def test_next_steps_on_overview(self):
        r = self.client.get(self.base)
        self.assertIn("Choose a package and pay", r.text)
        events.touch(self.ev["id"], paid_package="premium", status="published")
        r = self.client.get(self.base)
        self.assertIn("Add your guest list", r.text)
        add_guest(self.ev, "Ann", status="pending", phone="082 111 2222")
        self.assertIn("Send your invitations", self.client.get(self.base).text)

    # --- set-up help ------------------------------------------------------------------------------------------
    def test_setup_help_request(self):
        anon = Client(self.app)
        self.assertEqual(anon.get("/help-me-set-up").status, 200)
        r = anon.post("/help-me-set-up", {"name": "Busy Bride", "email": "bride@example.com", "reach": "whatsapp", "occasion": "white-wedding"})
        self.assertIn("mobile number", r.text)
        r = anon.post("/help-me-set-up", {"name": "Busy Bride", "email": "bride@example.com", "phone": "082 000 0000", "reach": "whatsapp",
                                          "occasion": "white-wedding", "package": "premium"})
        ref = re.search(r"reference is (S-\d+)", r.text).group(1)
        req = db.one("SELECT * FROM support_requests WHERE topic = 'setup_help'")
        self.assertIn("Premium", req["message"])
        self.assertTrue(db.one("SELECT 1 FROM email_logs WHERE to_email = 'bride@example.com' AND template_key = 'setup_help_received'"))
        self.assertTrue(ref.startswith("S-"))


class SuggestionTests(unittest.TestCase):
    def test_every_occasion_has_wording_and_a_programme(self):
        from app import catalog
        fresh_app("suggest")
        for c in catalog.CATEGORIES:
            self.assertGreaterEqual(len(suggestions.wording_options(c[0])), 2, c[0])
            self.assertTrue(suggestions.sample_programme(c[0], "", c[2]), c[0])
            for opt in suggestions.wording_options(c[0]):
                for k in ("welcome", "invitation", "rsvp_note", "closing"):
                    text = suggestions.fill_wording(opt[k], "A & B", "")
                    self.assertNotIn("{", text, (c[0], k))
                    self.assertNotIn("  ", text, (c[0], k))


if __name__ == "__main__":
    unittest.main()
