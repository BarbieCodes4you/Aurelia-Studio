"""Organiser dashboard: event list, event overview, sharing (WhatsApp, QR), reports and settings."""
from __future__ import annotations

import json
from urllib.parse import quote

from .. import auth, catalog, config, db, events, notify
from ..icons import i
from ..services import qr, reports
from ..services.storage import storage
from ..web import HTTPError, Response, download, esc, redirect, router
from . import forms
from .forms import Form, csrf
from .manage import base, go, guest_whatsapp, has, load, status_pill, wa_digits
from .shell import account_page, locked_panel, organiser_page, page_head


# =============================================================================================
# All events
# =============================================================================================
@router.get("/dashboard")
def dashboard_home(req):
    user = auth.require_user(req)
    rows = db.q("""SELECT DISTINCT e.* FROM events e LEFT JOIN event_admins a ON a.event_id = e.id
                   WHERE (e.owner_id = ? OR a.user_id = ?) AND e.status != 'archived'
                   ORDER BY CASE e.status WHEN 'draft' THEN 0 ELSE 1 END, e.updated_at DESC""", (user["id"], user["id"]))
    first = (user["name"] or "").split(" ")[0]
    head = page_head(f"Welcome back, {first}" if rows else f"Welcome, {first}",
                     "Your events, drafts and RSVPs in one place.",
                     f'<a class="btn btn--primary" href="/create">{i("plus")}Create an event</a>')
    if not user["email_verified_at"]:
        head += (f'<div class="notice notice--warn" style="margin-bottom:18px">{i("mail")}<div>Please confirm your email address '
                 f'so RSVP updates and reports reach you. <a class="text-link" href="/account">Resend the email</a></div></div>')
    if not rows:
        body = head + (f'<div class="empty"><span class="icon-tile icon-tile--soft">{i("sparkle")}</span>'
                       f'<h2 style="font-size:1.375rem">Create your first event</h2>'
                       f'<p>Choose a category and template, add your details, and get one link for invitations, RSVPs, '
                       f'menus, seating and more. Your progress saves as you go.</p>'
                       f'<a class="btn btn--primary btn--lg" href="/create">Create your event</a></div>')
        return account_page(req, "My events", body, "/dashboard")
    cards = []
    for e in rows:
        ev = events.parse(e)
        s = events.stats(ev["id"])
        role = "" if ev["owner_id"] == user["id"] else '<span class="tag">Co-admin</span>'
        days = forms.days_until(ev.get("event_date"))
        when = forms.fmt_date(ev.get("event_date"), long=False) or "Date not set"
        if days is not None and days >= 0:
            when += f" · {days} day{'s' if days != 1 else ''} to go" if days else " · today"
        if ev["status"] == "draft":
            done = len(ev.get("wizard_done") or [])
            action = (f'<a class="btn btn--primary btn--sm" href="{base(ev)}/setup/{ev["wizard_step"] or 1}">Continue setup</a>'
                      f'<span class="small muted">{done} of 10 steps done</span>')
            progress = f'<div class="progress"><span style="width:{done * 10}%"></span></div>'
        else:
            action = (f'<a class="btn btn--secondary btn--sm" href="{base(ev)}">Open dashboard</a>'
                      f'<a class="arrow-link" href="{events.public_path(ev)}" target="_blank" rel="noopener"><span>View website</span>{i("external")}</a>')
            progress = (f'<div class="bar-list__row"><span class="small muted">{s["attending"]} attending · {s["pending"]} to reply</span>'
                        f'<b class="mono small">{s["completion"]}%</b><div class="progress"><span style="width:{s["completion"]}%"></span></div></div>')
        cards.append(f"""<article class="box event-card"><div class="event-card__top"><div>
<h2 style="font-size:1.25rem"><a href="{base(ev)}" style="text-decoration:none">{esc(ev["name"])}</a></h2>
<div class="event-card__meta"><span>{esc(catalog.category_name(ev["category"]))}</span><span>{esc(when)}</span></div></div>
<div class="cluster">{role}{status_pill_event(ev)}</div></div>{progress}<div class="row">{action}</div></article>""")
    body = head + f'<div class="grid grid--2">{"".join(cards)}</div>'
    return account_page(req, "My events", body, "/dashboard")


def status_pill_event(ev) -> str:
    label = events.STATUS_LABELS.get(ev["status"], ev["status"])
    if ev["status"] == "draft" and not ev["paid_package"]:
        label = "Draft"
    return f'<span class="pill pill--{esc(ev["status"])}">{esc(label)}</span>'


