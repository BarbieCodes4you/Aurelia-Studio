"""Guest-facing event websites: public page, personal invitations, RSVP, unsubscribe, calendar,
plus the organiser preview and the template-gallery sample render."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .. import auth, catalog, config, db, events, notify
from ..eventsite import render as R
from ..eventsite import themes
from ..eventsite.demo import demo_event
from ..services import email as mail
from ..web import HTTPError, Response, esc, redirect, router
from .forms import EMAIL_RE, Form


def is_available(ev) -> bool:
    """Guests may open the site: published, paid, not suspended, inside the hosting period."""
    if not events.is_live(ev):
        return False
    hu = ev.get("hosting_until")
    if hu:
        try:
            if date.today() > date.fromisoformat(hu[:10]):
                return False
        except ValueError:
            pass
    return True


def simple_page(ev, title: str, body: str, status: int = 200) -> Response:
    """A small themed page (unavailable, unsubscribe) using the event's palette when known."""
    style, fonts = "", ""
    if ev:
        t = themes.resolve(R.design_key(ev), ev.get("design") or {})
        style = themes.css_vars(t) + R.contrast_vars(t["colors"])
        fonts = f'<link rel="stylesheet" href="{esc(themes.fonts_url(t["display"], t["body"]))}">'
    html = f"""<!doctype html><html lang="en-ZA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="robots" content="noindex"><link rel="icon" href="/favicon.svg" type="image/svg+xml">{fonts}
<link rel="stylesheet" href="/static/css/eventsite.css"></head>
<body class="ev ev-simple" style="{style}"><main class="ev-simple__card">{body}
<p class="ev-made"><a href="/">Made with {esc(config.BRAND_NAME)}</a></p></main></body></html>"""
    return Response(html, status=status)


def unavailable(ev=None) -> Response:
    body = ('<h1>This event page isn\'t available</h1><p>The link may be private, the page may not be published yet, '
            'or the event has ended. If you were invited, please check with the hosts.</p>')
    return simple_page(ev, "Event page not available", body, 404)


def _load(slug: str):
    ev = events.by_slug(slug)
    if ev is None:
        raise HTTPError(404)
    return ev


@router.get("/events/<slug:slug>")
def event_page(req, slug):
    ev = events.by_slug(slug)
    if ev is None:
        return unavailable()
    if is_available(ev):
        return Response(R.render(ev, "public", None, req))
    if auth.can_manage_event(req.user, ev):
        return Response(R.render(ev, "preview", None, req, notice="Guests see an 'unavailable' page until it is published"))
    return unavailable(ev)


def _guest(ev, token: str):
    g = db.one("SELECT * FROM guests WHERE token = ? AND event_id = ?", (token, ev["id"]))
    if g is None:
        raise HTTPError(404)
    return g


@router.get("/events/<slug:slug>/i/<token>")
def invitation(req, slug, token):
    ev = events.by_slug(slug)
    if ev is None:
        return unavailable()
    guest = db.one("SELECT * FROM guests WHERE token = ? AND event_id = ?", (token, ev["id"]))
    if guest is None:
        return unavailable(ev)
    if is_available(ev):
        if not guest["invited_at"] and not auth.can_manage_event(req.user, ev):    # the guest has their link
            db.run("UPDATE guests SET invited_at = ? WHERE id = ? AND invited_at IS NULL", (db.now(), guest["id"]))
        return Response(R.render(ev, "public", guest, req))
    if auth.can_manage_event(req.user, ev):
        return Response(R.render(ev, "preview", guest, req, notice=f"Personal link for {events.guest_name(guest)}"))
    return unavailable(ev)


# --- RSVP -----------------------------------------------------------------------------------------
STATUS_TEXT_GUEST = {"attending": "attending", "declined": "not attending"}
STATUS_TEXT_ORG = {"attending": "is attending", "declined": "can't attend"}


