"""Sample events for the template gallery. All names and venues are fictional."""
from __future__ import annotations

from datetime import date, timedelta

from .. import catalog

SAMPLES = {
    "weddings": {
        "name": "The wedding of Lerato & Daniel", "hosts": "Lerato & Daniel", "category": "white-wedding",
        "description": "After seven years, two cities and one very patient dog, we're making it official. Come and celebrate with us in the winelands.",
        "venue": {"name": "Oakhaven Wine Estate (sample venue)", "address": "Helshoogte Road, Stellenbosch, Western Cape",
                  "parking": "Free parking at the estate. Follow the signs past the cellar to the lower lawn.",
                  "directions": "From Cape Town take the N2, then the R310 towards Stellenbosch. The gate is 4 km past the town centre.",
                  "accommodation": "We've reserved rooms at two guesthouses nearby. Mention our names when booking."},
        "dress": ("Black tie optional", "Garden ceremony on grass: block heels are your friend. Bring a wrap for the evening."),
        "functions": [("Ceremony", "15:00", "16:00", "The Chapel Lawn", "Oakhaven Wine Estate, Stellenbosch"),
                      ("Reception", "17:30", "23:30", "The Barrel Hall", "Oakhaven Wine Estate, Stellenbosch")],
        "schedule": [("14:30", "Guests arrive", "Welcome drinks on the lawn.", "other"),
                     ("15:00", "Ceremony", "Please be seated by 14:50.", "ceremony"),
                     ("16:00", "Canapés and photographs", "", "activity"),
                     ("17:30", "Reception opens", "Find your table in the Barrel Hall.", "reception"),
                     ("19:00", "Speeches", "Father of the bride, best man and the couple.", "speech"),
                     ("20:30", "First dance", "Then the dance floor is yours.", "entertainment")],
        "menu": [("Starter", "Cape Malay spiced butternut soup", "Coriander, toasted seeds", ["Vegetarian"], 0),
                 ("Main", "Slow-roasted lamb shoulder", "Rosemary jus, crushed potatoes", [], 1),
                 ("Main", "Line fish with lemon beurre blanc", "Seasonal greens", ["Gluten-free"], 1),
                 ("Main", "Wild mushroom risotto", "Truffle oil, parmesan", ["Vegetarian"], 1),
                 ("Dessert", "Malva pudding", "Amarula custard", [], 0)],
        "drinks": "Estate wines, local craft beer and a non-alcoholic sparkling bar.",
        "registry": [("Home store registry", "https://example.com/registry", "Gifts for our first home."),
                     ("Honeymoon fund", "https://example.com/honeymoon", "Mozambique, here we come.")],
        "gift_note": "Your presence is the real gift. If you'd like to give something, we've set up two options.",
        "contacts": [("Naledi Khumalo", "Maid of honour", "082 000 0000", ""), ("Pieter van Wyk", "Best man", "083 000 0000", "")],
        "accommodation": [("Vine Cottage Guesthouse (sample)", "https://example.com/stay", "6 km from the venue, shuttle at 23:30.")],
        "instructions": "Unplugged ceremony: please keep phones away until the reception.",
        "sides": ["The Molefe family", "The Botha family"],
        "deadline_days": 60, "event_days": 120,
    },
    "baby": {
        "name": "Baby shower for Amahle", "hosts": "Amahle", "category": "baby-shower",
        "description": "Little one arrives in spring. Join us for tea, cake and terrible baby-name suggestions.",
        "venue": {"name": "The Jacaranda Garden Room (sample venue)", "address": "14 Acacia Avenue, Parkhurst, Johannesburg",
                  "parking": "Street parking on Acacia Avenue.", "directions": "", "accommodation": ""},
        "dress": ("Garden party pastels", ""),
        "functions": [],
        "schedule": [("11:00", "Welcome tea", "", "other"), ("11:45", "Games", "Guess the bump and baby bingo.", "activity"),
                     ("12:30", "Lunch", "", "reception"), ("13:30", "Gifts and cake", "", "other")],
        "menu": [("Lunch", "Grazing table", "Breads, cheeses, fruit and dips", ["Vegetarian"], 0),
                 ("Lunch", "Chicken and avocado sandwiches", "", [], 0), ("Sweet", "Lemon and berry cake", "", [], 0)],
        "drinks": "Rooibos iced tea, fresh juice and bubbly.",
        "registry": [("Baby registry", "https://example.com/baby", "Size 2 nappies are always welcome.")],
        "gift_note": "", "contacts": [("Zinhle Ndlovu", "Host", "071 000 0000", "")], "accommodation": [],
        "instructions": "", "sides": [], "deadline_days": 20, "event_days": 45,
    },
    "parties": {
        "name": "Thabo turns 40", "hosts": "Thabo's 40th", "category": "birthday",
        "description": "Four decades, one rooftop and a playlist he'll pretend not to know. Surprise him with us.",
        "venue": {"name": "Skyline Rooftop (sample venue)", "address": "220 Florida Road, Morningside, Durban",
                  "parking": "Secure parking behind the building.", "directions": "", "accommodation": ""},
        "dress": ("All black, one gold accent", "Think evening, not office."),
        "functions": [],
        "schedule": [("19:00", "Arrivals", "Thabo arrives at 19:45. Hide!", "other"),
                     ("20:00", "Surprise", "", "entertainment"), ("20:30", "Dinner", "", "reception"),
                     ("22:00", "DJ set", "", "entertainment")],
        "menu": [("Food", "Shisa nyama platters", "", [], 0), ("Food", "Vegetable skewers", "", ["Vegan"], 0)],
        "drinks": "Cash bar after the first round.", "registry": [], "gift_note": "No gifts, just good stories.",
        "contacts": [("Kagiso", "Partner in crime", "084 000 0000", "")], "accommodation": [], "instructions": "",
        "sides": [], "deadline_days": 14, "event_days": 30,
    },
    "other": {
        "name": "Graduation celebration", "hosts": "Dr Nomvula Dlamini", "category": "graduation",
        "description": "Seven years of study, one doctorate. Join the family for the ceremony and lunch afterwards.",
        "venue": {"name": "Great Hall, sample university", "address": "1 University Road, Braamfontein, Johannesburg",
                  "parking": "Visitor parking at Gate 2.", "directions": "", "accommodation": ""},
        "dress": ("Smart formal", ""),
        "functions": [("Graduation ceremony", "09:00", "11:30", "Great Hall", "Braamfontein"),
                      ("Family lunch", "13:00", "16:00", "The Courtyard Restaurant (sample)", "Melville")],
        "schedule": [("08:30", "Seating", "", "other"), ("09:00", "Academic procession", "", "ceremony"),
                     ("10:15", "Conferment of degrees", "", "ceremony"), ("13:00", "Lunch and toasts", "", "reception")],
        "menu": [("Lunch", "Braised beef short rib", "", [], 1), ("Lunch", "Roasted vegetable tart", "", ["Vegetarian"], 1),
                 ("Dessert", "Milk tart", "", [], 0)],
        "drinks": "", "registry": [], "gift_note": "", "contacts": [("Sipho Dlamini", "Brother", "076 000 0000", "")],
        "accommodation": [], "instructions": "Guests need a printed ticket for the Great Hall.", "sides": [],
        "deadline_days": 21, "event_days": 50,
    },
}