# =============================================================================================
# Event overview
# =============================================================================================
@router.get("/dashboard/events/<uid>")
def overview(req, uid):
    ev = load(req, uid)
    s = events.stats(ev["id"])
    days = forms.days_until(ev.get("event_date"))
    venue = ev.get("venue") or {}
    paid = catalog.package(ev["paid_package"])
    live = events.is_live(ev)

    if not paid:
        banner = (f'<div class="cta-panel" style="margin-bottom:22px"><div><h2 style="font-size:1.6rem">Ready to share it?</h2>'
                  f'<p>Your event is saved as a private draft. Choose a package and pay securely to publish your website and start collecting RSVPs.</p></div>'
                  f'<div class="btn-row"><a class="btn btn--primary btn--lg" href="{base(ev)}/setup/8">Choose a package</a>'
                  f'<a class="btn btn--secondary" href="{base(ev)}/setup/8">Preview</a></div></div>')
    elif ev["status"] == "suspended":
        banner = (f'<div class="notice notice--error" style="margin-bottom:22px">{i("alert")}<div><b>This event is suspended.</b> '
                  f'{esc(ev.get("suspended_reason") or "")} Guests can’t open the website. <a class="text-link" href="/contact">Contact support</a></div></div>')
    elif not live:
        banner = (f'<div class="notice notice--warn" style="margin-bottom:22px">{i("info")}<div>Your website is unpublished, so guests can’t open it. '
                  f'<a class="text-link" href="{base(ev)}/settings">Publish it again</a></div></div>')
    else:
        banner = ""

    if days is None:
        countdown = "Set your date"
    elif days > 0:
        countdown = f"{days} day{'s' if days != 1 else ''} to go"
    elif days == 0:
        countdown = "It’s today"
    else:
        countdown = f"{-days} days ago"

    kpis = f"""<div class="kpis" style="--n:5;margin-bottom:22px">
<div class="kpi kpi--accent"><span>Event date</span><b style="font-size:1.25rem">{esc(forms.fmt_date(ev.get("event_date"), long=False) or "Not set")}</b><small>{esc(countdown)}</small></div>
<div class="kpi"><span>Invited</span><b>{s["invited"]}</b><small>{s["headcount"]} people attending</small></div>
<div class="kpi"><span>Confirmed</span><b>{s["attending"]}</b><small>+{s["plus_ones"]} plus-ones · {s["children"]} children</small></div>
<div class="kpi"><span>Declined</span><b>{s["declined"]}</b><small>{s["pending"]} still pending</small></div>
<div class="kpi"><span>RSVP completion</span><b>{s["completion"]}%</b><div class="progress" style="margin-top:10px"><span style="width:{s["completion"]}%"></span></div></div></div>"""

    tables = events.tables(ev["id"])
    next_html = _next_steps(ev, s, paid, live, days, tables)
    checklist = [
        ("Event details and date", bool(ev.get("event_date") and ev.get("name")), f"{base(ev)}/setup/1"),
        ("Venue and directions", bool(venue.get("name")), f"{base(ev)}/setup/1"),
        ("Design chosen", 2 in (ev.get("wizard_done") or []), f"{base(ev)}/setup/2"),
        ("Package paid", bool(paid), f"{base(ev)}/setup/8"),
        ("Website published", live, f"{base(ev)}/settings"),
        ("Guests added", s["invited"] > 0, f"{base(ev)}/guests"),
    ]
    if has(ev, "seating"):
        checklist.append(("Everyone seated", bool(tables) and s["attending"] > 0 and s["unseated_parties"] == 0, f"{base(ev)}/seating"))
    if has(ev, "menu"):
        checklist.append(("Menu added", bool(events.menus(ev["id"])), f"{base(ev)}/menu"))
    done = sum(1 for _, ok, _ in checklist if ok)
    check_html = "".join(
        f'<li><a href="{href}" class="row" style="text-decoration:none;gap:10px;flex-wrap:nowrap">'
        f'<span class="icon-tile{" icon-tile--soft" if ok else ""}" style="width:28px;height:28px;border-radius:50%">{i("check") if ok else ""}</span>'
        f'<span{" class=muted" if ok else ""}>{esc(label)}</span></a>{"" if ok else i("arrow")}</li>' for label, ok, href in checklist)

    recent = db.q("""SELECT r.*, g.first_name, g.last_name, g.status FROM rsvp_responses r LEFT JOIN guests g ON g.id = r.guest_id
                     WHERE r.event_id = ? ORDER BY r.created_at DESC LIMIT 8""", (ev["id"],))
    recent_html = "".join(
        f'<li><span><b>{esc((r["first_name"] or "Removed guest") + " " + (r["last_name"] or ""))}</b><br>'
        f'<span class="small muted">{esc(forms.fmt_dt(r["created_at"]))}</span></span>{status_pill(r["status"]) if r["status"] else ""}</li>' for r in recent)
    recent_box = (f'<ul class="list-plain list-rows">{recent_html}</ul>' if recent else
                  '<p class="small muted">Responses appear here as soon as guests reply.</p>')

    link = events.public_url(ev)
    wa = "https://wa.me/?text=" + quote(_invite_message(ev))
    share = f"""<div class="box"><div class="box__head"><h2>Your one link</h2>{'<span class="pill pill--ok">Live</span>' if live else '<span class="pill pill--draft">Not live yet</span>'}</div>
<p class="mono small" style="overflow-wrap:anywhere">{esc(link)}</p><div class="row" style="margin-top:12px">
<button class="btn btn--secondary btn--sm" type="button" data-copy="{esc(link)}" data-copied="Link copied">{i("copy")}Copy</button>
<a class="btn btn--secondary btn--sm" href="{esc(wa)}" target="_blank" rel="noopener">{i("chat")}WhatsApp</a>
<a class="btn btn--ghost btn--sm" href="{base(ev)}/share">{i("qr")}QR code</a></div></div>"""

    actions = (f'<a class="btn btn--secondary btn--sm" href="{base(ev)}/setup/1">{i("edit")}Edit details</a>'
               f'<a class="btn btn--secondary btn--sm" href="{events.public_path(ev)}" target="_blank" rel="noopener">{i("eye")}View website</a>')
    head = page_head(ev["name"], esc(" · ".join(x for x in (catalog.category_name(ev["category"]), venue.get("name", "")) if x)), actions)
    booking = _booking_box(ev, paid, live)
    body = head + banner + next_html + kpis + f"""<div class="cols cols--2"><div class="stack">{booking}<div class="box"><div class="box__head"><h2>Recent RSVPs</h2>
<a class="arrow-link" href="{base(ev)}/rsvps"><span>All responses</span>{i("arrow")}</a></div>{recent_box}</div>{share}</div>
<div class="box"><div class="box__head"><h2>Checklist</h2><span class="small muted">{done} of {len(checklist)}</span></div>
<div class="progress" style="margin-bottom:12px"><span style="width:{round(100 * done / len(checklist))}%"></span></div>
<ul class="list-plain list-rows">{check_html}</ul></div></div>"""
    return organiser_page(req, ev, "Overview", body, "")


