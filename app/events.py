"""Event model helpers shared by the wizard, dashboard, event websites, admin and emails."""
from __future__ import annotations

import re
import secrets
from typing import Optional

from . import catalog, config, db

SECTION_KEYS = [
    # key, label, feature needed (None = every package)
    ("welcome", "Welcome", None),
    ("invitation", "Invitation", "invitation"),
    ("countdown", "Countdown", "countdown"),
    ("venue", "Venue and directions", "maps"),
    ("programme", "Programme", "programme"),
    ("menu", "Menu", "menu"),
    ("dress_code", "Dress code", None),
    ("rsvp", "RSVP", "rsvp"),
    ("seating", "Your table (personal links only)", "seating"),
    ("accommodation", "Accommodation", None),
    ("registry", "Gift registry", None),
    ("gallery", "Photo gallery", "gallery"),
    ("contact", "Contact", None),
]
SECTION_LABELS = {k: label for k, label, _ in SECTION_KEYS}
SECTION_FEATURE = {k: f for k, _, f in SECTION_KEYS}

STATUS_LABELS = {"draft": "Draft", "published": "Published", "unpublished": "Unpublished",
                 "suspended": "Suspended", "archived": "Archived"}

DIETARY_OPTIONS = ["Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "Dairy-free", "Nut allergy",
                   "Seafood allergy", "Diabetic", "No pork", "No red meat"]

JSON_FIELDS = ("venue", "design", "guest_settings", "info", "sections", "report_prefs", "wizard_done")


def parse(row) -> Optional[dict]:
    if row is None:
        return None
    ev = dict(row)
    for k in JSON_FIELDS:
        ev[k] = db.loads(ev.get(k), [] if k == "wizard_done" else {})
    return ev


def get(uid: str) -> Optional[dict]:
    return parse(db.one("SELECT * FROM events WHERE uid = ?", (uid,)))


def by_id(event_id: int) -> Optional[dict]:
    return parse(db.one("SELECT * FROM events WHERE id = ?", (event_id,)))


def by_slug(slug: str) -> Optional[dict]:
    return parse(db.one("SELECT * FROM events WHERE slug = ?", (slug,)))


def save_json(event_id: int, field: str, value) -> None:
    assert field in JSON_FIELDS
    db.run(f"UPDATE events SET {field} = ?, updated_at = ? WHERE id = ?", (db.dumps(value), db.now(), event_id))


def touch(event_id: int, **fields) -> None:
    fields["updated_at"] = db.now()
    db.update("events", event_id, fields)


RESERVED_SLUGS = {"new", "admin", "api", "static", "media", "dashboard", "login", "logout", "create", "templates"}


def unique_slug(base: str, exclude_id: Optional[int] = None) -> str:
    from .views.forms import slugify
    slug = slugify(base, 50)
    if slug in RESERVED_SLUGS:
        slug += "-event"
    candidate, n = slug, 2
    while True:
        row = db.one("SELECT id FROM events WHERE slug = ?", (candidate,))
        if row is None or row["id"] == exclude_id:
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


def default_sections() -> dict:
    return {k: True for k, _, _ in SECTION_KEYS}


def create(owner_id: int, category: str, template: str, name: str, hosts: str = "", is_demo: bool = False) -> dict:
    uid = secrets.token_hex(6)
    slug = unique_slug(hosts or name)
    now = db.now()
    feats = catalog.category_features(category)
    gs = {"estimated": 0, "categories": ["Family", "Friends"], "family_groups": [],
          "children_allowed": False, "max_children": 0, "plus_one_policy": "per_guest",
          "plus_ones_default": 0, "rsvp_deadline": ""}
    if "family_sides" in feats:
        gs["sides"] = ["Bride's family", "Groom's family"]
    event_id = db.insert("events", {
        "uid": uid, "owner_id": owner_id, "slug": slug, "status": "draft", "category": category,
        "template": template, "name": name, "hosts": hosts, "venue": "{}", "design": "{}",
        "guest_settings": db.dumps(gs), "info": "{}", "sections": db.dumps(default_sections()),
        "report_prefs": db.dumps({"summary": "weekly", "new_rsvp": True, "auto_reminders": True}),
        "selected_package": "premium", "wizard_step": 1, "wizard_done": "[]", "is_demo": 1 if is_demo else 0,
        "created_at": now, "updated_at": now,
    })
    return by_id(event_id)


def public_url(ev) -> str:
    return f"{config.BASE_URL}/events/{ev['slug']}"


