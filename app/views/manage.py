"""Organiser tools: guests (with CSV import), RSVPs, seating editor, menu, programme, communications."""
from __future__ import annotations

import csv
import io
import json
import re
import secrets
from urllib.parse import quote

from .. import auth, catalog, db, events, notify
from ..icons import i
from ..services import email as mail
from ..web import HTTPError, Response, download, esc, json_response, redirect, router, url
from . import forms
from .forms import Form, csrf
from .shell import locked_panel, organiser_page, page_head

MEAL_PILL = ' <span class="pill pill--gold pill--plain">Meal option</span>'
BR_MUTED = '<br><span class="small muted">'
BR_SMALL = '<br><span class="small">'
COURSES = ["Canapés", "Starter", "Main", "Dessert", "Drinks", "Late-night", "Other"]
KINDS = [("ceremony", "Ceremony"), ("reception", "Reception"), ("speech", "Speech"), ("entertainment", "Entertainment"),
         ("activity", "Activity"), ("meal", "Meal"), ("other", "Other")]
STATUS_LABEL = {"attending": "Attending", "declined": "Declined", "pending": "Pending"}
DEFAULT_CATEGORIES = ["Family", "Friends", "Colleagues"]


# --- helpers ----------------------------------------------------------------------------------
def load(req, uid: str) -> dict:
    return events.parse(auth.event_for(req, uid))


def base(ev) -> str:
    return f"/dashboard/events/{ev['uid']}"


def has(ev, feature: str) -> bool:
    return catalog.has_feature(ev, feature)


def go(req, ev, suffix: str, kind: str = "", msg: str = ""):
    if msg:
        req.flash(kind or "success", msg)
    return redirect(base(ev) + suffix)


def _guest(ev, gid: int):
    g = db.one("SELECT * FROM guests WHERE id = ? AND event_id = ?", (gid, ev["id"]))
    if g is None:
        raise HTTPError(404)
    return g


def status_pill(status: str) -> str:
    return f'<span class="pill pill--{esc(status)}">{esc(STATUS_LABEL.get(status, status))}</span>'


def wa_digits(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    if d.startswith("0") and len(d) == 10:
        d = "27" + d[1:]
    return d


def guest_whatsapp(ev, g) -> str:
    msg = (f"Hi {g['first_name']}, you're invited to {ev['name']}. "
           f"Your personal invitation and RSVP link: {events.invite_url(ev, g)}")
    d = wa_digits(g["phone"])
    return f"https://wa.me/{d}?text={quote(msg)}" if d else f"https://wa.me/?text={quote(msg)}"


def categories_for(ev) -> list:
    gs = ev.get("guest_settings") or {}
    cats = [c for c in (gs.get("categories") or []) if c]
    if not has(ev, "guest_categories"):
        return DEFAULT_CATEGORIES
    return list(dict.fromkeys(cats + DEFAULT_CATEGORIES + ["VIP"]))


def tabs(ev, current: str, items: list) -> str:
    links = "".join(f'<a href="{base(ev)}{s}"{" aria-current=page" if s == current else ""}>{esc(l)}</a>' for s, l in items)
    return f'<nav class="tabs" aria-label="Section">{links}</nav>'


# =============================================================================================
# Guests
# =============================================================================================
@router.get("/dashboard/events/<uid>/guests")
def guests_list(req, uid):
    ev = load(req, uid)
    if not has(ev, "basic_dashboard"):
        return organiser_page(req, ev, "Guests", page_head("Guests") + locked_panel(ev, "basic_dashboard", "The guest dashboard"), "/guests")
    can_edit = has(ev, "guest_management")
    personal = has(ev, "personal_invites")
    st, cat, grp, qtext = req.arg("status"), req.arg("category"), req.arg("group"), req.arg("q").strip()
    sql = """SELECT g.*, t.name AS table_name FROM guests g
             LEFT JOIN seat_assignments a ON a.guest_id = g.id LEFT JOIN seating_tables t ON t.id = a.table_id
             WHERE g.event_id = ?"""
    params: list = [ev["id"]]
    if st in STATUS_LABEL:
        sql += " AND g.status = ?"
        params.append(st)
    if cat:
        sql += " AND g.category = ?"
        params.append(cat)
    if grp:
        sql += " AND g.family_group = ?"
        params.append(grp)
    if qtext:
        sql += " AND (g.first_name || ' ' || g.last_name LIKE ? OR g.email LIKE ? OR g.phone LIKE ?)"
        like = f"%{qtext}%"
        params += [like, like, like]
    sql += " ORDER BY g.last_name COLLATE NOCASE, g.first_name COLLATE NOCASE"
    rows = db.q(sql, params)
    s = events.stats(ev["id"])
    all_cats = [r[0] for r in db.q("SELECT DISTINCT category FROM guests WHERE event_id = ? AND category != '' ORDER BY 1", (ev["id"],))]
    all_groups = [r[0] for r in db.q("SELECT DISTINCT family_group FROM guests WHERE event_id = ? AND family_group != '' ORDER BY 1", (ev["id"],))]

    actions = ""
    if can_edit:
        actions = (f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/guests/import">{i("upload")}Import CSV</a>'
                   f'<a class="btn btn--primary btn--sm" href="{base(ev)}/guests/new">{i("plus")}Add guest</a>')
    head = page_head("Guests", f"{s['invited']} on the list · {s['headcount']} people attending including plus-ones and children.", actions)
    notice = ""
    if not can_edit:
        notice = ('<div class="notice" style="margin-bottom:16px">' + i("info") + '<div>Guests who RSVP through your '
                  'event link appear here. Adding, importing and editing guests is part of the Premium Experience. '
                  f'<a class="text-link" href="{base(ev)}/setup/8">Compare packages</a></div></div>')

    def opts(values, current, blank):
        return f'<option value="">{blank}</option>' + "".join(
            f'<option value="{esc(v)}"{" selected" if v == current else ""}>{esc(v)}</option>' for v in values)

    status_opts = opts(list(STATUS_LABEL), st, "All statuses").replace(">attending<", ">Attending<").replace(">declined<", ">Declined<").replace(">pending<", ">Pending<")
    toolbar = (f'<form class="toolbar" method="get" role="search">'
               f'<input class="input grow" type="search" name="q" value="{esc(qtext)}" placeholder="Search name, email or phone" aria-label="Search guests">'
               f'<select class="select" name="status" data-autosubmit aria-label="Status">{status_opts}</select>'
               + (f'<select class="select" name="category" data-autosubmit aria-label="Category">{opts(all_cats, cat, "All categories")}</select>' if all_cats else "")
               + (f'<select class="select" name="group" data-autosubmit aria-label="Family group">{opts(all_groups, grp, "All groups")}</select>' if all_groups else "")
               + '<button class="btn btn--secondary btn--sm" type="submit">Filter</button>'
               + (f'<a class="btn btn--ghost btn--sm" href="{base(ev)}/guests">Clear</a>' if (st or cat or grp or qtext) else "")
               + "</form>")
    if not rows:
        if st or cat or grp or qtext:
            body = '<div class="empty"><p>No guests match these filters.</p></div>'
        else:
            cta = (f'<div class="btn-row"><a class="btn btn--primary" href="{base(ev)}/guests/new">Add your first guest</a>'
                   f'<a class="btn btn--secondary" href="{base(ev)}/guests/import">Import a CSV</a></div>') if can_edit else \
                  f'<a class="btn btn--primary" href="{base(ev)}/share">Share your event link</a>'
            body = (f'<div class="empty"><span class="icon-tile icon-tile--soft">{i("users")}</span>'
                    f'<h2 style="font-size:1.25rem">No guests yet</h2><p>Add guests one by one, import a spreadsheet, '
                    f'or let guests RSVP through your shared link.</p>{cta}</div>')
    else:
        trs = []
        for g in rows:
            party = events.party_size(g)
            sub = " · ".join(x for x in (g["email"], g["phone"]) if x)
            tags = "".join(f'<span class="tag">{esc(t)}</span> ' for t in (g["category"], g["family_group"], g["side"]) if t)
            if g["is_vip"]:
                tags += '<span class="pill pill--gold pill--plain">VIP</span> '
            if g["unsubscribed_at"]:
                tags += '<span class="tag" title="Asked not to receive event emails">No emails</span>'
            row_actions = []
            if can_edit:
                row_actions.append(f'<a class="btn btn--ghost btn--sm" href="{base(ev)}/guests/{g["id"]}" aria-label="Edit {esc(events.guest_name(g))}">{i("edit")}</a>')
            if personal:
                row_actions.append(f'<button class="btn btn--ghost btn--sm" type="button" data-copy="{esc(events.invite_url(ev, g))}" data-copied="Personal link copied" aria-label="Copy personal link">{i("link")}</button>')
                row_actions.append(f'<a class="btn btn--ghost btn--sm" href="{esc(guest_whatsapp(ev, g))}" target="_blank" rel="noopener" aria-label="Send on WhatsApp">{i("chat")}</a>')
            if can_edit:
                label = "Undo check-in" if g["checked_in_at"] else "Check in"
                row_actions.append(f'<form method="post" action="{base(ev)}/guests/{g["id"]}/checkin" style="display:inline">{csrf(req)}'
                                   f'<button class="btn btn--ghost btn--sm" type="submit" title="{label}" aria-label="{label}">'
                                   f'{i("check") if not g["checked_in_at"] else i("close")}</button></form>')
            checked = f'<span class="pill pill--ok pill--plain" title="Checked in">Here</span>' if g["checked_in_at"] else ""
            box = (f'<td><input type="checkbox" name="ids" value="{g["id"]}" form="bulk" aria-label="Select {esc(events.guest_name(g))}"></td>'
                   if can_edit else "")
            trs.append(f'<tr>{box}<td><b>{esc(events.guest_name(g))}</b> {checked}<span class="table__sub">{esc(sub)}</span></td>'
                       f'<td>{tags or "<span class=muted>—</span>"}</td><td>{status_pill(g["status"])}</td>'
                       f'<td class="num mono">{party if g["status"] != "declined" else "—"}</td>'
                       f'<td>{esc(g["table_name"] or "")}</td><td style="white-space:nowrap;text-align:right">{"".join(row_actions)}</td></tr>')
        head_box = '<th><span class="sr-only">Select</span></th>' if can_edit else ""
        body = (f'<div class="table-wrap"><table class="table"><thead><tr>{head_box}<th>Guest</th><th>Groups</th><th>Status</th>'
                f'<th class="num">Party</th><th>Table</th><th><span class="sr-only">Actions</span></th></tr></thead>'
                f'<tbody>{"".join(trs)}</tbody></table></div>')
        if can_edit:
            cat_opts = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in categories_for(ev))
            body = (f'<form id="bulk" class="toolbar" method="post" action="{base(ev)}/guests/bulk" '
                    f'data-confirm="Apply this to the selected guests?">{csrf(req)}'
                    f'<span class="small muted">With selected:</span>'
                    f'<select class="select select--sm" name="action" aria-label="Bulk action"><option value="category">Set category</option>'
                    f'<option value="pending">Mark as pending</option><option value="delete">Delete</option></select>'
                    f'<select class="select select--sm" name="category" aria-label="Category">{cat_opts}</select>'
                    f'<button class="btn btn--secondary btn--sm" type="submit">Apply</button>'
                    f'<span class="small muted" style="margin-left:auto">{len(rows)} shown</span></form>') + body
    exports = ""
    if has(ev, "reports"):
        exports = (f'<div class="row" style="margin-top:14px"><span class="small muted">Download:</span>'
                   f'<a class="chip" href="{base(ev)}/reports/guests.csv">{i("download")}CSV</a>'
                   f'<a class="chip" href="{base(ev)}/reports/guests.pdf">{i("download")}PDF</a></div>')
    return organiser_page(req, ev, "Guests", head + notice + toolbar + body + exports, "/guests")


