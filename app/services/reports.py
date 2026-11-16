"""Organiser reports as CSV (Excel-friendly, UTF-8 with BOM) and PDF.

    filename, data, content_type = build(ev, "final", "pdf")
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Optional

from .. import catalog, db, events
from ..views.forms import fmt_date, fmt_dt, fmt_time
from .pdf import PDF

KINDS = {
    "guests": ("Complete guest list", "Everyone on the list with contact details, status, party size and table."),
    "rsvp": ("RSVP report", "Every response with plus-ones, children, meal and requests."),
    "seating": ("Seating chart", "Tables, occupancy and who sits where."),
    "dietary": ("Dietary report", "Dietary requirements and allergies of attending guests, for the caterer."),
    "meals": ("Meal selection report", "Meal choice counts and each guest's selection."),
    "outstanding": ("Outstanding RSVP report", "Guests who haven't replied yet, with contact details."),
    "final": ("Final event administration report", "Totals, guests, meals, dietary needs, requests and seating in one document."),
}
FORMATS = ("csv", "pdf")
STATUS = {"attending": "Attending", "declined": "Declined", "pending": "Pending"}


def _guests(event_id: int):
    return db.q("""SELECT g.*, m.name AS meal_name, t.name AS table_name
                   FROM guests g
                   LEFT JOIN menu_items m ON m.id = g.meal_item_id
                   LEFT JOIN seat_assignments a ON a.guest_id = g.id
                   LEFT JOIN seating_tables t ON t.id = a.table_id
                   WHERE g.event_id = ?
                   ORDER BY g.last_name COLLATE NOCASE, g.first_name COLLATE NOCASE""", (event_id,))


def _csv(headers: list, rows: list) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(headers)
    for r in rows:
        w.writerow(["" if v is None else _safe_cell(v) for v in r])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _safe_cell(v):
    """Neutralise spreadsheet formula injection in text cells."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") and not v[1:].replace(".", "").isdigit():
        return "'" + v
    return v


def _subtitle(ev) -> str:
    bits = [events.title(ev)]
    if ev.get("event_date"):
        bits.append(fmt_date(ev["event_date"]))
    venue = (ev.get("venue") or {}).get("name")
    if venue:
        bits.append(venue)
    return " · ".join(bits)


def _party(g) -> int:
    return events.party_size(g) if g["status"] != "declined" else 0


def _totals(ev) -> list:
    s = events.stats(ev["id"])
    return [("Total invited", s["invited"]), ("Confirmed", s["attending"]), ("Declined", s["declined"]),
            ("Pending RSVPs", s["pending"]), ("Plus-ones attending", s["plus_ones"]),
            ("Children attending", s["children"]), ("Total headcount", s["headcount"]),
            ("RSVP completion", f"{s['completion']}%")]


def _table_rows(ev):
    tables = events.tables(ev["id"])
    seated = {}
    for r in db.q("""SELECT a.table_id, g.* FROM seat_assignments a JOIN guests g ON g.id = a.guest_id
                     WHERE a.event_id = ? ORDER BY g.last_name COLLATE NOCASE, g.first_name COLLATE NOCASE""", (ev["id"],)):
        seated.setdefault(r["table_id"], []).append(r)
    return tables, seated


def build(ev: dict, kind: str, fmt: str, user_id: Optional[int] = None, delivered: str = "download"):
    if kind not in KINDS or fmt not in FORMATS:
        raise ValueError("Unknown report")
    if not isinstance(ev, dict) or not isinstance(ev.get("venue"), dict):
        ev = events.by_id(ev["id"])
    title, _ = KINDS[kind]
    guests = _guests(ev["id"])
    filename = f"{ev['slug']}-{kind}.{fmt}"
    data = _BUILDERS[kind](ev, guests, fmt, title)
    if user_id is not None:
        db.insert("report_runs", {"event_id": ev["id"], "user_id": user_id, "kind": kind, "format": fmt,
                                  "delivered": delivered, "created_at": db.now()})
    ctype = "text/csv; charset=utf-8" if fmt == "csv" else "application/pdf"
    return filename, data, ctype


# --- builders ---------------------------------------------------------------------------------
def _b_guests(ev, guests, fmt, title):
    headers = ["First name", "Last name", "Email", "Phone", "Category", "Family group", "Side", "VIP", "Child",
               "Status", "Plus-ones", "Children", "Party size", "Table", "Checked in"]
    rows = [[g["first_name"], g["last_name"], g["email"], g["phone"], g["category"], g["family_group"], g["side"],
             "Yes" if g["is_vip"] else "", "Yes" if g["is_child"] else "", STATUS[g["status"]], g["plus_ones"],
             g["children"], _party(g), g["table_name"] or "", "Yes" if g["checked_in_at"] else ""] for g in guests]
    if fmt == "csv":
        return _csv(headers, rows)
    doc = PDF(title, _subtitle(ev))
    doc.kv(_totals(ev)[:4])
    doc.table(["Name", "Contact", "Category", "Status", "Party", "Table"],
              [[events.guest_name(g) + (" (VIP)" if g["is_vip"] else ""), g["email"] or g["phone"],
                " / ".join(x for x in (g["category"], g["family_group"]) if x), STATUS[g["status"]], _party(g),
                g["table_name"] or ""] for g in guests], [2.2, 2.4, 1.8, 1.1, .7, 1.2])
    return doc.output()


