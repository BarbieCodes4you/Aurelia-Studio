"""Organiser dashboard tests: guests, CSV import, access control, package gating, seating API,
reports, QR codes and communications."""
from __future__ import annotations

import unittest

from tests.helpers import Client, fresh_app, make_user

from app import auth, db, events
from app.services import pdf, qr, reports


def session_for(client: Client, user) -> None:
    client.cookies["aur_sid"] = auth.create_session(user["id"])


def make_event(owner, package="premium", live=False, name="Sarah & John's Wedding"):
    ev = events.create(owner["id"], "white-wedding", "atelier", name, "Sarah & John")
    fields = {"event_date": "2027-03-20", "start_time": "14:00"}
    if package:
        fields.update({"paid_package": package, "selected_package": package})
    if live:
        fields["status"] = "published"
    events.touch(ev["id"], **fields)
    return events.by_id(ev["id"])


def add_guest(ev, first, status="attending", email="", plus=0, kids=0, **extra):
    now = db.now()
    gid = db.insert("guests", {"event_id": ev["id"], "token": events.new_guest_token(), "first_name": first,
                               "last_name": extra.pop("last_name", "Test"), "email": email, "status": status,
                               "plus_ones": plus, "plus_ones_allowed": max(plus, 1), "children": kids,
                               "created_at": now, "updated_at": now, **extra})
    return db.one("SELECT * FROM guests WHERE id = ?", (gid,))


