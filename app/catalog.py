"""Event categories, website templates and packages: defaults, seeding and lookups.

Defaults are inserted once; after that the admin dashboard owns the rows (prices, features,
limits, names, active flags), so nothing here overrides admin edits.
"""
from __future__ import annotations

from typing import Optional

from . import db

GROUPS = {
    "weddings": {"name": "Weddings", "path": "/weddings",
                 "blurb": "White weddings, traditional ceremonies, lobola, engagements and celebrations that run over several days."},
    "baby": {"name": "Baby celebrations", "path": "/baby-celebrations",
             "blurb": "Baby showers, gender reveals and welcome-baby gatherings, with RSVPs and gift lists in one place."},
    "parties": {"name": "Parties", "path": "/parties",
                "blurb": "Birthdays, anniversaries and private celebrations that deserve more than a group message."},
    "other": {"name": "Other events", "path": "/celebrations",
              "blurb": "Graduations, corporate functions and family gatherings with programmes, menus and seating."},
}

# slug, name, group, description, feature hints
CATEGORIES = [
    ("white-wedding", "White wedding", "weddings", "Ceremony and reception with RSVPs, menus, programme and seating.", ["seating", "menu"]),
    ("traditional-wedding", "Traditional wedding", "weddings", "Several ceremonies and venues, with separate family guest lists.", ["family_sides", "multi_function"]),
    ("lobola", "Lobola celebration", "weddings", "Family delegations, arrival times and the celebration that follows.", ["family_sides"]),
    ("engagement", "Engagement celebration", "weddings", "Announce the news and gather everyone in one place.", []),
    ("multi-day-wedding", "Multi-day wedding", "weddings", "Welcome dinner, ceremony, reception and farewell brunch on one link.", ["multi_function"]),
    ("baby-shower", "Baby shower", "baby", "Invitations, RSVPs and the gift registry together.", ["registry"]),
    ("gender-reveal", "Gender reveal", "baby", "Countdown, venue and a guess-the-gender RSVP note.", []),
    ("welcome-baby", "Welcome baby", "baby", "Introduce the newest family member to the people who matter.", []),
    ("birthday", "Birthday", "parties", "Milestone or surprise, with dress code and directions.", []),
    ("anniversary", "Anniversary", "parties", "Celebrate the years together with a programme and menu.", ["menu"]),
    ("private-celebration", "Private celebration", "parties", "Dinners, launches and get-togethers by invitation.", []),
    ("graduation", "Graduation", "other", "Ceremony details, after-party and family seating.", []),
    ("corporate", "Corporate event", "other", "Agenda, catering choices and seating for teams and clients.", ["menu", "seating"]),
    ("family-celebration", "Family celebration", "other", "Reunions, unveilings and milestones, organised in one link.", ["family_sides"]),
]

# slug, name, design key, direction, groups, description, tags
TEMPLATES = [
    ("atelier", "Atelier", "atelier", "Minimalist luxury", ["weddings", "other", "parties"],
     "Ivory and ink, a fine serif and generous space. A centred monogram leads into one calm column.", ["ivory", "serif", "monogram"]),
    ("folio", "Folio", "folio", "Modern editorial", ["weddings", "parties", "other"],
     "A magazine spread: oversized headline, an index that follows you down the page, and a split layout.", ["editorial", "split", "bold type"]),
    ("bloom", "Bloom", "bloom", "Romantic floral", ["weddings", "baby"],
     "Blush and sage with drawn botanicals, arched frames and a flowing script for your names.", ["floral", "script", "arches"]),
    ("heritage", "Heritage", "heritage", "African traditional luxury", ["weddings", "other"],
     "Rich ochre, indigo and terracotta with geometric beadwork borders. Built for several ceremonies and both families.", ["traditional", "pattern", "multi-ceremony"]),
    ("champagne", "Champagne", "champagne", "Champagne and gold", ["weddings", "parties", "other"],
     "Midnight backdrop, gold foil lettering and Art Deco fans. Glass panels catch the light.", ["deco", "dark", "gold"]),
    ("linea", "Linea", "linea", "Contemporary minimalist", ["weddings", "other", "parties"],
     "A strict grid, a clean sans and a horizontal timeline. Quietly modern.", ["grid", "sans", "timeline"]),
    ("confetti", "Confetti", "confetti", "Pastel celebrations", ["baby", "parties"],
     "Soft pastels, rounded type and playful paper shapes for showers, reveals and first birthdays.", ["pastel", "playful", "rounded"]),
    ("pulse", "Pulse", "pulse", "Bold modern celebrations", ["parties", "other"],
     "Big type, strong colour blocks and a scrolling ticker. For birthdays that mean it.", ["bold", "colour block", "ticker"]),
    ("aurora", "Aurora", "aurora", "Glass and light", ["weddings", "parties", "other", "baby"],
     "Frosted glass cards over a slow, iridescent light field. Our most futuristic design.", ["glass", "glossy", "modern"]),
    ("laureate", "Laureate", "laureate", "Classic honours", ["other", "parties"],
     "Navy and gold, a crest monogram and a two-column agenda. Made for graduations and formal functions.", ["formal", "crest", "agenda"]),
    ("cradle", "Cradle", "cradle", "Soft storybook", ["baby"],
     "Cream, sage and hand-drawn moons and stars, laid out like the pages of a picture book.", ["storybook", "soft", "illustrated"]),
]