def _rerender(req, ev, guest, form, status=400):
    values = {k: (",".join(v) if k == "dietary" else v[0]) for k, v in req.form.items() if k != "_csrf"}
    return Response(R.render(ev, "public", guest, req, form={"errors": form.errors, "values": values}), status=status)


@router.post("/events/<slug:slug>/rsvp")
def rsvp(req, slug):
    ev = events.by_slug(slug)
    if ev is None or not is_available(ev):
        return unavailable(ev)
    token = req.get("token")
    guest = _guest(ev, token) if token else None
    back = f"/events/{ev['slug']}" + (f"/i/{guest['token']}" if guest else "")
    if req.get("website"):  # honeypot: pretend all is well
        return redirect(back + "?rsvp=thanks#rsvp")
    if auth.rate_limited(f"rsvp:{req.ip}", 30, 600):
        raise HTTPError(429, "Too many replies from this connection. Please wait a few minutes and try again.")
    closed = R.rsvp_closed(ev)
    if closed:
        return Response(R.render(ev, "public", guest, req, notice=closed), status=409)

    f = Form(req)
    status = f.choice("status", ["attending", "declined"], "answer", required=True)
    if not status and "status" not in f.errors:
        f.error("status", "Tell us whether you'll attend.")
    if guest is None:
        first = f.text("first_name", "First name", required=True, max=80)
        last = f.text("last_name", "Surname", required=True, max=80)
        email_addr = f.email("email", required=True)
        phone = f.phone("phone")
    allow = R.allowances(ev, guest)
    plus = f.integer("plus_ones", "Guests joining you", min=0, max=allow["plus_ones"]) if allow["plus_ones"] else 0
    kids = f.integer("children", "Children", min=0, max=allow["children"]) if allow["children"] else 0
    plus_names = f.text("plus_one_names", "Their names", max=300) if allow["plus_ones"] else ""
    special = f.text("special_requests", "Message", max=1000)
    meal_id = None
    meal_options = {m["id"]: m for m in events.meal_options(ev["id"])}
    if meal_options and catalog.has_feature(ev, "menu", public=True) and events.visible_sections(ev)["menu"]:
        raw = f.text("meal_item_id", "Meal choice", max=12)
        if raw:
            try:
                meal_id = int(raw)
            except ValueError:
                meal_id = None
            if meal_id not in meal_options:
                f.error("meal_item_id", "Choose one of the listed meals.")
                meal_id = None
    dietary, allergies = "", ""
    if catalog.has_feature(ev, "dietary", public=True):
        offered = set(ev["info"].get("dietary_options") or events.DIETARY_OPTIONS)
        dietary = ", ".join(d for d in req.getlist("dietary") if d in offered)
        allergies = f.text("allergies", "Allergies", max=300)
    funcs = events.functions(ev["id"])
    multi = len(funcs) > 1 and catalog.has_feature(ev, "multi_functions", public=True)
    chosen_funcs = set()
    if multi:
        valid = {fn["id"] for fn in funcs}
        for x in req.getlist("functions"):
            if x.isdigit() and int(x) in valid:
                chosen_funcs.add(int(x))
        if status == "attending" and not chosen_funcs:
            f.error("functions", "Choose at least one part of the celebration.")
    if not f.ok:
        return _rerender(req, ev, guest, f)
    if status == "declined":
        plus, kids, plus_names, meal_id, dietary, allergies = 0, 0, "", None, "", ""

    now = db.now()
    via = "personal" if guest else "general"
    with db.transaction():
        if guest is None:
            existing = db.one("""SELECT * FROM guests WHERE event_id = ? AND email = ? AND status = 'pending'
                                 ORDER BY id LIMIT 1""", (ev["id"], email_addr))
            if existing is not None:
                guest_id = existing["id"]
                db.update("guests", guest_id, {"phone": existing["phone"] or phone})
            else:
                guest_id = db.insert("guests", {
                    "event_id": ev["id"], "token": events.new_guest_token(), "first_name": first, "last_name": last,
                    "email": email_addr, "phone": phone, "source": "general_link",
                    "plus_ones_allowed": allow["plus_ones"], "children_allowed": allow["children"],
                    "invited_at": None, "created_at": now, "updated_at": now})
        else:
            guest_id = guest["id"]
        db.update("guests", guest_id, {
            "status": status, "plus_ones": plus, "plus_one_names": plus_names, "children": kids,
            "meal_item_id": meal_id, "dietary": dietary, "allergies": allergies, "special_requests": special,
            "responded_at": now, "updated_at": now})
        if multi:
            db.run("DELETE FROM guest_functions WHERE guest_id = ?", (guest_id,))
            for fn in funcs:
                db.insert("guest_functions", {"guest_id": guest_id, "function_id": fn["id"],
                                              "attending": 1 if (status == "attending" and fn["id"] in chosen_funcs) else 0})
        db.insert("rsvp_responses", {"event_id": ev["id"], "guest_id": guest_id, "via": via, "created_at": now,
                                     "payload": db.dumps({"status": status, "plus_ones": plus, "plus_one_names": plus_names,
                                                          "children": kids, "meal_item_id": meal_id, "dietary": dietary,
                                                          "allergies": allergies, "special_requests": special,
                                                          "functions": sorted(chosen_funcs)})})
    g = db.one("SELECT * FROM guests WHERE id = ?", (guest_id,))
    _notify(ev, g)
    return redirect(f"/events/{ev['slug']}/i/{g['token']}?rsvp=thanks#rsvp" if guest else back + "?rsvp=thanks#rsvp")