def _guest_form(req, ev, g=None, f: Form = None) -> str:
    v = dict(g) if g else {"plus_ones_allowed": (ev["guest_settings"] or {}).get("plus_ones_default", 0) or 0,
                           "children_allowed": 0, "email_consent": 1, "status": "pending", "plus_ones": 0, "children": 0}
    if f is not None:
        v.update({k: val for k, val in f.data.items()})
    errors = f.errors if f else {}
    gs = ev.get("guest_settings") or {}
    cats = categories_for(ev)
    groups = sorted(set(gs.get("family_groups") or []) | {r[0] for r in db.q(
        "SELECT DISTINCT family_group FROM guests WHERE event_id = ? AND family_group != ''", (ev["id"],))})
    sides = gs.get("sides") or []
    meals = events.meal_options(ev["id"])
    datalist = "".join(f'<option value="{esc(x)}">' for x in groups)
    side_html = forms.select("side", "Side", [(s, s) for s in sides], v.get("side", ""), blank="Not set", errors=errors) if sides else ""
    meal_html = forms.select("meal_item_id", "Meal choice", [(m["id"], m["name"]) for m in meals], v.get("meal_item_id") or "",
                             blank="No selection", errors=errors) if meals and has(ev, "menu") else ""
    action = f"{base(ev)}/guests/{g['id']}" if g else f"{base(ev)}/guests/new"
    delete = ""
    if g:
        delete = (f'<form method="post" action="{base(ev)}/guests/{g["id"]}/delete" data-confirm="Remove {esc(events.guest_name(g))} from the guest list?">'
                  f'{csrf(req)}<button class="btn btn--danger btn--sm" type="submit">{i("trash")}Remove guest</button></form>')
    link = ""
    if g and has(ev, "personal_invites"):
        link = (f'<div class="notice">{i("link")}<div><b>Personal invitation link</b><br><span class="mono small" style="overflow-wrap:anywhere">{esc(events.invite_url(ev, g))}</span>'
                f'<div class="row" style="margin-top:8px"><button class="chip" type="button" data-copy="{esc(events.invite_url(ev, g))}">{i("copy")}Copy</button>'
                f'<a class="chip" href="{esc(guest_whatsapp(ev, g))}" target="_blank" rel="noopener">{i("chat")}WhatsApp</a></div></div></div>')
    cat_field = forms.select("category", "Category", [(c, c) for c in cats], v.get("category", ""), blank="No category", errors=errors)
    return f"""{forms.errors_summary(errors)}{link}
<form class="form box" method="post" action="{action}" style="margin-top:16px">{csrf(req)}
<fieldset><legend>Who</legend><div class="form-row form-row--2">
{forms.field("first_name", "First name", v.get("first_name", ""), required=True, errors=errors, attrs={"maxlength": 80, "autocomplete": "off"})}
{forms.field("last_name", "Last name", v.get("last_name", ""), errors=errors, attrs={"maxlength": 80, "autocomplete": "off"})}
{forms.field("email", "Email", v.get("email", ""), type="email", errors=errors, attrs={"autocomplete": "off"})}
{forms.field("phone", "Mobile (for WhatsApp)", v.get("phone", ""), type="tel", errors=errors, hint="South African numbers like 082 123 4567 work.")}
</div></fieldset>
<fieldset><legend>Groups</legend><div class="form-row form-row--3">{cat_field}
<div class="field"><label for="f-family-group">Family group</label><input class="input" id="f-family-group" name="family_group" list="groups" value="{esc(v.get("family_group", ""))}" maxlength="80"><datalist id="groups">{datalist}</datalist></div>
{side_html}</div>
<div class="row">{forms.check("is_vip", "VIP guest", bool(v.get("is_vip")))}{forms.check("is_child", "This guest is a child", bool(v.get("is_child")))}</div></fieldset>
<fieldset><legend>Invitation allowances</legend><div class="form-row form-row--2">
{forms.field("plus_ones_allowed", "Plus-ones allowed", v.get("plus_ones_allowed", 0), type="number", errors=errors, attrs={"min": 0, "max": 10})}
{forms.field("children_allowed", "Children allowed", v.get("children_allowed", 0), type="number", errors=errors, attrs={"min": 0, "max": 10})}
</div></fieldset>
<fieldset><legend>Response</legend><div class="form-row form-row--3">
{forms.select("status", "RSVP status", [(k, l) for k, l in STATUS_LABEL.items()], v.get("status", "pending"), errors=errors)}
{forms.field("plus_ones", "Plus-ones coming", v.get("plus_ones", 0), type="number", errors=errors, attrs={"min": 0, "max": 10})}
{forms.field("children", "Children coming", v.get("children", 0), type="number", errors=errors, attrs={"min": 0, "max": 10})}
</div><div class="form-row form-row--2" style="margin-top:16px">
{forms.field("plus_one_names", "Plus-one names", v.get("plus_one_names", ""), errors=errors, attrs={"maxlength": 200})}
{meal_html or "<div></div>"}
{forms.field("dietary", "Dietary requirements", v.get("dietary", ""), errors=errors, attrs={"maxlength": 200})}
{forms.field("allergies", "Allergies", v.get("allergies", ""), errors=errors, attrs={"maxlength": 200})}
</div>{forms.field("special_requests", "Special requests", v.get("special_requests", ""), type="textarea", errors=errors, attrs={"maxlength": 1000, "rows": 3})}</fieldset>
<fieldset><legend>Private</legend>{forms.field("notes", "Organiser notes (never shown to guests)", v.get("notes", ""), type="textarea", errors=errors, attrs={"maxlength": 1000, "rows": 3})}
{forms.check("email_consent", "This guest expects event emails from me", bool(v.get("email_consent")), hint="Untick if the guest hasn't agreed to receive emails. Required by POPIA for direct communication.")}</fieldset>
<div class="row row--between"><a class="btn btn--ghost" href="{base(ev)}/guests">Cancel</a><button class="btn btn--primary" type="submit">{"Save changes" if g else "Add guest"}</button></div>
</form><div style="margin-top:16px">{delete}</div>"""


def _read_guest(req, ev, g=None) -> Form:
    f = Form(req)
    f.text("first_name", "First name", required=True, max=80)
    f.text("last_name", "Last name", max=80)
    email = f.email("email")
    f.phone("phone")
    f.text("category", max=60)
    f.text("family_group", "Family group", max=80)
    f.text("side", max=60)
    f.flag("is_vip")
    f.flag("is_child")
    f.integer("plus_ones_allowed", "Plus-ones allowed", min=0, max=10)
    f.integer("children_allowed", "Children allowed", min=0, max=10)
    f.choice("status", list(STATUS_LABEL), "status", default="pending")
    f.integer("plus_ones", "Plus-ones coming", min=0, max=10)
    f.integer("children", "Children coming", min=0, max=10)
    f.text("plus_one_names", "Plus-one names", max=200)
    f.text("dietary", "Dietary requirements", max=200)
    f.text("allergies", max=200)
    f.text("special_requests", "Special requests", max=1000)
    f.text("notes", max=1000)
    f.flag("email_consent")
    meal = req.get("meal_item_id")
    f.data["meal_item_id"] = None
    if meal:
        if not db.one("SELECT 1 FROM menu_items WHERE id = ? AND event_id = ? AND selectable = 1", (meal, ev["id"])):
            f.error("meal_item_id", "Choose one of the meal options.")
        else:
            f.data["meal_item_id"] = int(meal)
    if f.data["category"] and f.data["category"] not in categories_for(ev):
        f.error("category", "Choose one of the listed categories.")
    if email:
        dup = db.one("SELECT id FROM guests WHERE event_id = ? AND email = ? AND id != ?", (ev["id"], email, g["id"] if g else 0))
        if dup:
            f.error("email", "Another guest on this list already uses that email.")
    if f.data["plus_ones"] > max(f.data["plus_ones_allowed"], 0):
        f.error("plus_ones", "Plus-ones coming can't be more than the plus-ones allowed.")
    if f.data["status"] != "attending":
        f.data["plus_ones"] = 0 if f.data["status"] == "declined" else f.data["plus_ones"]
    return f


def _guest_values(f: Form) -> dict:
    keys = ["first_name", "last_name", "email", "phone", "category", "family_group", "side", "plus_ones_allowed",
            "children_allowed", "status", "plus_ones", "children", "plus_one_names", "dietary", "allergies",
            "special_requests", "notes", "meal_item_id"]
    v = {k: f.data[k] for k in keys}
    v["is_vip"] = 1 if f.data["is_vip"] else 0
    v["is_child"] = 1 if f.data["is_child"] else 0
    v["email_consent"] = 1 if f.data["email_consent"] else 0
    return v


def _need_edit(req, ev, title, suffix):
    if not has(ev, "guest_management"):
        return organiser_page(req, ev, title, page_head(title) + locked_panel(ev, "guest_management", "Guest management"), suffix)
    return None


@router.route("/dashboard/events/<uid>/guests/new", methods=("GET", "POST"))
def guest_new(req, uid):
    ev = load(req, uid)
    blocked = _need_edit(req, ev, "Add guest", "/guests")
    if blocked:
        return blocked
    f = None
    if req.method == "POST":
        f = _read_guest(req, ev)
        if f.ok:
            v = _guest_values(f)
            now = db.now()
            v.update({"event_id": ev["id"], "token": events.new_guest_token(), "source": "organiser",
                      "created_at": now, "updated_at": now})
            if v["status"] != "pending":
                v["responded_at"] = now
            db.insert("guests", v)
            req.flash("success", f"{v['first_name']} added to your guest list.")
            return redirect(f"{base(ev)}/guests/new" if req.get("again") else f"{base(ev)}/guests")
    crumbs = f'<p class="small"><a class="text-link" href="{base(ev)}/guests">Guests</a> / Add guest</p>'
    return organiser_page(req, ev, "Add guest", crumbs + page_head("Add a guest") + _guest_form(req, ev, None, f), "/guests")


@router.route("/dashboard/events/<uid>/guests/<int:gid>", methods=("GET", "POST"))
def guest_edit(req, uid, gid):
    ev = load(req, uid)
    blocked = _need_edit(req, ev, "Edit guest", "/guests")
    if blocked:
        return blocked
    g = _guest(ev, gid)
    f = None
    if req.method == "POST":
        f = _read_guest(req, ev, g)
        if f.ok:
            v = _guest_values(f)
            v["updated_at"] = db.now()
            if v["status"] != g["status"] and v["status"] != "pending":
                v["responded_at"] = db.now()
            if v["status"] == "declined":
                db.run("DELETE FROM seat_assignments WHERE guest_id = ?", (g["id"],))
            db.update("guests", g["id"], v)
            req.flash("success", "Guest saved.")
            return redirect(f"{base(ev)}/guests")
    crumbs = f'<p class="small"><a class="text-link" href="{base(ev)}/guests">Guests</a> / {esc(events.guest_name(g))}</p>'
    return organiser_page(req, ev, "Edit guest", crumbs + page_head(events.guest_name(g)) + _guest_form(req, ev, g, f), "/guests")


@router.post("/dashboard/events/<uid>/guests/<int:gid>/delete")
def guest_delete(req, uid, gid):
    ev = load(req, uid)
    if not has(ev, "guest_management"):
        raise HTTPError(403, "Guest management isn't included in this event's package.")
    g = _guest(ev, gid)
    db.run("DELETE FROM guests WHERE id = ?", (g["id"],))
    return go(req, ev, "/guests", "success", f"{events.guest_name(g)} removed.")


@router.post("/dashboard/events/<uid>/guests/<int:gid>/checkin")
def guest_checkin(req, uid, gid):
    ev = load(req, uid)
    if not has(ev, "guest_management"):
        raise HTTPError(403, "Attendance tracking isn't included in this event's package.")
    g = _guest(ev, gid)
    db.run("UPDATE guests SET checked_in_at = ?, updated_at = ? WHERE id = ?",
           (None if g["checked_in_at"] else db.now(), db.now(), g["id"]))
    return go(req, ev, "/guests", "success",
              f"{events.guest_name(g)} {'is no longer checked in' if g['checked_in_at'] else 'checked in'}.")


