"""Navigation for the organiser dashboard and the admin dashboard.

Every dashboard page renders through `organiser_page()` or `admin_page()` so the sidebar and
locked-feature markers stay consistent across modules.
"""
from __future__ import annotations

from .. import catalog, events
from ..icons import i
from ..web import esc
from .layout import app_shell, side_link


# (path suffix, label, icon, feature needed)
EVENT_NAV = [
    ("", "Overview", "dashboard", None),
    ("/setup/1", "Event setup", "wand", None),
    ("/guests", "Guests", "users", "basic_dashboard"),
    ("/rsvps", "RSVPs", "check", "basic_dashboard"),
    ("/seating", "Seating", "seat", "seating"),
    ("/menu", "Menu", "dish", "menu"),
    ("/programme", "Programme", "list", "programme"),
    ("/communications", "Communications", "mail", "email_notifications"),
    ("/share", "Share", "chat", None),
    ("/reports", "Reports", "file", "basic_dashboard"),
    ("/settings", "Settings", "settings", None),
]


def event_nav(ev, current: str) -> str:
    base = f"/dashboard/events/{ev['uid']}"
    status = events.STATUS_LABELS.get(ev["status"], ev["status"])
    pill_kind = ev["status"]
    paid = catalog.package(ev["paid_package"])
    pkg_line = paid["name"] if paid else "Not paid yet"
    links = []
    for suffix, label, icon, feature in EVENT_NAV:
        href = base + suffix
        cur = current if not suffix.startswith("/setup") else (href if current.startswith(base + "/setup") else current)
        locked = feature is not None and not catalog.has_feature(ev, feature)
        links.append(side_link(href, label, icon, cur, locked))
    return (f'<a class="side-link" href="/dashboard">{i("arrow-left")}<span>All events</span></a>'
            f'<div class="side-event"><b>{esc(ev["name"])}</b><span>{esc(pkg_line)}</span>'
            f'<div style="margin-top:8px"><span class="pill pill--{esc(pill_kind)}">{esc(status)}</span></div></div>'
            + "".join(links) +
            f'<div class="side-group"><a class="side-link" href="{events.public_path(ev)}" target="_blank" rel="noopener">{i("external")}<span>View website</span></a></div>')


def account_nav(current: str, user) -> str:
    links = [
        side_link("/dashboard", "My events", "home", current),
        side_link("/create", "Create an event", "plus", current),
        side_link("/dashboard/billing", "Orders and receipts", "card", current),
        side_link("/account", "Account", "user", current),
        side_link("/contact", "Help and support", "support", current),
    ]
    if user is not None and user["role"] == "admin":
        links.append('<div class="side-group"><div class="side-group__label">Platform</div>'
                     + side_link("/admin", "Admin dashboard", "shield", current) + "</div>")
    return "".join(links)


ADMIN_NAV = [
    ("/admin", "Overview", "chart"),
    ("/admin/customers", "Customers", "users"),
    ("/admin/events", "Events", "calendar"),
    ("/admin/orders", "Payments", "card"),
    ("/admin/hosting", "Hosting periods", "clock"),
    ("/admin/packages", "Packages", "tag"),
    ("/admin/templates", "Templates", "layout"),
    ("/admin/categories", "Categories", "list"),
    ("/admin/emails", "Email templates", "mail"),
    ("/admin/outbox", "Email log", "send"),
    ("/admin/support", "Support", "support"),
    ("/admin/audit", "Audit log", "shield"),
]


def admin_nav(current: str) -> str:
    return (side_link("/dashboard", "Back to my events", "arrow-left", current)
            + '<div class="side-group"><div class="side-group__label">Administration</div>'
            + "".join(side_link(h, l, ic, current) for h, l, ic in ADMIN_NAV) + "</div>")


def organiser_page(req, ev, title: str, body: str, current_suffix: str = "", extra_head: str = "",
                   extra_scripts: str = "") -> str:
    current = f"/dashboard/events/{ev['uid']}{current_suffix}"
    return app_shell(req, f"{title} · {ev['name']}", body, event_nav(ev, current), ev, extra_head, extra_scripts)


def account_page(req, title: str, body: str, current: str = "/dashboard", extra_head: str = "") -> str:
    return app_shell(req, title, body, account_nav(current, req.user), None, extra_head)


def admin_page(req, title: str, body: str, current: str = "/admin", extra_head: str = "", extra_scripts: str = "") -> str:
    return app_shell(req, f"{title} · Admin", body, admin_nav(current), None, extra_head, extra_scripts)


def locked_panel(ev, feature: str, what: str) -> str:
    """Shown in place of a tool the event's package doesn't include."""
    need = next((p for p in catalog.packages() if feature in catalog.package_features(p["code"])), None)
    name = need["name"] if need else "a higher package"
    tile = '<span class="icon-tile icon-tile--soft">' + i("lock") + "</span>"
    return (f'<div class="empty">{tile}'
            f'<h2 style="font-size:1.25rem">{esc(what)} is part of the {esc(name)}</h2>'
            f'<p>Upgrade this event to unlock it. You only pay the difference.</p>'
            f'<a class="btn btn--primary" href="/dashboard/events/{ev["uid"]}/setup/8">See packages</a></div>')


def page_head(title: str, intro: str = "", actions: str = "") -> str:
    return (f'<div class="page-head"><div><h1>{esc(title)}</h1>{f"<p>{intro}</p>" if intro else ""}</div>'
            f'{f"<div class=btn-row>{actions}</div>" if actions else ""}</div>')
