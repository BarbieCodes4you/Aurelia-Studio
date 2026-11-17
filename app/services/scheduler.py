"""Background jobs: RSVP summaries, reminders, post-event reports, hosting expiry, clean-up.

`loop()` runs in a daemon thread started by run.py. `run_once(today)` does one pass and is
safe to repeat: every email is guarded by a sent_markers row (event_id, marker), so a job that
already ran for a period, guest or date never sends twice. Demo events never get emails and
suspended events are skipped entirely.
"""
from __future__ import annotations

import sqlite3
import sys
import time
import traceback
from datetime import date, timedelta
from typing import Optional

from .. import catalog, config, db, events, notify
from . import email as mail


def mark(event_id: int, marker: str) -> bool:
    """Claim a marker. True the first time (go ahead and send), False if already claimed."""
    try:
        cur = db.connect().execute(
            "INSERT OR IGNORE INTO sent_markers (event_id, marker, created_at) VALUES (?, ?, ?)",
            (event_id, marker, db.now()))
        return cur.rowcount == 1
    except sqlite3.Error:
        return False


def _date(value) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _email_events() -> list:
    rows = db.q("SELECT * FROM events WHERE is_demo = 0 AND status != 'suspended' AND paid_package IS NOT NULL")
    return [events.parse(r) for r in rows]


def _summaries(ev, today: date) -> int:
    prefs = ev.get("report_prefs") or {}
    freq = prefs.get("summary", "none")
    event_day = _date(ev.get("event_date"))
    if not events.is_live(ev) or freq not in ("daily", "weekly") or (event_day and event_day < today):
        return 0
    if freq == "daily":
        marker, since = f"summary-d-{today.isoformat()}", today - timedelta(days=1)
    else:
        if today.weekday() != 0:
            return 0
        y, w, _ = today.isocalendar()
        marker, since = f"summary-w-{y}-{w:02d}", today - timedelta(days=7)
    if not mark(ev["id"], marker):
        return 0
    st = events.stats(ev["id"])
    new_count = db.val("SELECT COUNT(*) FROM rsvp_responses WHERE event_id = ? AND created_at >= ?",
                       (ev["id"], since.isoformat()), 0)
    notify.organiser(ev, "rsvp_summary", {"summary_table": notify.summary_table_html(st),
                                          "completion": st["completion"], "new_count": new_count})
    return 1


def _outstanding(ev, today: date) -> int:
    deadline = _date((ev.get("guest_settings") or {}).get("rsvp_deadline"))
    if not deadline or not events.is_live(ev):
        return 0
    days = (deadline - today).days
    if days not in (7, 2):
        return 0
    st = events.stats(ev["id"])
    if st["pending"] <= 0 or not mark(ev["id"], f"outstanding-{days}-{deadline.isoformat()}"):
        return 0
    notify.organiser(ev, "outstanding_reminder", {"pending": st["pending"]})
    return 1


def _auto_guest_reminders(ev, today: date) -> int:
    prefs = ev.get("report_prefs") or {}
    if not prefs.get("auto_reminders") or not events.is_live(ev) or not catalog.has_feature(ev, "reminders", public=True):
        return 0
    deadline = _date((ev.get("guest_settings") or {}).get("rsvp_deadline"))
    if not deadline or not (0 <= (deadline - today).days <= 5):
        return 0
    used, allowed = events.email_quota(ev)
    sent = 0
    base = notify.event_vars(ev)
    for g in db.q("SELECT * FROM guests WHERE event_id = ? AND status = 'pending' ORDER BY id", (ev["id"],)):
        if used >= allowed:
            break
        if not notify.can_email_guest(g):
            continue
        if not mark(ev["id"], f"auto-remind-{g['id']}"):
            continue
        result = mail.send(g["email"], "guest_reminder", {**base, **notify.guest_vars(ev, g)},
                           event_id=ev["id"], guest_id=g["id"], batch_id=f"auto-{today.isoformat()}")
        if result["status"] == "sent":
            used += 1
            sent += 1
    return sent


