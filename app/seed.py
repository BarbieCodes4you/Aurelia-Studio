"""Demo data for development and demos. Every row is flagged is_demo = 1 and every email ends in
@demo.aurelia.example, so it is easy to tell apart from customer data and to remove.

    python3 run.py --seed-only

Demo logins (development only, never use in production):
    admin@demo.aurelia.example     / Demo-Admin-2026
    thandi@demo.aurelia.example    / Demo-Host-2026

Payments for the demo events go through the real sandbox checkout verification path, so they are
recorded as mode='sandbox' orders and never count as revenue.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from . import auth, catalog, db, events
from .services import payments

DEMO_DOMAIN = "demo.aurelia.example"
ADMIN = ("admin@" + DEMO_DOMAIN, "Demo-Admin-2026", "Ayesha Patel (demo admin)")
HOST = ("thandi@" + DEMO_DOMAIN, "Demo-Host-2026", "Thandi Mokoena")

FIRST = ["Lerato", "Sipho", "Thabo", "Naledi", "Ayanda", "Kabelo", "Zanele", "Bongani", "Palesesa", "Mandla", "Nomvula", "Tshepo",
         "Lindiwe", "Sibusiso", "Refilwe", "Themba", "Karabo", "Nandi", "Lwazi", "Dineo", "Johan", "Annelie", "Pieter", "Marike",
         "Ravi", "Priya", "Yusuf", "Fatima", "Michael", "Sarah", "David", "Megan", "Kagiso", "Busisiwe", "Musa", "Ntombi",
         "Andile", "Keabetswe", "Tumelo", "Amahle", "Sizwe", "Hlengiwe", "Mpho", "Onthatile", "Riaan", "Chantel", "Imran", "Zainab"]
LAST = ["Mokoena", "Dlamini", "Nkosi", "Khumalo", "Mahlangu", "Ndlovu", "Botha", "van der Merwe", "Naidoo", "Pillay", "Jacobs",
        "Mthembu", "Zulu", "Molefe", "Sithole", "Maseko", "Smith", "Petersen", "Cele", "Mabaso", "Venter", "Govender", "Adams", "Radebe"]


def _reset() -> None:
    db.run("DELETE FROM orders WHERE event_id IN (SELECT id FROM events WHERE is_demo = 1)")
    db.run("DELETE FROM events WHERE is_demo = 1")
    db.run("DELETE FROM users WHERE is_demo = 1")


def _user(email, pw, name, role="customer"):
    uid = db.insert("users", {"email": email, "name": name, "password_hash": auth.hash_password(pw), "role": role,
                              "email_verified_at": db.now(), "is_demo": 1, "created_at": db.now()})
    return db.one("SELECT * FROM users WHERE id = ?", (uid,))


def _pay(ev, user, code):
    """Pay through the sandbox gateway's signed-notification path (sandbox mode, never revenue)."""
    order = payments.create_order(events.by_id(ev["id"]), user, code)
    gw = payments.SandboxGateway()
    body, sig = gw.build_notification(order, "approve")
    gw_name = "sandbox"
    db.run("UPDATE orders SET gateway = 'sandbox', mode = 'sandbox' WHERE id = ?", (order["id"],))
    payments.apply(gw.verify(body, sig), gw_name)


def _guests(ev, rng, n, sides=None, groups=None, cats=("Family", "Friends", "Colleagues")):
    meals = [m["id"] for m in events.meal_options(ev["id"])]
    diets = ["", "", "", "", "Vegetarian", "Halal", "Gluten-free", "Vegan", "No pork"]
    out = []
    now = db.now()
    for k in range(n):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        r = rng.random()
        status = "attending" if r < 0.66 else "declined" if r < 0.8 else "pending"
        plus_allowed = 1 if rng.random() < 0.45 else 0
        kids_allowed = rng.choice([0, 0, 0, 1, 2])
        g = {"event_id": ev["id"], "token": events.new_guest_token(), "first_name": first, "last_name": last,
             "email": f"{first.lower()}.{last.lower().replace(' ', '')}{k}@{DEMO_DOMAIN}",
             "phone": f"+27 8{rng.randint(1, 4)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
             "category": rng.choice(cats), "family_group": rng.choice(groups) if groups and rng.random() < .6 else "",
             "side": rng.choice(sides) if sides else "", "is_vip": 1 if rng.random() < .06 else 0,
             "plus_ones_allowed": plus_allowed, "children_allowed": kids_allowed, "status": status,
             "plus_ones": (1 if plus_allowed and rng.random() < .7 else 0) if status == "attending" else 0,
             "children": (rng.randint(0, kids_allowed) if kids_allowed else 0) if status == "attending" else 0,
             "meal_item_id": rng.choice(meals) if meals and status == "attending" else None,
             "dietary": rng.choice(diets) if status == "attending" else "",
             "allergies": "Peanuts" if status == "attending" and rng.random() < .04 else "",
             "special_requests": "Wheelchair access please" if status == "attending" and rng.random() < .03 else "",
             "source": "import", "email_consent": 1, "invited_at": now,
             "responded_at": now if status != "pending" else None, "created_at": now, "updated_at": now}
        g["plus_one_names"] = rng.choice(FIRST) + " " + last if g["plus_ones"] else ""
        gid = db.insert("guests", g)
        if status != "pending":
            db.insert("rsvp_responses", {"event_id": ev["id"], "guest_id": gid, "via": "personal", "created_at": now,
                                         "payload": db.dumps({"status": status, "plus_ones": g["plus_ones"], "children": g["children"]})})
        out.append((gid, g))
    return out