@router.post("/dashboard/events/<uid>/guests/bulk")
def guest_bulk(req, uid):
    ev = load(req, uid)
    if not has(ev, "guest_management"):
        raise HTTPError(403, "Guest management isn't included in this event's package.")
    ids = [int(x) for x in req.getlist("ids") if x.isdigit()]
    if not ids:
        return go(req, ev, "/guests", "error", "Select at least one guest first.")
    marks = ",".join("?" for _ in ids)
    action = req.get("action")
    if action == "delete":
        db.run(f"DELETE FROM guests WHERE event_id = ? AND id IN ({marks})", [ev["id"], *ids])
        return go(req, ev, "/guests", "success", f"Removed {len(ids)} guests.")
    if action == "pending":
        db.run(f"UPDATE guests SET status = 'pending', updated_at = ? WHERE event_id = ? AND id IN ({marks})", [db.now(), ev["id"], *ids])
        return go(req, ev, "/guests", "success", f"{len(ids)} guests marked as pending.")
    cat = req.get("category")
    if cat not in categories_for(ev):
        return go(req, ev, "/guests", "error", "Choose one of the listed categories.")
    db.run(f"UPDATE guests SET category = ?, updated_at = ? WHERE event_id = ? AND id IN ({marks})", [cat, db.now(), ev["id"], *ids])
    return go(req, ev, "/guests", "success", f"Category set to {cat} for {len(ids)} guests.")


# --- CSV import ---------------------------------------------------------------------------------
IMPORT_COLUMNS = ["first_name", "last_name", "email", "phone", "category", "family_group", "side",
                  "plus_ones_allowed", "children_allowed", "vip", "child"]
ALIASES = {
    "first_name": {"first_name", "first", "firstname", "first name", "given name", "name"},
    "last_name": {"last_name", "last", "lastname", "last name", "surname", "family name"},
    "email": {"email", "e-mail", "email address"},
    "phone": {"phone", "mobile", "cell", "cellphone", "phone number", "whatsapp"},
    "category": {"category", "type", "guest type"},
    "family_group": {"family_group", "family group", "family", "group", "household"},
    "side": {"side"},
    "plus_ones_allowed": {"plus_ones_allowed", "plus ones", "plus-ones", "plus ones allowed", "plus_ones", "+1"},
    "children_allowed": {"children_allowed", "children", "children allowed", "kids"},
    "vip": {"vip"},
    "child": {"child", "is child", "is_child"},
}
MAX_IMPORT = 2000


def parse_import(ev, text: str):
    """Returns (rows, problems). rows are ready-to-insert dicts; problems are (line, message)."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = next(reader)
    except StopIteration:
        return [], [(1, "The file is empty.")]
    mapping = {}
    for idx, h in enumerate(header):
        key = h.strip().lower().replace("-", " ").replace("_", " ")
        for col, names in ALIASES.items():
            if key in {n.replace("_", " ").replace("-", " ") for n in names} and col not in mapping.values():
                mapping[idx] = col
                break
    if "first_name" not in mapping.values():
        return [], [(1, "Add a first_name column (see the template).")]
    existing = {r[0].lower() for r in db.q("SELECT email FROM guests WHERE event_id = ? AND email != ''", (ev["id"],))}
    seen: set = set()
    rows, problems = [], []
    cats = categories_for(ev)
    sides = (ev.get("guest_settings") or {}).get("sides") or []
    for line_no, raw in enumerate(reader, start=2):
        if not any(c.strip() for c in raw):
            continue
        if len(rows) >= MAX_IMPORT:
            problems.append((line_no, f"Only {MAX_IMPORT} guests can be imported at once; the rest were skipped."))
            break
        rec = {col: (raw[idx].strip() if idx < len(raw) else "") for idx, col in mapping.items()}
        if not rec.get("first_name"):
            problems.append((line_no, "Missing first name."))
            continue
        if "last_name" not in mapping.values() and " " in rec["first_name"]:
            rec["first_name"], rec["last_name"] = rec["first_name"].split(" ", 1)
        email = rec.get("email", "").lower()
        if email and not forms.EMAIL_RE.match(email):
            problems.append((line_no, f"“{email}” isn't a valid email address."))
            continue
        if email and (email in existing or email in seen):
            problems.append((line_no, f"{email} is already on the guest list."))
            continue
        nums = {}
        bad = False
        for k in ("plus_ones_allowed", "children_allowed"):
            val = rec.get(k, "") or "0"
            if not val.isdigit() or int(val) > 10:
                problems.append((line_no, f"{k.replace('_', ' ').capitalize()} must be a number from 0 to 10."))
                bad = True
                break
            nums[k] = int(val)
        if bad:
            continue
        cat = rec.get("category", "")
        match = next((c for c in cats if c.lower() == cat.lower()), None)
        if cat and not match:
            problems.append((line_no, f"Category “{cat}” isn't one of: {', '.join(cats)}. Imported without a category."))
        side = rec.get("side", "")
        side = next((s for s in sides if s.lower() == side.lower()), "") if side else ""
        seen.add(email)
        rows.append({
            "first_name": rec["first_name"][:80], "last_name": rec.get("last_name", "")[:80], "email": email,
            "phone": rec.get("phone", "")[:30], "category": match or "", "family_group": rec.get("family_group", "")[:80],
            "side": side, "plus_ones_allowed": nums["plus_ones_allowed"], "children_allowed": nums["children_allowed"],
            "is_vip": 1 if rec.get("vip", "").lower() in ("1", "yes", "y", "true", "x") else 0,
            "is_child": 1 if rec.get("child", "").lower() in ("1", "yes", "y", "true", "x") else 0,
        })
    return rows, problems


@router.get("/dashboard/events/<uid>/guests/template.csv")
def guest_template(req, uid):
    ev = load(req, uid)
    sample = ("﻿first_name,last_name,email,phone,category,family_group,side,plus_ones_allowed,children_allowed,vip,child\r\n"
              "Lerato,Dlamini,lerato@example.com,082 555 0101,Family,Dlamini family,,1,0,yes,\r\n"
              "Pieter,van Wyk,,071 555 0102,Friends,,,0,2,,\r\n")
    return download(sample, f"{ev['slug']}-guest-template.csv", "text/csv; charset=utf-8")


@router.route("/dashboard/events/<uid>/guests/import", methods=("GET", "POST"))
def guest_import(req, uid):
    ev = load(req, uid)
    blocked = _need_edit(req, ev, "Import guests", "/guests")
    if blocked:
        return blocked
    crumbs = f'<p class="small"><a class="text-link" href="{base(ev)}/guests">Guests</a> / Import</p>'
    if req.method == "POST":
        text = req.get("csv_text")
        up = req.file("csv")
        if up is not None and up.data:
            if up.size > 2 * 1024 * 1024:
                req.flash("error", "CSV files must be 2 MB or smaller.")
                return redirect(f"{base(ev)}/guests/import")
            raw = up.data
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1252", "replace")
        if not text.strip():
            req.flash("error", "Choose a CSV file or paste your guest list.")
            return redirect(f"{base(ev)}/guests/import")
        rows, problems = parse_import(ev, text)
        if req.get("confirm") == "1":
            now = db.now()
            with db.transaction():
                for r in rows:
                    db.insert("guests", {**r, "event_id": ev["id"], "token": events.new_guest_token(), "source": "import",
                                         "email_consent": 1, "created_at": now, "updated_at": now})
            msg = f"Imported {len(rows)} guests."
            if problems:
                msg += f" {len(problems)} rows were skipped or adjusted."
            req.flash("success", msg)
            return redirect(f"{base(ev)}/guests")
        preview_rows = "".join(
            f'<tr><td>{esc(r["first_name"])} {esc(r["last_name"])}</td><td>{esc(r["email"])}</td><td>{esc(r["phone"])}</td>'
            f'<td>{esc(r["category"])}</td><td>{esc(r["family_group"])}</td><td class="num">{r["plus_ones_allowed"]}</td>'
            f'<td class="num">{r["children_allowed"]}</td></tr>' for r in rows[:200])
        more = f'<p class="small muted" style="margin-top:8px">Showing the first 200 of {len(rows)}.</p>' if len(rows) > 200 else ""
        prob = ""
        if problems:
            items = "".join(f"<li>Line {n}: {esc(m)}</li>" for n, m in problems[:100])
            prob = f'<div class="notice notice--warn" style="margin-bottom:16px">{i("alert")}<div><b>{len(problems)} rows need attention</b><ul style="margin:6px 0 0;padding-left:18px">{items}</ul></div></div>'
        confirm = ""
        if rows:
            confirm = (f'<form method="post" action="{base(ev)}/guests/import" class="row row--between" style="margin-top:16px">{csrf(req)}'
                       f'<input type="hidden" name="confirm" value="1"><textarea name="csv_text" hidden>{esc(text)}</textarea>'
                       f'<a class="btn btn--ghost" href="{base(ev)}/guests/import">Start again</a>'
                       f'<button class="btn btn--primary" type="submit">Import {len(rows)} guests</button></form>')
        else:
            confirm = f'<p style="margin-top:16px"><a class="btn btn--secondary" href="{base(ev)}/guests/import">Try another file</a></p>'
        table = (f'<div class="table-wrap"><table class="table"><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Category</th>'
                 f'<th>Family group</th><th class="num">+1</th><th class="num">Kids</th></tr></thead><tbody>{preview_rows}</tbody></table></div>') if rows else \
            '<div class="empty"><p>No guests could be read from this file.</p></div>'
        body = crumbs + page_head("Check your import", f"{len(rows)} guests ready to import. Nothing is saved until you confirm.") + prob + table + more + confirm
        return organiser_page(req, ev, "Import guests", body, "/guests")
    body = crumbs + page_head("Import guests from a spreadsheet",
                              "Save your spreadsheet as CSV. We'll show you a preview before anything is added.") + f"""
<div class="cols cols--2"><form class="box form" method="post" action="{base(ev)}/guests/import" enctype="multipart/form-data">{csrf(req)}
<label class="file-drop">{i("upload")}<b>Choose a CSV file</b><span class="small muted">or drag it here · 2 MB max</span><span class="small" data-files></span>
<input type="file" name="csv" accept=".csv,text/csv"></label>
{forms.field("csv_text", "Or paste rows (with the header line)", "", type="textarea", attrs={"rows": 6, "placeholder": "first_name,last_name,email,phone"})}
<div class="row row--end"><button class="btn btn--primary" type="submit">Preview import</button></div></form>
<div class="box stack" style="--stack:12px"><h2 style="font-size:1.0625rem">Columns we understand</h2>
<p class="small muted">first_name (required), last_name, email, phone, category, family_group, side, plus_ones_allowed, children_allowed, vip, child. Guests whose email is already on your list are skipped.</p>
<a class="btn btn--secondary btn--sm" href="{base(ev)}/guests/template.csv">{i("download")}Download the template</a>
<p class="small muted">Categories available: {esc(", ".join(categories_for(ev)))}.</p></div></div>"""
    return organiser_page(req, ev, "Import guests", body, "/guests")


# =============================================================================================
# RSVPs
# =============================================================================================
@router.get("/dashboard/events/<uid>/rsvps")
def rsvps(req, uid):
    ev = load(req, uid)
    if not has(ev, "basic_dashboard"):
        return organiser_page(req, ev, "RSVPs", page_head("RSVPs") + locked_panel(ev, "basic_dashboard", "RSVP tracking"), "/rsvps")
    s = events.stats(ev["id"])
    st = req.arg("status")
    sql = """SELECT g.*, m.name AS meal_name FROM guests g LEFT JOIN menu_items m ON m.id = g.meal_item_id
             WHERE g.event_id = ?"""
    params = [ev["id"]]
    if st in STATUS_LABEL:
        sql += " AND g.status = ?"
        params.append(st)
    rows = db.q(sql + " ORDER BY COALESCE(g.responded_at, '') DESC, g.last_name COLLATE NOCASE", params)
    deadline = (ev.get("guest_settings") or {}).get("rsvp_deadline")
    kpis = f"""<div class="kpis" style="--n:5;margin-bottom:20px">