def public_path(ev) -> str:
    return f"/events/{ev['slug']}"


def invite_url(ev, guest) -> str:
    return f"{config.BASE_URL}/events/{ev['slug']}/i/{guest['token']}"


def new_guest_token() -> str:
    return secrets.token_urlsafe(12)


def add_pasted_guests(ev, people: list[dict]) -> int:
    """Add guests from suggestions.parse_guest_list(). People already on the list (same name, or same
    email or mobile) are skipped. Returns how many were added."""
    have = db.q("SELECT first_name, last_name, email, phone FROM guests WHERE event_id = ?", (ev["id"],))
    names = {f"{g['first_name']} {g['last_name']}".strip().lower() for g in have}
    emails = {g["email"].lower() for g in have if g["email"]}
    phones = {re.sub(r"\D", "", g["phone"]) for g in have if g["phone"]}
    now, added = db.now(), 0
    for p in people:
        digits = re.sub(r"\D", "", p.get("phone", ""))
        if p["name"].lower() in names or (p.get("email") and p["email"] in emails) or (digits and digits in phones):
            continue
        first, _, last = p["name"].partition(" ")
        db.insert("guests", {"event_id": ev["id"], "token": new_guest_token(), "first_name": first[:60], "last_name": last[:80],
                             "email": p.get("email", "")[:200], "phone": p.get("phone", "")[:40], "source": "import",
                             "email_consent": 1, "created_at": now, "updated_at": now})
        names.add(p["name"].lower())
        if p.get("email"):
            emails.add(p["email"])
        if digits:
            phones.add(digits)
        added += 1
    return added


def is_live(ev) -> bool:
    """Guests can open the website."""
    return ev["status"] == "published" and bool(ev["paid_package"])


def title(ev) -> str:
    return ev["hosts"] or ev["name"]


# --- related records -------------------------------------------------------------------------
def functions(event_id: int):
    return db.q("SELECT * FROM event_functions WHERE event_id = ? ORDER BY sort, func_date, start_time, id", (event_id,))


def schedule(event_id: int):
    return db.q("""SELECT s.*, f.name AS function_name FROM schedule_items s
                   LEFT JOIN event_functions f ON f.id = s.function_id
                   WHERE s.event_id = ? ORDER BY COALESCE(f.sort, 0), s.sort, s.item_time, s.id""", (event_id,))


def menus(event_id: int) -> list[dict]:
    out = []
    for m in db.q("SELECT * FROM menus WHERE event_id = ? ORDER BY sort, id", (event_id,)):
        items = [dict(r, tags=db.loads(r["tags"], [])) for r in
                 db.q("SELECT * FROM menu_items WHERE menu_id = ? ORDER BY sort, id", (m["id"],))]
        out.append(dict(m, items=items))
    return out


def meal_options(event_id: int):
    return db.q("SELECT * FROM menu_items WHERE event_id = ? AND selectable = 1 ORDER BY sort, id", (event_id,))


def uploads(event_id: int, kind: Optional[str] = None):
    if kind:
        return db.q("SELECT * FROM uploads WHERE event_id = ? AND kind = ? ORDER BY sort, id", (event_id, kind))
    return db.q("SELECT * FROM uploads WHERE event_id = ? ORDER BY kind, sort, id", (event_id,))


def upload_url(upload) -> str:
    return f"/media/{upload['storage_key']}" if upload else ""


def tables(event_id: int) -> list[dict]:
    rows = db.q("""SELECT t.*,
                     COALESCE(SUM(CASE WHEN g.status != 'declined' THEN 1 + g.plus_ones + g.children ELSE 0 END), 0) AS seated,
                     COUNT(g.id) AS parties
                   FROM seating_tables t
                   LEFT JOIN seat_assignments a ON a.table_id = t.id
                   LEFT JOIN guests g ON g.id = a.guest_id
                   WHERE t.event_id = ? GROUP BY t.id ORDER BY t.sort, t.id""", (event_id,))
    return [dict(r) for r in rows]


def party_size(g) -> int:
    return 1 + int(g["plus_ones"] or 0) + int(g["children"] or 0)