def _booking_box(ev, paid, live) -> str:
    """The client's booking at a glance: package, payment, receipt, website link and how long it stays online."""
    if not paid:
        return ""
    order = db.one("SELECT * FROM orders WHERE event_id = ? AND status = 'paid' ORDER BY paid_at DESC, id DESC LIMIT 1", (ev["id"],))
    rows = [("Package", esc(paid["name"]))]
    if order:
        rows.append(("Paid", f'{catalog.money(order["amount_cents"])} on {esc(forms.fmt_date((order["paid_at"] or "")[:10]))}'
                             f'{" (test payment)" if order["mode"] == "sandbox" else ""}'))
        rows.append(("Reference", f'<span class="mono">{esc(order["invoice_no"] or order["uid"])}</span> · '
                                  f'<a class="text-link" href="/dashboard/orders/{esc(order["uid"])}/receipt">Receipt</a>'))
    pill = '<span class="pill pill--ok">Live</span>' if live else '<span class="pill pill--draft">Not live</span>'
    rows.append(("Website", f'<a class="text-link" href="{esc(events.public_path(ev))}" target="_blank" rel="noopener">{esc(events.public_url(ev))}</a> {pill}'))
    if ev.get("hosting_until"):
        rows.append(("Online until", esc(forms.fmt_date(ev["hosting_until"]))))
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    return (f'<div class="box"><div class="box__head"><h2>Your booking</h2><a class="arrow-link" href="/dashboard/billing"><span>Billing</span>{i("arrow")}</a></div>'
            f'<dl class="dl">{dl}</dl></div>')


def _next_steps(ev, s, paid, live, days, tables) -> str:
    """The next three things to do, in order, so the organiser never has to work out what's next."""
    venue = ev.get("venue") or {}
    not_sent = db.val("SELECT COUNT(*) FROM guests WHERE event_id = ? AND invited_at IS NULL AND status != 'declined'", (ev["id"],), 0)
    steps = []   # (title, why, link, button)
    if not (ev.get("hosts") and ev.get("event_date")):
        steps.append(("Add your names and date", "Guests see these first.", f"{base(ev)}/setup/1", "Add details"))
    if not (venue.get("name") and venue.get("address")):
        steps.append(("Add your venue", "So guests get directions and a map.", f"{base(ev)}/setup/1", "Add venue"))
    if not paid:
        pass                                    # the "Ready to share it?" banner above already asks for this
    elif not live and ev["status"] != "suspended":
        steps.append(("Publish your website", "It's paid for. Publish it so guests can open your link.", f"{base(ev)}/settings", "Publish"))
    if live and has(ev, "guest_management") and s["invited"] == 0:
        steps.append(("Add your guest list", "Paste names or import a spreadsheet. Each guest gets a personal RSVP link.", f"{base(ev)}/guests/import", "Add guests"))
    if live and has(ev, "personal_invites") and not_sent:
        steps.append(("Send your invitations", f"{not_sent} guest{'s' if not_sent != 1 else ''} haven't been sent their invitation yet. Send them on WhatsApp, one tap each.",
                      f"{base(ev)}/share/whatsapp", "Start sending"))
    elif live and not has(ev, "personal_invites") and s["invited"] == 0:
        steps.append(("Share your link", "Send it on WhatsApp, by email or as a QR code. Guests reply on the website.", f"{base(ev)}/share", "Share"))
    if live and s["pending"] and s["invited"] - not_sent > 0 and (days is None or days >= 0):
        steps.append(("Remind guests who haven't replied", f"{s['pending']} still to reply.", f"{base(ev)}/share/whatsapp?mode=remind", "Send reminders"))
    if has(ev, "seating") and s["attending"] and s["unseated_parties"]:
        steps.append(("Seat your guests", f"{s['unseated_parties']} confirmed part{'y' if s['unseated_parties'] == 1 else 'ies'} without a table. Seat everyone automatically, then fine-tune.",
                      f"{base(ev)}/seating", "Open seating"))
    if days is not None and days < 0 and has(ev, "gallery") and not db.val("SELECT COUNT(*) FROM uploads WHERE event_id = ? AND kind = 'gallery' AND created_at >= ?", (ev["id"], ev["event_date"] or ""), 0):
        steps.append(("Share photos from the day", "Add your favourites to the gallery. Guests see them on the link they already have.", f"{base(ev)}/setup/7", "Add photos"))
    if days is not None and days < 0 and has(ev, "reports"):
        steps.append(("Download your final report", "Attendance, meals and seating in one file to keep.", f"{base(ev)}/reports", "Reports"))
    if not steps:
        return ""
    cards = "".join(f'<a class="next-step" href="{href}"><span class="mono tiny">NEXT {n}</span><b>{esc(t)}</b><span class="small muted">{esc(w)}</span>'
                    f'<span class="arrow-link small"><span>{esc(btn)}</span>{i("arrow")}</span></a>' for n, (t, w, href, btn) in enumerate(steps[:3], 1))
    return f'<div class="next-steps" style="margin-bottom:22px">{cards}</div>'


# =============================================================================================
# Share
# =============================================================================================
def _invite_message(ev) -> str:
    date = forms.fmt_date(ev.get("event_date"))
    when = f" on {date}" if date else ""
    return (f"You're invited to {ev['name']}{when}. Everything you need, from directions to RSVP, "
            f"is on our event page: {events.public_url(ev)}")


def _reminder_message(ev, g) -> str:
    gs = ev.get("guest_settings") or {}
    by = f" by {forms.fmt_date(gs['rsvp_deadline'], long=False)}" if gs.get("rsvp_deadline") else ""
    return (f"Hi {g['first_name']}, a quick reminder to let us know{by} if you can make it to {ev['name']}. "
            f"It takes a minute: {events.invite_url(ev, g)}")