<div class="kpi"><span>Invited</span><b>{s["invited"]}</b></div>
<div class="kpi"><span>Attending</span><b>{s["attending"]}</b><small>{s["headcount"]} people with guests</small></div>
<div class="kpi"><span>Declined</span><b>{s["declined"]}</b></div>
<div class="kpi"><span>Still to reply</span><b>{s["pending"]}</b><small>{("Deadline " + forms.fmt_date(deadline, False)) if deadline else "No deadline set"}</small></div>
<div class="kpi kpi--accent"><span>Replied</span><b>{s["completion"]}%</b><div class="progress" style="margin-top:10px"><span style="width:{s["completion"]}%"></span></div></div></div>"""
    filt = [("", "All", s["invited"]), ("attending", "Attending", s["attending"]), ("declined", "Declined", s["declined"]),
            ("pending", "Pending", s["pending"])]
    chips = "".join(f'<a class="chip{" is-active" if st == k else ""}" href="{base(ev)}/rsvps{("?status=" + k) if k else ""}"'
                    f'{" aria-current=page" if st == k else ""}>{l} <span class="count">{n}</span></a>' for k, l, n in filt)
    actions = ""
    if has(ev, "reminders") and s["pending"]:
        actions += f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/communications?template=guest_reminder&amp;audience=pending">{i("bell")}Remind pending guests</a>'
    if has(ev, "personal_invites") and s["pending"]:
        actions += f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/share/whatsapp?mode=remind">{i("chat")}Remind on WhatsApp</a>'
    if has(ev, "reports"):
        actions += f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/reports/rsvp.csv">{i("download")}Export CSV</a>'
    trs = []
    for g in rows:
        details = "; ".join(x for x in (g["meal_name"], g["dietary"], g["allergies"]) if x)
        form = (f'<form method="post" action="{base(ev)}/rsvps/{g["id"]}/status" class="row" style="gap:6px;flex-wrap:nowrap">{csrf(req)}'
                f'<select class="select select--sm" name="status" aria-label="Status for {esc(events.guest_name(g))}" data-autosubmit>'
                + "".join(f'<option value="{k}"{" selected" if g["status"] == k else ""}>{l}</option>' for k, l in STATUS_LABEL.items())
                + '</select><noscript><button class="btn btn--ghost btn--sm">Save</button></noscript></form>')
        party = f'{1 + g["plus_ones"]}{(" + " + str(g["children"]) + " kids") if g["children"] else ""}' if g["status"] == "attending" else "—"
        trs.append(f'<tr><td><b>{esc(events.guest_name(g))}</b><span class="table__sub">{esc(forms.fmt_dt(g["responded_at"]) or "No reply yet")}'
                   f'{" · via general link" if g["source"] == "general_link" else ""}</span></td><td>{form}</td>'
                   f'<td class="mono">{party}</td><td class="small">{esc(details) or "<span class=muted>—</span>"}'
                   f'{("<br><span class=muted>“" + esc(g["special_requests"]) + "”</span>") if g["special_requests"] else ""}</td></tr>')
    table = (f'<div class="table-wrap"><table class="table"><thead><tr><th>Guest</th><th>Status</th><th>Party</th><th>Meal, dietary and notes</th></tr></thead>'
             f'<tbody>{"".join(trs)}</tbody></table></div>') if rows else \
        f'<div class="empty"><span class="icon-tile icon-tile--soft">{i("check")}</span><p>No responses in this view yet. Share your link to start collecting RSVPs.</p><a class="btn btn--secondary" href="{base(ev)}/share">Share options</a></div>'
    history = db.q("""SELECT r.*, g.first_name, g.last_name FROM rsvp_responses r LEFT JOIN guests g ON g.id = r.guest_id
                      WHERE r.event_id = ? ORDER BY r.created_at DESC LIMIT 30""", (ev["id"],))
    hist = "".join(
        f'<li><span><b>{esc((h["first_name"] or "Removed guest") + " " + (h["last_name"] or ""))}</b> '
        f'{esc(STATUS_LABEL.get(db.loads(h["payload"]).get("status", ""), "responded").lower())}'
        f'<span class="muted small"> · {"personal link" if h["via"] == "personal" else "general link"}</span></span>'
        f'<time class="small muted">{esc(forms.fmt_dt(h["created_at"]))}</time></li>' for h in history)
    hist_box = (f'<div class="box" style="margin-top:20px"><div class="box__head"><h2>Response history</h2></div>'
                f'<ul class="list-plain list-rows">{hist}</ul></div>') if history else ""
    rsvp_state = "open" if ev["rsvp_open"] else "closed"
    head = page_head("RSVPs", f"RSVPs are {rsvp_state}. Change a response here if a guest tells you directly.", actions)
    return organiser_page(req, ev, "RSVPs", head + kpis + f'<div class="chips-scroll" style="margin-bottom:14px">{chips}</div>' + table + hist_box, "/rsvps")


@router.post("/dashboard/events/<uid>/rsvps/<int:gid>/status")
def rsvp_status(req, uid, gid):
    ev = load(req, uid)
    g = _guest(ev, gid)
    status = req.get("status")
    if status not in STATUS_LABEL:
        return go(req, ev, "/rsvps", "error", "Choose attending, declined or pending.")
    fields = {"status": status, "updated_at": db.now(), "responded_at": db.now() if status != "pending" else None}
    if status == "declined":
        fields.update({"plus_ones": 0, "children": 0})
        db.run("DELETE FROM seat_assignments WHERE guest_id = ?", (g["id"],))
    db.update("guests", g["id"], fields)
    db.insert("rsvp_responses", {"event_id": ev["id"], "guest_id": g["id"], "via": "personal",
                                 "payload": db.dumps({"status": status, "by": "organiser"}), "created_at": db.now()})
    return go(req, ev, "/rsvps", "success", f"{events.guest_name(g)} marked as {STATUS_LABEL[status].lower()}.")


# =============================================================================================
# Seating
# =============================================================================================
def seating_state(ev) -> dict:
    tables = events.tables(ev["id"])
    guests = db.q("""SELECT g.*, a.table_id FROM guests g LEFT JOIN seat_assignments a ON a.guest_id = g.id
                     WHERE g.event_id = ? AND g.status != 'declined'
                     ORDER BY g.family_group COLLATE NOCASE, g.last_name COLLATE NOCASE, g.first_name COLLATE NOCASE""", (ev["id"],))
    return {
        "tables": [{"id": t["id"], "name": t["name"], "capacity": t["capacity"], "shape": t["shape"], "x": t["pos_x"],
                    "y": t["pos_y"], "notes": t["notes"], "seated": t["seated"]} for t in tables],
        "guests": [{"id": g["id"], "name": events.guest_name(g), "status": g["status"], "party": events.party_size(g),
                    "table": g["table_id"], "group": g["family_group"] or g["category"], "vip": bool(g["is_vip"])} for g in guests],
        "advanced": has(ev, "advanced_seating"),
    }


def _check_seating_complete(ev) -> bool:
    s = events.stats(ev["id"])
    if s["attending"] == 0 or s["unseated_parties"] > 0:
        return False
    if db.one("SELECT 1 FROM sent_markers WHERE event_id = ? AND marker = 'seating_complete'", (ev["id"],)):
        return False
    db.run("INSERT OR IGNORE INTO sent_markers (event_id, marker, created_at) VALUES (?, 'seating_complete', ?)", (ev["id"], db.now()))
    tables = [t for t in events.tables(ev["id"]) if t["seated"]]
    notify.organiser(ev, "seating_complete", {"tables": len(tables), "seated": sum(t["seated"] for t in tables)})
    return True


@router.get("/dashboard/events/<uid>/seating")
def seating(req, uid):
    ev = load(req, uid)
    if not has(ev, "seating"):
        return organiser_page(req, ev, "Seating", page_head("Seating chart") + locked_panel(ev, "seating", "The seating chart"), "/seating")
    state = seating_state(ev)
    data = json.dumps(state).replace("</", "<\\/")
    s = events.stats(ev["id"])
    exports = ""
    if has(ev, "reports"):
        exports = (f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/reports/seating.pdf">{i("download")}PDF</a>'
                   f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/reports/seating.csv">{i("download")}CSV</a>')
    actions = exports + f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/seating/print" target="_blank" rel="noopener">{i("print")}Print</a>'
    head = page_head("Seating chart", f"<span data-seat-summary>{s['seated_parties']} of {s['attending']} attending parties seated.</span> Drag guests onto tables; drag tables to arrange the room.", actions)
    shape_opts = '<option value="round">Round</option>' + ('<option value="long">Long</option>' if state["advanced"] else "")
    body = head + f"""