def demo_event(template_slug: str, group: str = "weddings") -> dict:
    if group not in SAMPLES:
        group = "weddings"
    t = catalog.template(template_slug)
    design = t["design"] if t else template_slug
    s = SAMPLES[group]
    today = date.today()
    ev_date = today + timedelta(days=s["event_days"])
    first_time = s["functions"][0][1] if s["functions"] else s["schedule"][0][0]
    functions = [{"id": k + 1, "name": n, "func_date": ev_date.isoformat(), "start_time": st, "end_time": en,
                  "venue_name": vn, "address": ad, "map_url": "", "description": "", "dress_code": ""}
                 for k, (n, st, en, vn, ad) in enumerate(s["functions"])]
    schedule = [{"item_time": tm, "title": ti, "description": de, "kind": kd,
                 "function_name": (functions[0]["name"] if functions and tm < "17:00" else functions[-1]["name"]) if functions else ""}
                for tm, ti, de, kd in s["schedule"]]
    items = [{"id": k + 1, "course": c, "name": n, "description": d, "tags": tags, "selectable": sel}
             for k, (c, n, d, tags, sel) in enumerate(s["menu"])]
    menus = [{"name": "Menu" if group != "weddings" else "Reception menu", "description": "", "items": items}] if items else []
    return {
        "_demo": True, "_design": design, "_group": group,
        "_functions": functions, "_schedule": schedule, "_menus": menus, "_hero": "",
        "_gallery": [{"url": "", "caption": c} for c in ("", "", "", "", "", "")],
        "id": 0, "uid": "demo", "slug": f"sample-{template_slug}", "status": "published", "owner_id": 0,
        "template": template_slug, "category": s["category"], "name": s["name"], "hosts": s["hosts"],
        "description": s["description"], "event_date": ev_date.isoformat(), "start_time": first_time,
        "end_time": "23:00" if group in ("weddings", "parties") else "16:00",
        "venue": dict(s["venue"], map_url=""),
        "design": {}, "guest_settings": {
            "estimated": 150, "categories": ["Family", "Friends"], "sides": s["sides"],
            "children_allowed": group == "baby", "max_children": 2, "plus_one_policy": "per_guest",
            "plus_ones_default": 1, "rsvp_deadline": (today + timedelta(days=s["deadline_days"])).isoformat()},
        "info": {"dress_code": s["dress"][0], "dress_code_notes": s["dress"][1],
                 "registry": [{"name": n, "url": u, "note": no} for n, u, no in s["registry"]],
                 "gift_note": s["gift_note"],
                 "contacts": [{"name": n, "role": r, "phone": ph, "email": em} for n, r, ph, em in s["contacts"]],
                 "accommodation": [{"name": n, "url": u, "note": no} for n, u, no in s["accommodation"]],
                 "instructions": s["instructions"], "drinks": s["drinks"], "catering_notes": "",
                 "dietary_options": []},
        "sections": {}, "report_prefs": {}, "selected_package": "signature", "paid_package": "signature",
        "hosting_until": None, "rsvp_open": 1, "published_at": None, "wizard_done": [],
    }