def _broadcast_box(ev, with_queue: bool = True) -> str:
    msg = _invite_message(ev)
    return f"""<div class="box"><div class="box__head"><h2>Send to many people at once</h2></div>
<p class="small muted">Use a WhatsApp broadcast list: everyone gets the message privately, as if you'd sent it to them alone.</p>
<ol class="small" style="margin:10px 0 12px;padding-left:20px;display:grid;gap:6px"><li>In WhatsApp, open <b>Broadcast lists</b> (Android: ⋮ › New broadcast; iPhone: Chats › Lists or Broadcast lists).</li>
<li>Add your guests, up to 256 per list.</li><li>Paste this message and send.</li></ol>
<textarea class="textarea" id="broadcast-msg" rows="4" readonly aria-label="Message for a broadcast list">{esc(msg)}</textarea>
<div class="row" style="margin-top:10px"><button class="btn btn--secondary btn--sm" type="button" data-copy-target="#broadcast-msg" data-copied="Message copied">{i("copy")}Copy message</button></div>
<p class="tiny muted" style="margin-top:10px">Only people who have your number saved in their phone receive broadcasts. For everyone else, {"send one by one, or " if with_queue else ""}post the message in a group chat.</p></div>"""


@router.route("/dashboard/events/<uid>/share/whatsapp", methods=("GET", "POST"))
def whatsapp_queue(req, uid):
    """Send personal invitations (or reminders) on WhatsApp one guest at a time: one tap to open
    WhatsApp with the message ready, one tap for the next guest. Nothing is sent automatically."""
    ev = load(req, uid)
    mode = "remind" if (req.arg("mode") or req.get("mode")) == "remind" else "invite"
    skip = [int(x) for x in (req.arg("skip") or req.get("skip") or "").split(",") if x.isdigit()][:500]
    title = "Remind guests on WhatsApp" if mode == "remind" else "Send invitations on WhatsApp"
    if not has(ev, "personal_invites"):
        body = page_head(title, "Personal links for each guest are part of Premium. You can still share your one link with everyone.") + _broadcast_box(ev, with_queue=False)
        return organiser_page(req, ev, title, body, "/share")
    today = db.now()[:10]
    if req.method == "POST":
        g = db.one("SELECT * FROM guests WHERE id = ? AND event_id = ?", (req.get("guest_id"), ev["id"]))
        if g and req.get("action") == "sent":
            if mode == "invite":
                db.run("UPDATE guests SET invited_at = COALESCE(invited_at, ?), updated_at = ? WHERE id = ?", (db.now(), db.now(), g["id"]))
            else:
                db.run("INSERT OR IGNORE INTO sent_markers (event_id, marker, created_at) VALUES (?, ?, ?)",
                       (ev["id"], f"wa-remind:{g['id']}:{today}", db.now()))
        elif g:
            skip.append(g["id"])
        q = {"mode": mode if mode == "remind" else "", "skip": ",".join(map(str, skip))}
        return redirect(f"{base(ev)}/share/whatsapp" + ("?" + "&".join(f"{k}={v}" for k, v in q.items() if v) if any(q.values()) else ""))
    if mode == "invite":
        todo = db.q("""SELECT * FROM guests WHERE event_id = ? AND invited_at IS NULL AND status != 'declined' AND phone != ''
                       ORDER BY is_vip DESC, last_name COLLATE NOCASE, first_name COLLATE NOCASE""", (ev["id"],))
        done = db.val("SELECT COUNT(*) FROM guests WHERE event_id = ? AND invited_at IS NOT NULL AND phone != ''", (ev["id"],), 0)
    else:
        todo = db.q("""SELECT g.* FROM guests g WHERE g.event_id = ? AND g.status = 'pending' AND g.phone != '' AND g.invited_at IS NOT NULL
                       AND NOT EXISTS (SELECT 1 FROM sent_markers m WHERE m.event_id = g.event_id AND m.marker = 'wa-remind:' || g.id || ':' || ?)
                       ORDER BY g.last_name COLLATE NOCASE, g.first_name COLLATE NOCASE""", (ev["id"], today))
        done = db.val("SELECT COUNT(*) FROM sent_markers WHERE event_id = ? AND marker LIKE ?", (ev["id"], f"wa-remind:%:{today}"), 0)
    queue = [g for g in todo if g["id"] not in skip and wa_digits(g["phone"])]
    skipped = [g for g in todo if g["id"] in skip]
    no_phone = db.val("SELECT COUNT(*) FROM guests WHERE event_id = ? AND phone = '' AND status != 'declined'", (ev["id"],), 0)
    total = done + len(queue) + len(skipped)
    tabs_html = (f'<nav class="tabs" aria-label="Section" style="margin-bottom:18px"><a href="{base(ev)}/share/whatsapp"{" aria-current=page" if mode == "invite" else ""}>Invitations</a>'
                 f'<a href="{base(ev)}/share/whatsapp?mode=remind"{" aria-current=page" if mode == "remind" else ""}>Reminders</a></nav>')
    if queue:
        g = queue[0]
        msg = guest_whatsapp(ev, g) if mode == "invite" else f"https://wa.me/{wa_digits(g['phone'])}?text={quote(_reminder_message(ev, g))}"
        text = (f"Hi {g['first_name']}, you're invited to {ev['name']}. Your personal invitation and RSVP link: {events.invite_url(ev, g)}"
                if mode == "invite" else _reminder_message(ev, g))
        form = lambda action, label, cls: (f'<form method="post">{csrf(req)}<input type="hidden" name="mode" value="{mode}"><input type="hidden" name="skip" value="{",".join(map(str, skip))}">'
                                           f'<input type="hidden" name="guest_id" value="{g["id"]}"><input type="hidden" name="action" value="{action}">'
                                           f'<button class="btn {cls}" type="submit"{" data-next-guest" if action == "sent" else ""}>{label}</button></form>')
        card = f"""<div class="box wa-queue"><div class="row row--between"><span class="mono small">{done + 1} of {total}</span><span class="small muted">{len(queue) - 1} after this one</span></div>
<div class="progress"><span style="width:{round(100 * done / total) if total else 0}%"></span></div>
<div><h2 style="font-size:1.375rem">{esc(events.guest_name(g))}{' <span class="pill pill--gold pill--plain">VIP</span>' if g["is_vip"] else ""}</h2><p class="mono small muted">{esc(g["phone"])}</p></div>
<div class="notice">{i("chat")}<span class="small" style="white-space:pre-wrap">{esc(text)}</span></div>
<div class="btn-row"><a class="btn btn--primary btn--lg" href="{esc(msg)}" target="_blank" rel="noopener" data-open-wa>{i("chat")}Open WhatsApp</a>
{form("sent", "Sent, next guest " + i("arrow", "i--arrow"), "btn--secondary btn--lg")}{form("skip", "Skip for now", "btn--ghost")}</div>
<p class="tiny muted">WhatsApp opens with the message ready. Press send there, come back and tap “Sent, next guest”.</p></div>"""
    else:
        msg_done = ("Everyone with a mobile number has their invitation." if mode == "invite" else "Everyone who hasn't replied has had a reminder today.")
        card = (f'<div class="box"><div class="empty"><span class="icon-tile icon-tile--soft">{i("check")}</span><h2 style="font-size:1.25rem">{msg_done}</h2>'
                + (f'<p>You skipped {len(skipped)}. <a class="text-link" href="{base(ev)}/share/whatsapp{"?mode=remind" if mode == "remind" else ""}">Go through them again</a>.</p>' if skipped else "")
                + f'<a class="btn btn--secondary" href="{base(ev)}/rsvps">See RSVPs</a></div></div>')
    extra = ""
    if no_phone:
        extra = (f'<div class="notice" style="margin-top:14px">{i("info")}<span>{no_phone} guest{"s have" if no_phone != 1 else " has"} no mobile number. '
                 f'<a class="text-link" href="{base(ev)}/guests">Add numbers</a> or <a class="text-link" href="{base(ev)}/communications">email them instead</a>.</span></div>')
    js = """<script>(function(){var a=document.querySelector('[data-open-wa]'),n=document.querySelector('[data-next-guest]');if(a&&n)a.addEventListener('click',function(){setTimeout(function(){n.classList.remove('btn--secondary');n.classList.add('btn--primary');n.focus();},400);});})();</script>"""
    intro = ("One guest at a time, each with their own RSVP link. Two taps per guest." if mode == "invite"
             else "Guests who were invited but haven't replied yet, each with their own RSVP link.")
    body = page_head(title, intro) + tabs_html + f'<div class="cols cols--2"><div>{card}{extra}</div>{_broadcast_box(ev)}</div>' + js
    return organiser_page(req, ev, title, body, "/share")