<div class="seating" data-seating data-api="{base(ev)}/seating/api">
<aside class="seat-pool box" aria-label="Guests and tables">
<form class="stack" style="--stack:10px" data-new-table><h2 style="font-size:1rem">Add a table</h2>
<div class="form-row form-row--2"><input class="input input--sm" name="name" placeholder="Table name" maxlength="40" aria-label="Table name">
<input class="input input--sm" name="capacity" type="number" min="1" max="40" value="10" aria-label="Capacity"></div>
<div class="row"><select class="select select--sm" name="shape" aria-label="Shape" style="width:auto">{shape_opts}</select>
<button class="btn btn--primary btn--sm" type="submit">{i("plus")}Add</button></div></form>
<details style="margin-top:10px"><summary class="small" style="cursor:pointer;min-height:36px;display:flex;align-items:center">Create several tables at once</summary>
<form class="row" data-auto-tables style="margin-top:8px"><input class="input input--sm" name="count" type="number" min="1" max="60" value="10" style="width:80px" aria-label="Number of tables">
<span class="small">tables of</span><input class="input input--sm" name="capacity" type="number" min="1" max="40" value="10" style="width:80px" aria-label="Seats per table">
<button class="btn btn--secondary btn--sm" type="submit">Create</button></form></details>
<div data-table-editor hidden style="margin-top:14px;padding-top:14px;border-top:1px solid var(--color-line)"></div>
<hr><button class="btn btn--primary btn--sm btn--block" type="button" data-autoseat>{i("wand")}Seat everyone automatically</button>
<p class="tiny muted" style="margin:6px 0 0">Keeps families and groups together. Guests you've already placed stay where they are.</p>
<hr><div class="row row--between"><h2 style="font-size:1rem">Not seated</h2><label class="switch small"><input type="checkbox" data-include-pending><span>Include pending</span></label></div>
<p class="small muted" style="margin:4px 0 10px">Drag a guest onto a table, or tap a guest then tap a table.</p>
<div data-pool aria-live="polite"></div></aside>
<div><div class="floor" data-floor><span class="floor__label">Floor plan</span></div>
<p class="small muted" style="margin-top:10px">Party sizes include plus-ones and children. Tables turn amber when full and red when over capacity.</p></div>
</div><script type="application/json" id="seating-data">{data}</script>"""
    return organiser_page(req, ev, "Seating", body, "/seating", extra_scripts='<script src="/static/js/seating.js" defer></script>')


@router.get("/dashboard/events/<uid>/seating/api/state")
def seating_api_state(req, uid):
    ev = load(req, uid)
    if not has(ev, "seating"):
        raise HTTPError(403, "Seating isn't included in this event's package.")
    return json_response({"ok": True, "state": seating_state(ev)})


@router.post("/dashboard/events/<uid>/seating/api/<action>")
def seating_api(req, uid, action):
    ev = load(req, uid)
    if not has(ev, "seating"):
        raise HTTPError(403, "Seating isn't included in this event's package.")
    body = req.json or {}
    warning = ""
    advanced = has(ev, "advanced_seating")

    def table_row(tid):
        t = db.one("SELECT * FROM seating_tables WHERE id = ? AND event_id = ?", (tid, ev["id"]))
        if t is None:
            raise HTTPError(404, "Table not found.")
        return t

    def clean_int(v, lo, hi, label):
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise HTTPError(400, f"{label} must be a number.")
        if n < lo or n > hi:
            raise HTTPError(400, f"{label} must be between {lo} and {hi}.")
        return n

    count = db.val("SELECT COUNT(*) FROM seating_tables WHERE event_id = ?", (ev["id"],), 0)
    if action == "create":
        if count >= 120:
            raise HTTPError(400, "An event can have up to 120 tables.")
        name = str(body.get("name") or "").strip()[:40] or f"Table {count + 1}"
        cap = clean_int(body.get("capacity", 10), 1, 40, "Capacity")
        shape = body.get("shape") if body.get("shape") in ("round", "long") else "round"
        if shape == "long" and not advanced:
            shape = "round"
        (x, y), = events.floor_slots(ev["id"], 1)
        db.insert("seating_tables", {"event_id": ev["id"], "name": name, "capacity": cap, "shape": shape,
                                     "pos_x": x, "pos_y": y, "sort": count})
    elif action == "autocreate":
        n = clean_int(body.get("count", 10), 1, 60, "Number of tables")
        cap = clean_int(body.get("capacity", 10), 1, 40, "Seats per table")
        if count + n > 120:
            raise HTTPError(400, "An event can have up to 120 tables.")
        with db.transaction():
            for k, (x, y) in enumerate(events.floor_slots(ev["id"], n)):
                db.insert("seating_tables", {"event_id": ev["id"], "name": f"Table {count + k + 1}", "capacity": cap,
                                             "shape": "round", "pos_x": x, "pos_y": y, "sort": count + k})
    elif action == "update":
        t = table_row(body.get("id"))
        fields = {}
        if "name" in body:
            fields["name"] = str(body["name"]).strip()[:40] or t["name"]
        if "capacity" in body:
            fields["capacity"] = clean_int(body["capacity"], 1, 40, "Capacity")
        if "shape" in body and body["shape"] in ("round", "long"):
            fields["shape"] = body["shape"] if (advanced or body["shape"] == "round") else "round"
        if "notes" in body:
            fields["notes"] = str(body["notes"]).strip()[:200]
        for k, col, top in (("x", "pos_x", 100.0), ("y", "pos_y", 20000.0)):    # x: percent of the width; y: px from the top
            if k in body:
                try:
                    fields[col] = max(0.0, min(top, float(body[k])))
                except (TypeError, ValueError):
                    raise HTTPError(400, "Position must be a number.")
        db.update("seating_tables", t["id"], fields)
    elif action == "delete":
        t = table_row(body.get("id"))
        db.run("DELETE FROM seating_tables WHERE id = ?", (t["id"],))
    elif action == "assign":
        g = db.one("SELECT * FROM guests WHERE id = ? AND event_id = ?", (body.get("guest_id"), ev["id"]))
        if g is None:
            raise HTTPError(404, "Guest not found.")
        if g["status"] == "declined":
            raise HTTPError(400, "Declined guests can't be seated.")
        tid = body.get("table_id")
        if tid in (None, "", 0):
            db.run("DELETE FROM seat_assignments WHERE guest_id = ?", (g["id"],))
        else:
            t = table_row(tid)
            current = db.val("""SELECT COALESCE(SUM(1 + g.plus_ones + g.children), 0) FROM seat_assignments a
                                JOIN guests g ON g.id = a.guest_id WHERE a.table_id = ? AND g.id != ? AND g.status != 'declined'""",
                             (t["id"], g["id"]), 0)
            if current + events.party_size(g) > t["capacity"]:
                warning = f"{t['name']} is now over capacity ({current + events.party_size(g)} of {t['capacity']})."
            db.run("""INSERT INTO seat_assignments (guest_id, table_id, event_id, assigned_at) VALUES (?, ?, ?, ?)
                      ON CONFLICT(guest_id) DO UPDATE SET table_id = excluded.table_id, assigned_at = excluded.assigned_at""",
                   (g["id"], t["id"], ev["id"], db.now()))
            _check_seating_complete(ev)
    elif action == "autoseat":
        message, warning = _auto_seat(ev, bool(body.get("include_pending")), count)
        _check_seating_complete(ev)
        return json_response({"ok": True, "warning": warning, "message": message, "state": seating_state(ev)})
    else:
        raise HTTPError(404)
    return json_response({"ok": True, "warning": warning, "state": seating_state(ev)})


def _auto_seat(ev, include_pending: bool, table_count: int) -> tuple:
    """Seat every unseated party, keeping each family or group together where it fits. Groups go
    largest first, VIPs first within a group, each to the table that leaves the least space over."""
    statuses = ("attending", "pending") if include_pending else ("attending",)
    marks = ",".join("?" * len(statuses))
    guests = db.q(f"""SELECT g.* FROM guests g LEFT JOIN seat_assignments a ON a.guest_id = g.id
                      WHERE g.event_id = ? AND a.guest_id IS NULL AND g.status IN ({marks})""", (ev["id"], *statuses))
    if not guests:
        return "Everyone who's coming already has a seat.", ""
    people = sum(events.party_size(g) for g in guests)
    created = 0
    if table_count == 0:
        layout = events.seating_layout(ev)
        need = min(60, max(-(-people // int(layout.get("capacity") or 10)), int(layout.get("count") or 0)))
        with db.transaction():
            created = events.create_layout_tables(ev, layout, need)
    tables = events.tables(ev["id"])
    free = {t["id"]: t["capacity"] - t["seated"] for t in tables if t["notes"] != events.TOP_TABLE_NOTE}   # the top table is set by hand
    empty = [t["id"] for t in tables if t["id"] in free and t["seated"] == 0]                                # in floor-plan order
    groups: dict[str, list] = {}
    for g in guests:
        groups.setdefault((g["family_group"] or g["side"] or g["category"] or "").strip().lower() or f"~{g['id']}", []).append(g)
    ordered = sorted(groups.values(), key=lambda grp: -sum(events.party_size(g) for g in grp))
    seated, left_out, now = 0, [], db.now()
    with db.transaction():
        for grp in ordered:
            grp.sort(key=lambda g: (not g["is_vip"], g["last_name"].lower(), g["first_name"].lower()))
            size = sum(events.party_size(g) for g in grp)
            fits = [tid for tid, room in free.items() if room >= size]
            if fits:                                # the whole group at one table: its own table while there are spare ones
                spare = [t for t in empty if t in fits]
                tid = spare[0] if spare else min(fits, key=lambda t: free[t] - size)
                if tid in empty:
                    empty.remove(tid)
                free[tid] -= size
                plan = [(g, tid) for g in grp]
            else:                                   # too big for any table: party by party, roomiest table first
                plan = []
                for g in grp:
                    room = [t for t, r in free.items() if r >= events.party_size(g)]
                    if not room:
                        left_out.append(g)
                        continue
                    tid = max(room, key=lambda t: free[t])
                    free[tid] -= events.party_size(g)
                    if tid in empty:
                        empty.remove(tid)
                    plan.append((g, tid))
            for g, tid in plan:
                db.run("INSERT INTO seat_assignments (guest_id, table_id, event_id, assigned_at) VALUES (?, ?, ?, ?)",
                       (g["id"], tid, ev["id"], now))
                seated += 1
    message = f"Seated {seated} part{'y' if seated == 1 else 'ies'}" + (f" and created {created} tables from your layout" if created else "") + ". Drag anyone to fine-tune."
    warning = ""
    if left_out:
        n = sum(events.party_size(g) for g in left_out)
        warning = f"{len(left_out)} part{'y' if len(left_out) == 1 else 'ies'} ({n} people) didn't fit. Add a table or raise a table's capacity, then seat again."
    return message, warning


@router.get("/dashboard/events/<uid>/seating/print")
def seating_print(req, uid):
    ev = load(req, uid)
    if not has(ev, "seating"):
        raise HTTPError(403, "Seating isn't included in this event's package.")
    tables = events.tables(ev["id"])
    people = {}
    for r in db.q("""SELECT a.table_id, g.* FROM seat_assignments a JOIN guests g ON g.id = a.guest_id
                     WHERE a.event_id = ? AND g.status != 'declined' ORDER BY g.last_name COLLATE NOCASE""", (ev["id"],)):
        people.setdefault(r["table_id"], []).append(r)
    cards = "".join(
        f'<section class="box" style="break-inside:avoid"><h2 style="font-size:1.1rem">{esc(t["name"])}</h2>'
        f'<p class="small muted">{t["seated"]} of {t["capacity"]} seats</p><ul class="list-plain" style="margin-top:8px">'
        + "".join(f'<li style="padding:3px 0">{esc(events.guest_name(g))}'
                  f'{(" + " + esc(g["plus_one_names"] or str(g["plus_ones"]))) if g["plus_ones"] else ""}'
                  f'{(" + " + str(g["children"]) + " children") if g["children"] else ""}</li>' for g in people.get(t["id"], []))
        + "</ul></section>" for t in tables)
    from .layout import head
    return (head(f"Seating chart · {ev['name']}", noindex=True) +
            f'<body style="padding:32px"><div class="row row--between no-print" style="margin-bottom:20px">'
            f'<a class="btn btn--ghost btn--sm" href="{base(ev)}/seating">{i("arrow-left")}Back</a>'
            f'<button class="btn btn--primary btn--sm" onclick="window.print()">{i("print")}Print</button></div>'
            f'<h1 style="font-size:2rem">{esc(ev["name"])}</h1><p class="muted">Seating chart · {esc(forms.fmt_date(ev.get("event_date")))}</p>'
            f'<div class="seat-list-view" style="margin-top:24px">{cards or "<p>No tables yet.</p>"}</div></body></html>')


# =============================================================================================
# Menu
# =============================================================================================
def _tag_checks(selected) -> str:
    return '<div class="row" style="gap:4px 14px">' + "".join(
        forms.check("tags", t, t in (selected or []), value=t) for t in ["Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "Dairy-free", "Contains nuts", "Spicy"]) + "</div>"


@router.get("/dashboard/events/<uid>/menu")
def menu(req, uid):
    ev = load(req, uid)
    if not has(ev, "menu"):
        return organiser_page(req, ev, "Menu", page_head("Menu") + locked_panel(ev, "menu", "The digital menu"), "/menu")
    menus = events.menus(ev["id"])
    course_opts = "".join(f'<option>{c}</option>' for c in COURSES)
    blocks = []
    for m in menus:
        items = "".join(
            f'<li><span><span class="tag">{esc(it["course"])}</span> <b>{esc(it["name"])}</b>'
            f'{MEAL_PILL if it["selectable"] else ""}'
            f'{(BR_MUTED + esc(it["description"]) + "</span>") if it["description"] else ""}'
            f'{(BR_SMALL + esc(", ".join(it["tags"])) + "</span>") if it["tags"] else ""}</span>'
            f'<span class="row" style="flex-wrap:nowrap"><a class="btn btn--ghost btn--sm" href="{base(ev)}/menu/items/{it["id"]}" aria-label="Edit {esc(it["name"])}">{i("edit")}</a>'
            f'<form method="post" action="{base(ev)}/menu/items/{it["id"]}/delete" data-confirm="Remove {esc(it["name"])}?">{csrf(req)}'
            f'<button class="btn btn--ghost btn--sm" type="submit" aria-label="Remove {esc(it["name"])}">{i("trash")}</button></form></span></li>'
            for it in m["items"])
        blocks.append(f"""<div class="box"><div class="box__head"><div><h2>{esc(m["name"])}</h2>{f'<p class="small muted">{esc(m["description"])}</p>' if m["description"] else ""}</div>