def stats(event_id: int) -> dict:
    r = db.one("""SELECT COUNT(*) AS invited,
                    SUM(status = 'attending') AS attending, SUM(status = 'declined') AS declined,
                    SUM(status = 'pending') AS pending,
                    SUM(CASE WHEN status = 'attending' THEN plus_ones ELSE 0 END) AS plus_ones,
                    SUM(CASE WHEN status = 'attending' THEN children ELSE 0 END) AS children
                  FROM guests WHERE event_id = ?""", (event_id,))
    invited = r["invited"] or 0
    attending = r["attending"] or 0
    declined = r["declined"] or 0
    pending = r["pending"] or 0
    plus = r["plus_ones"] or 0
    kids = r["children"] or 0
    responded = attending + declined
    seated = db.val("""SELECT COUNT(*) FROM seat_assignments a JOIN guests g ON g.id = a.guest_id
                       WHERE a.event_id = ? AND g.status = 'attending'""", (event_id,), 0)
    return {
        "invited": invited, "attending": attending, "declined": declined, "pending": pending,
        "plus_ones": plus, "children": kids, "headcount": attending + plus + kids,
        "responded": responded, "completion": round(100 * responded / invited) if invited else 0,
        "seated_parties": seated, "unseated_parties": max(0, attending - seated),
    }


def guest_name(g) -> str:
    return f"{g['first_name']} {g['last_name']}".strip()


def visible_sections(ev, public: bool = True) -> dict:
    """Sections switched on by the organiser and allowed by the package (paid one when public)."""
    chosen = {**default_sections(), **(ev.get("sections") or {})}
    out = {}
    for key, _, feature in SECTION_KEYS:
        allowed = feature is None or catalog.has_feature(ev, feature, public=public)
        out[key] = bool(chosen.get(key)) and allowed
    return out


def email_quota(ev) -> tuple[int, int]:
    """(used, allowed) guest emails for this event."""
    allowed = catalog.limit(ev, "email_sends", 0)
    used = db.val("SELECT COUNT(*) FROM email_logs WHERE event_id = ? AND audience = 'guest' AND status = 'sent'",
                  (ev["id"],), 0)
    return used, allowed


def package_gaps(ev, code: str) -> list[str]:
    """What this event already has that package `code` would not show guests, in plain words.
    Used on the review and package steps so nobody pays for less than they set up."""
    feats, lim = catalog.package_features(code), catalog.package_limits(code)
    gaps = []
    n = db.val("SELECT COUNT(*) FROM schedule_items WHERE event_id = ?", (ev["id"],), 0)
    if n and "programme" not in feats:
        gaps.append(f"your programme ({n} item{'s' if n != 1 else ''})")
    n = db.val("SELECT COUNT(*) FROM menu_items WHERE event_id = ?", (ev["id"],), 0)
    if n and "menu" not in feats:
        gaps.append(f"your menu ({n} dish{'es' if n != 1 else ''})")
    if db.val("SELECT COUNT(*) FROM seating_tables WHERE event_id = ?", (ev["id"],), 0) and "seating" not in feats:
        gaps.append("the seating chart")
    n = db.val("SELECT COUNT(*) FROM uploads WHERE event_id = ? AND kind = 'gallery'", (ev["id"],), 0)
    allowed = int(lim.get("gallery_photos", 0)) if "gallery" in feats else 0
    if n > allowed:
        gaps.append(f"your photo gallery ({n} photos)" if not allowed else f"{n - allowed} of your {n} gallery photos")
    n = db.val("SELECT COUNT(*) FROM event_functions WHERE event_id = ?", (ev["id"],), 0)
    allowed = int(lim.get("functions", 1)) if "multi_functions" in feats else 1
    if n > allowed:
        gaps.append(f"{n - allowed} of your {n} event functions")
    design = ev["design"] if isinstance(ev["design"], dict) else db.loads(ev["design"], {})
    if (design or {}).get("colors") and "advanced_design" not in feats:
        gaps.append("your own colours")
    gs = ev["guest_settings"] if isinstance(ev["guest_settings"], dict) else db.loads(ev["guest_settings"], {})
    if len((gs or {}).get("categories") or []) > 1 and "guest_categories" not in feats:
        gaps.append("several guest categories")
    return gaps


DRAFT_COOKIE = "aurelia_draft"


def draft_token(ev) -> str:
    """Token for the shareable draft preview (/events/<slug>/draft/<token>). Tied to the event's uid
    and creation time, so it stays the same for the event's life and works for nothing else."""
    from . import auth
    return auth.sign(f"{ev['uid']}~{ev['created_at']}", "draft-preview").rpartition(".")[2]


def draft_url(ev) -> str:
    return f"{config.BASE_URL}/events/{ev['slug']}/draft/{draft_token(ev)}"


def draft_token_ok(ev, token: str) -> bool:
    import hmac
    return bool(token) and hmac.compare_digest(token, draft_token(ev))
