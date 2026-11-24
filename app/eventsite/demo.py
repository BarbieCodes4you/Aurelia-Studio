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


_TRADITIONAL = {
    "name": "Lerato & Sipho's traditional wedding", "hosts": "Lerato & Sipho", "category": "traditional-wedding",
    "description": "Two families, one celebration. Join us for umembeso in the morning and the wedding celebration that follows.",
    "venue": {"name": "Inkosi Gardens (sample venue)", "address": "Muldersdrift, Gauteng",
              "parking": "Parking on the lawn, with marshals to guide you.", "directions": "", "accommodation": ""},
    "dress": ("Traditional attire", "Wear your family's colours with pride."),
    "functions": [("Umembeso", "10:00", "13:00", "The Dlamini family home (sample)", "Soweto, Johannesburg"),
                  ("Wedding celebration", "14:00", "21:00", "Inkosi Gardens (sample venue)", "Muldersdrift, Gauteng")],
    "schedule": [("10:00", "Umembeso", "Gifts are presented to the bride's family.", "ceremony"),
                 ("12:30", "Lunch", "", "reception"), ("14:00", "Wedding celebration", "", "ceremony"),
                 ("16:00", "Speeches and dancing", "", "entertainment")],
    "menu": [("Main", "Slow-cooked beef stew", "With dumplings", [], 0), ("Main", "Roast chicken", "", [], 0),
             ("Sides", "Pap, chakalaka and samp", "", ["Vegetarian"], 0), ("Dessert", "Malva pudding", "Custard", [], 0)],
    "sides": ["The Dlamini family", "The Mahlangu family"],
}

# A few designs read best with their own kind of sample (a 21st for Glitter, a Christmas lunch for
# Festive...). Keys override the occasion's sample above; "on" fixes the month and day.
TEMPLATE_SAMPLES = {
    "nguni": {"weddings": _TRADITIONAL},
    "terracotta": {"weddings": dict(_TRADITIONAL, name="Lerato & Sipho's lobola celebration", category="lobola",
                                    description="Our families are coming together. Join us for the lobola and the celebration that follows.",
                                    venue={"name": "The Mahlangu family home (sample)", "address": "Soweto, Johannesburg",
                                           "parking": "Street parking, with marshals on the day.", "directions": "", "accommodation": ""},
                                    functions=[],
                                    schedule=[("10:00", "Families arrive", "", "other"), ("11:00", "Negotiations", "For the family delegations.", "ceremony"),
                                              ("14:00", "Celebration", "Lunch, music and dancing for everyone.", "reception")])},
    "glitter": {"parties": {
        "name": "Naledi turns 21", "hosts": "Naledi's 21st",
        "description": "Twenty-one, glitter everywhere and a playlist we've been building for months. Dress up and shine.",
        "venue": {"name": "The Mirror Room (sample venue)", "address": "Rosebank, Johannesburg",
                  "parking": "Secure parking in the basement.", "directions": "", "accommodation": ""},
        "dress": ("Glitter, sequins and chrome", "Silver, gold or anything that sparkles."), "end": "01:00",
        "schedule": [("19:00", "Doors open", "Welcome cocktails.", "other"), ("20:00", "Dinner", "", "reception"),
                     ("21:00", "Speeches and cake", "", "speech"), ("22:00", "Dance floor opens", "", "entertainment")]}},
    "matcha": {"parties": {
        "name": "Zanele's matcha morning", "hosts": "Zanele's 30th",
        "description": "A slow Saturday: a gentle pilates class, matcha and pastries, and the people I love. Bring a mat if you have one.",
        "venue": {"name": "The Studio on 7th (sample venue)", "address": "Melville, Johannesburg",
                  "parking": "Street parking on 7th Street.", "directions": "", "accommodation": ""},
        "dress": ("Athleisure in soft colours", "Comfortable enough to stretch, cute enough for photos."), "end": "12:30",
        "schedule": [("09:00", "Arrive and settle in", "", "other"), ("09:30", "Pilates class", "Mats provided.", "activity"),
                     ("10:30", "Matcha and brunch", "", "reception"), ("11:30", "Cake", "", "other")],
        "menu": [("Brunch", "Matcha lattes", "Oat, almond or full cream", ["Vegan option"], 0),
                 ("Brunch", "Berry yoghurt bowls", "", ["Vegetarian"], 0), ("Brunch", "Croissants and pastries", "", [], 0)],
        "drinks": "Matcha, fresh juice and sparkling water.", "gift_note": "No gifts, just good company."}},
    "festive": {
        "parties": {
            "name": "The Mokoena family Christmas lunch", "hosts": "Christmas at the Mokoenas", "category": "private-celebration",
            "description": "Christmas lunch is at ours this year. Bring your appetite, your best festive outfit and a gift for secret Santa.",
            "venue": {"name": "The Mokoena family home (sample)", "address": "Morningside, Durban",
                      "parking": "Park in the street; the gate will be open.", "directions": "", "accommodation": ""},
            "dress": ("Something red or green", ""), "on": (12, 25), "end": "18:00",
            "schedule": [("12:00", "Arrivals and drinks", "", "other"), ("13:00", "Christmas lunch", "", "reception"),
                         ("15:00", "Secret Santa", "", "activity"), ("16:00", "Dessert and games", "", "entertainment")],
            "menu": [("Lunch", "Glazed gammon", "Pineapple and mustard glaze", [], 0), ("Lunch", "Roast chicken and potatoes", "", [], 0),
                     ("Lunch", "Festive salads", "", ["Vegetarian"], 0), ("Dessert", "Trifle", "", [], 0)],
            "gift_note": "Secret Santa: one gift of about R150, wrapped and labelled."},
        "other": {
            "name": "Kumo Studio year-end function", "hosts": "Kumo Studio year-end", "category": "corporate",
            "description": "Thank you for a wonderful year. Join the team for dinner, awards and a little dancing.",
            "venue": {"name": "The Glasshouse (sample venue)", "address": "Sandton, Johannesburg",
                      "parking": "Valet parking at the entrance.", "directions": "", "accommodation": ""},
            "dress": ("Festive smart", ""), "on": (12, 12), "functions": [], "end": "23:00",
            "schedule": [("18:30", "Welcome drinks", "", "other"), ("19:30", "Dinner", "", "reception"),
                         ("20:30", "Awards", "", "speech"), ("21:30", "Dancing", "", "entertainment")]}},
    "cheers": {
        "parties": {
            "name": "New Year's Eve on the rooftop", "hosts": "Cheers to 2027",
            "description": "Out with the old, in with the new. Join us on the rooftop to toast the year.",
            "venue": {"name": "Skyline Rooftop (sample venue)", "address": "Florida Road, Morningside, Durban",
                      "parking": "Secure parking behind the building.", "directions": "", "accommodation": ""},
            "dress": ("Black, gold and a little sparkle", ""), "on": (12, 31), "end": "01:00",
            "schedule": [("20:00", "Doors open", "", "other"), ("21:00", "Dinner", "", "reception"),
                         ("23:45", "Countdown", "", "entertainment"), ("23:59", "Champagne toast", "", "speech")]},
        "weddings": {
            "name": "Thandi & Kabelo are engaged", "hosts": "Thandi & Kabelo", "category": "engagement",
            "description": "She said yes! Join us for champagne, dinner and far too many toasts.",
            "venue": {"name": "The Courtyard (sample venue)", "address": "Bree Street, Cape Town",
                      "parking": "Paid parking on Bree Street.", "directions": "", "accommodation": ""},
            "dress": ("Cocktail", ""), "functions": [],
            "schedule": [("18:00", "Welcome drinks", "", "other"), ("19:00", "Toasts", "", "speech"),
                         ("19:30", "Dinner", "", "reception"), ("21:00", "Dancing", "", "entertainment")]}},
}