@router.get("/dashboard/events/<uid>/share")
def share(req, uid):
    ev = load(req, uid)
    link = events.public_url(ev)
    message = req.arg("message") or _invite_message(ev)
    wa = "https://wa.me/?text=" + quote(message)
    live = events.is_live(ev)
    note = "" if live else (f'<div class="notice notice--warn" style="margin-bottom:18px">{i("info")}<div>Your link is reserved, '
                            f'but guests will only see the website once it is paid for and published. '
                            f'<a class="text-link" href="{base(ev)}/setup/8">Publish now</a></div></div>')
    personal = (f'<div class="notice" style="margin-top:12px">{i("chat")}<div><span>Each guest also has a personal link that opens their own RSVP.</span>'
                f'<div style="margin-top:10px"><a class="btn btn--secondary btn--sm" href="{base(ev)}/share/whatsapp">Send personal invitations on WhatsApp</a></div></div></div>') if has(ev, "personal_invites") else ""
    sub_js = json.dumps("Invitation: " + ev["name"]).replace("<", "\\u003c")
    body = page_head("Share your event", "One link for everything. Paste it anywhere: WhatsApp, email, SMS or social media.") + note + f"""
<div class="cols cols--2"><div class="stack">
<div class="box"><div class="box__head"><h2>Event link</h2></div><div class="row" style="flex-wrap:nowrap">
<input class="input mono" id="share-link" value="{esc(link)}" readonly aria-label="Event link" style="font-size:.875rem">
<button class="btn btn--primary" type="button" data-copy-target="#share-link" data-copied="Link copied">{i("copy")}Copy</button></div>{personal}</div>
<div class="box"><div class="box__head"><h2>Invitation message</h2></div>
<textarea class="textarea" id="share-message" rows="5" aria-label="Invitation message" data-wa-source>{esc(message)}</textarea>
<div class="row" style="margin-top:12px"><a class="btn btn--primary" id="wa-link" href="{esc(wa)}" target="_blank" rel="noopener">{i("chat")}Share on WhatsApp</a>
<button class="btn btn--secondary" type="button" data-copy-target="#share-message" data-copied="Message copied">{i("copy")}Copy message</button>
<a class="btn btn--ghost" id="mail-link" href="mailto:?subject={quote("Invitation: " + ev["name"])}&amp;body={quote(message)}">{i("mail")}Email</a></div>
<p class="small muted" style="margin-top:12px">WhatsApp opens with your message ready; you choose the chats and press send. We don’t send WhatsApp messages automatically.</p></div></div>
<div class="box" style="text-align:center"><div class="box__head"><h2>QR code</h2></div>
<div style="max-width:260px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid var(--color-line)">{qr.svg(link, 260)}</div>
<p class="small muted" style="margin:12px auto;max-width:36ch">For printed invitations, welcome boards and table cards. Scanning opens your event website.</p>
<div class="row" style="justify-content:center"><a class="btn btn--secondary btn--sm" href="{base(ev)}/share/qr.png" download>{i("download")}PNG</a>
<a class="btn btn--secondary btn--sm" href="{base(ev)}/share/qr.svg" download>{i("download")}SVG</a></div></div></div>
<script>(function(){{var t=document.querySelector("[data-wa-source]"),a=document.getElementById("wa-link"),m=document.getElementById("mail-link");
var sub={sub_js};
t.addEventListener("input",function(){{a.href="https://wa.me/?text="+encodeURIComponent(t.value);m.href="mailto:?subject="+encodeURIComponent(sub)+"&body="+encodeURIComponent(t.value);}});}})();</script>"""
    return organiser_page(req, ev, "Share", body, "/share")