class ManageTests(unittest.TestCase):
    def setUp(self):
        self.app = fresh_app("manage")
        self.owner = make_user()
        self.client = Client(self.app)
        session_for(self.client, self.owner)
        self.ev = make_event(self.owner)
        self.base = f"/dashboard/events/{self.ev['uid']}"

    # --- guests ---------------------------------------------------------------------------------
    def test_dashboard_lists_events(self):
        r = self.client.get("/dashboard")
        self.assertEqual(r.status, 200)
        self.assertIn("Sarah &amp; John&#x27;s Wedding", r.text)
        r = self.client.get(self.base)
        self.assertEqual(r.status, 200)
        self.assertIn("RSVP completion", r.text)

    def test_guest_crud(self):
        r = self.client.post(self.base + "/guests/new", {"first_name": "Lerato", "last_name": "Dlamini",
                                                          "email": "lerato@example.com", "plus_ones_allowed": "1",
                                                          "children_allowed": "0", "status": "pending",
                                                          "plus_ones": "0", "children": "0", "email_consent": "1"})
        self.assertEqual(r.status, 303, r.text[:400])
        g = db.one("SELECT * FROM guests WHERE email = 'lerato@example.com'")
        self.assertIsNotNone(g)
        # duplicate email rejected
        r = self.client.post(self.base + "/guests/new", {"first_name": "Copy", "email": "lerato@example.com",
                                                          "status": "pending", "plus_ones": "0", "children": "0"})
        self.assertEqual(r.status, 200)
        self.assertIn("already uses that email", r.text)
        # edit
        r = self.client.post(f"{self.base}/guests/{g['id']}", {"first_name": "Lerato", "last_name": "Mokoena",
                                                                "email": "lerato@example.com", "status": "attending",
                                                                "plus_ones_allowed": "1", "plus_ones": "1",
                                                                "children": "0", "children_allowed": "0"})
        self.assertEqual(r.status, 303)
        g = db.one("SELECT * FROM guests WHERE id = ?", (g["id"],))
        self.assertEqual((g["last_name"], g["status"], g["plus_ones"]), ("Mokoena", "attending", 1))
        listing = self.client.get(self.base + "/guests")
        self.assertIn("Lerato Mokoena", listing.text)
        # delete
        r = self.client.post(f"{self.base}/guests/{g['id']}/delete")
        self.assertEqual(r.status, 303)
        self.assertIsNone(db.one("SELECT 1 FROM guests WHERE id = ?", (g["id"],)))

    def test_csv_import_with_bad_rows(self):
        add_guest(self.ev, "Existing", email="dup@example.com")
        csv_text = ("first_name,last_name,email,phone,category,family_group,plus_ones_allowed,children_allowed,vip\n"
                    "Ayanda,Zulu,ayanda@example.com,082 555 0101,Family,Zulu family,1,0,yes\n"
                    ",Nobody,missing@example.com,,,,0,0,\n"
                    "Bad,Email,not-an-email,,,,0,0,\n"
                    "Dupe,Person,dup@example.com,,,,0,0,\n"
                    "Kids,Wrong,kids@example.com,,,,0,many,\n"
                    "Pieter,van Wyk,,071 555 0102,Friends,,0,2,\n")
        r = self.client.post(self.base + "/guests/import", {"csv_text": csv_text})
        self.assertEqual(r.status, 200)
        self.assertIn("2 guests ready to import", r.text)
        self.assertIn("4 rows need attention", r.text)
        self.assertEqual(db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (self.ev["id"],)), 1)
        r = self.client.post(self.base + "/guests/import", {"csv_text": csv_text, "confirm": "1"})
        self.assertEqual(r.status, 303)
        rows = db.q("SELECT * FROM guests WHERE event_id = ? AND source = 'import' ORDER BY first_name", (self.ev["id"],))
        self.assertEqual([g["first_name"] for g in rows], ["Ayanda", "Pieter"])
        self.assertEqual(rows[0]["is_vip"], 1)
        self.assertEqual(rows[1]["children_allowed"], 2)
        # multipart upload path works too
        r = self.client.multipart(self.base + "/guests/import", {}, {"csv": ("g.csv", b"\xef\xbb\xbffirst_name,email\nNew,new@example.com\n", "text/csv")})
        self.assertIn("1 guests ready to import", r.text)

    def test_other_users_get_404(self):
        stranger = make_user(email="stranger@example.com")
        other = Client(self.app)
        session_for(other, stranger)
        for path in ("", "/guests", "/seating", "/reports/final.pdf", "/settings", "/share/qr.png"):
            self.assertEqual(other.get(self.base + path).status, 404, path)
        g = add_guest(self.ev, "Private")
        self.assertEqual(other.post(f"{self.base}/guests/{g['id']}/delete").status, 404)
        self.assertIsNotNone(db.one("SELECT 1 FROM guests WHERE id = ?", (g["id"],)))
        # anonymous users are sent to log in
        anon = Client(self.app)
        r = anon.get(self.base + "/guests")
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith("/login"))

    # --- package gating -------------------------------------------------------------------------
    def test_essential_is_locked_out_of_seating(self):
        ess = make_event(self.owner, package="essential", name="Small party")
        b = f"/dashboard/events/{ess['uid']}"
        r = self.client.get(b + "/seating")
        self.assertEqual(r.status, 200)
        self.assertIn("is part of the", r.text)
        self.assertNotIn("data-seating", r.text)
        r = self.client.post(b + "/seating/api/create", json_body={"name": "T1", "capacity": 8})
        self.assertEqual(r.status, 403)
        self.assertEqual(self.client.get(b + "/reports/final.pdf").status, 403)
        self.assertIn("is part of the", self.client.get(b + "/guests/new").text)
        # premium works
        r = self.client.get(self.base + "/seating")
        self.assertIn("data-seating", r.text)

    # --- seating ----------------------------------------------------------------------------------
    def test_auto_seat_keeps_families_together(self):
        import json
        mok = [add_guest(self.ev, n, family_group="Mokoena family", plus=1) for n in ("Thabo", "Lindi")]   # 4 people
        dla = [add_guest(self.ev, n, family_group="Dlamini family") for n in ("Sipho", "Ayanda", "Zola")]  # 3 people
        add_guest(self.ev, "Pending Pat", status="pending")
        r = json.loads(self.client.post(self.base + "/seating/api/autoseat", json_body={}).text)
        self.assertIn("created", r["message"])
        top = [t for t in r["state"]["tables"] if t["name"] == "Head table"]
        self.assertEqual(len(top), 1)                         # a wedding gets a head table from the default layout
        self.assertEqual(top[0]["seated"], 0)                 # and nobody is seated there automatically
        tables = {g["table"] for g in r["state"]["guests"] if g["name"].split()[0] in ("Thabo", "Lindi", "Sipho", "Ayanda", "Zola")}
        self.assertEqual(len(tables), 1)                      # 7 people fit one table of 10
        self.assertEqual(r["warning"], "")
        self.assertIsNone(db.one("SELECT 1 FROM seat_assignments a JOIN guests g ON g.id = a.guest_id WHERE g.first_name = 'Pending'"))
        # a second run with nothing left to seat says so; including pending seats Pat
        r = json.loads(self.client.post(self.base + "/seating/api/autoseat", json_body={}).text)
        self.assertIn("already has a seat", r["message"])
        r = json.loads(self.client.post(self.base + "/seating/api/autoseat", json_body={"include_pending": True}).text)
        self.assertIn("Seated 1 party", r["message"])

    def test_auto_seat_gives_each_group_its_own_table_when_there_is_room(self):
        import json
        for n in ("Thabo", "Lindi"):
            add_guest(self.ev, n, family_group="Mokoena family")
        for n in ("Sipho", "Ayanda"):
            add_guest(self.ev, n, family_group="Dlamini family")
        self.client.post(self.base + "/seating/api/autocreate", json_body={"count": 3, "capacity": 10})
        r = json.loads(self.client.post(self.base + "/seating/api/autoseat", json_body={}).text)
        by_group = {}
        for g in r["state"]["guests"]:
            by_group.setdefault(g["group"], set()).add(g["table"])
        self.assertEqual(len(by_group["Mokoena family"]), 1)
        self.assertEqual(len(by_group["Dlamini family"]), 1)
        self.assertNotEqual(by_group["Mokoena family"], by_group["Dlamini family"])

    def test_auto_seat_splits_big_groups_and_reports_overflow(self):
        import json
        for n in range(7):
            add_guest(self.ev, f"Cousin{n}", family_group="Big family", plus=1)        # 14 people
        self.client.post(self.base + "/seating/api/autocreate", json_body={"count": 1, "capacity": 10})
        r = json.loads(self.client.post(self.base + "/seating/api/autoseat", json_body={}).text)
        self.assertIn("Seated 5 parties", r["message"])
        self.assertIn("2 parties (4 people) didn't fit", r["warning"])
        self.assertEqual(r["state"]["tables"][0]["seated"], 10)

    def test_next_steps_count_only_guests_without_their_invitation(self):
        from app.views.dashboard import next_steps
        events.touch(self.ev["id"], status="published", published_at=db.now(), hosting_until="2099-01-01")
        a = add_guest(self.ev, "Amy", status="pending")
        add_guest(self.ev, "Ben", status="attending")                 # replied through the general link
        add_guest(self.ev, "Cy", status="pending")
        steps = {t: w for t, w, _, _ in next_steps(events.by_id(self.ev["id"]))}
        self.assertIn("2 guests haven't been sent", steps["Send your invitations"])
        self.assertNotIn("Remind guests who haven't replied", steps)
        # Amy opens her personal link: she has her invitation now
        Client(self.app).get(f"/events/{self.ev['slug']}/i/{a['token']}")
        steps = {t: w for t, w, _, _ in next_steps(events.by_id(self.ev["id"]))}
        self.assertIn("1 guest hasn't been sent", steps["Send your invitations"])
        self.assertEqual(steps["Remind guests who haven't replied"], "1 still to reply.")

    def test_new_tables_take_free_places_on_the_floor(self):
        events.create_layout_tables(self.ev, {"top": "head", "guest": "round", "capacity": 10}, 3)
        tables = events.tables(self.ev["id"])
        head = [t for t in tables if t["notes"] == events.TOP_TABLE_NOTE][0]
        guests = [t for t in tables if t["notes"] != events.TOP_TABLE_NOTE]
        self.assertEqual((head["pos_x"], head["pos_y"]), (50, events.FLOOR_TOP))
        self.assertEqual(sorted(t["pos_x"] for t in guests), [16.7, 50, 83.3])       # three tables spread across the room
        self.assertTrue(all(t["pos_y"] >= head["pos_y"] + events.FLOOR_TOP_ROW for t in guests))   # below the head table, in pixels
        # tables added by hand fill a gap left by a deleted one, then start a new row; none land on another
        db.run("DELETE FROM seating_tables WHERE id = ?", (guests[0]["id"],))
        self.client.post(self.base + "/seating/api/autocreate", json_body={"count": 5, "capacity": 10})
        spots = [(t["pos_x"], t["pos_y"]) for t in events.tables(self.ev["id"])]
        self.assertEqual(len(spots), 8)
        for i, (x, y) in enumerate(spots):
            for (x2, y2) in spots[i + 1:]:
                self.assertFalse(abs(x - x2) < 20 and abs(y - y2) < events.FLOOR_ROW * 0.8, spots)
        self.assertIn((guests[0]["pos_x"], guests[0]["pos_y"]), spots)                  # the gap is used first
        # moving a table stores pixels from the top, beyond the old 100% limit
        self.client.post(self.base + "/seating/api/update", json_body={"id": guests[1]["id"], "x": 40, "y": 1500})
        self.assertEqual(db.val("SELECT pos_y FROM seating_tables WHERE id = ?", (guests[1]["id"],)), 1500)

    def test_seating_api(self):
        a = add_guest(self.ev, "Ann", plus=1)      # party of 2
        b = add_guest(self.ev, "Ben", kids=2)       # party of 3
        add_guest(self.ev, "Dee", status="declined")
        r = self.client.post(self.base + "/seating/api/create", json_body={"name": "Family", "capacity": 4})
        self.assertEqual(r.status, 200, r.text)
        r = self.client.post(self.base + "/seating/api/autocreate", json_body={"count": 2, "capacity": 6})
        import json
        state = json.loads(r.text)["state"]
        self.assertEqual(len(state["tables"]), 3)
        self.assertEqual(len(state["guests"]), 2)  # declined guests are not seatable
        t1, t2 = state["tables"][0]["id"], state["tables"][1]["id"]
        r = json.loads(self.client.post(self.base + "/seating/api/assign", json_body={"guest_id": a["id"], "table_id": t1}).text)
        self.assertEqual(r["warning"], "")
        r = json.loads(self.client.post(self.base + "/seating/api/assign", json_body={"guest_id": b["id"], "table_id": t1}).text)
        self.assertIn("over capacity", r["warning"])
        seated = {t["id"]: t["seated"] for t in r["state"]["tables"]}
        self.assertEqual(seated[t1], 5)
        # everyone seated -> one completion email
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'seating_complete'"), 1)
        # move
        r = json.loads(self.client.post(self.base + "/seating/api/assign", json_body={"guest_id": b["id"], "table_id": t2}).text)
        seated = {t["id"]: t["seated"] for t in r["state"]["tables"]}
        self.assertEqual((seated[t1], seated[t2]), (2, 3))
        # unassign
        self.client.post(self.base + "/seating/api/assign", json_body={"guest_id": b["id"], "table_id": None})
        self.assertIsNone(db.one("SELECT 1 FROM seat_assignments WHERE guest_id = ?", (b["id"],)))
        # move a table, then delete it
        self.client.post(self.base + "/seating/api/update", json_body={"id": t2, "x": 55.5, "y": 40, "name": "Friends"})
        t = db.one("SELECT * FROM seating_tables WHERE id = ?", (t2,))
        self.assertEqual((t["pos_x"], t["name"]), (55.5, "Friends"))
        self.client.post(self.base + "/seating/api/delete", json_body={"id": t2})
        self.assertIsNone(db.one("SELECT 1 FROM seating_tables WHERE id = ?", (t2,)))
        # bad capacity rejected
        r = self.client.post(self.base + "/seating/api/create", json_body={"capacity": 0})
        self.assertEqual(r.status, 400)
        # seating completion email not repeated
        self.client.post(self.base + "/seating/api/assign", json_body={"guest_id": b["id"], "table_id": t1})
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'seating_complete'"), 1)
        self.assertEqual(self.client.get(self.base + "/seating/print").status, 200)

    # --- reports ----------------------------------------------------------------------------------
    def test_every_report_builds(self):
        m = db.insert("menus", {"event_id": self.ev["id"], "name": "Dinner"})
        beef = db.insert("menu_items", {"menu_id": m, "event_id": self.ev["id"], "name": "Beef fillet", "selectable": 1})
        t = db.insert("seating_tables", {"event_id": self.ev["id"], "name": "Table 1", "capacity": 8})
        g = add_guest(self.ev, "Zanele", plus=1, meal_item_id=beef, dietary="Halal", special_requests="Wheelchair access",
                      plus_one_names="Sipho")
        add_guest(self.ev, "Pending", status="pending", email="p@example.com")
        add_guest(self.ev, "=cmd()", status="declined")
        db.insert("seat_assignments", {"guest_id": g["id"], "table_id": t, "event_id": self.ev["id"], "assigned_at": db.now()})
        for kind in reports.KINDS:
            for fmt in reports.FORMATS:
                r = self.client.get(f"{self.base}/reports/{kind}.{fmt}")
                self.assertEqual(r.status, 200, (kind, fmt, r.text[:200]))
                if fmt == "pdf":
                    self.assertTrue(r.body.startswith(b"%PDF-1.4"), kind)
                    self.assertIn(b"%%EOF", r.body[-10:])
                else:
                    self.assertTrue(r.body.startswith(b"\xef\xbb\xbf"), kind)
                    self.assertGreater(len(r.text.splitlines()), 1)
        final = reports.build(events.by_id(self.ev["id"]), "final", "csv")[1].decode("utf-8-sig")
        for needle in ("Zanele", "Beef fillet", "Halal", "Wheelchair access", "Table 1", "Total invited", "'=cmd()"):
            self.assertIn(needle, final)
        self.assertEqual(db.val("SELECT COUNT(*) FROM report_runs WHERE event_id = ?", (self.ev["id"],)), 14)
        atts = reports.final_attachments(events.by_id(self.ev["id"]))
        self.assertEqual([a[0].rsplit(".", 1)[1] for a in atts], ["pdf", "csv"])

    def test_pdf_paginates(self):
        doc = pdf.PDF("Long list", "Test")
        doc.table(["Name", "Status"], [[f"Guest {n}", "Attending"] for n in range(200)])
        out = doc.output()
        import re
        pages = int(re.search(rb"/Count (\d+)", out).group(1))
        self.assertGreater(pages, 4)
        self.assertEqual(out.count(b"/Type /Page "), pages)

    # --- QR ------------------------------------------------------------------------------------
    def test_qr_structure(self):
        text = "https://aurelia.example/events/sarah-and-john"
        m = qr.matrix(text)
        n = len(m)
        self.assertEqual(n, 33)  # 45 bytes at level M -> version 4
        finder = [[True] * 7, [True, False, False, False, False, False, True], [True, False, True, True, True, False, True]]
        for (x0, y0) in ((0, 0), (n - 7, 0), (0, n - 7)):
            self.assertEqual(m[y0][x0:x0 + 7], finder[0])
            self.assertEqual(m[y0 + 1][x0:x0 + 7], finder[1])
            self.assertEqual(m[y0 + 3][x0:x0 + 7], finder[2])
        for k in range(8, n - 8):
            self.assertEqual(m[6][k], k % 2 == 0)
            self.assertEqual(m[k][6], k % 2 == 0)
        ecl, mask = qr.read_format(m)
        self.assertEqual(ecl, 0)
        self.assertIn(mask, range(8))
        self.assertTrue(m[n - 8][8])  # dark module
        self.assertTrue(qr.png(text).startswith(b"\x89PNG"))
        self.assertIn("<svg", qr.svg(text))
        self.assertEqual(len(qr.matrix("x" * 200)), 57)  # version 10
        with self.assertRaises(qr.QRError):
            qr.matrix("x" * 400)
        r = self.client.get(self.base + "/share")
        self.assertIn("wa.me/?text=", r.text)
        self.assertTrue(self.client.get(self.base + "/share/qr.png").body.startswith(b"\x89PNG"))
        # "Email me this link" sends the link to whoever is signed in
        self.assertIn("Email me this link", r.text)
        r = self.client.post(self.base + "/share/email-me", {})
        self.assertEqual(r.status, 303)
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE template_key = 'event_link' AND to_email = ?", (self.owner["email"],)), 1)

    # --- communications -------------------------------------------------------------------------
    def test_comms_preview_and_send_requires_live(self):
        add_guest(self.ev, "Amy", status="pending", email="amy@example.com")
        add_guest(self.ev, "Bo", status="pending", email="bo@example.com", unsubscribed_at=db.now())
        add_guest(self.ev, "Cy", status="pending", email="cy@example.com", email_consent=0)
        add_guest(self.ev, "Di", status="pending")
        data = {"template": "guest_reminder", "audience": "pending", "message": "Hope to see you!"}
        r = self.client.post(self.base + "/communications/preview", data)
        self.assertEqual(r.status, 200)
        self.assertIn('data-recipient-count>1<', r.text)
        self.assertIn('data-skipped-count>3<', r.text)
        self.assertIn("paid for and published", r.text)
        r = self.client.post(self.base + "/communications/send", data)
        self.assertEqual(r.status, 303)
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE audience = 'guest'"), 0)
        # once live it sends, skipping unsubscribed/no-consent guests
        events.touch(self.ev["id"], status="published")
        r = self.client.post(self.base + "/communications/send", data)
        self.assertEqual(r.status, 303)
        sent = db.q("SELECT to_email FROM email_logs WHERE audience = 'guest'")
        self.assertEqual([s["to_email"] for s in sent], ["amy@example.com"])

    def test_comms_feature_gate(self):
        events.touch(self.ev["id"], status="published")
        add_guest(self.ev, "Amy", status="pending", email="amy@example.com")
        r = self.client.post(self.base + "/communications/send", {"template": "custom_message", "audience": "all",
                                                                   "subject": "Hello", "message": "Hi"})
        self.assertEqual(r.status, 303)
        self.assertEqual(db.val("SELECT COUNT(*) FROM email_logs WHERE audience = 'guest'"), 0)  # needs Signature

    def test_final_report_email(self):
        add_guest(self.ev, "Amy", email="amy@example.com")
        r = self.client.post(self.base + "/communications/final-report")
        self.assertEqual(r.status, 303)
        log = db.one("SELECT * FROM email_logs WHERE template_key = 'final_report'")
        self.assertEqual(log["status"], "sent")

    # --- settings, menu, programme ---------------------------------------------------------------
    def test_settings_and_tools(self):
        r = self.client.post(self.base + "/settings/slug", {"slug": "zanele-and-sipho"})
        self.assertEqual(r.status, 303)
        self.assertEqual(events.by_id(self.ev["id"])["slug"], "zanele-and-sipho")
        self.client.post(self.base + "/settings/sections", {"sections": ["welcome", "rsvp"]})
        sec = events.by_id(self.ev["id"])["sections"]
        self.assertTrue(sec["rsvp"])
        self.assertFalse(sec["menu"])
        self.client.post(self.base + "/settings/publish")
        self.assertEqual(events.by_id(self.ev["id"])["status"], "published")
        self.client.post(self.base + "/menu/new", {"name": "Dinner"})
        mid = db.val("SELECT id FROM menus WHERE event_id = ?", (self.ev["id"],))
        self.client.post(f"{self.base}/menu/{mid}/items", {"course": "Main", "name": "Lamb", "selectable": "1", "tags": ["Halal"]})
        self.assertEqual(len(events.meal_options(self.ev["id"])), 1)
        self.client.post(self.base + "/programme/functions", {"name": "Ceremony", "start_time": "14:00"})
        r = self.client.post(self.base + "/programme/functions", {"name": "Reception"})
        self.assertEqual(len(events.functions(self.ev["id"])), 2)  # premium allows 3
        self.client.post(self.base + "/programme/items", {"item_time": "15:00", "title": "Vows", "kind": "ceremony"})
        self.assertEqual(len(events.schedule(self.ev["id"])), 1)
        for path in ("/menu", "/programme", "/communications", "/reports", "/settings", "/rsvps", "/share"):
            self.assertEqual(self.client.get(self.base + path).status, 200, path)
        r = self.client.post(self.base + "/settings/delete", {"confirm_name": "wrong"})
        self.assertIsNotNone(events.by_id(self.ev["id"]))
        r = self.client.post(self.base + "/settings/delete", {"confirm_name": self.ev["name"]})
        self.assertIsNone(events.by_id(self.ev["id"]))


if __name__ == "__main__":
    unittest.main()