<form method="post" action="{base(ev)}/menu/{m["id"]}/delete" data-confirm="Delete the {esc(m["name"])} menu and its dishes?">{csrf(req)}<button class="btn btn--danger btn--sm" type="submit">Delete menu</button></form></div>
{f'<ul class="list-plain list-rows">{items}</ul>' if items else '<p class="small muted">No dishes yet.</p>'}
<details style="margin-top:12px"><summary class="btn btn--secondary btn--sm" style="list-style:none;display:inline-flex">{i("plus")}Add a dish</summary>
<form class="form" method="post" action="{base(ev)}/menu/{m["id"]}/items" style="margin-top:12px">{csrf(req)}
<div class="form-row form-row--3"><div class="field"><label>Course</label><select class="select" name="course">{course_opts}</select></div>
{forms.field("name", "Dish", "", required=True, attrs={"maxlength": 120})}{forms.field("description", "Description", "", attrs={"maxlength": 300})}</div>
{_tag_checks([])}{forms.check("selectable", "Guests choose this as their meal", False, hint="Meal options appear in the RSVP form.")}
<div class="row row--end"><button class="btn btn--primary btn--sm" type="submit">Add dish</button></div></form></details></div>""")
    # selections + dietary
    counts = db.q("""SELECT m.name, COUNT(g.id) AS n FROM menu_items m LEFT JOIN guests g ON g.meal_item_id = m.id AND g.status = 'attending'
                     WHERE m.event_id = ? AND m.selectable = 1 GROUP BY m.id ORDER BY m.sort, m.id""", (ev["id"],))
    no_choice = db.val("SELECT COUNT(*) FROM guests WHERE event_id = ? AND status = 'attending' AND meal_item_id IS NULL", (ev["id"],), 0)
    total = sum(r["n"] for r in counts) + no_choice
    bars = "".join(f'<div class="bar-list__row"><span>{esc(r["name"])}</span><b class="mono">{r["n"]}</b>'
                   f'<div class="progress"><span style="width:{round(100 * r["n"] / total) if total else 0}%"></span></div></div>' for r in counts)
    if counts:
        bars += f'<div class="bar-list__row"><span class="muted">No selection yet</span><b class="mono">{no_choice}</b></div>'
    dietary = db.q("""SELECT * FROM guests WHERE event_id = ? AND status = 'attending' AND (dietary != '' OR allergies != '')
                      ORDER BY last_name COLLATE NOCASE""", (ev["id"],)) if has(ev, "dietary") else []
    diet_rows = "".join(f'<li><span><b>{esc(events.guest_name(g))}</b><br><span class="small muted">{esc("; ".join(x for x in (g["dietary"], g["allergies"]) if x))}</span></span></li>' for g in dietary)
    exports = ""
    if has(ev, "reports"):
        exports = (f'<div class="row" style="margin-top:14px"><a class="chip" href="{base(ev)}/reports/meals.pdf">{i("download")}Meal report</a>'
                   f'<a class="chip" href="{base(ev)}/reports/dietary.pdf">{i("download")}Dietary report</a>'
                   f'<a class="chip" href="{base(ev)}/reports/meals.csv">{i("download")}CSV for caterer</a></div>')
    drinks = (ev.get("info") or {}).get("drinks", "")
    side = f"""<div class="stack"><div class="box"><div class="box__head"><h2>Meal selections</h2></div>
{f'<div class="bar-list">{bars}</div>' if counts else '<p class="small muted">Mark dishes as meal options and guests will choose one when they RSVP.</p>'}{exports}</div>
<div class="box"><div class="box__head"><h2>Dietary requirements</h2><span class="pill pill--plain">{len(dietary)}</span></div>
{f'<ul class="list-plain list-rows">{diet_rows}</ul>' if diet_rows else '<p class="small muted">No dietary requirements from attending guests yet.</p>'}</div>
<form class="box form" method="post" action="{base(ev)}/menu/drinks">{csrf(req)}{forms.field("drinks", "Drinks information", drinks, type="textarea", attrs={"rows": 3, "maxlength": 600}, hint="Shown under the menu on your website, e.g. cash bar after 22:00.")}
<div class="row row--end"><button class="btn btn--secondary btn--sm" type="submit">Save</button></div></form></div>"""
    add_menu = f"""<form class="box form" method="post" action="{base(ev)}/menu/new">{csrf(req)}<h2 style="font-size:1.0625rem">Add a menu</h2>
<div class="form-row form-row--2">{forms.field("name", "Menu name", "", required=True, attrs={"maxlength": 80, "placeholder": "Reception dinner"})}
{forms.field("description", "Note", "", attrs={"maxlength": 200, "placeholder": "Served from 19:00"})}</div>
<div class="row row--end"><button class="btn btn--primary btn--sm" type="submit">Add menu</button></div></form>"""
    main = "".join(blocks) if blocks else f'<div class="empty"><span class="icon-tile icon-tile--soft">{i("dish")}</span><p>Create a menu, then add dishes. Mark the dishes guests choose between as meal options.</p></div>'
    body = page_head("Menu", "Your digital menu appears on the event website. Meal options are offered in the RSVP form.") + \
        f'<div class="cols cols--2"><div class="stack">{main}{add_menu}</div>{side}</div>'
    return organiser_page(req, ev, "Menu", body, "/menu")


def _need_menu(ev):
    if not has(ev, "menu"):
        raise HTTPError(403, "The digital menu isn't included in this event's package.")


@router.post("/dashboard/events/<uid>/menu/new")
def menu_new(req, uid):
    ev = load(req, uid)
    _need_menu(ev)
    f = Form(req)
    name = f.text("name", "Menu name", required=True, max=80)
    desc = f.text("description", max=200)
    if not f.ok:
        return go(req, ev, "/menu", "error", " ".join(f.errors.values()))
    sort = db.val("SELECT COALESCE(MAX(sort), 0) + 1 FROM menus WHERE event_id = ?", (ev["id"],), 1)
    db.insert("menus", {"event_id": ev["id"], "name": name, "description": desc, "sort": sort})
    return go(req, ev, "/menu", "success", f"{name} added.")


@router.post("/dashboard/events/<uid>/menu/<int:mid>/delete")
def menu_delete(req, uid, mid):
    ev = load(req, uid)
    _need_menu(ev)
    db.run("DELETE FROM menus WHERE id = ? AND event_id = ?", (mid, ev["id"]))
    return go(req, ev, "/menu", "success", "Menu deleted.")


def _read_item(req) -> Form:
    f = Form(req)
    f.choice("course", COURSES, "course", default="Main")
    f.text("name", "Dish", required=True, max=120)
    f.text("description", max=300)
    f.flag("selectable")
    f.data["tags"] = [t for t in req.getlist("tags") if t][:8]
    return f


@router.post("/dashboard/events/<uid>/menu/<int:mid>/items")
def menu_item_new(req, uid, mid):
    ev = load(req, uid)
    _need_menu(ev)
    if not db.one("SELECT 1 FROM menus WHERE id = ? AND event_id = ?", (mid, ev["id"])):
        raise HTTPError(404)
    f = _read_item(req)
    if not f.ok:
        return go(req, ev, "/menu", "error", " ".join(f.errors.values()))
    sort = db.val("SELECT COALESCE(MAX(sort), 0) + 1 FROM menu_items WHERE menu_id = ?", (mid,), 1)
    db.insert("menu_items", {"menu_id": mid, "event_id": ev["id"], "course": f.data["course"], "name": f.data["name"],
                             "description": f.data["description"], "tags": db.dumps(f.data["tags"]),
                             "selectable": 1 if f.data["selectable"] else 0, "sort": sort})
    return go(req, ev, "/menu", "success", f"{f.data['name']} added.")


@router.route("/dashboard/events/<uid>/menu/items/<int:item_id>", methods=("GET", "POST"))
def menu_item_edit(req, uid, item_id):
    ev = load(req, uid)
    _need_menu(ev)
    it = db.one("SELECT * FROM menu_items WHERE id = ? AND event_id = ?", (item_id, ev["id"]))
    if it is None:
        raise HTTPError(404)
    errors = {}
    if req.method == "POST":
        f = _read_item(req)
        if f.ok:
            db.update("menu_items", it["id"], {"course": f.data["course"], "name": f.data["name"], "description": f.data["description"],
                                               "tags": db.dumps(f.data["tags"]), "selectable": 1 if f.data["selectable"] else 0})
            return go(req, ev, "/menu", "success", "Dish saved.")
        errors = f.errors
    course_opts = "".join(f'<option{" selected" if c == it["course"] else ""}>{c}</option>' for c in COURSES)
    body = (f'<p class="small"><a class="text-link" href="{base(ev)}/menu">Menu</a> / {esc(it["name"])}</p>' + page_head("Edit dish")
            + forms.errors_summary(errors) +
            f"""<form class="form box" method="post" style="max-width:720px">{csrf(req)}
<div class="form-row form-row--2"><div class="field"><label>Course</label><select class="select" name="course">{course_opts}</select></div>
{forms.field("name", "Dish", it["name"], required=True, errors=errors, attrs={"maxlength": 120})}</div>
{forms.field("description", "Description", it["description"], type="textarea", attrs={"rows": 3, "maxlength": 300})}
{_tag_checks(db.loads(it["tags"], []))}{forms.check("selectable", "Guests choose this as their meal", bool(it["selectable"]))}
<div class="row row--between"><a class="btn btn--ghost" href="{base(ev)}/menu">Cancel</a><button class="btn btn--primary" type="submit">Save dish</button></div></form>""")
    return organiser_page(req, ev, "Edit dish", body, "/menu")


@router.post("/dashboard/events/<uid>/menu/items/<int:item_id>/delete")
def menu_item_delete(req, uid, item_id):
    ev = load(req, uid)
    _need_menu(ev)
    db.run("DELETE FROM menu_items WHERE id = ? AND event_id = ?", (item_id, ev["id"]))
    return go(req, ev, "/menu", "success", "Dish removed.")


@router.post("/dashboard/events/<uid>/menu/drinks")
def menu_drinks(req, uid):
    ev = load(req, uid)
    _need_menu(ev)
    info = dict(ev.get("info") or {})
    info["drinks"] = req.get("drinks")[:600]
    events.save_json(ev["id"], "info", info)
    return go(req, ev, "/menu", "success", "Drinks information saved.")


# =============================================================================================
# Programme
# =============================================================================================
@router.get("/dashboard/events/<uid>/programme")
def programme(req, uid):
    ev = load(req, uid)
    if not has(ev, "programme"):
        return organiser_page(req, ev, "Programme", page_head("Programme") + locked_panel(ev, "programme", "The event programme"), "/programme")
    funcs = events.functions(ev["id"])
    items = events.schedule(ev["id"])
    max_f = catalog.limit(ev, "functions", 1) if has(ev, "multi_functions") else 1
    func_opts = '<option value="">Whole event</option>' + "".join(f'<option value="{f["id"]}">{esc(f["name"])}</option>' for f in funcs)
    kind_opts = "".join(f'<option value="{k}">{l}</option>' for k, l in KINDS)
    flist = "".join(
        f'<li><span><b>{esc(f["name"])}</b><br><span class="small muted">{esc(" · ".join(x for x in (forms.fmt_date(f["func_date"], False), " to ".join(y for y in (f["start_time"], f["end_time"]) if y), f["venue_name"]) if x))}</span></span>'
        f'<span class="row" style="flex-wrap:nowrap"><a class="btn btn--ghost btn--sm" href="{base(ev)}/programme/functions/{f["id"]}" aria-label="Edit {esc(f["name"])}">{i("edit")}</a>'
        f'<form method="post" action="{base(ev)}/programme/functions/{f["id"]}/delete" data-confirm="Delete {esc(f["name"])}? Its programme items stay, under the whole event.">{csrf(req)}'
        f'<button class="btn btn--ghost btn--sm" type="submit" aria-label="Delete {esc(f["name"])}">{i("trash")}</button></form></span></li>' for f in funcs)
    can_add_f = len(funcs) < max_f
    add_f = (f"""<details{" open" if not funcs else ""} style="margin-top:12px"><summary class="btn btn--secondary btn--sm" style="list-style:none;display:inline-flex">{i("plus")}Add a function</summary>