def _event_reminders(ev, today: date) -> int:
    event_day = _date(ev.get("event_date"))
    if not event_day:
        return 0
    days = (event_day - today).days
    if days not in (7, 1) or not mark(ev["id"], f"event-reminder-{days}-{event_day.isoformat()}"):
        return 0
    text = "Tomorrow" if days == 1 else f"{days} days to go"
    lower = "tomorrow" if days == 1 else f"in {days} days"
    notify.organiser(ev, "event_reminder", {"days_text": text, "days_text_lower": lower})
    return 1


def _next_steps(ev, today: date) -> int:
    """From the day after the website goes live (for a week): what's left to do, if anything. The same list
    the dashboard shows, so a client who has already shared their link and seen replies gets no email."""
    published = _date(ev.get("published_at"))
    if not events.is_live(ev) or not published or not (1 <= (today - published).days <= 7):
        return 0
    from ..views.dashboard import next_steps
    steps = [(t, w, config.BASE_URL + href, link) for t, w, href, link in next_steps(ev)[:3]]
    if not steps or not mark(ev["id"], "next-steps"):
        return 0
    notify.organiser(ev, "setup_instructions", {"steps": notify.steps_html(steps)}, owner_only=True)
    return 1


def _post_event(ev, today: date) -> int:
    event_day = _date(ev.get("event_date"))
    if not event_day or not (1 <= (today - event_day).days <= 3):
        return 0
    if not mark(ev["id"], "post-event"):
        return 0
    attachments = []
    try:
        from . import reports  # built by the organiser-dashboard module
        attachments = list(reports.final_attachments(ev) or [])
    except ImportError:
        attachments = []
    except Exception:  # a broken report must not stop the email
        traceback.print_exc(file=sys.stderr)
        attachments = []
    st = events.stats(ev["id"])
    notify.organiser(ev, "post_event", {"summary_table": notify.summary_table_html(st)}, attachments=attachments)
    return 1


def _expire_hosting(today: date) -> int:
    rows = db.q("SELECT id, uid FROM events WHERE status = 'published' AND hosting_until IS NOT NULL AND hosting_until < ?",
                (today.isoformat(),))
    for r in rows:
        events.touch(r["id"], status="unpublished")
        db.insert("audit_log", {"actor_id": None, "action": "event.hosting_expired", "target": r["uid"], "meta": "{}",
                                "created_at": db.now()})
    return len(rows)


def _prune() -> int:
    now = db.now()
    c = db.connect()
    n = c.execute("DELETE FROM sessions WHERE expires_at < ?", (now,)).rowcount
    n += c.execute("DELETE FROM user_tokens WHERE expires_at < ? OR used_at IS NOT NULL", (now,)).rowcount
    return n


JOBS = [("next_steps", _next_steps), ("summaries", _summaries), ("outstanding", _outstanding), ("guest_reminders", _auto_guest_reminders),
        ("event_reminders", _event_reminders), ("post_event", _post_event)]


def run_once(today: Optional[date] = None) -> dict:
    today = today or date.today()
    counts = {name: 0 for name, _ in JOBS}
    for ev in _email_events():
        for name, job in JOBS:
            try:
                counts[name] += job(ev, today)
            except Exception:
                print(f"[scheduler] {name} failed for event {ev['uid']}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
    counts["hosting_expired"] = _expire_hosting(today)
    counts["pruned"] = _prune()
    return counts


def loop() -> None:
    while True:
        try:
            counts = run_once()
            if any(counts.values()) and config.DEBUG:
                print(f"[scheduler] {counts}", file=sys.stderr)
        except Exception:
            traceback.print_exc(file=sys.stderr)
        time.sleep(max(30, config.SCHEDULER_INTERVAL_SECONDS))