FEATURES = {
    # Essential
    "website": "Personalised event website",
    "premium_template": "Premium template",
    "invitation": "Digital invitation",
    "unlimited_sharing": "Unlimited event link sharing",
    "rsvp": "RSVP functionality",
    "maps": "Google Maps directions",
    "countdown": "Countdown timer",
    "basic_dashboard": "Basic guest dashboard",
    "email_notifications": "Email notifications",
    # Premium
    "advanced_design": "Advanced website customisation",
    "guest_management": "Guest management (add, import, edit)",
    "seating": "Seating chart",
    "menu": "Digital menu",
    "programme": "Event programme",
    "dietary": "Dietary requirements",
    "reports": "Downloadable guest reports",
    "personal_invites": "Personalised guest invitations",
    "gallery": "Photo gallery",
    "reminders": "RSVP reminders",
    "multi_functions": "Additional event functions",
    # Signature
    "multi_pages": "Multiple event pages",
    "guest_categories": "Multiple guest categories",
    "advanced_seating": "Advanced seating management",
    "custom_pdf": "Custom PDF invitation designs",
    "co_admins": "Additional administrator access",
    "advanced_comms": "Advanced guest communication",
    "custom_domain": "Custom domain support",
    "detailed_reports": "Detailed event reporting",
    "priority_support": "Priority support",
    "extended_hosting": "Extended hosting period",
}

ESSENTIAL = ["website", "premium_template", "invitation", "unlimited_sharing", "rsvp", "maps",
             "countdown", "basic_dashboard", "email_notifications"]
PREMIUM = ESSENTIAL + ["advanced_design", "guest_management", "seating", "menu", "programme", "dietary",
                       "reports", "personal_invites", "gallery", "reminders", "multi_functions"]
SIGNATURE = PREMIUM + ["multi_pages", "guest_categories", "advanced_seating", "custom_pdf", "co_admins",
                       "advanced_comms", "custom_domain", "detailed_reports", "priority_support", "extended_hosting"]

LIMIT_LABELS = {
    "email_sends": "Guest emails included",
    "hosting_months": "Website hosted for (months)",
    "functions": "Event functions (ceremonies, receptions)",
    "admins": "Administrators",
    "gallery_photos": "Gallery photos",
}

PACKAGES = [
    {"code": "essential", "name": "Essential Experience", "tagline": "A beautiful event website with RSVPs.",
     "price_cents": 899_900, "features": ESSENTIAL, "rank": 1, "highlight": 0,
     "limits": {"email_sends": 300, "hosting_months": 6, "functions": 1, "admins": 1, "gallery_photos": 0},
     "bullets": [FEATURES[k] for k in ESSENTIAL]},
    {"code": "premium", "name": "Premium Experience", "tagline": "Guests, seating, menus and reports, all managed.",
     "price_cents": 1_299_900, "features": PREMIUM, "rank": 2, "highlight": 1,
     "limits": {"email_sends": 1500, "hosting_months": 9, "functions": 3, "admins": 1, "gallery_photos": 40},
     "bullets": ["Everything in Essential"] + [FEATURES[k] for k in PREMIUM if k not in ESSENTIAL]},
    {"code": "signature", "name": "Signature Experience", "tagline": "For multi-day, multi-family and formal events.",
     "price_cents": 1_799_900, "features": SIGNATURE, "rank": 3, "highlight": 0,
     "limits": {"email_sends": 5000, "hosting_months": 18, "functions": 8, "admins": 4, "gallery_photos": 150},
     "bullets": ["Everything in Premium"] + [FEATURES[k] for k in SIGNATURE if k not in PREMIUM]},
]