def _notify(ev, g) -> None:
    details = notify.rsvp_details_html(ev, g)
    try:
        if notify.can_email_guest(g):
            v = {**notify.event_vars(ev), **notify.guest_vars(ev, g),
                 "status_text": STATUS_TEXT_GUEST.get(g["status"], g["status"]), "details": details}
            mail.send(g["email"], "rsvp_confirmation", v, event_id=ev["id"], guest_id=g["id"])
        if (ev.get("report_prefs") or {}).get("new_rsvp", True):
            st = events.stats(ev["id"])
            notify.organiser(ev, "new_rsvp", {"guest_name": events.guest_name(g),
                                              "status_text": STATUS_TEXT_ORG.get(g["status"], g["status"]),
                                              "details": details, "attending": st["attending"],
                                              "declined": st["declined"], "pending": st["pending"]})
    except Exception as e:  # never lose an RSVP because an email failed
        import sys
        print(f"[rsvp] notification failed: {e}", file=sys.stderr)


# --- unsubscribe ---------------------------------------------------------------------------------
@router.route("/events/<slug:slug>/u/<token>", methods=("GET", "POST"))
def unsubscribe(req, slug, token):
    ev = events.by_slug(slug)
    if ev is None:
        return unavailable()
    g = db.one("SELECT * FROM guests WHERE token = ? AND event_id = ?", (token, ev["id"]))
    if g is None:
        return unavailable(ev)
    host = esc(events.title(ev))
    if req.method == "POST":
        db.update("guests", g["id"], {"unsubscribed_at": db.now(), "email_consent": 0, "updated_at": db.now()})
        body = (f"<h1>You won't receive more emails</h1><p>We've stopped event emails from {host} to "
                f"{esc(g['email'] or 'you')}. Your RSVP is unchanged, and the event page still works from your link.</p>"
                f'<p><a class="ev-btn ev-btn--ghost" href="/events/{esc(ev["slug"])}/i/{esc(g["token"])}">Back to the event</a></p>')
        return simple_page(ev, "Unsubscribed", body)
    if g["unsubscribed_at"]:
        body = f"<h1>You're already unsubscribed</h1><p>You won't receive event emails from {host}.</p>"
        return simple_page(ev, "Unsubscribed", body)
    body = (f"<h1>Stop event emails?</h1><p>You'll no longer receive invitations, reminders or updates about "
            f"<b>{esc(ev['name'])}</b> from {host}. Under the Protection of Personal Information Act (POPIA) you can "
            f"withdraw consent at any time; we'll record the date you did.</p>"
            f'<form method="post"><input type="hidden" name="_csrf" value="{esc(req.csrf)}">'
            f'<button class="ev-btn" type="submit">Stop emails</button></form>')
    return simple_page(ev, "Unsubscribe", body)


