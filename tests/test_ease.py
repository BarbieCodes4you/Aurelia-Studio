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
        r = self.client.post(self.base + "/setup/3", {"guest_paste": "Name\tPhone\nThandi Mokoena\t082 123 4567\nSipho Dlamini, sipho@example.com\nThandi Mokoena\t082 123 4567",
                                                      "plus_one_policy": "per_guest", "nav": "stay"})
        self.assertEqual(r.status, 303, r.text[:300])
        names = [g["first_name"] + " " + g["last_name"] for g in db.q("SELECT * FROM guests WHERE event_id = ? ORDER BY id", (self.ev["id"],))]
        self.assertEqual(names, ["Thandi Mokoena", "Sipho Dlamini"])
        # pasting the same people again adds nobody
        self.client.post(self.base + "/setup/3", {"guest_paste": "Sipho Dlamini, sipho@example.com", "nav": "stay"})
        self.assertEqual(db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (self.ev["id"],)), 2)

    def test_guest_paste_needs_premium(self):
        events.touch(self.ev["id"], selected_package="essential")
        r = self.client.post(self.base + "/setup/3", {"guest_paste": "Thandi Mokoena", "nav": "stay"})
        self.assertEqual(r.status, 200)
        self.assertIn("part of the Premium package", r.text)

    def test_sample_programme_and_menu_paste(self):
        r = self.client.post(self.base + "/setup/4", {"nav": "sample"})
        self.assertEqual(r.status, 303)
        items = events.schedule(self.ev["id"])
        self.assertEqual(items[1]["item_time"], "14:00")     # the ceremony starts at the event's start time
        self.assertEqual(items[1]["kind"], "ceremony")
        self.assertEqual(items[1]["title"], "Ceremony")
        r = self.client.post(self.base + "/setup/5", {"menu_name": "Reception menu", "menu_paste": "Starters\nSoup\nMain: Lamb - jus\nDessert: Malva pudding",
                                                      "nav": "next"})
        self.assertEqual(r.status, 303)
        dishes = db.q("SELECT course, name, description FROM menu_items WHERE event_id = ? ORDER BY sort", (self.ev["id"],))
        self.assertEqual([(d["course"], d["name"]) for d in dishes], [("Starter", "Soup"), ("Main", "Lamb"), ("Dessert", "Malva pudding")])

    def test_blank_starter_rows_are_ignored(self):
        r = self.client.post(self.base + "/setup/4", {"si-0-day": "0", "si-1-day": "0", "fn-0-id": "", "nav": "next"})
        self.assertEqual(r.status, 303, r.text[:400])
        r = self.client.post(self.base + "/setup/5", {"mi-0-course": "Main", "mi-1-course": "Main", "nav": "next"})
        self.assertEqual(r.status, 303, r.text[:400])

    def test_seating_step_can_wait_for_rsvps(self):
        r = self.client.post(self.base + "/setup/6", {"top_table": "head", "guest_tables": "round", "table_count": "12", "capacity": "10", "nav": "next"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.tables(self.ev["id"]), [])
        self.assertEqual(events.seating_layout(events.by_id(self.ev["id"]))["top"], "head")

    def test_package_gaps_shown_on_review_and_package_steps(self):
        self.client.post(self.base + "/setup/4", {"nav": "sample"})
        self.assertEqual(events.package_gaps(events.by_id(self.ev["id"]), "premium"), [])
        self.assertIn("your programme", events.package_gaps(events.by_id(self.ev["id"]), "essential")[0])
        r = self.client.get(self.base + "/setup/8")
        self.assertIn("Show someone before you pay", r.text)
        self.assertIn("Won't show your programme", r.text.replace("&#x27;", "'").replace("&#39;", "'"))

    def test_event_name_follows_names(self):
        r = self.client.post(self.base + "/setup/1", {"hosts": "Lerato & Sipho", "event_date": "2027-03-14", "venue_name": "Avianto", "address": "Muldersdrift", "nav": "stay"})
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
        self.assertIn("Ready to share it?", r.text)
        events.touch(self.ev["id"], paid_package="premium", status="published")
        r = self.client.get(self.base)
        self.assertIn("Add your guest list", r.text)
        add_guest(self.ev, "Ann", status="pending", phone="082 111 2222")
        self.assertIn("Send your invitations", self.client.get(self.base).text)

    def test_booking_box_on_overview(self):
        self.assertNotIn("Your booking", self.client.get(self.base).text)
        events.touch(self.ev["id"], paid_package="premium", status="published", hosting_until="2027-09-30")
        db.insert("orders", {"uid": "ord123", "event_id": self.ev["id"], "user_id": self.owner["id"], "package_code": "premium",
                             "amount_cents": 1299900, "description": "Premium Experience", "status": "paid", "mode": "sandbox", "gateway": "sandbox", "invoice_no": "INV-0001",
                             "paid_at": "2026-11-16T10:00:00", "created_at": db.now(), "updated_at": db.now()})
        t = self.client.get(self.base).text
        self.assertIn("Your booking", t)
        self.assertIn("R12,999", t)
        self.assertIn("/dashboard/orders/ord123/receipt", t)
        self.assertIn("Online until", t)

    def test_home_explains_why_digital(self):
        t = Client(self.app).get("/").text
        self.assertIn("Why send your invitations this way", t)
        self.assertLess(t.index("Why send your invitations this way"), t.index("Finished event websites"))

    def test_seating_step_explains_placing_guests(self):
        self.assertIn("Seat everyone automatically", self.client.get(self.base + "/setup/6").text)

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


class GuestImportTests(unittest.TestCase):
    def setUp(self):
        self.app = fresh_app("guestimport")
        self.owner = make_user()
        self.client = Client(self.app)
        session_for(self.client, self.owner)
        self.ev = make_event(self.owner, package=None)
        self.base = f"/dashboard/events/{self.ev['uid']}"

    def test_upload_excel_and_family_headings(self):
        import io
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Name</t></si>'
                       '<si><t>Mobile</t></si><si><t>Family</t></si><si><t>Lerato Dube</t></si><si><t>Dube family</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                       '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'
                       '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2"><v>831112222</v></c><c r="C2" t="s"><v>4</v></c></row></sheetData></worksheet>')
        r = self.client.multipart(self.base + "/setup/3", {"guest_paste": "Mokoena family:\nThandi Mokoena, 082 123 4567", "nav": "stay"},
                                  {"guest_file": ("guests.xlsx", b.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(r.status, 303, r.text[:300])
        rows = db.q("SELECT first_name, last_name, phone, family_group FROM guests WHERE event_id = ? ORDER BY id", (self.ev["id"],))
        self.assertEqual([tuple(x) for x in rows], [("Thandi", "Mokoena", "082 123 4567", "Mokoena family"), ("Lerato", "Dube", "0831112222", "Dube family")])

    def test_unreadable_file_explains(self):
        r = self.client.multipart(self.base + "/setup/3", {"nav": "stay"}, {"guest_file": ("guests.xlsx", b"PK\x03\x04 broken", "application/octet-stream")})
        self.assertEqual(r.status, 200)
        self.assertIn("couldn", r.text)