def ensure_catalog() -> None:
    if not db.val("SELECT COUNT(*) FROM categories"):
        for i, (slug, name, group, desc, feats) in enumerate(CATEGORIES):
            db.insert("categories", {"slug": slug, "name": name, "group_slug": group, "description": desc,
                                     "features": db.dumps(feats), "sort": i})
    existing = {r["slug"] for r in db.q("SELECT slug FROM templates")}
    for i, (slug, name, design, direction, groups, desc, tags) in enumerate(TEMPLATES):
        if slug not in existing:
            db.insert("templates", {"slug": slug, "name": name, "design": design, "direction": direction,
                                    "groups": db.dumps(groups), "description": desc, "tags": db.dumps(tags),
                                    "sort": i, "updated_at": db.now()})
    if not db.val("SELECT COUNT(*) FROM packages"):
        for p in PACKAGES:
            db.insert("packages", {"code": p["code"], "name": p["name"], "tagline": p["tagline"],
                                   "price_cents": p["price_cents"], "features": db.dumps(p["features"]),
                                   "bullets": db.dumps(p["bullets"]), "limits": db.dumps(p["limits"]),
                                   "rank": p["rank"], "highlight": p["highlight"], "updated_at": db.now()})


# --- lookups -------------------------------------------------------------------------------
def categories(active_only: bool = True):
    sql = "SELECT * FROM categories" + (" WHERE active = 1" if active_only else "") + " ORDER BY sort, name"
    return db.q(sql)


def category(slug: str):
    return db.one("SELECT * FROM categories WHERE slug = ?", (slug,))


def category_name(slug: str) -> str:
    c = category(slug)
    return c["name"] if c else slug.replace("-", " ").capitalize()


def category_features(slug: str) -> list:
    c = category(slug)
    return db.loads(c["features"], []) if c else []


def templates(group: Optional[str] = None, active_only: bool = True):
    rows = db.q("SELECT * FROM templates" + (" WHERE active = 1" if active_only else "") + " ORDER BY sort, name")
    if group:
        rows = [r for r in rows if group in db.loads(r["groups"], [])]
    return rows


def template(slug: str):
    return db.one("SELECT * FROM templates WHERE slug = ?", (slug,))


def packages(active_only: bool = True):
    return db.q("SELECT * FROM packages" + (" WHERE active = 1" if active_only else "") + " ORDER BY rank")


def package(code: Optional[str]):
    if not code:
        return None
    return db.one("SELECT * FROM packages WHERE code = ?", (code,))


def package_features(code: Optional[str]) -> set:
    p = package(code)
    return set(db.loads(p["features"], [])) if p else set()


def package_limits(code: Optional[str]) -> dict:
    p = package(code)
    return db.loads(p["limits"], {}) if p else {}


def money(cents: int, decimals: bool = False) -> str:
    """R12,999 style; Rand uses a comma as thousands separator here for readability."""
    rands = cents / 100
    if decimals:
        return "R" + f"{rands:,.2f}"
    return "R" + f"{rands:,.0f}"


# --- per-event entitlement --------------------------------------------------------------
def planning_package(event) -> str:
    """Package whose tools the organiser can use: the paid one, else the one being considered."""
    return event["paid_package"] or event["selected_package"] or "premium"


def is_paid(event) -> bool:
    return bool(event["paid_package"])


def has_feature(event, key: str, public: bool = False) -> bool:
    """`public=True` asks whether guests may see it, which needs a verified payment."""
    code = event["paid_package"] if public else planning_package(event)
    return key in package_features(code)


def limit(event, key: str, default: int = 0) -> int:
    return int(package_limits(planning_package(event)).get(key, default))