@router.get("/dashboard/events/<uid>/share/qr.svg")
def share_qr_svg(req, uid):
    ev = load(req, uid)
    return download(qr.svg(events.public_url(ev), 1024), f"{ev['slug']}-qr.svg", "image/svg+xml")


@router.get("/dashboard/events/<uid>/share/qr.png")
def share_qr_png(req, uid):
    ev = load(req, uid)
    return download(qr.png(events.public_url(ev), scale=16), f"{ev['slug']}-qr.png", "image/png")


# =============================================================================================
# Reports
# =============================================================================================
@router.get("/dashboard/events/<uid>/reports")
def reports_page(req, uid):
    ev = load(req, uid)
    if not has(ev, "basic_dashboard"):
        return organiser_page(req, ev, "Reports", page_head("Reports") + locked_panel(ev, "basic_dashboard", "Reports"), "/reports")
    can = has(ev, "reports")
    rows = []
    for kind, (title, desc) in reports.KINDS.items():
        links = (f'<a class="chip" href="{base(ev)}/reports/{kind}.pdf">{i("download")}PDF</a>'
                 f'<a class="chip" href="{base(ev)}/reports/{kind}.csv">{i("download")}CSV</a>') if can else f'<span class="tag">{i("lock")} Premium</span>'
        rows.append(f'<li><span><b>{esc(title)}</b><br><span class="small muted">{esc(desc)}</span></span><span class="row" style="flex-wrap:nowrap">{links}</span></li>')
    prefs = {"summary": "weekly", "new_rsvp": True, "auto_reminders": True, **(ev.get("report_prefs") or {})}
    summary_opts = [("none", "Don't send summaries"), ("daily", "Daily summary"), ("weekly", "Weekly summary (Mondays)")]
    final = ""
    if can:
        final = (f'<form method="post" action="{base(ev)}/communications/final-report">{csrf(req)}<input type="hidden" name="back" value="/reports">'
                 f'<button class="btn btn--primary btn--sm" type="submit">{i("mail")}Email me the final report</button></form>')
    upsell = "" if can else (f'<div class="notice" style="margin-bottom:16px">{i("lock")}<div>Downloadable reports are part of the Premium Experience. '
                             f'Your RSVP numbers stay visible on the dashboard. <a class="text-link" href="{base(ev)}/setup/8">Compare packages</a></div></div>')
    reminders_switch = forms.switch("auto_reminders", "Remind guests who haven't replied, 7 and 2 days before the RSVP deadline",
                                    bool(prefs.get("auto_reminders"))) if has(ev, "reminders") else \
        '<p class="small muted">Automatic guest reminders are part of the Premium Experience.</p>'
    body = page_head("Reports", "Download what your venue, caterer and planner need, or have it emailed to you.", final) + upsell + f"""
<div class="cols cols--2"><div class="box"><ul class="list-plain list-rows">{"".join(rows)}</ul></div>
<form class="box form" method="post" action="{base(ev)}/reports/prefs">{csrf(req)}<div class="box__head"><h2>Automatic emails</h2></div>
{forms.select("summary", "RSVP summaries to you", summary_opts, prefs.get("summary", "weekly"))}
{forms.switch("new_rsvp", "Email me every new RSVP", bool(prefs.get("new_rsvp")))}
{reminders_switch}
<p class="small muted">Event reminders reach you a week and a day before the event, and a post-event report follows the day after.</p>
<div class="row row--end"><button class="btn btn--secondary btn--sm" type="submit">Save preferences</button></div></form></div>"""
    return organiser_page(req, ev, "Reports", body, "/reports")


@router.get("/dashboard/events/<uid>/reports/<kind>.<fmt>")
def report_download(req, uid, kind, fmt):
    ev = load(req, uid)
    if kind not in reports.KINDS or fmt not in reports.FORMATS:
        raise HTTPError(404)
    if not has(ev, "reports"):
        raise HTTPError(403, "Downloadable reports are part of the Premium Experience.")
    name, data, ctype = reports.build(ev, kind, fmt, user_id=req.user["id"])
    return download(data, name, ctype)


@router.post("/dashboard/events/<uid>/reports/prefs")
def report_prefs(req, uid):
    ev = load(req, uid)
    f = Form(req)
    summary = f.choice("summary", ["none", "daily", "weekly"], "summary", default="weekly")
    prefs = dict(ev.get("report_prefs") or {})
    prefs.update({"summary": summary, "new_rsvp": f.flag("new_rsvp")})
    if has(ev, "reminders"):
        prefs["auto_reminders"] = f.flag("auto_reminders")
    events.save_json(ev["id"], "report_prefs", prefs)
    return go(req, ev, "/reports", "success", "Email preferences saved.")


