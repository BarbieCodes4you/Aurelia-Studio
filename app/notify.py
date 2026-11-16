"""Common email variables and organiser/guest notification helpers."""
from __future__ import annotations

from typing import Optional

from . import catalog, config, db, events
from .services import email as mail
from .views.forms import fmt_date, fmt_time
from .web import esc


def event_vars(ev) -> dict:
    base = f"{config.BASE_URL}/dashboard/events/{ev['uid']}"
    venue = ev.get("venue") or {}
    gs = ev.get("guest_settings") or {}
    days = None
    try:
        from .views.forms import days_until
        days = days_until(ev.get("event_date"))
    except Exception:
        pass
    if days is None:
        days_text = "date to be confirmed"
    elif days > 1:
        days_text = f"{days} days to go"
    elif days == 1:
        days_text = "tomorrow"
    elif days == 0:
        days_text = "today"
    else:
        days_text = "the event has passed"
    return {
        "event_name": ev["name"], "hosts": events.title(ev),
        "event_date": fmt_date(ev.get("event_date")) or "date to be confirmed",
        "start_time": fmt_time(ev.get("start_time")) or "time to be confirmed",
        "venue_name": venue.get("name", ""), "venue_address": venue.get("address", ""),
        "public_url": events.public_url(ev), "dashboard_url": base, "rsvp_url": base + "/rsvps",
        "share_url": base + "/share", "reports_url": base + "/reports", "seating_url": base + "/seating",
        "comms_url": base + "/communications", "remind_url": base + "/communications?template=guest_reminder",
        "deadline": fmt_date(gs.get("rsvp_deadline")) or "the date on the invitation",
        "hosting_until": fmt_date(ev.get("hosting_until")) or "the end of your hosting period",
        "days_to_go": days_text,
    }


def guest_vars(ev, g) -> dict:
    return {"guest_first": g["first_name"], "guest_name": events.guest_name(g),
            "invite_url": events.invite_url(ev, g),
            "unsubscribe_url": f"{config.BASE_URL}/events/{ev['slug']}/u/{g['token']}"}


def can_email_guest(g) -> bool:
    return bool(g["email"]) and bool(g["email_consent"]) and not g["unsubscribed_at"]


def organiser_recipients(ev) -> list:
    owner = db.one("SELECT * FROM users WHERE id = ?", (ev["owner_id"],))
    out = [owner] if owner else []
    if catalog.has_feature(ev, "co_admins"):
        out += list(db.q("""SELECT u.* FROM event_admins a JOIN users u ON u.id = a.user_id
                            WHERE a.event_id = ?""", (ev["id"],)))
    return out


def organiser(ev, key: str, extra: Optional[dict] = None, attachments: Optional[list] = None,
              owner_only: bool = False) -> list:
    results = []
    recipients = organiser_recipients(ev)
    if owner_only:
        recipients = recipients[:1]
    for user in recipients:
        v = {**event_vars(ev), "first_name": mail.first_name(user["name"]), **(extra or {})}
        results.append(mail.send(user["email"], key, v, event_id=ev["id"], user_id=user["id"],
                                 attachments=attachments))
    return results


def summary_table_html(stats: dict) -> str:
    rows = [("Invited", stats["invited"]), ("Attending", stats["attending"]), ("Declined", stats["declined"]),
            ("Still to reply", stats["pending"]), ("Plus-ones", stats["plus_ones"]), ("Children", stats["children"]),
            ("Total headcount", stats["headcount"])]
    cells = "".join(
        f"<tr><td style='padding:8px 0;border-bottom:1px solid #EEE;color:#625D5E'>{esc(k)}</td>"
        f"<td style='padding:8px 0;border-bottom:1px solid #EEE;text-align:right;font-weight:600'>{v}</td></tr>"
        for k, v in rows)
    return f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='margin:0 0 18px'>{cells}</table>"


def rsvp_details_html(ev, g) -> str:
    parts = []
    if g["status"] == "attending":
        if g["plus_ones"]:
            parts.append(("Plus-ones", f"{g['plus_ones']} {('(' + g['plus_one_names'] + ')') if g['plus_one_names'] else ''}"))
        if g["children"]:
            parts.append(("Children", g["children"]))
        if g["meal_item_id"]:
            meal = db.one("SELECT name FROM menu_items WHERE id = ?", (g["meal_item_id"],))
            if meal:
                parts.append(("Meal", meal["name"]))
        if g["dietary"]:
            parts.append(("Dietary", g["dietary"]))
        if g["allergies"]:
            parts.append(("Allergies", g["allergies"]))
    if g["special_requests"]:
        parts.append(("Note", g["special_requests"]))
    if not parts:
        return ""
    cells = "".join(f"<tr><td style='padding:6px 12px 6px 0;color:#625D5E'>{esc(k)}</td><td style='padding:6px 0'>{esc(v)}</td></tr>"
                    for k, v in parts)
    return f"<table role='presentation' cellpadding='0' cellspacing='0' style='margin:0 0 18px'>{cells}</table>"


def publish(ev, actor_id: Optional[int] = None, send_emails: bool = True) -> tuple[bool, str]:
    """Make the event website public. Requires a verified payment and an unsuspended event."""
    ev = events.by_id(ev["id"])
    if not ev["paid_package"]:
        return False, "Publishing needs a confirmed payment."
    if ev["status"] == "suspended":
        return False, "This event is suspended. Contact support."
    first_time = not ev["published_at"]
    fields = {"status": "published"}
    if first_time:
        fields["published_at"] = db.now()
    if not ev["hosting_until"]:
        months = catalog.limit(ev, "hosting_months", 6)
        fields["hosting_until"] = events.hosting_end(ev, months)
    events.touch(ev["id"], **fields)
    db.insert("audit_log", {"actor_id": actor_id, "action": "event.publish", "target": ev["uid"], "meta": "{}",
                            "created_at": db.now()})
    if send_emails and first_time:
        ev = events.by_id(ev["id"])
        organiser(ev, "website_published", owner_only=True)
        organiser(ev, "event_link", owner_only=True)
        organiser(ev, "setup_instructions", owner_only=True)
    return True, "Your event website is live."


def unpublish(ev, actor_id: Optional[int] = None) -> None:
    events.touch(ev["id"], status="unpublished")
    db.insert("audit_log", {"actor_id": actor_id, "action": "event.unpublish", "target": ev["uid"], "meta": "{}",
                            "created_at": db.now()})
