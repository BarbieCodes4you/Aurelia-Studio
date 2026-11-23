"""Event websites, template previews, RSVP and media access."""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.helpers import Client, fresh_app, make_user, login, find  # noqa: F401  (helpers first)

from app import catalog, db, events
from app.eventsite.render import render
from app.eventsite.demo import demo_event

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82")


def make_event(owner, template="atelier", paid="premium", status="published", **gs_over):
    ev = events.create(owner["id"], "white-wedding", template, "The wedding of Ayanda & Lwazi", "Ayanda & Lwazi")
    gs = dict(ev["guest_settings"], plus_one_policy="per_guest", plus_ones_default=1, children_allowed=True,
              max_children=2, rsvp_deadline=(date.today() + timedelta(days=30)).isoformat())
    gs.update(gs_over)
    events.save_json(ev["id"], "guest_settings", gs)
    events.save_json(ev["id"], "venue", {"name": "Test Hall", "address": "1 Main Road, Durban"})
    fields = {"event_date": (date.today() + timedelta(days=60)).isoformat(), "start_time": "15:00", "status": status}
    if paid:
        fields["paid_package"] = paid
    events.touch(ev["id"], **fields)
    return events.by_id(ev["id"])


def add_guest(ev, first, last, email="", plus_allowed=0, kids_allowed=0):
    now = db.now()
    gid = db.insert("guests", {"event_id": ev["id"], "token": events.new_guest_token(), "first_name": first,
                               "last_name": last, "email": email, "plus_ones_allowed": plus_allowed,
                               "children_allowed": kids_allowed, "created_at": now, "updated_at": now})
    return db.one("SELECT * FROM guests WHERE id = ?", (gid,))


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("eventsite-templates")

    def test_every_template_renders_demo(self):
        c = Client(self.app)
        slugs = [t["slug"] for t in catalog.templates()]
        self.assertGreaterEqual(len(slugs), 10)
        bodies = set()
        for slug in slugs:
            for group in ("weddings", "baby", "parties", "other"):
                r = c.get(f"/templates/{slug}/preview?group={group}")
                self.assertEqual(r.status, 200, (slug, group))
                self.assertIn("Sample content", r.text)
                self.assertIn(f"d-{catalog.template(slug)['design']}", r.text)
            bodies.add(r.text.split('<main id="ev-main">')[1][:400])
        self.assertEqual(len(bodies), len(slugs), "each design should have its own structure")

    def test_unknown_template_404(self):
        self.assertEqual(Client(self.app).get("/templates/nope/preview").status, 404)

    def test_render_function_direct(self):
        html = render(demo_event("heritage", "weddings"), "demo")
        self.assertIn("Two families", html)
        self.assertIn("The ceremonies", html)


class CulturalStyleTests(unittest.TestCase):
    """Heritage can be styled Ndebele, Zulu, Xhosa, Pedi, Venda, Tsonga or Swati."""

    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("eventsite-cultures")

    def test_each_culture_renders_its_own_pattern_and_colours(self):
        from app.eventsite import themes
        self.assertEqual(set(themes.CULTURES), {"ndebele", "zulu", "xhosa", "pedi", "venda", "tsonga", "swati"})
        for key, (name, _, palette, motif) in themes.CULTURES.items():
            ev = demo_event("heritage", "weddings")
            ev["design"] = {"palette": key}
            html = render(ev, "demo")
            self.assertIn(f"cult-{key}", html)
            self.assertIn(f'id="bd-{key}-hr-top"', html)
            self.assertIn(f"--m1:{motif[0]}", html)
            self.assertIn(f"--ev-accent:{palette['accent']}", html)
        classic = render(demo_event("heritage", "weddings"), "demo")
        self.assertNotIn("cult-", classic)

    def test_template_page_previews_a_culture_and_carries_it_to_create(self):
        c = Client(self.app)
        r = c.get("/templates/heritage?group=weddings&style=zulu")
        self.assertEqual(r.status, 200)
        self.assertIn("preview?group=weddings&amp;palette=zulu", r.text)
        self.assertIn("/create?template=heritage&group=weddings&amp;palette=zulu", r.text)
        self.assertIn("Cultural style", r.text)
        self.assertIn("cult-zulu", c.get("/templates/heritage/preview?group=weddings&palette=zulu").text)
        self.assertNotIn("cult-", c.get("/templates/atelier/preview?group=weddings&palette=zulu").text)

    def test_design_step_offers_cultures_and_create_keeps_the_choice(self):
        make_user("culture@example.com")
        c = Client(self.app)
        login(c, "culture@example.com")
        r = c.post("/create", {"category": "traditional-wedding", "template": "heritage", "hosts": "Zanele & Musa", "palette": "xhosa"})
        self.assertEqual(r.status, 303, r.text[:300])
        ev = db.one("SELECT e.* FROM events e JOIN users u ON u.id = e.owner_id WHERE u.email = ?", ("culture@example.com",))
        self.assertEqual(db.loads(ev["design"], {}).get("palette"), "xhosa")
        step2 = c.get(f"/dashboard/events/{ev['uid']}/setup/2").text
        self.assertIn("Cultural style", step2)
        self.assertIn('value="xhosa" checked', step2)


class PublicSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("eventsite-public")
        cls.owner = make_user("owner@example.com")
        cls.other = make_user("other@example.com")

    def test_draft_is_private(self):
        ev = make_event(self.owner, paid=None, status="draft")
        anon = Client(self.app)
        r = anon.get(f"/events/{ev['slug']}")
        self.assertEqual(r.status, 404)
        self.assertNotIn("Ayanda", r.text)
        stranger = Client(self.app)
        login(stranger, "other@example.com")
        self.assertEqual(stranger.get(f"/events/{ev['slug']}").status, 404)
        self.assertEqual(stranger.get(f"/dashboard/events/{ev['uid']}/preview").status, 404)
        owner = Client(self.app)
        login(owner, "owner@example.com")
        r = owner.get(f"/events/{ev['slug']}")
        self.assertEqual(r.status, 200)
        self.assertIn("Preview", r.text)
        self.assertEqual(owner.get(f"/dashboard/events/{ev['uid']}/preview").status, 200)

    def test_published_paid_renders(self):
        ev = make_event(self.owner, template="champagne")
        r = Client(self.app).get(f"/events/{ev['slug']}")
        self.assertEqual(r.status, 200)
        self.assertIn("Ayanda", r.text)
        self.assertIn("d-champagne", r.text)
        self.assertIn('action="/events/' + ev["slug"] + '/rsvp"', r.text)
        ics = Client(self.app).get(f"/events/{ev['slug']}/calendar.ics")
        self.assertEqual(ics.status, 200)
        self.assertIn("BEGIN:VEVENT", ics.text)

    def test_published_without_payment_is_private(self):
        ev = make_event(self.owner, paid=None, status="published")
        self.assertEqual(Client(self.app).get(f"/events/{ev['slug']}").status, 404)

    def test_hosting_expired(self):
        ev = make_event(self.owner)
        events.touch(ev["id"], hosting_until=(date.today() - timedelta(days=1)).isoformat())
        self.assertEqual(Client(self.app).get(f"/events/{ev['slug']}").status, 404)


class RSVPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("eventsite-rsvp")
        cls.owner = make_user("host@example.com")

    def test_personal_rsvp_caps_plus_ones(self):
        ev = make_event(self.owner)
        g = add_guest(ev, "Zola", "Mthembu", "zola@example.com", plus_allowed=1)
        c = Client(self.app)
        page = c.get(f"/events/{ev['slug']}/i/{g['token']}")
        self.assertEqual(page.status, 200)
        self.assertIn("Zola", page.text)
        # over the allowance is refused
        r = c.post(f"/events/{ev['slug']}/rsvp", {"token": g["token"], "status": "attending", "plus_ones": "3"})
        self.assertEqual(r.status, 400)
        self.assertEqual(db.one("SELECT status FROM guests WHERE id = ?", (g["id"],))["status"], "pending")
        r = c.post(f"/events/{ev['slug']}/rsvp", {"token": g["token"], "status": "attending", "plus_ones": "1",
                                                   "plus_one_names": "Sizwe", "children": "1"})
        self.assertEqual(r.status, 303)
        self.assertIn("rsvp=thanks", r.location)
        row = db.one("SELECT * FROM guests WHERE id = ?", (g["id"],))
        self.assertEqual((row["status"], row["plus_ones"], row["children"]), ("attending", 1, 1))
        self.assertEqual(db.val("SELECT COUNT(*) FROM rsvp_responses WHERE guest_id = ?", (g["id"],)), 1)
        logs = {r["template_key"] for r in db.q("SELECT template_key FROM email_logs WHERE event_id = ?", (ev["id"],))}
        self.assertIn("rsvp_confirmation", logs)
        self.assertIn("new_rsvp", logs)
        thanks = c.get(r.location.split("#")[0])
        self.assertIn("Reply received", thanks.text)

    def test_general_rsvp_creates_guest_and_matches_pending(self):
        ev = make_event(self.owner, template="aurora")
        c = Client(self.app)
        r = c.post(f"/events/{ev['slug']}/rsvp", {"first_name": "New", "last_name": "Person", "email": "new@example.com",
                                                   "status": "declined"})
        self.assertEqual(r.status, 303)
        g = db.one("SELECT * FROM guests WHERE event_id = ? AND email = ?", (ev["id"], "new@example.com"))
        self.assertEqual((g["status"], g["source"]), ("declined", "general_link"))
        invited = add_guest(ev, "Kate", "Naidoo", "kate@example.com")
        c.post(f"/events/{ev['slug']}/rsvp", {"first_name": "Kate", "last_name": "N", "email": "KATE@example.com",
                                              "status": "attending"})
        self.assertEqual(db.one("SELECT status FROM guests WHERE id = ?", (invited["id"],))["status"], "attending")
        self.assertEqual(db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (ev["id"],)), 2)

    def test_general_rsvp_validates(self):
        ev = make_event(self.owner)
        r = Client(self.app).post(f"/events/{ev['slug']}/rsvp", {"first_name": "", "email": "bad", "status": "maybe"})
        self.assertEqual(r.status, 400)
        self.assertIn("ev-errors", r.text)

    def test_rsvp_after_deadline_refused(self):
        ev = make_event(self.owner, rsvp_deadline=(date.today() - timedelta(days=1)).isoformat())
        g = add_guest(ev, "Late", "Larry")
        c = Client(self.app)
        self.assertIn("RSVPs closed", c.get(f"/events/{ev['slug']}/i/{g['token']}").text)
        r = c.post(f"/events/{ev['slug']}/rsvp", {"token": g["token"], "status": "attending"})
        self.assertEqual(r.status, 409)
        self.assertEqual(db.one("SELECT status FROM guests WHERE id = ?", (g["id"],))["status"], "pending")

    def test_rsvp_refused_on_unpublished(self):
        ev = make_event(self.owner, paid=None, status="draft")
        r = Client(self.app).post(f"/events/{ev['slug']}/rsvp", {"first_name": "A", "last_name": "B",
                                                                  "email": "a@example.com", "status": "attending"})
        self.assertEqual(r.status, 404)
        self.assertEqual(db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (ev["id"],)), 0)

    def test_guest_page_never_shows_other_guests(self):
        ev = make_event(self.owner)
        a = add_guest(ev, "Alpha", "Visible", "alpha@example.com")
        b = add_guest(ev, "Bravo", "Secretname", "bravo@example.com")
        c = Client(self.app)
        for path in (f"/events/{ev['slug']}", f"/events/{ev['slug']}/i/{a['token']}"):
            html = c.get(path).text
            self.assertNotIn("Secretname", html)
            self.assertNotIn("bravo@example.com", html)
            self.assertNotIn(b["token"], html)

    def test_seating_shown_only_on_personal_link(self):
        ev = make_event(self.owner)
        g = add_guest(ev, "Seat", "Holder")
        tid = db.insert("seating_tables", {"event_id": ev["id"], "name": "Table Protea", "capacity": 8})
        db.insert("seat_assignments", {"guest_id": g["id"], "table_id": tid, "event_id": ev["id"], "assigned_at": db.now()})
        c = Client(self.app)
        self.assertIn("Table Protea", c.get(f"/events/{ev['slug']}/i/{g['token']}").text)
        self.assertNotIn("Table Protea", c.get(f"/events/{ev['slug']}").text)

    def test_honeypot_and_unsubscribe(self):
        ev = make_event(self.owner)
        c = Client(self.app)
        r = c.post(f"/events/{ev['slug']}/rsvp", {"first_name": "Bot", "last_name": "Bot", "email": "bot@example.com",
                                                   "status": "attending", "website": "spam"})
        self.assertEqual(r.status, 303)
        self.assertIsNone(db.one("SELECT 1 FROM guests WHERE email = 'bot@example.com'"))
        g = add_guest(ev, "Unsub", "Me", "u@example.com")
        self.assertIn("POPIA", c.get(f"/events/{ev['slug']}/u/{g['token']}").text)
        c.post(f"/events/{ev['slug']}/u/{g['token']}", {})
        row = db.one("SELECT * FROM guests WHERE id = ?", (g["id"],))
        self.assertTrue(row["unsubscribed_at"])
        self.assertEqual(row["email_consent"], 0)

    def test_wrong_token_404(self):
        ev = make_event(self.owner)
        self.assertEqual(Client(self.app).get(f"/events/{ev['slug']}/i/notatoken").status, 404)


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = fresh_app("eventsite-media")
        cls.owner = make_user("media@example.com")

    def _upload(self, ev):
        from app.services.storage import save_image
        from app.web import UploadedFile
        return save_image(UploadedFile("a.png", "image/png", PNG), ev, self.owner["id"], "gallery")

    def test_media_access(self):
        draft = make_event(self.owner, paid=None, status="draft")
        up = self._upload(draft)
        anon = Client(self.app)
        self.assertEqual(anon.get(f"/media/{up['storage_key']}").status, 404)
        owner = Client(self.app)
        login(owner, "media@example.com")
        r = owner.get(f"/media/{up['storage_key']}")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "image/png")
        live = make_event(self.owner)
        up2 = self._upload(live)
        self.assertEqual(anon.get(f"/media/{up2['storage_key']}").status, 200)
        self.assertIn(up2["storage_key"], anon.get(f"/events/{live['slug']}").text)
        self.assertEqual(anon.get("/media/../aurelia.sqlite3").status, 404)


if __name__ == "__main__":
    unittest.main()