<form class="form" method="post" action="{base(ev)}/programme/functions" style="margin-top:12px">{csrf(req)}{_function_fields({})}
<div class="row row--end"><button class="btn btn--primary btn--sm" type="submit">Add function</button></div></form></details>""" if can_add_f else
             f'<p class="small muted" style="margin-top:12px">Your package includes {max_f} function{"s" if max_f != 1 else ""}. '
             + ("" if has(ev, "multi_functions") else f'<a class="text-link" href="{base(ev)}/setup/8">Upgrade for more ceremonies and venues.</a>') + "</p>")
    rows = []
    current = object()
    for it in items:
        if it["function_name"] != current:
            current = it["function_name"]
            rows.append(f'<li style="border:0;padding-top:16px"><b class="small" style="color:var(--color-accent-text)">{esc(current or "Whole event")}</b></li>')
        rows.append(f'<li><span style="display:grid;grid-template-columns:64px 1fr;gap:12px"><time>{esc(it["item_time"] or "—")}</time>'
                    f'<span><b>{esc(it["title"])}</b> <span class="tag">{esc(dict(KINDS).get(it["kind"], it["kind"]))}</span>'
                    f'{(BR_MUTED + esc(it["description"]) + "</span>") if it["description"] else ""}</span></span>'
                    f'<span class="row" style="flex-wrap:nowrap"><a class="btn btn--ghost btn--sm" href="{base(ev)}/programme/items/{it["id"]}" aria-label="Edit {esc(it["title"])}">{i("edit")}</a>'
                    f'<form method="post" action="{base(ev)}/programme/items/{it["id"]}/delete" data-confirm="Remove {esc(it["title"])}?">{csrf(req)}'
                    f'<button class="btn btn--ghost btn--sm" type="submit" aria-label="Remove {esc(it["title"])}">{i("trash")}</button></form></span></li>')
    schedule_html = f'<ul class="list-plain list-rows">{"".join(rows)}</ul>' if rows else '<p class="small muted">No programme items yet.</p>'
    body = page_head("Programme", "Add the parts of your day. The programme shows on your event website in time order.") + f"""
<div class="cols cols--2"><div class="box"><div class="box__head"><h2>Schedule</h2></div>{schedule_html}
<form class="form" method="post" action="{base(ev)}/programme/items" style="margin-top:18px;padding-top:18px;border-top:1px solid var(--color-line)">{csrf(req)}
<h3 style="font-size:1rem">Add to the programme</h3>
<div class="form-row form-row--3">{forms.field("item_time", "Time", "", type="time")}{forms.field("title", "What happens", "", required=True, attrs={"maxlength": 120, "placeholder": "First dance"})}
<div class="field"><label for="f-kind">Type</label><select class="select" id="f-kind" name="kind">{kind_opts}</select></div></div>
<div class="form-row form-row--2">{forms.field("description", "Details", "", attrs={"maxlength": 300})}
<div class="field"><label for="f-function">Part of</label><select class="select" id="f-function" name="function_id">{func_opts}</select></div></div>
<div class="row row--end"><button class="btn btn--primary btn--sm" type="submit">Add item</button></div></form></div>
<div class="box"><div class="box__head"><h2>Functions</h2><span class="small muted">{len(funcs)} of {max_f}</span></div>
<p class="small muted">Ceremonies, receptions or days, each with its own date, time and venue.</p>
{f'<ul class="list-plain list-rows">{flist}</ul>' if flist else ""}{add_f}</div></div>"""
    return organiser_page(req, ev, "Programme", body, "/programme")


def _function_fields(v) -> str:
    return f"""<div class="form-row form-row--2">{forms.field("name", "Name", v.get("name", ""), required=True, attrs={"maxlength": 80, "placeholder": "Ceremony"})}
{forms.field("func_date", "Date", v.get("func_date", ""), type="date")}
{forms.field("start_time", "Starts", v.get("start_time", ""), type="time")}{forms.field("end_time", "Ends", v.get("end_time", ""), type="time")}
{forms.field("venue_name", "Venue", v.get("venue_name", ""), attrs={"maxlength": 120})}{forms.field("address", "Address", v.get("address", ""), attrs={"maxlength": 250})}
{forms.field("map_url", "Map link", v.get("map_url", ""), type="url", hint="Paste a Google Maps link.")}{forms.field("dress_code", "Dress code", v.get("dress_code", ""), attrs={"maxlength": 120})}</div>
{forms.field("description", "Description", v.get("description", ""), type="textarea", attrs={"rows": 3, "maxlength": 600})}"""


def _read_function(req) -> Form:
    f = Form(req)
    f.text("name", "Name", required=True, max=80)
    f.date("func_date", "Date")
    f.time("start_time", "Start time")
    f.time("end_time", "End time")
    f.text("venue_name", "Venue", max=120)
    f.text("address", max=250)
    f.url("map_url", "Map link")
    f.text("dress_code", "Dress code", max=120)
    f.text("description", max=600)
    return f


def _need_programme(ev):
    if not has(ev, "programme"):
        raise HTTPError(403, "The programme isn't included in this event's package.")


@router.post("/dashboard/events/<uid>/programme/functions")
def function_new(req, uid):
    ev = load(req, uid)
    _need_programme(ev)
    max_f = catalog.limit(ev, "functions", 1) if has(ev, "multi_functions") else 1
    if len(events.functions(ev["id"])) >= max_f:
        return go(req, ev, "/programme", "error", f"Your package includes {max_f} function{'s' if max_f != 1 else ''}.")
    f = _read_function(req)
    if not f.ok:
        return go(req, ev, "/programme", "error", " ".join(f.errors.values()))
    sort = db.val("SELECT COALESCE(MAX(sort), 0) + 1 FROM event_functions WHERE event_id = ?", (ev["id"],), 1)
    db.insert("event_functions", {"event_id": ev["id"], "sort": sort, **f.data})
    return go(req, ev, "/programme", "success", f"{f.data['name']} added.")


@router.route("/dashboard/events/<uid>/programme/functions/<int:fid>", methods=("GET", "POST"))
def function_edit(req, uid, fid):
    ev = load(req, uid)
    _need_programme(ev)
    fn = db.one("SELECT * FROM event_functions WHERE id = ? AND event_id = ?", (fid, ev["id"]))
    if fn is None:
        raise HTTPError(404)
    errors, values = {}, dict(fn)
    if req.method == "POST":
        f = _read_function(req)
        if f.ok:
            db.update("event_functions", fn["id"], f.data)
            return go(req, ev, "/programme", "success", "Function saved.")
        errors, values = f.errors, f.data
    body = (f'<p class="small"><a class="text-link" href="{base(ev)}/programme">Programme</a> / {esc(fn["name"])}</p>' + page_head("Edit function")
            + forms.errors_summary(errors) + f'<form class="form box" method="post" style="max-width:820px">{csrf(req)}{_function_fields(values)}'
            f'<div class="row row--between"><a class="btn btn--ghost" href="{base(ev)}/programme">Cancel</a><button class="btn btn--primary" type="submit">Save</button></div></form>')
    return organiser_page(req, ev, "Edit function", body, "/programme")


@router.post("/dashboard/events/<uid>/programme/functions/<int:fid>/delete")
def function_delete(req, uid, fid):
    ev = load(req, uid)
    _need_programme(ev)
    db.run("DELETE FROM event_functions WHERE id = ? AND event_id = ?", (fid, ev["id"]))
    return go(req, ev, "/programme", "success", "Function deleted.")


def _read_item_sched(req, ev) -> Form:
    f = Form(req)
    f.time("item_time", "Time")
    f.text("title", "What happens", required=True, max=120)
    f.text("description", "Details", max=300)
    f.choice("kind", [k for k, _ in KINDS], "type", default="other")
    fid = req.get("function_id")
    f.data["function_id"] = None
    if fid:
        if not db.one("SELECT 1 FROM event_functions WHERE id = ? AND event_id = ?", (fid, ev["id"])):
            f.error("function_id", "Choose one of your functions.")
        else:
            f.data["function_id"] = int(fid)
    return f


@router.post("/dashboard/events/<uid>/programme/items")
def schedule_new(req, uid):
    ev = load(req, uid)
    _need_programme(ev)
    f = _read_item_sched(req, ev)
    if not f.ok:
        return go(req, ev, "/programme", "error", " ".join(f.errors.values()))
    sort = db.val("SELECT COALESCE(MAX(sort), 0) + 1 FROM schedule_items WHERE event_id = ?", (ev["id"],), 1)
    db.insert("schedule_items", {"event_id": ev["id"], "sort": sort, **f.data})
    return go(req, ev, "/programme", "success", f"{f.data['title']} added to the programme.")


@router.route("/dashboard/events/<uid>/programme/items/<int:item_id>", methods=("GET", "POST"))
def schedule_edit(req, uid, item_id):
    ev = load(req, uid)
    _need_programme(ev)
    it = db.one("SELECT * FROM schedule_items WHERE id = ? AND event_id = ?", (item_id, ev["id"]))
    if it is None:
        raise HTTPError(404)
    errors, v = {}, dict(it)
    if req.method == "POST":
        f = _read_item_sched(req, ev)
        if f.ok:
            db.update("schedule_items", it["id"], f.data)
            return go(req, ev, "/programme", "success", "Programme item saved.")
        errors, v = f.errors, f.data
    funcs = events.functions(ev["id"])
    func_opts = '<option value="">Whole event</option>' + "".join(
        f'<option value="{fn["id"]}"{" selected" if fn["id"] == v.get("function_id") else ""}>{esc(fn["name"])}</option>' for fn in funcs)
    kind_opts = "".join(f'<option value="{k}"{" selected" if k == v.get("kind") else ""}>{l}</option>' for k, l in KINDS)
    body = (f'<p class="small"><a class="text-link" href="{base(ev)}/programme">Programme</a> / {esc(it["title"])}</p>' + page_head("Edit programme item")
            + forms.errors_summary(errors) + f"""<form class="form box" method="post" style="max-width:720px">{csrf(req)}