def _b_rsvp(ev, guests, fmt, title):
    headers = ["Name", "Status", "Responded", "Plus-ones", "Plus-one names", "Children", "Meal", "Dietary",
               "Allergies", "Special requests", "Source"]
    rows = [[events.guest_name(g), STATUS[g["status"]], fmt_dt(g["responded_at"]), g["plus_ones"], g["plus_one_names"],
             g["children"], g["meal_name"] or "", g["dietary"], g["allergies"], g["special_requests"],
             {"general_link": "General link", "import": "Imported"}.get(g["source"], "Organiser")] for g in guests]
    if fmt == "csv":
        return _csv(headers, rows)
    doc = PDF(title, _subtitle(ev))
    doc.kv(_totals(ev))
    for status in ("attending", "declined", "pending"):
        subset = [g for g in guests if g["status"] == status]
        doc.heading(f"{STATUS[status]} ({len(subset)})")
        doc.table(["Name", "Replied", "+1", "Kids", "Meal", "Notes"],
                  [[events.guest_name(g), fmt_dt(g["responded_at"]), g["plus_ones"] or "", g["children"] or "",
                    g["meal_name"] or "", "; ".join(x for x in (g["dietary"], g["allergies"], g["special_requests"]) if x)]
                   for g in subset], [2, 1.6, .5, .5, 1.6, 3])
    return doc.output()


def _b_seating(ev, guests, fmt, title):
    tables, seated = _table_rows(ev)
    if fmt == "csv":
        rows = []
        for t in tables:
            people = seated.get(t["id"], [])
            if not people:
                rows.append([t["name"], t["capacity"], t["seated"], "", "", ""])
            for g in people:
                rows.append([t["name"], t["capacity"], t["seated"], events.guest_name(g), STATUS[g["status"]], _party(g)])
        assigned = {g["id"] for ps in seated.values() for g in ps}
        for g in guests:
            if g["status"] == "attending" and g["id"] not in assigned:
                rows.append(["Unassigned", "", "", events.guest_name(g), STATUS[g["status"]], _party(g)])
        return _csv(["Table", "Capacity", "Seated", "Guest", "Status", "Party size"], rows)
    doc = PDF(title, _subtitle(ev))
    doc.table(["Table", "Capacity", "Seated", "Free"],
              [[t["name"], t["capacity"], t["seated"], _free(t)] for t in tables],
              [3, 1, 1, 1])
    for t in tables:
        people = seated.get(t["id"], [])
        doc.heading(f"{t['name']}  ·  {t['seated']} of {t['capacity']}")
        if t["notes"]:
            doc.text(t["notes"], 9, muted=True)
        doc.table(["Guest", "Party", "Meal / dietary"],
                  [[events.guest_name(g) + (f" + {g['plus_one_names'] or g['plus_ones']}" if g["plus_ones"] else ""),
                    _party(g), "; ".join(x for x in (_meal(g), g["dietary"], g["allergies"]) if x)] for g in people],
                  [3, .8, 3])
    assigned = {g["id"] for ps in seated.values() for g in ps}
    loose = [g for g in guests if g["status"] == "attending" and g["id"] not in assigned]
    if loose:
        doc.heading(f"Not yet seated ({len(loose)})")
        doc.table(["Guest", "Party"], [[events.guest_name(g), _party(g)] for g in loose], [4, 1])
    return doc.output()


def _free(t) -> str:
    free = t["capacity"] - t["seated"]
    return str(free) if free >= 0 else f"Over by {-free}"


def _att(g, key):
    return (g[key] or "") if g["status"] == "attending" else ""


def _meal(g):
    try:
        return g["meal_name"] or ""
    except (IndexError, KeyError):
        row = db.one("SELECT name FROM menu_items WHERE id = ?", (g["meal_item_id"],)) if g["meal_item_id"] else None
        return row["name"] if row else ""


def _b_dietary(ev, guests, fmt, title):
    subset = [g for g in guests if g["status"] == "attending" and (g["dietary"] or g["allergies"])]
    rows = [[events.guest_name(g), g["dietary"], g["allergies"], g["meal_name"] or "", g["table_name"] or ""] for g in subset]
    if fmt == "csv":
        return _csv(["Guest", "Dietary requirements", "Allergies", "Meal", "Table"], rows)
    doc = PDF(title, _subtitle(ev))
    counts = Counter()
    for g in subset:
        for part in (g["dietary"] or "").split(","):
            if part.strip():
                counts[part.strip()] += 1
    if counts:
        doc.kv([(k, v) for k, v in counts.most_common()])
    doc.table(["Guest", "Dietary", "Allergies", "Meal", "Table"], rows, [2, 2, 2, 1.6, 1])
    return doc.output()