def _next_date(month: int, day: int, after: date) -> date:
    d = date(after.year, month, day)
    return d if d >= after else date(after.year + 1, month, day)


def demo_event(template_slug: str, group: str = "weddings") -> dict:
    if group not in SAMPLES:
        group = "weddings"
    t = catalog.template(template_slug)
    design = t["design"] if t else template_slug
    s = dict(SAMPLES[group], **TEMPLATE_SAMPLES.get(template_slug, {}).get(group, {}))
    today = date.today()
    ev_date = today + timedelta(days=s["event_days"])
    deadline = today + timedelta(days=s["deadline_days"])
    if s.get("on"):
        ev_date = _next_date(*s["on"], today + timedelta(days=10))
        deadline = max(today + timedelta(days=3), ev_date - timedelta(days=10))
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
        "_functions": functions, "_schedule": schedule, "_menus": menus, "_hero": _stock_hero(template_slug, group),
        "_gallery": _stock_gallery(template_slug, group),
        "id": 0, "uid": "demo", "slug": f"sample-{template_slug}", "status": "published", "owner_id": 0,
        "template": template_slug, "category": s["category"], "name": s["name"], "hosts": s["hosts"],
        "description": s["description"], "event_date": ev_date.isoformat(), "start_time": first_time,
        "end_time": s.get("end") or ("23:00" if group in ("weddings", "parties") else "16:00"),
        "venue": dict(s["venue"], map_url=""),
        "design": {}, "guest_settings": {
            "estimated": 150, "categories": ["Family", "Friends"], "sides": s["sides"],
            "children_allowed": group == "baby", "max_children": 2, "plus_one_policy": "per_guest",
            "plus_ones_default": 1, "rsvp_deadline": deadline.isoformat()},
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


def _stock_hero(slug: str, group: str) -> str:
    """The sample's main photo: the template's own (static/img/stock/tpl-<slug>.jpg) when added, else
    the occasion's photo."""
    from .. import stock
    if stock.url(f"tpl-{slug}"):
        return stock.url(f"tpl-{slug}")
    if slug == "heritage" and stock.url("traditional"):
        return stock.url("traditional")
    return stock.url(group)


def _stock_gallery(slug: str, group: str) -> list:
    """Real photos when they have been added (static/img/stock/gallery/<slot>/), else six art tiles."""
    from .. import stock
    slot = "traditional" if slug == "heritage" and stock.gallery("traditional") else group
    photos = stock.gallery(slot) or (stock.gallery("weddings") if group == "weddings" else [])
    if photos:
        return [{"url": u, "caption": ""} for u in photos[:9]]
    return [{"url": "", "caption": ""} for _ in range(6)]