<div class="form-row form-row--3">{forms.field("item_time", "Time", v.get("item_time") or "", type="time", errors=errors)}{forms.field("title", "What happens", v.get("title", ""), required=True, errors=errors, attrs={"maxlength": 120})}
<div class="field"><label for="f-kind">Type</label><select class="select" id="f-kind" name="kind">{kind_opts}</select></div></div>
{forms.field("description", "Details", v.get("description", ""), type="textarea", attrs={"rows": 3, "maxlength": 300})}
<div class="field"><label for="f-function">Part of</label><select class="select" id="f-function" name="function_id">{func_opts}</select></div>
<div class="row row--between"><a class="btn btn--ghost" href="{base(ev)}/programme">Cancel</a><button class="btn btn--primary" type="submit">Save</button></div></form>""")
    return organiser_page(req, ev, "Edit programme item", body, "/programme")


@router.post("/dashboard/events/<uid>/programme/items/<int:item_id>/delete")
def schedule_delete(req, uid, item_id):
    ev = load(req, uid)
    _need_programme(ev)
    db.run("DELETE FROM schedule_items WHERE id = ? AND event_id = ?", (item_id, ev["id"]))
    return go(req, ev, "/programme", "success", "Removed from the programme.")


# =============================================================================================
# Communications
# =============================================================================================
GUEST_TEMPLATES = [
    ("guest_invitation", "Invitation with personal RSVP link", "personal_invites"),
    ("guest_reminder", "RSVP reminder", "reminders"),
    ("guest_event_reminder", "Event reminder", "email_notifications"),
    ("final_info", "Final event information", "email_notifications"),
    ("thank_you", "Thank-you message", "email_notifications"),
    ("venue_update", "Venue update", "advanced_comms"),
    ("programme_update", "Programme update", "advanced_comms"),
    ("custom_message", "Your own message", "advanced_comms"),
]
TEMPLATE_FEATURE = {k: f for k, _, f in GUEST_TEMPLATES}
AUDIENCES = [("all", "Everyone with an email address"), ("pending", "Guests who haven't replied"),
             ("attending", "Guests who are attending"), ("declined", "Guests who declined")]


def recipients(ev, audience: str):
    rows = db.q("SELECT * FROM guests WHERE event_id = ? ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE", (ev["id"],))
    if audience in ("pending", "attending", "declined"):
        rows = [g for g in rows if g["status"] == audience]
    elif audience.startswith("category:"):
        cat = audience.split(":", 1)[1]
        rows = [g for g in rows if g["category"] == cat]
    eligible = [g for g in rows if notify.can_email_guest(g)]
    return eligible, len(rows) - len(eligible)


def _message_html(text: str) -> str:
    return "<br>".join(esc(line) for line in text.strip().split("\n")) if text.strip() else ""


def _guest_email_vars(ev, g, message: str, subject: str) -> dict:
    return {**notify.event_vars(ev), **notify.guest_vars(ev, g), "message_html": _message_html(message), "subject": subject}


def _comms_form_values(req, ev):
    tpl = req.get("template") or req.arg("template") or "guest_invitation"
    if tpl not in TEMPLATE_FEATURE:
        tpl = "guest_invitation"
    audience = req.get("audience") or req.arg("audience") or "all"
    cats = {g[0] for g in db.q("SELECT DISTINCT category FROM guests WHERE event_id = ? AND category != ''", (ev["id"],))}
    if audience not in dict(AUDIENCES) and not (audience.startswith("category:") and audience.split(":", 1)[1] in cats):
        audience = "all"
    return tpl, audience, req.get("subject")[:150], req.get("message")[:3000], sorted(cats)


def _send_blockers(ev, tpl: str, count: int) -> list:
    problems = []
    if not events.is_live(ev):
        problems.append("Guest emails can be sent once your event website is paid for and published.")
    if not has(ev, TEMPLATE_FEATURE[tpl]):
        problems.append(f"“{dict((k, l) for k, l, _ in GUEST_TEMPLATES)[tpl]}” isn't included in this event's package.")
    used, allowed = events.email_quota(ev)
    if used + count > allowed:
        problems.append(f"This would go over your package's {allowed} guest emails ({used} used).")
    if count == 0:
        problems.append("No guests in this audience can receive email.")
    return problems


@router.get("/dashboard/events/<uid>/communications")
def comms(req, uid):
    ev = load(req, uid)
    if not has(ev, "email_notifications"):
        return organiser_page(req, ev, "Communications", page_head("Communications") + locked_panel(ev, "email_notifications", "Email communication"), "/communications")
    tpl, audience, subject, message, cats = _comms_form_values(req, ev)
    used, allowed = events.email_quota(ev)
    tpl_opts = "".join(
        f'<option value="{k}"{" selected" if k == tpl else ""}{"" if has(ev, f) else " disabled"}>{esc(l)}{"" if has(ev, f) else " (upgrade)"}</option>'
        for k, l, f in GUEST_TEMPLATES)
    aud_opts = "".join(f'<option value="{k}"{" selected" if k == audience else ""}>{esc(l)}</option>' for k, l in AUDIENCES)
    aud_opts += "".join(f'<option value="category:{esc(c)}"{" selected" if audience == "category:" + c else ""}>Category: {esc(c)}</option>' for c in cats)
    live_note = "" if events.is_live(ev) else (
        f'<div class="notice notice--warn" style="margin-bottom:16px">{i("alert")}<div>You can draft and preview messages now. '
        f'Sending to guests starts once your website is paid for and published. <a class="text-link" href="{base(ev)}/setup/8">Publish your event</a></div></div>')
    logs = db.q("SELECT * FROM email_logs WHERE event_id = ? ORDER BY created_at DESC, id DESC LIMIT 40", (ev["id"],))
    log_rows = "".join(
        f'<tr><td>{esc(l["subject"])}<span class="table__sub">{esc(l["to_email"])}</span></td><td>{"Guest" if l["audience"] == "guest" else "You"}</td>'
        f'<td><span class="pill pill--{esc(l["status"])}">{esc(l["status"].capitalize())}</span></td><td class="small muted">{esc(forms.fmt_dt(l["created_at"]))}</td></tr>' for l in logs)
    log_box = (f'<div class="table-wrap"><table class="table"><thead><tr><th>Email</th><th>To</th><th>Status</th><th>When</th></tr></thead><tbody>{log_rows}</tbody></table></div>'
               if logs else '<div class="empty"><p>No emails sent for this event yet.</p></div>')
    final_btn = ""
    if has(ev, "reports"):
        final_btn = (f'<form method="post" action="{base(ev)}/communications/final-report">{csrf(req)}'
                     f'<button class="btn btn--secondary btn--sm" type="submit">{i("file")}Email me the final report</button></form>')
    body = page_head("Communications", "Email your guests with a preview before anything is sent. Only guests who expect event emails, and haven't opted out, receive them.", final_btn) + live_note + f"""
<div class="cols cols--2"><form class="box form" method="post" action="{base(ev)}/communications/preview">{csrf(req)}
<div class="box__head"><h2>New message</h2><span class="small muted mono">{used} / {allowed} guest emails used</span></div>
<div class="form-row form-row--2"><div class="field"><label for="f-template">Message type</label><select class="select" id="f-template" name="template">{tpl_opts}</select></div>
<div class="field"><label for="f-audience">Send to</label><select class="select" id="f-audience" name="audience">{aud_opts}</select></div></div>
{forms.field("subject", "Subject (for “Your own message”)", subject, attrs={"maxlength": 150})}
{forms.field("message", "Your message", message, type="textarea", attrs={"rows": 7, "maxlength": 3000}, hint="Added to the email in your words. Leave empty for reminders.")}
<div class="row row--end"><button class="btn btn--primary" type="submit">{i("eye")}Preview</button></div></form>
<div class="stack"><div class="box"><div class="box__head"><h2>Good to know</h2></div><ul class="small muted" style="margin:0;padding-left:18px;display:grid;gap:8px">
<li>Every guest gets their own personal link in the email.</li><li>Guests can opt out from any email; we never email them again for this event.</li>
<li>WhatsApp messages are sent by you from the <a class="text-link" href="{base(ev)}/share">Share</a> page.</li>
<li>Sharing your link is unlimited; emails count towards your package's allowance.</li></ul></div></div></div>
<h2 style="font-size:1.125rem;margin:28px 0 12px">Email log</h2>{log_box}"""
    return organiser_page(req, ev, "Communications", body, "/communications")


@router.post("/dashboard/events/<uid>/communications/preview")
def comms_preview(req, uid):
    ev = load(req, uid)
    if not has(ev, "email_notifications"):
        raise HTTPError(403)
    tpl, audience, subject, message, _ = _comms_form_values(req, ev)
    if tpl == "custom_message" and not subject:
        req.flash("error", "Add a subject for your own message.")
        return redirect(url(f"{base(ev)}/communications", template=tpl, audience=audience))
    eligible, skipped = recipients(ev, audience)
    problems = _send_blockers(ev, tpl, len(eligible))
    sample = eligible[0] if eligible else {"first_name": "Guest", "last_name": "", "token": "preview", "email": ""}
    msg = mail.compose(tpl, _guest_email_vars(ev, sample, message, subject))
    hidden = (f'<input type="hidden" name="template" value="{esc(tpl)}"><input type="hidden" name="audience" value="{esc(audience)}">'
              f'<input type="hidden" name="subject" value="{esc(subject)}"><textarea name="message" hidden>{esc(message)}</textarea>')
    who = ", ".join(esc(events.guest_name(g)) for g in eligible[:6]) + (f" and {len(eligible) - 6} more" if len(eligible) > 6 else "")
    blockers = ""
    if problems:
        blockers = f'<div class="notice notice--warn">{i("alert")}<div><b>This can’t be sent yet</b><ul style="margin:6px 0 0;padding-left:18px">' + \
            "".join(f"<li>{esc(p)}</li>" for p in problems) + "</ul></div></div>"
    send = (f'<form method="post" action="{base(ev)}/communications/send" data-confirm="Send this email to {len(eligible)} guests?">{csrf(req)}{hidden}'
            f'<button class="btn btn--primary btn--block" type="submit"{" disabled" if problems else ""}>{i("send")}Send to {len(eligible)} guests</button></form>')
    edit = (f'<form method="get" action="{base(ev)}/communications"><input type="hidden" name="template" value="{esc(tpl)}">'
            f'<input type="hidden" name="audience" value="{esc(audience)}"><button class="btn btn--ghost btn--block" type="submit">Back and edit</button></form>')
    body = page_head("Preview", "Check the email below. Each guest sees their own name and personal link.") + f"""
<div class="cols cols--2"><div class="box" style="padding:0;overflow:hidden"><div class="preview-frame__bar"><span><b>Subject:</b> {esc(msg["subject"])}</span></div>
<iframe title="Email preview" sandbox="" srcdoc="{esc(msg["html"])}" style="width:100%;height:720px;border:0;background:#F5F5F4"></iframe></div>
<div class="stack"><div class="box stack" style="--stack:12px"><div class="kpis" style="--n:2"><div class="kpi"><span>Will receive it</span><b data-recipient-count>{len(eligible)}</b></div>
<div class="kpi"><span>Skipped</span><b data-skipped-count>{skipped}</b><small>no email, no consent or opted out</small></div></div>
{f'<p class="small muted">{who}</p>' if eligible else ""}{blockers}{send}{edit}</div></div></div>"""
    return organiser_page(req, ev, "Preview email", body, "/communications")


@router.post("/dashboard/events/<uid>/communications/send")
def comms_send(req, uid):
    ev = load(req, uid)
    if not has(ev, "email_notifications"):
        raise HTTPError(403)
    tpl, audience, subject, message, _ = _comms_form_values(req, ev)
    eligible, skipped = recipients(ev, audience)
    problems = _send_blockers(ev, tpl, len(eligible))
    if problems:
        req.flash("error", problems[0])
        return redirect(url(f"{base(ev)}/communications", template=tpl, audience=audience))
    batch = secrets.token_hex(6)
    sent = failed = 0
    for g in eligible:
        r = mail.send(g["email"], tpl, _guest_email_vars(ev, g, message, subject), event_id=ev["id"], guest_id=g["id"], batch_id=batch)
        if r["status"] == "sent":
            sent += 1
            if tpl == "guest_invitation" and not g["invited_at"]:
                db.run("UPDATE guests SET invited_at = ? WHERE id = ?", (db.now(), g["id"]))
        else:
            failed += 1
    auth.audit(req.user["id"], "comms.send", ev["uid"], template=tpl, audience=audience, sent=sent, failed=failed, batch=batch)
    msg = f"Sent to {sent} guests."
    if failed:
        msg += f" {failed} could not be delivered; see the email log."
    if skipped:
        msg += f" {skipped} skipped."
    req.flash("success" if not failed else "error", msg)
    return redirect(f"{base(ev)}/communications")


@router.post("/dashboard/events/<uid>/communications/final-report")
def comms_final_report(req, uid):
    ev = load(req, uid)
    if not has(ev, "reports"):
        raise HTTPError(403, "Downloadable reports aren't included in this event's package.")
    from ..services import reports
    s = events.stats(ev["id"])
    res = notify.organiser(ev, "final_report", {"summary_table": notify.summary_table_html(s)},
                           attachments=reports.final_attachments(ev, user_id=req.user["id"]), owner_only=False)
    back = req.get("back") if req.get("back") in ("/reports", "/communications") else "/communications"
    if any(r["status"] == "sent" for r in res):
        return go(req, ev, back, "success", "The final report is on its way to your inbox (PDF and CSV attached).")
    return go(req, ev, back, "error", "The report email couldn't be delivered. Please download it instead.")