# --- calendar -------------------------------------------------------------------------------------
def _ics_text(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/events/<slug:slug>/calendar.ics")
def calendar(req, slug):
    ev = events.by_slug(slug)
    if ev is None or not (is_available(ev) or auth.can_manage_event(req.user, ev)) or not ev.get("event_date"):
        return unavailable(ev)
    start = datetime.fromisoformat(f"{ev['event_date']}T{ev.get('start_time') or '12:00'}") - timedelta(hours=2)
    if ev.get("end_time"):
        end = datetime.fromisoformat(f"{ev['event_date']}T{ev['end_time']}") - timedelta(hours=2)
        if end <= start:
            end += timedelta(days=1)
    else:
        end = start + timedelta(hours=4)
    fmt = "%Y%m%dT%H%M%SZ"
    v = ev.get("venue") or {}
    loc = ", ".join(x for x in (v.get("name"), v.get("address")) if x)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{config.BRAND_NAME}//Events//EN", "CALSCALE:GREGORIAN",
             "BEGIN:VEVENT", f"UID:{ev['uid']}@{config.BRAND_NAME.lower()}",
             f"DTSTAMP:{datetime.utcnow().strftime(fmt)}", f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
             f"SUMMARY:{_ics_text(ev['name'])}", f"LOCATION:{_ics_text(loc)}", f"URL:{events.public_url(ev)}",
             f"DESCRIPTION:{_ics_text('Details and RSVP: ' + events.public_url(ev))}", "END:VEVENT", "END:VCALENDAR"]
    r = Response("\r\n".join(lines) + "\r\n", content_type="text/calendar; charset=utf-8")
    r.header("Content-Disposition", f'attachment; filename="{ev["slug"]}.ics"')
    return r


# --- previews --------------------------------------------------------------------------------------
@router.get("/events/<slug:slug>/draft/<token>")
def draft_preview(req, slug, token):
    """Read-only draft the organiser shares with family before paying. RSVPs are switched off."""
    ev = events.by_slug(slug)
    if ev is None or ev["status"] in ("suspended", "archived") or not events.draft_token_ok(ev, token):
        raise HTTPError(404)
    r = Response(R.render(ev, "preview", None, req, notice="Shared draft from " + (ev["hosts"] or "the hosts")))
    r.header("Cache-Control", "no-store")
    r.header("X-Robots-Tag", "noindex, nofollow")
    r.set_cookie(events.DRAFT_COOKIE, f"{ev['id']}.{token}", max_age=3 * 3600, path="/media/")
    return r



@router.get("/templates/<slug:slug>/preview")
def template_preview(req, slug):
    t = catalog.template(slug)
    if t is None or not t["active"]:
        raise HTTPError(404)
    groups = db.loads(t["groups"], [])
    group = req.arg("group") if req.arg("group") in ("weddings", "baby", "parties", "other") else (groups[0] if groups else "weddings")
    r = Response(R.render(demo_event(slug, group), "demo", None, req))
    r.header("Cache-Control", "no-cache")
    return r


@router.get("/dashboard/events/<uid>/preview")
def organiser_preview(req, uid):
    row = auth.event_for(req, uid)
    ev = events.parse(row)
    gtoken = req.arg("guest")
    guest = db.one("SELECT * FROM guests WHERE token = ? AND event_id = ?", (gtoken, ev["id"])) if gtoken else None
    r = Response(R.render(ev, "preview", guest, req))
    r.header("Cache-Control", "no-store")
    return r