# =============================================================================================
# Settings
# =============================================================================================
@router.get("/dashboard/events/<uid>/settings")
def settings(req, uid):
    ev = load(req, uid)
    vis = {**events.default_sections(), **(ev.get("sections") or {})}
    toggles = []
    for key, label, feature in events.SECTION_KEYS:
        allowed = feature is None or has(ev, feature)
        extra = {} if allowed else {"disabled": True}
        lock = "" if allowed else f' <span class="tag">{i("lock")} not in package</span>'
        toggles.append(f'<label class="switch"><input type="checkbox" name="sections" value="{key}"'
                       f'{" checked" if vis.get(key) and allowed else ""}{" disabled" if extra else ""}><span>{esc(label)}{lock}</span></label>')
    owner = ev["owner_id"] == req.user["id"]
    live = events.is_live(ev)
    if not ev["paid_package"]:
        pub = (f'<p class="small muted">Publishing needs a confirmed payment.</p>'
               f'<a class="btn btn--primary btn--sm" href="{base(ev)}/setup/8">Choose a package</a>')
    elif ev["status"] == "suspended":
        pub = '<p class="small">This event is suspended by the platform. <a class="text-link" href="/contact">Contact support</a>.</p>'
    elif live:
        pub = (f'<p class="small muted">Your website is live. Unpublishing hides it from guests straight away; you can publish it again any time.</p>'
               f'<form method="post" action="{base(ev)}/settings/unpublish" data-confirm="Hide the website from guests?">{csrf(req)}'
               f'<button class="btn btn--danger btn--sm" type="submit">Unpublish website</button></form>')
    else:
        pub = (f'<p class="small muted">Your website is hidden from guests.</p><form method="post" action="{base(ev)}/settings/publish">{csrf(req)}'
               f'<button class="btn btn--primary btn--sm" type="submit">Publish website</button></form>')
    hosting = f'<p class="small muted" style="margin-top:8px">Hosted until {esc(forms.fmt_date(ev["hosting_until"]))}.</p>' if ev.get("hosting_until") else ""

    admins_box = ""
    if has(ev, "co_admins"):
        admins = db.q("SELECT u.id, u.name, u.email FROM event_admins a JOIN users u ON u.id = a.user_id WHERE a.event_id = ?", (ev["id"],))
        limit = catalog.limit(ev, "admins", 1)
        lis = "".join(
            f'<li><span><b>{esc(a["name"])}</b><br><span class="small muted">{esc(a["email"])}</span></span>'
            + (f'<form method="post" action="{base(ev)}/settings/admins/{a["id"]}/remove" data-confirm="Remove {esc(a["name"])}?">{csrf(req)}'
               f'<button class="btn btn--ghost btn--sm" type="submit">Remove</button></form>' if owner else "") + "</li>" for a in admins)
        add = ""
        if owner and 1 + len(admins) < limit:
            add = (f'<form class="row" method="post" action="{base(ev)}/settings/admins" style="margin-top:12px;flex-wrap:nowrap">{csrf(req)}'
                   f'<input class="input input--sm" type="email" name="email" placeholder="their@email.com" required aria-label="Administrator email">'
                   f'<button class="btn btn--secondary btn--sm" type="submit">Add</button></form>'
                   f'<p class="small muted" style="margin-top:6px">They need an {esc(config.BRAND_NAME)} account with this email.</p>')
        admins_box = (f'<div class="box"><div class="box__head"><h2>Administrators</h2><span class="small muted">{1 + len(admins)} of {limit}</span></div>'
                      f'<ul class="list-plain list-rows"><li><span><b>Owner</b></span><span class="tag">Full access</span></li>{lis}</ul>{add}</div>')
    else:
        admins_box = (f'<div class="box"><div class="box__head"><h2>Administrators</h2></div><p class="small muted">Add co-hosts or planners with the Signature Experience.</p></div>')

    danger = ""
    if owner:
        danger = f"""<div class="box" style="border-color:color-mix(in srgb,var(--error) 30%,transparent)"><div class="box__head"><h2>Delete event</h2></div>
<p class="small muted">This permanently removes the website, guests, RSVPs, seating and uploads. Payments and receipts stay on record. It can’t be undone.</p>
<form class="form" method="post" action="{base(ev)}/settings/delete" style="margin-top:12px">{csrf(req)}
{forms.field("confirm_name", f"Type “{ev['name']}” to confirm", "", attrs={"autocomplete": "off"})}
<div><button class="btn btn--danger btn--sm" type="submit">Delete permanently</button></div></form></div>"""
    body = page_head("Settings", "Control what guests see and who can manage this event.") + f"""
<div class="cols cols--even"><div class="stack">
<form class="box form" method="post" action="{base(ev)}/settings/sections">{csrf(req)}<div class="box__head"><h2>Website sections</h2></div>
<p class="small muted">Switch off anything you don’t want public. Guest lists are never shown publicly.</p>
<div style="display:grid;gap:2px">{"".join(toggles)}</div><div class="row row--end"><button class="btn btn--secondary btn--sm" type="submit">Save sections</button></div></form>
<form class="box form" method="post" action="{base(ev)}/settings/slug">{csrf(req)}<div class="box__head"><h2>Website address</h2></div>
<div class="field"><label for="f-slug">{esc(config.BASE_URL)}/events/</label><input class="input mono" id="f-slug" name="slug" value="{esc(ev["slug"])}" maxlength="60" pattern="[a-z0-9-]+" required></div>
<p class="small muted">Lower-case letters, numbers and hyphens. Changing it breaks links you’ve already shared.{" Custom domains are available on request for Signature events." if has(ev, "custom_domain") else ""}</p>
<div class="row row--end"><button class="btn btn--secondary btn--sm" type="submit">Save address</button></div></form></div>
<div class="stack"><div class="box"><div class="box__head"><h2>Publishing</h2>{status_pill_event(ev)}</div>{pub}{hosting}</div>
<form class="box form" method="post" action="{base(ev)}/settings/rsvp">{csrf(req)}<div class="box__head"><h2>RSVPs</h2></div>
{forms.switch("rsvp_open", "Accept RSVPs", bool(ev["rsvp_open"]))}<p class="small muted">Close RSVPs once your numbers are final; guests will see a short note instead of the form.</p>
<div class="row row--end"><button class="btn btn--secondary btn--sm" type="submit">Save</button></div></form>
{admins_box}{danger}</div></div>"""
    return organiser_page(req, ev, "Settings", body, "/settings")