def _b_meals(ev, guests, fmt, title):
    attending = [g for g in guests if g["status"] == "attending"]
    counts = Counter(g["meal_name"] or "No selection" for g in attending)
    options = [m["name"] for m in events.meal_options(ev["id"])]
    for o in options:
        counts.setdefault(o, 0)
    if fmt == "csv":
        rows = [["Count", k, v, ""] for k, v in sorted(counts.items())]
        rows += [["Guest", events.guest_name(g), g["meal_name"] or "No selection", g["dietary"]] for g in attending]
        return _csv(["Row type", "Name", "Meal / count", "Dietary"], rows)
    doc = PDF(title, _subtitle(ev))
    doc.heading("Totals")
    doc.kv([(k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])])
    doc.heading("By guest")
    doc.table(["Guest", "Meal", "Dietary", "Table"],
              [[events.guest_name(g), g["meal_name"] or "No selection", g["dietary"], g["table_name"] or ""] for g in attending],
              [2, 2, 2, 1])
    return doc.output()


def _b_outstanding(ev, guests, fmt, title):
    subset = [g for g in guests if g["status"] == "pending"]
    rows = [[events.guest_name(g), g["email"], g["phone"], g["category"], g["family_group"], fmt_dt(g["invited_at"]),
             events.invite_url(ev, g)] for g in subset]
    if fmt == "csv":
        return _csv(["Guest", "Email", "Phone", "Category", "Family group", "Invited", "Personal link"], rows)
    doc = PDF(title, _subtitle(ev))
    deadline = (ev.get("guest_settings") or {}).get("rsvp_deadline")
    doc.text(f"{len(subset)} guests haven't replied." + (f" RSVP deadline: {fmt_date(deadline)}." if deadline else ""))
    doc.table(["Guest", "Email", "Phone", "Group"], [r[:4] for r in rows], [2, 2.6, 1.6, 1.4])
    return doc.output()


def _b_final(ev, guests, fmt, title):
    tables, seated = _table_rows(ev)
    attending = [g for g in guests if g["status"] == "attending"]
    meal_counts = Counter(g["meal_name"] or "No selection" for g in attending)
    if fmt == "csv":
        rows = [["Summary", k, v, "", "", "", "", "", ""] for k, v in _totals(ev)]
        rows += [["Meal total", k, v, "", "", "", "", "", ""] for k, v in sorted(meal_counts.items())]
        rows += [["Table", t["name"], f"{t['seated']} of {t['capacity']}", "", "", "", "", "", ""] for t in tables]
        rows += [["Guest", events.guest_name(g), STATUS[g["status"]], g["plus_ones"], g["children"], g["meal_name"] or "",
                  "; ".join(x for x in (g["dietary"], g["allergies"]) if x), g["special_requests"], g["table_name"] or ""]
                 for g in guests]
        return _csv(["Section", "Name", "Status / value", "Plus-ones", "Children", "Meal", "Dietary and allergies",
                     "Special requests", "Table"], rows)
    doc = PDF(title, _subtitle(ev))
    venue = ev.get("venue") or {}
    doc.kv([("Event", ev["name"]), ("Date", fmt_date(ev.get("event_date")) or "To be confirmed"),
            ("Time", " to ".join(x for x in (fmt_time(ev.get("start_time")), fmt_time(ev.get("end_time"))) if x) or "To be confirmed"),
            ("Venue", ", ".join(x for x in (venue.get("name"), venue.get("address")) if x) or "To be confirmed")])
    doc.heading("Totals")
    doc.kv(_totals(ev))
    doc.heading("Meal selections")
    doc.kv([(k, v) for k, v in sorted(meal_counts.items(), key=lambda kv: -kv[1])] or [("Meals", "No selections yet")])
    if catalog.has_feature(ev, "detailed_reports"):
        doc.heading("By guest category")
        cats = Counter((g["category"] or "Uncategorised") for g in attending)
        doc.kv([(k, f"{v} attending") for k, v in cats.most_common()] or [("Categories", "None")])
    doc.heading("Table occupancy")
    doc.table(["Table", "Capacity", "Seated", "Free"],
              [[t["name"], t["capacity"], t["seated"], _free(t)] for t in tables], [3, 1, 1, 1])
    doc.heading("Guests")
    doc.table(["Guest", "Status", "+1", "Kids", "Meal", "Dietary / allergies", "Requests", "Table"],
              [[events.guest_name(g), STATUS[g["status"]], _att(g, "plus_ones"), _att(g, "children"), g["meal_name"] or "",
                "; ".join(x for x in (g["dietary"], g["allergies"]) if x), g["special_requests"], g["table_name"] or ""]
               for g in guests], [1.8, 1, .45, .6, 1.3, 1.6, 1.6, 1])
    return doc.output()


_BUILDERS = {"guests": _b_guests, "rsvp": _b_rsvp, "seating": _b_seating, "dietary": _b_dietary,
             "meals": _b_meals, "outstanding": _b_outstanding, "final": _b_final}


def final_attachments(ev, user_id: Optional[int] = None) -> list:
    out = []
    for fmt in ("pdf", "csv"):
        name, data, ctype = build(ev, "final", fmt, user_id=user_id, delivered="email")
        out.append((name, data, ctype.split(";")[0]))
    return out