def _seat(ev, guests, leave_unseated=6):
    tables = events.tables(ev["id"])
    attending = [(gid, g) for gid, g in guests if g["status"] == "attending"]
    attending = attending[:max(0, len(attending) - leave_unseated)]
    t = 0
    load = {tb["id"]: 0 for tb in tables}
    for gid, g in attending:
        size = 1 + g["plus_ones"] + g["children"]
        tries = 0
        while load[tables[t]["id"]] + size > tables[t]["capacity"] and tries < len(tables):
            t = (t + 1) % len(tables)
            tries += 1
        if tries >= len(tables):
            break
        db.insert("seat_assignments", {"guest_id": gid, "table_id": tables[t]["id"], "event_id": ev["id"], "assigned_at": db.now()})
        load[tables[t]["id"]] += size


def _tables(ev, names, cap=10, shape="round"):
    for n, name in enumerate(names):
        db.insert("seating_tables", {"event_id": ev["id"], "name": name, "capacity": cap, "shape": shape,
                                     "pos_x": 12 + (n % 5) * 19, "pos_y": 20 + (n // 5) * 24, "sort": n})


def _menu(ev, name, items):
    mid = db.insert("menus", {"event_id": ev["id"], "name": name, "sort": 0})
    for n, (course, dish, desc, tags, sel) in enumerate(items):
        db.insert("menu_items", {"menu_id": mid, "event_id": ev["id"], "course": course, "name": dish, "description": desc,
                                 "tags": db.dumps(tags), "selectable": 1 if sel else 0, "sort": n})


def run() -> None:
    rng = random.Random(2026)
    _reset()
    _user(*ADMIN, role="admin")
    host = _user(*HOST)
    today = date.today()

    # 1. Premium white wedding, published --------------------------------------------------------
    ev = events.create(host["id"], "white-wedding", "champagne", "Our wedding", "Lerato & Sipho", is_demo=True)
    d = today + timedelta(days=118)
    events.touch(ev["id"], description="We're getting married, and we'd love you there.", event_date=d.isoformat(),
                 start_time="14:00", end_time="23:30",
                 venue=db.dumps({"name": "The Glasshouse at Oakridge (demo venue)", "address": "12 Oakridge Lane, Muldersdrift, Gauteng",
                                 "parking": "Free parking at the main gate; shuttles run to the ceremony lawn.",
                                 "directions": "Take the N14 towards Krugersdorp, exit at Muldersdrift Road and follow the gold signs."}),
                 design=db.dumps({"palette": "midnight", "monogram": "L & S", "wording": {
                     "welcome": "Together with their families", "invitation": "Lerato and Sipho request the pleasure of your company as they celebrate their marriage.",
                     "rsvp_note": "Kindly reply by the date below.", "closing": "We can't wait to celebrate with you."}}),
                 guest_settings=db.dumps({"estimated": 150, "categories": ["Family", "Friends", "Colleagues"], "family_groups": ["Dube family", "Nkosi family"],
                                          "children_allowed": True, "max_children": 2, "plus_one_policy": "per_guest", "plus_ones_default": 0,
                                          "rsvp_deadline": (d - timedelta(days=45)).isoformat()}),
                 info=db.dumps({"dress_code": "Black tie", "dress_code_notes": "Shades of emerald, black and gold.",
                                "registry": [{"name": "Honeymoon fund", "url": "https://example.com/registry", "note": "Zanzibar, here we come"}],
                                "gift_note": "Your presence is our present.", "contacts": [{"name": "Zanele Dube", "role": "Maid of honour", "phone": "+27 82 000 0101", "email": ""}],
                                "accommodation": [{"name": "Oakridge Guest Lodge (demo)", "url": "https://example.com/lodge", "note": "Quote DUBE-NKOSI for 10% off"}],
                                "dietary_options": ["Vegetarian", "Vegan", "Halal", "Gluten-free", "Nut allergy"], "drinks": "Welcome bubbles, open bar until 23:00."}),
                 wizard_step=10, wizard_done=db.dumps(list(range(1, 10))))
    f1 = db.insert("event_functions", {"event_id": ev["id"], "name": "Ceremony", "func_date": d.isoformat(), "start_time": "14:00", "end_time": "15:00",
                                       "venue_name": "The Lawn", "sort": 0})
    f2 = db.insert("event_functions", {"event_id": ev["id"], "name": "Reception", "func_date": d.isoformat(), "start_time": "17:30", "end_time": "23:30",
                                       "venue_name": "The Glasshouse", "sort": 1})
    for n, (t, title, kind, fid) in enumerate([("13:30", "Guests arrive", "other", f1), ("14:00", "Ceremony", "ceremony", f1),
                                               ("15:00", "Canapés and photographs", "meal", f1), ("17:30", "Reception doors open", "reception", f2),
                                               ("18:30", "Dinner is served", "meal", f2), ("20:00", "Speeches", "speech", f2),
                                               ("21:00", "First dance", "entertainment", f2), ("21:15", "Dance floor opens", "entertainment", f2)]):
        db.insert("schedule_items", {"event_id": ev["id"], "function_id": fid, "item_time": t, "title": title, "kind": kind, "sort": n})
    _menu(ev, "Reception menu", [("Starter", "Butternut and coconut soup", "Toasted pumpkin seeds", ["Vegan"], False),
                                 ("Main", "Slow-roasted beef fillet", "Red wine jus, pomme purée", [], True),
                                 ("Main", "Line fish", "Lemon butter, seasonal greens", ["Gluten-free"], True),
                                 ("Main", "Wild mushroom risotto", "Parmesan crisp", ["Vegetarian"], True),
                                 ("Dessert", "Malva pudding", "Amarula custard", [], False)])
    _tables(ev, ["Head table", "Protea", "Baobab", "Fynbos", "Jacaranda", "Marula", "Acacia", "Aloe", "Strelitzia", "Yellowwood",
                 "Kiaat", "Leadwood", "Stinkwood", "Cycad", "Agapanthus"])
    _pay(ev, host, "premium")
    guests = _guests(events.by_id(ev["id"]), rng, 150, groups=["Dube family", "Nkosi family"])
    _seat(ev, guests)

    # 2. Signature traditional wedding, published -------------------------------------------------
    ev2 = events.create(host["id"], "traditional-wedding", "heritage", "Umembeso and wedding", "Nomvula & Themba", is_demo=True)
    d2 = today + timedelta(days=60)
    events.touch(ev2["id"], event_date=d2.isoformat(), start_time="09:00", end_time="22:00",
                 venue=db.dumps({"name": "Mahlangu family home (demo)", "address": "45 Protea Street, Soweto, Gauteng"}),
                 design=db.dumps({"palette": "ochre", "monogram": "N & T", "wording": {"welcome": "Two families, one celebration"}}),
                 guest_settings=db.dumps({"estimated": 220, "categories": ["Family", "Friends", "Church", "Elders"], "sides": ["Mahlangu family", "Khumalo family"],
                                          "family_groups": ["Mahlangu delegation", "Khumalo delegation"], "children_allowed": True, "max_children": 3,
                                          "plus_one_policy": "per_guest", "rsvp_deadline": (d2 - timedelta(days=21)).isoformat()}),
                 info=db.dumps({"dress_code": "Traditional attire", "dress_code_notes": "Ochre and indigo, or your family colours."}),
                 wizard_step=10, wizard_done=db.dumps(list(range(1, 10))))
    a = db.insert("event_functions", {"event_id": ev2["id"], "name": "Umembeso (gift-giving)", "func_date": d2.isoformat(), "start_time": "09:00",
                                      "end_time": "13:00", "venue_name": "Mahlangu family home", "address": "45 Protea Street, Soweto", "sort": 0})
    b = db.insert("event_functions", {"event_id": ev2["id"], "name": "Wedding celebration", "func_date": (d2 + timedelta(days=1)).isoformat(),
                                      "start_time": "11:00", "end_time": "22:00", "venue_name": "Khumalo homestead (demo)", "address": "Plot 7, Hammanskraal, Gauteng", "sort": 1})
    for n, (t, title, kind, fid) in enumerate([("09:00", "Khumalo delegation arrives", "ceremony", a), ("10:30", "Gift-giving", "ceremony", a),
                                               ("12:00", "Lunch", "meal", a), ("11:00", "Wedding ceremony", "ceremony", b), ("14:00", "Celebration and dancing", "entertainment", b)]):
        db.insert("schedule_items", {"event_id": ev2["id"], "function_id": fid, "item_time": t, "title": title, "kind": kind, "sort": n})
    _menu(ev2, "Celebration menu", [("Main", "Beef stew and dumplings", "", [], True), ("Main", "Chicken curry", "", ["Halal"], True),
                                    ("Main", "Chakalaka and pap", "", ["Vegetarian"], True)])
    _tables(ev2, [f"Table {n}" for n in range(1, 21)], cap=12, shape="long")
    _pay(ev2, host, "signature")
    g2 = _guests(events.by_id(ev2["id"]), rng, 90, sides=["Mahlangu family", "Khumalo family"], groups=["Mahlangu delegation", "Khumalo delegation"],
                 cats=("Family", "Friends", "Church", "Elders"))
    for gid, _ in g2[:60]:
        for fid in (a, b):
            db.insert("guest_functions", {"guest_id": gid, "function_id": fid, "attending": 1})
    _seat(ev2, g2, leave_unseated=10)

    # 3. Baby shower, unpaid draft -------------------------------------------------------------------
    ev3 = events.create(host["id"], "baby-shower", "bloom", "Amahle's baby shower", "Amahle", is_demo=True)
    events.touch(ev3["id"], event_date=(today + timedelta(days=40)).isoformat(), start_time="11:00", end_time="15:00",
                 venue=db.dumps({"name": "Rosebank garden café (demo)", "address": "Rosebank, Johannesburg"}),
                 design=db.dumps({"palette": "blush"}), selected_package="essential", wizard_step=4, wizard_done=db.dumps([1, 2, 3]))

    # 4. A second customer with a party, and a support request --------------------------------------
    other = _user("kagiso@" + DEMO_DOMAIN, "Demo-Host-2026", "Kagiso Molefe")
    ev4 = events.create(other["id"], "birthday", "pulse", "Kagiso turns 40", "Kagiso's 40th", is_demo=True)
    events.touch(ev4["id"], event_date=(today + timedelta(days=25)).isoformat(), start_time="19:00",
                 venue=db.dumps({"name": "Rooftop at 44 Stanley (demo)", "address": "44 Stanley Avenue, Milpark, Johannesburg"}),
                 info=db.dumps({"dress_code": "Cocktail"}), guest_settings=db.dumps({"rsvp_deadline": (today + timedelta(days=15)).isoformat(),
                                                                                    "plus_one_policy": "open", "plus_ones_default": 1}),
                 wizard_step=10, wizard_done=db.dumps(list(range(1, 10))))
    _pay(ev4, other, "essential")
    _guests(events.by_id(ev4["id"]), rng, 40, cats=("Friends", "Colleagues"))
    db.insert("support_requests", {"user_id": other["id"], "event_id": ev4["id"], "name": other["name"], "email": other["email"], "topic": "event",
                                   "message": "Can I change the date of my party after publishing? (demo request)", "created_at": db.now(), "updated_at": db.now()})
    db.run("UPDATE events SET is_demo = 1 WHERE owner_id IN (SELECT id FROM users WHERE is_demo = 1)")
    # demo emails sent while seeding would clutter the outbox log: mark them clearly
    db.run("UPDATE email_logs SET status = 'skipped', error = 'Demo seed: not delivered' WHERE to_email LIKE ?", (f"%@{DEMO_DOMAIN}",))
    print(f"Demo data loaded: {db.val('SELECT COUNT(*) FROM events WHERE is_demo = 1')} events, "
          f"{db.val('SELECT COUNT(*) FROM guests g JOIN events e ON e.id = g.event_id WHERE e.is_demo = 1')} guests.")
    print(f"Demo host login: {HOST[0]}   Demo admin login: {ADMIN[0]}   (passwords are in app/seed.py)")