@router.post("/dashboard/events/<uid>/settings/sections")
def settings_sections(req, uid):
    ev = load(req, uid)
    chosen = set(req.getlist("sections"))
    current = {**events.default_sections(), **(ev.get("sections") or {})}
    for key, _, feature in events.SECTION_KEYS:
        if feature is None or has(ev, feature):
            current[key] = key in chosen
    events.save_json(ev["id"], "sections", current)
    return go(req, ev, "/settings", "success", "Website sections saved.")


@router.post("/dashboard/events/<uid>/settings/slug")
def settings_slug(req, uid):
    ev = load(req, uid)
    slug = req.get("slug").lower()
    if not forms.SLUG_RE.match(slug) or slug in events.RESERVED_SLUGS:
        return go(req, ev, "/settings", "error", "Use 3 to 60 lower-case letters, numbers and hyphens.")
    if slug == ev["slug"]:
        return go(req, ev, "/settings", "info", "That’s already your address.")
    if db.one("SELECT 1 FROM events WHERE slug = ? AND id != ?", (slug, ev["id"])):
        return go(req, ev, "/settings", "error", f"/events/{slug} is taken. Try adding your date or a word.")
    events.touch(ev["id"], slug=slug)
    auth.audit(req.user["id"], "event.slug", ev["uid"], old=ev["slug"], new=slug)
    return go(req, ev, "/settings", "success", f"Your website is now at /events/{slug}.")


@router.post("/dashboard/events/<uid>/settings/rsvp")
def settings_rsvp(req, uid):
    ev = load(req, uid)
    open_ = req.get("rsvp_open") == "1"
    events.touch(ev["id"], rsvp_open=1 if open_ else 0)
    return go(req, ev, "/settings", "success", "RSVPs are open." if open_ else "RSVPs are closed.")


@router.post("/dashboard/events/<uid>/settings/publish")
def settings_publish(req, uid):
    ev = load(req, uid)
    ok, msg = notify.publish(ev, req.user["id"])
    return go(req, ev, "/settings", "success" if ok else "error", msg)


@router.post("/dashboard/events/<uid>/settings/unpublish")
def settings_unpublish(req, uid):
    ev = load(req, uid)
    if ev["status"] != "published":
        return go(req, ev, "/settings", "info", "The website isn’t published.")
    notify.unpublish(ev, req.user["id"])
    return go(req, ev, "/settings", "success", "Your website is now hidden from guests.")


@router.post("/dashboard/events/<uid>/settings/admins")
def settings_admin_add(req, uid):
    ev = load(req, uid)
    if ev["owner_id"] != req.user["id"]:
        raise HTTPError(403, "Only the event owner can change administrators.")
    if not has(ev, "co_admins"):
        raise HTTPError(403, "Additional administrators are part of the Signature Experience.")
    email = req.get("email").lower()
    count = db.val("SELECT COUNT(*) FROM event_admins WHERE event_id = ?", (ev["id"],), 0)
    if 1 + count >= catalog.limit(ev, "admins", 1):
        return go(req, ev, "/settings", "error", "You’ve reached your package’s administrator limit.")
    user = db.one("SELECT * FROM users WHERE email = ?", (email,)) if forms.EMAIL_RE.match(email or "") else None
    if user is None:
        return go(req, ev, "/settings", "error", "No account uses that email yet. Ask them to register first, then add them.")
    if user["id"] == ev["owner_id"]:
        return go(req, ev, "/settings", "info", "That’s you, the owner.")
    db.run("INSERT OR IGNORE INTO event_admins (event_id, user_id, role, created_at) VALUES (?, ?, 'editor', ?)",
           (ev["id"], user["id"], db.now()))
    from ..services import email as mail
    mail.send(user["email"], "co_admin_invite", {**notify.event_vars(ev), "inviter": req.user["name"]},
              event_id=ev["id"], user_id=user["id"])
    auth.audit(req.user["id"], "event.admin_add", ev["uid"], user=user["email"])
    return go(req, ev, "/settings", "success", f"{user['name']} can now manage this event.")


@router.post("/dashboard/events/<uid>/settings/admins/<int:user_id>/remove")
def settings_admin_remove(req, uid, user_id):
    ev = load(req, uid)
    if ev["owner_id"] != req.user["id"]:
        raise HTTPError(403, "Only the event owner can change administrators.")
    db.run("DELETE FROM event_admins WHERE event_id = ? AND user_id = ?", (ev["id"], user_id))
    return go(req, ev, "/settings", "success", "Administrator removed.")


@router.post("/dashboard/events/<uid>/settings/delete")
def settings_delete(req, uid):
    ev = load(req, uid)
    if ev["owner_id"] != req.user["id"]:
        raise HTTPError(403, "Only the event owner can delete it.")
    if req.get("confirm_name").strip() != ev["name"].strip():
        return go(req, ev, "/settings", "error", "Type the event name exactly to delete it.")
    for up in events.uploads(ev["id"]):
        storage.delete(up["storage_key"])
    paid_orders = db.val("SELECT COUNT(*) FROM orders WHERE event_id = ? AND status = 'paid'", (ev["id"],), 0)
    if paid_orders:
        # Keep financial records: archive instead of hard-deleting, but wipe guest data (POPIA).
        with db.transaction():
            db.run("DELETE FROM guests WHERE event_id = ?", (ev["id"],))
            db.run("DELETE FROM seating_tables WHERE event_id = ?", (ev["id"],))
            db.run("DELETE FROM uploads WHERE event_id = ?", (ev["id"],))
            db.run("UPDATE events SET status = 'archived', updated_at = ? WHERE id = ?", (db.now(), ev["id"]))
    else:
        db.run("DELETE FROM events WHERE id = ?", (ev["id"],))
    auth.audit(req.user["id"], "event.delete", ev["uid"], name=ev["name"])
    req.flash("success", f"{ev['name']} was deleted.")
    return redirect("/dashboard")
