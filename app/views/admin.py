"""Platform administrator dashboard.

Every handler starts with `auth.require_admin(req)`, so permissions are enforced on the server
for each request (customers get 403, visitors are sent to log in). Every change is recorded in
the audit log. Admins can refund-mark orders but can never mark an order paid: only a verified
gateway notification does that (app/services/payments.py).
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .. import auth, catalog, config, db, events, notify
from ..icons import i
from ..services import email as mail
from ..web import HTTPError, Response, download, esc, redirect, router, url
from .forms import SLUG_RE, Form, check, csrf, errors_summary, field, fmt_date, fmt_dt, select, switch
from .shell import admin_page, page_head

EXTRA_HEAD = '<link rel="stylesheet" href="/static/css/admin.css">'
PER_PAGE = 50


# --- small helpers ------------------------------------------------------------------------------
def _page(req, title: str, body: str, current: str) -> str:
    return admin_page(req, title, body, current, extra_head=EXTRA_HEAD)


def _pill(status: str, label: Optional[str] = None) -> str:
    return f'<span class="pill pill--{esc(status)}">{esc(label or status.replace("_", " ").capitalize())}</span>'


def _table(headers: list, rows: list, empty: str = "Nothing to show yet.") -> str:
    if not rows:
        return f'<div class="empty"><p>{esc(empty)}</p></div>'
    th = "".join(f'<th{" class=num" if h.startswith(">") else ""}>{esc(h.lstrip(">"))}</th>' for h in headers)
    body = []
    for r in rows:
        tds = []
        for idx, cell in enumerate(r):
            num = headers[idx].startswith(">") if idx < len(headers) else False
            tds.append(f'<td{" class=num" if num else ""}>{cell}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f'<div class="table-wrap"><table class="table"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _pager(req, total: int) -> tuple[int, str]:
    try:
        page = max(1, int(req.arg("page", "1")))
    except ValueError:
        page = 1
    pages = max(1, -(-total // PER_PAGE))
    page = min(page, pages)
    if pages == 1:
        return 0, f'<p class="tiny muted admin-count">{total} {"row" if total == 1 else "rows"}</p>'
    q = {k: v[0] for k, v in req.query.items() if k != "page"}
    prev = f'<a class="btn btn--secondary btn--sm" href="{esc(url(req.path, **q, page=page - 1))}">Previous</a>' if page > 1 else ""
    nxt = f'<a class="btn btn--secondary btn--sm" href="{esc(url(req.path, **q, page=page + 1))}">Next</a>' if page < pages else ""
    return (page - 1) * PER_PAGE, (f'<div class="row row--between admin-count"><span class="tiny muted">{total} rows · page {page} of {pages}</span>'
                                   f'<span class="row">{prev}{nxt}</span></div>')


def _filters(req, controls: str) -> str:
    return (f'<form class="toolbar" method="get" action="{esc(req.path)}" role="search">{controls}'
            f'<button class="btn btn--secondary btn--sm" type="submit">{i("filter")}Filter</button>'
            f'<a class="btn btn--ghost btn--sm" href="{esc(req.path)}">Clear</a></form>')


def _sel(name: str, label: str, options: list, value: str) -> str:
    opts = "".join(f'<option value="{esc(v)}"{" selected" if v == value else ""}>{esc(t)}</option>' for v, t in options)
    return f'<label class="sr-only" for="flt-{name}">{esc(label)}</label><select class="select select--sm" id="flt-{name}" name="{name}" data-autosubmit>{opts}</select>'


def _search(value: str, placeholder: str) -> str:
    return (f'<label class="sr-only" for="flt-q">Search</label><input class="input input--sm grow" id="flt-q" type="search" '
            f'name="q" value="{esc(value)}" placeholder="{esc(placeholder)}">')


def _post_button(action: str, label: str, req, cls: str = "btn btn--secondary btn--sm", confirm: str = "",
                 hidden: Optional[dict] = None) -> str:
    extra = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in (hidden or {}).items())
    conf = f' data-confirm="{esc(confirm)}"' if confirm else ""
    return f'<form method="post" action="{esc(action)}"{conf} style="display:inline">{csrf(req)}{extra}<button class="{cls}" type="submit">{esc(label)}</button></form>'


def _cents(rands: str) -> Optional[int]:
    raw = re.sub(r"[\sR,]", "", rands or "")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value < 0 or value > 1_000_000:
        return None
    return int(round(value * 100))


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


def _user_link(user_id, email: str) -> str:
    if not user_id:
        return esc(email or "—")
    return f'<a href="/admin/customers/{int(user_id)}">{esc(email)}</a>'


def _event_link(uid: str, name: str) -> str:
    return f'<a href="/admin/events/{esc(uid)}">{esc(name)}</a>' if uid else "—"


# --- analytics ----------------------------------------------------------------------------------
def revenue_stats() -> dict:
    """Live revenue (real payments only) kept apart from sandbox test payments. Demo events excluded."""
    def agg(where: str):
        r = db.one(f"""SELECT COUNT(*) AS n, COALESCE(SUM(o.amount_cents), 0) AS total
                       FROM orders o JOIN events e ON e.id = o.event_id WHERE e.is_demo = 0 AND {where}""")
        return {"count": r["n"], "cents": r["total"]}
    live = agg("o.status = 'paid' AND o.mode = 'live'")
    sandbox = agg("o.status = 'paid' AND o.mode = 'sandbox'")
    refunded = agg("o.status = 'refunded' AND o.mode = 'live'")
    by_package = [dict(r) for r in db.q("""SELECT o.package_code AS code, COUNT(*) AS n, SUM(o.amount_cents) AS cents
                                           FROM orders o JOIN events e ON e.id = o.event_id
                                           WHERE e.is_demo = 0 AND o.status = 'paid' AND o.mode = 'live'
                                           GROUP BY o.package_code ORDER BY cents DESC""")]
    avg = live["cents"] // live["count"] if live["count"] else 0
    return {"live": live, "sandbox": sandbox, "refunded": refunded, "by_package": by_package, "average_cents": avg}


def _weeks(n: int = 8) -> list[date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday - timedelta(weeks=k) for k in range(n - 1, -1, -1)]


def _bars(values: list[tuple[str, float]], fmt=lambda v: str(int(v))) -> str:
    top = max([v for _, v in values] + [0])
    bars = []
    for label, v in values:
        h = 3 if top == 0 else max(3, round(100 * v / top))
        bars.append(f'<div style="height:{h}%" title="{esc(label)}: {esc(fmt(v))}"><span>{esc(label)}</span>'
                    f'<b class="bar-val">{esc(fmt(v))}</b></div>')
    return f'<div class="chart-bars admin-bars" role="img" aria-label="Weekly chart">{"".join(bars)}</div>'


def _bar_list(rows: list[tuple[str, int, str]]) -> str:
    if not rows:
        return '<p class="muted small">No data yet.</p>'
    top = max(v for _, v, _ in rows) or 1
    out = []
    for label, v, shown in rows:
        out.append(f'<div class="bar-list__row"><span>{esc(label)}</span><b class="mono">{esc(shown)}</b>'
                   f'<div class="progress"><span style="width:{round(100 * v / top)}%"></span></div></div>')
    return f'<div class="bar-list">{"".join(out)}</div>'


@router.get("/admin/backup")
def backup(req):
    """Everything needed to restore the platform: a consistent copy of the database plus every uploaded
    photo, in one zip. Download it now and then and keep it somewhere safe (e.g. Google Drive)."""
    import io
    import os
    import sqlite3
    import tempfile
    import zipfile
    admin = auth.require_admin(req)
    stamp = db.now()[:16].replace(":", "").replace("T", "-")
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory(dir=str(config.DATA_DIR)) as tmp:
        copy = os.path.join(tmp, "aurelia.sqlite3")
        src = sqlite3.connect(str(config.DATABASE_PATH))
        dst = sqlite3.connect(copy)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy, "aurelia.sqlite3")
            for root, _, files in os.walk(str(config.UPLOAD_DIR)):
                for f in files:
                    full = os.path.join(root, f)
                    z.write(full, os.path.join("uploads", os.path.relpath(full, str(config.UPLOAD_DIR))), compress_type=zipfile.ZIP_STORED)
            z.writestr("README.txt", "Aurelia Studio backup " + stamp + ".\nTo restore: stop the app, put aurelia.sqlite3 and the uploads folder "
                                     "back into the data folder (/data on Railway), then start it again.\n")
    auth.audit(admin["id"], "admin.backup", stamp)
    return download(buf.getvalue(), f"aurelia-studio-backup-{stamp}.zip", "application/zip")


def launch_checks() -> list:
    """(level, text) for set-up that still needs attention, in launch order. Shown on the admin overview."""
    import os
    out = []
    if config.ON_RAILWAY and not os.path.ismount(config.DATA_DIR):
        out.append(("error", f"No volume is attached at {config.DATA_DIR}, so the database and photos are lost on every update. "
                             f"In Railway, add a volume to this service with mount path {config.DATA_DIR}."))
    if re.match(r"^https?://(127\.0\.0\.1|localhost)\b", config.BASE_URL):
        out.append(("error" if not config.DEBUG else "info",
                    f"Links in emails and payment returns point to {config.BASE_URL}. Set BASE_URL to your public address, "
                    "e.g. https://aureliastudios.co.za."))
    elif config.BASE_URL.endswith(".up.railway.app"):
        out.append(("info", f"Using Railway's address ({config.BASE_URL}). Once aureliastudios.co.za shows as active in Railway, "
                            "set BASE_URL=https://aureliastudios.co.za (deploy guide, part 3)."))
    if config.ADMIN_PASSWORD:
        out.append(("warn", "Delete the ADMIN_PASSWORD variable now that you can sign in. Your account keeps its password."))
    if config.EMAIL_PROVIDER == "outbox":
        out.append(("warn", "Emails aren't sent yet: they're only saved in the outbox. Connect Resend to send them (deploy guide, part 4)."))
    if config.PAYMENT_GATEWAY != "payfast":
        out.append(("warn", "Payments are in test mode, so anyone can publish a website without paying. Connect PayFast "
                            "(deploy guide, part 5), then delete ALLOW_SANDBOX_PAYMENTS."))
    elif config.PAYFAST_SANDBOX:
        out.append(("info", "PayFast is in sandbox mode: no real money moves. Set PAYFAST_SANDBOX=0 with your live merchant details to go live."))
    elif config.ALLOW_SANDBOX_PAYMENTS and not config.DEBUG:
        out.append(("warn", "Delete ALLOW_SANDBOX_PAYMENTS: PayFast is live, and the test checkout shouldn't be available."))
    if not config.VAT_NUMBER or "INFORMATION_OFFICER_EMAIL" not in os.environ:
        out.append(("info", "Before you announce it: add COMPANY_ADDRESS, VAT_NUMBER (if registered) and INFORMATION_OFFICER_EMAIL."))
    return out


def _launch_box() -> str:
    items = launch_checks()
    if not items:
        return ""
    icon = {"error": "alert", "warn": "alert", "info": "info"}
    rows = "".join(f'<li class="launch-check launch-check--{lvl}">{i(icon[lvl])}<span>{esc(text)}</span></li>' for lvl, text in items)
    return (f'<section class="box" style="margin-bottom:var(--gap)"><div class="box__head"><h2>Launch checks</h2>'
            f'<span class="tiny muted">{len(items)} to look at</span></div><ul class="launch-checks">{rows}</ul></section>')


@router.get("/admin")
def overview(req):
    auth.require_admin(req)
    customers = db.val("SELECT COUNT(*) FROM users WHERE role = 'customer' AND is_demo = 0", (), 0)
    new7 = db.val("SELECT COUNT(*) FROM users WHERE is_demo = 0 AND created_at >= ?", (_since(7),), 0)
    new30 = db.val("SELECT COUNT(*) FROM users WHERE is_demo = 0 AND created_at >= ?", (_since(30),), 0)
    by_status = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) AS n FROM events WHERE is_demo = 0 GROUP BY status")}
    total_events = sum(by_status.values())
    paid_events = db.val("SELECT COUNT(*) FROM events WHERE is_demo = 0 AND paid_package IS NOT NULL", (), 0)
    conversion = round(100 * paid_events / total_events) if total_events else 0
    rsvps = db.val("""SELECT COUNT(*) FROM rsvp_responses r JOIN events e ON e.id = r.event_id WHERE e.is_demo = 0""", (), 0)
    open_support = db.val("SELECT COUNT(*) FROM support_requests WHERE status != 'resolved'", (), 0)
    rev = revenue_stats()
    demo_events = db.val("SELECT COUNT(*) FROM events WHERE is_demo = 1", (), 0)

    weeks = _weeks()
    signups, revenue = [], []
    for start in weeks:
        end = start + timedelta(days=7)
        lbl = start.strftime("%-d %b")
        signups.append((lbl, db.val("SELECT COUNT(*) FROM users WHERE is_demo = 0 AND created_at >= ? AND created_at < ?",
                                    (start.isoformat(), end.isoformat()), 0)))
        revenue.append((lbl, db.val("""SELECT COALESCE(SUM(o.amount_cents), 0) FROM orders o JOIN events e ON e.id = o.event_id
                                       WHERE e.is_demo = 0 AND o.status = 'paid' AND o.mode = 'live'
                                       AND o.paid_at >= ? AND o.paid_at < ?""", (start.isoformat(), end.isoformat()), 0) / 100))

    pkg_names = {p["code"]: p["name"] for p in catalog.packages(active_only=False)}
    status_rows = [(events.STATUS_LABELS.get(s, s), n, str(n)) for s, n in sorted(by_status.items(), key=lambda x: -x[1])]
    pkg_rows = [(pkg_names.get(r["code"], r["code"]), r["cents"], f'{catalog.money(r["cents"])} · {r["n"]}') for r in rev["by_package"]]
    tpl_rows = [(r["name"] or r["template"], r["n"], str(r["n"])) for r in db.q(
        """SELECT e.template, t.name, COUNT(*) AS n FROM events e LEFT JOIN templates t ON t.slug = e.template
           WHERE e.is_demo = 0 GROUP BY e.template ORDER BY n DESC LIMIT 6""")]
    cat_rows = [(r["name"] or r["category"], r["n"], str(r["n"])) for r in db.q(
        """SELECT e.category, c.name, COUNT(*) AS n FROM events e LEFT JOIN categories c ON c.slug = e.category
           WHERE e.is_demo = 0 GROUP BY e.category ORDER BY n DESC LIMIT 6""")]

    recent_orders = db.q("""SELECT o.*, e.name AS event_name, e.uid AS event_uid, u.email FROM orders o
                            JOIN events e ON e.id = o.event_id JOIN users u ON u.id = o.user_id
                            ORDER BY o.created_at DESC LIMIT 6""")
    order_rows = [[f'<a href="/admin/orders/{esc(o["uid"])}">{esc(o["uid"])}</a><span class="table__sub">{esc(o["email"])}</span>',
                   esc(pkg_names.get(o["package_code"], o["package_code"])),
                   f'{_pill(o["status"])} {_pill("sandbox", "Sandbox") if o["mode"] == "sandbox" else ""}',
                   f'<span class="mono">{catalog.money(o["amount_cents"])}</span>'] for o in recent_orders]
    recent_users = db.q("SELECT * FROM users ORDER BY created_at DESC LIMIT 6")
    user_rows = [[f'<a href="/admin/customers/{u["id"]}">{esc(u["name"])}</a><span class="table__sub">{esc(u["email"])}</span>',
                  esc(fmt_dt(u["created_at"])),
                  _pill("info", "Demo") if u["is_demo"] else _pill("ok" if u["status"] == "active" else "suspended", u["status"].capitalize())]
                 for u in recent_users]

    body = page_head("Platform overview", "Live figures across every customer and event. "
                     + (f"{demo_events} demo events are excluded from all totals." if demo_events else "Demo data is excluded from all totals."),
                     f'<a class="btn btn--secondary btn--sm" href="/admin/backup">{i("download")}Download a backup</a>')
    body += _launch_box()
    body += f"""<div class="kpis">
<div class="kpi kpi--accent"><span>Live revenue</span><b>{catalog.money(rev['live']['cents'])}</b><small>{rev['live']['count']} paid orders · avg {catalog.money(rev['average_cents'])}</small></div>
<div class="kpi"><span>Customers</span><b>{customers}</b><small>+{new7} in 7 days · +{new30} in 30 days</small></div>
<div class="kpi"><span>Published websites</span><b>{by_status.get('published', 0)}</b><small>{total_events} events in total</small></div>
<div class="kpi"><span>Draft → paid conversion</span><b>{conversion}%</b><small>{paid_events} of {total_events} events paid</small></div>
</div>
<div class="kpis" style="margin-top:12px">
<div class="kpi"><span>RSVPs received</span><b>{rsvps}</b><small>All guest submissions</small></div>
<div class="kpi"><span>Refunded (live)</span><b>{catalog.money(rev['refunded']['cents'])}</b><small>{rev['refunded']['count']} orders</small></div>
<div class="kpi admin-sandbox"><span>Sandbox test payments</span><b>{catalog.money(rev['sandbox']['cents'])}</b><small>{rev['sandbox']['count']} orders · not revenue, no money moved</small></div>
<div class="kpi"><span>Open support requests</span><b>{open_support}</b><small><a class="text-link" href="/admin/support">View queue</a></small></div>
</div>
<div class="cols cols--even" style="margin-top:var(--gap)">
<section class="box"><div class="box__head"><h2>New customers per week</h2><span class="tiny muted">Last 8 weeks</span></div>{_bars(signups)}</section>
<section class="box"><div class="box__head"><h2>Live revenue per week</h2><span class="tiny muted">Rand, paid live orders</span></div>{_bars(revenue, lambda v: catalog.money(int(v * 100)))}</section>
<section class="box"><div class="box__head"><h2>Events by status</h2></div>{_bar_list(status_rows)}</section>
<section class="box"><div class="box__head"><h2>Revenue by package</h2></div>{_bar_list(pkg_rows)}</section>
<section class="box"><div class="box__head"><h2>Popular templates</h2><a class="arrow-link" href="/admin/templates"><span>Manage</span>{i("arrow")}</a></div>{_bar_list(tpl_rows)}</section>
<section class="box"><div class="box__head"><h2>Popular categories</h2><a class="arrow-link" href="/admin/categories"><span>Manage</span>{i("arrow")}</a></div>{_bar_list(cat_rows)}</section>
<section class="box"><div class="box__head"><h2>Recent orders</h2><a class="arrow-link" href="/admin/orders"><span>All payments</span>{i("arrow")}</a></div>{_table(["Order", "Package", "Status", ">Amount"], order_rows, "No orders yet.")}</section>
<section class="box"><div class="box__head"><h2>Recent sign-ups</h2><a class="arrow-link" href="/admin/customers"><span>All customers</span>{i("arrow")}</a></div>{_table(["Customer", "Joined", "Status"], user_rows, "No customers yet.")}</section>
</div>"""
    return _page(req, "Overview", body, "/admin")


# --- customers ----------------------------------------------------------------------------------
@router.get("/admin/customers")
def customers(req):
    auth.require_admin(req)
    q, role, status = req.arg("q"), req.arg("role"), req.arg("status")
    where, params = ["1 = 1"], []
    if q:
        where.append("(u.email LIKE ? OR u.name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if role in ("customer", "admin"):
        where.append("u.role = ?")
        params.append(role)
    if status in ("active", "suspended"):
        where.append("u.status = ?")
        params.append(status)
    w = " AND ".join(where)
    total = db.val(f"SELECT COUNT(*) FROM users u WHERE {w}", params, 0)
    offset, pager = _pager(req, total)
    rows = db.q(f"""SELECT u.*, (SELECT COUNT(*) FROM events e WHERE e.owner_id = u.id) AS n_events,
                      (SELECT COALESCE(SUM(amount_cents), 0) FROM orders o WHERE o.user_id = u.id AND o.status = 'paid' AND o.mode = 'live') AS spent
                    FROM users u WHERE {w} ORDER BY u.created_at DESC LIMIT ? OFFSET ?""", params + [PER_PAGE, offset])
    table = _table(["Customer", "Role", "Status", ">Events", ">Spent (live)", "Joined"], [[
        f'<a href="/admin/customers/{u["id"]}">{esc(u["name"])}</a><span class="table__sub">{esc(u["email"])}</span>',
        esc(u["role"].capitalize()) + (" · demo" if u["is_demo"] else ""),
        _pill("ok" if u["status"] == "active" else "suspended", u["status"].capitalize()),
        str(u["n_events"]), f'<span class="mono">{catalog.money(u["spent"])}</span>', esc(fmt_dt(u["created_at"]))]
        for u in rows], "No customers match these filters.")
    controls = (_search(q, "Name or email") +
                _sel("role", "Role", [("", "All roles"), ("customer", "Customers"), ("admin", "Admins")], role) +
                _sel("status", "Status", [("", "Any status"), ("active", "Active"), ("suspended", "Suspended")], status))
    body = page_head("Customers", "Everyone with an account.") + _filters(req, controls) + table + pager
    return _page(req, "Customers", body, "/admin/customers")


@router.get("/admin/customers/<int:user_id>")
def customer_detail(req, user_id):
    admin = auth.require_admin(req)
    u = db.one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not u:
        raise HTTPError(404)
    evs = db.q("SELECT * FROM events WHERE owner_id = ? ORDER BY created_at DESC", (user_id,))
    ords = db.q("""SELECT o.*, e.name AS event_name FROM orders o JOIN events e ON e.id = o.event_id
                   WHERE o.user_id = ? ORDER BY o.created_at DESC""", (user_id,))
    tickets = db.q("SELECT * FROM support_requests WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    is_self = u["id"] == admin["id"]
    actions = ""
    if not is_self:
        if u["status"] == "active":
            actions += _post_button(f"/admin/customers/{user_id}/status", "Suspend account", req, "btn btn--danger btn--sm",
                                    "Suspend this account? They will be signed out and can't log in.", {"status": "suspended"})
        else:
            actions += _post_button(f"/admin/customers/{user_id}/status", "Reactivate account", req, hidden={"status": "active"})
        if u["role"] == "admin":
            actions += _post_button(f"/admin/customers/{user_id}/role", "Remove admin access", req, confirm="Remove admin access?", hidden={"role": "customer"})
        else:
            actions += _post_button(f"/admin/customers/{user_id}/role", "Make administrator", req,
                                    confirm="Give this person full access to the admin dashboard?", hidden={"role": "admin"})
    else:
        actions = '<span class="tiny muted">This is your account. Another admin must change your role or status.</span>'
    info = f"""<dl class="dl">
<dt>Email</dt><dd>{esc(u['email'])} {_pill('ok', 'Verified') if u['email_verified_at'] else _pill('pending', 'Not verified')}</dd>
<dt>Phone</dt><dd>{esc(u['phone'] or '—')}</dd><dt>Role</dt><dd>{esc(u['role'].capitalize())}</dd>
<dt>Status</dt><dd>{_pill('ok' if u['status'] == 'active' else 'suspended', u['status'].capitalize())}</dd>
<dt>Marketing consent</dt><dd>{'Yes' if u['marketing_consent'] else 'No'}</dd>
<dt>Joined</dt><dd>{esc(fmt_dt(u['created_at']))}</dd><dt>Last login</dt><dd>{esc(fmt_dt(u['last_login_at']) or '—')}</dd>
<dt>Demo account</dt><dd>{'Yes' if u['is_demo'] else 'No'}</dd></dl>"""
    ev_table = _table(["Event", "Status", "Package", "Date"], [[
        _event_link(e["uid"], e["name"]), _pill(e["status"], events.STATUS_LABELS.get(e["status"])),
        esc(e["paid_package"] or f'{e["selected_package"] or "—"} (unpaid)'), esc(fmt_date(e["event_date"], False) or "—")]
        for e in evs], "No events yet.")
    ord_table = _table(["Order", "Event", "Status", ">Amount", "Created"], [[
        f'<a href="/admin/orders/{esc(o["uid"])}">{esc(o["uid"])}</a>', esc(o["event_name"]),
        f'{_pill(o["status"])} {_pill("sandbox", "Sandbox") if o["mode"] == "sandbox" else ""}',
        f'<span class="mono">{catalog.money(o["amount_cents"])}</span>', esc(fmt_dt(o["created_at"]))] for o in ords], "No orders.")
    sup_table = _table(["Request", "Status", "Created"], [[
        f'<a href="/admin/support/{t["id"]}">{esc(t["topic"].capitalize())}: {esc(t["message"][:60])}</a>', _pill(t["status"]),
        esc(fmt_dt(t["created_at"]))] for t in tickets], "No support requests.")
    body = (f'<p><a class="arrow-link" href="/admin/customers">{i("arrow-left")}<span>All customers</span></a></p>'
            + page_head(u["name"], esc(u["email"]), actions)
            + f'<div class="cols cols--2"><section class="box"><div class="box__head"><h2>Events</h2></div>{ev_table}'
              f'<div class="box__head" style="margin-top:24px"><h2>Orders</h2></div>{ord_table}'
              f'<div class="box__head" style="margin-top:24px"><h2>Support</h2></div>{sup_table}</section>'
              f'<section class="box"><div class="box__head"><h2>Account</h2></div>{info}</section></div>')
    return _page(req, u["name"], body, "/admin/customers")


@router.post("/admin/customers/<int:user_id>/status")
def customer_status(req, user_id):
    admin = auth.require_admin(req)
    u = db.one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not u:
        raise HTTPError(404)
    status = req.get("status")
    if status not in ("active", "suspended"):
        raise HTTPError(400, "Unknown status.")
    if u["id"] == admin["id"]:
        req.flash("error", "You can't change the status of your own account.")
        return redirect(f"/admin/customers/{user_id}")
    db.run("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    if status == "suspended":
        auth.destroy_user_sessions(user_id)
    auth.audit(admin["id"], f"user.{'suspend' if status == 'suspended' else 'reactivate'}", u["email"])
    req.flash("success", f"{u['name']} is now {status}.")
    return redirect(f"/admin/customers/{user_id}")


@router.post("/admin/customers/<int:user_id>/role")
def customer_role(req, user_id):
    admin = auth.require_admin(req)
    u = db.one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not u:
        raise HTTPError(404)
    role = req.get("role")
    if role not in ("customer", "admin"):
        raise HTTPError(400, "Unknown role.")
    if u["id"] == admin["id"]:
        req.flash("error", "You can't change your own role.")
        return redirect(f"/admin/customers/{user_id}")
    db.run("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    auth.audit(admin["id"], "user.role", u["email"], role=role)
    req.flash("success", f"{u['name']} is now {'an administrator' if role == 'admin' else 'a customer'}.")
    return redirect(f"/admin/customers/{user_id}")


# --- events ---------------------------------------------------------------------------------------
@router.get("/admin/events")
def events_list(req):
    auth.require_admin(req)
    q, status, cat, pkg, demo = req.arg("q"), req.arg("status"), req.arg("category"), req.arg("package"), req.arg("demo")
    where, params = ["1 = 1"], []
    if q:
        where.append("(e.name LIKE ? OR e.slug LIKE ? OR e.hosts LIKE ? OR u.email LIKE ?)")
        params += [f"%{q}%"] * 4
    if status in events.STATUS_LABELS:
        where.append("e.status = ?")
        params.append(status)
    if cat:
        where.append("e.category = ?")
        params.append(cat)
    if pkg == "unpaid":
        where.append("e.paid_package IS NULL")
    elif pkg:
        where.append("e.paid_package = ?")
        params.append(pkg)
    if demo == "hide":
        where.append("e.is_demo = 0")
    elif demo == "only":
        where.append("e.is_demo = 1")
    w = " AND ".join(where)
    total = db.val(f"SELECT COUNT(*) FROM events e JOIN users u ON u.id = e.owner_id WHERE {w}", params, 0)
    offset, pager = _pager(req, total)
    rows = db.q(f"""SELECT e.*, u.email, u.id AS owner, (SELECT COUNT(*) FROM guests g WHERE g.event_id = e.id) AS n_guests
                    FROM events e JOIN users u ON u.id = e.owner_id WHERE {w}
                    ORDER BY e.updated_at DESC LIMIT ? OFFSET ?""", params + [PER_PAGE, offset])
    pkg_names = {p["code"]: p["name"] for p in catalog.packages(active_only=False)}
    table = _table(["Event", "Owner", "Status", "Package", "Event date", ">Guests"], [[
        _event_link(e["uid"], e["name"]) + f'<span class="table__sub">/events/{esc(e["slug"])}{" · demo" if e["is_demo"] else ""}</span>',
        _user_link(e["owner"], e["email"]), _pill(e["status"], events.STATUS_LABELS.get(e["status"])),
        esc(pkg_names.get(e["paid_package"], "Unpaid") if e["paid_package"] else "Unpaid"),
        esc(fmt_date(e["event_date"], False) or "—"), str(e["n_guests"])] for e in rows], "No events match these filters.")
    controls = (_search(q, "Event, slug, host or owner email")
                + _sel("status", "Status", [("", "Any status")] + list(events.STATUS_LABELS.items()), status)
                + _sel("category", "Category", [("", "Any category")] + [(c["slug"], c["name"]) for c in catalog.categories(False)], cat)
                + _sel("package", "Package", [("", "Any package"), ("unpaid", "Unpaid")] + [(p["code"], p["name"]) for p in catalog.packages(False)], pkg)
                + _sel("demo", "Demo data", [("", "Including demo"), ("hide", "Hide demo"), ("only", "Demo only")], demo))
    body = page_head("Events", "Every event created on the platform.") + _filters(req, controls) + table + pager
    return _page(req, "Events", body, "/admin/events")


def _load_event(uid: str):
    ev = events.get(uid)
    if not ev:
        raise HTTPError(404)
    return ev


@router.get("/admin/events/<uid>")
def event_detail(req, uid):
    auth.require_admin(req)
    ev = _load_event(uid)
    owner = db.one("SELECT * FROM users WHERE id = ?", (ev["owner_id"],))
    st = events.stats(ev["id"])
    ords = db.q("SELECT * FROM orders WHERE event_id = ? ORDER BY created_at DESC", (ev["id"],))
    pkg_names = {p["code"]: p["name"] for p in catalog.packages(active_only=False)}
    emails_sent = db.val("SELECT COUNT(*) FROM email_logs WHERE event_id = ? AND status = 'sent'", (ev["id"],), 0)
    actions = []
    if ev["status"] == "suspended":
        actions.append(_post_button(f"/admin/events/{uid}/reactivate", "Reactivate event", req, "btn btn--primary btn--sm"))
    else:
        if ev["status"] == "published":
            actions.append(_post_button(f"/admin/events/{uid}/unpublish", "Unpublish", req, confirm="Take this website offline?"))
        elif ev["paid_package"]:
            actions.append(_post_button(f"/admin/events/{uid}/publish", "Publish", req))
    actions.append(f'<a class="btn btn--secondary btn--sm" href="{events.public_path(ev)}" target="_blank" rel="noopener">{i("external")}Public site</a>')
    suspend_box = ""
    if ev["status"] != "suspended":
        suspend_box = f"""<section class="box"><div class="box__head"><h2>Suspend event</h2></div>
<p class="small muted" style="margin-bottom:12px">Takes the website offline for guests and stops all automatic emails. Use for policy or payment problems.</p>
<form method="post" action="/admin/events/{esc(uid)}/suspend" class="form" data-confirm="Suspend this event?">{csrf(req)}
{field("reason", "Reason (shown to the organiser)", "", required=True, attrs={"maxlength": 300})}
<div><button class="btn btn--danger btn--sm" type="submit">Suspend event</button></div></form></section>"""
    else:
        suspend_box = (f'<div class="notice notice--error">{i("alert")}<div><b>Suspended.</b> '
                       f'{esc(ev["suspended_reason"] or "No reason recorded.")}</div></div>')
    ord_table = _table(["Order", "Package", "Status", ">Amount", "Created"], [[
        f'<a href="/admin/orders/{esc(o["uid"])}">{esc(o["uid"])}</a>', esc(pkg_names.get(o["package_code"], o["package_code"])),
        f'{_pill(o["status"])} {_pill("sandbox", "Sandbox") if o["mode"] == "sandbox" else ""}',
        f'<span class="mono">{catalog.money(o["amount_cents"])}</span>', esc(fmt_dt(o["created_at"]))] for o in ords], "No orders yet.")
    info = f"""<dl class="dl">
<dt>Owner</dt><dd>{_user_link(owner['id'] if owner else None, owner['email'] if owner else '')}</dd>
<dt>Category</dt><dd>{esc(catalog.category_name(ev['category']))}</dd><dt>Template</dt><dd>{esc(ev['template'])}</dd>
<dt>Public URL</dt><dd><span class="mono small">{esc(events.public_url(ev))}</span></dd>
<dt>Event date</dt><dd>{esc(fmt_date(ev['event_date']) or '—')}</dd>
<dt>Selected package</dt><dd>{esc(pkg_names.get(ev['selected_package'], ev['selected_package'] or '—'))}</dd>
<dt>Paid package</dt><dd>{esc(pkg_names.get(ev['paid_package'], 'Not paid') if ev['paid_package'] else 'Not paid')}</dd>
<dt>Published</dt><dd>{esc(fmt_dt(ev['published_at']) or '—')}</dd><dt>Hosted until</dt><dd>{esc(fmt_date(ev['hosting_until']) or '—')}</dd>
<dt>Created</dt><dd>{esc(fmt_dt(ev['created_at']))}</dd><dt>Emails sent</dt><dd>{emails_sent}</dd>
<dt>Demo event</dt><dd>{'Yes' if ev['is_demo'] else 'No'}</dd></dl>"""
    kpis = f"""<div class="kpis" style="--n:5;margin-bottom:var(--gap)">
<div class="kpi"><span>Invited</span><b>{st['invited']}</b></div><div class="kpi"><span>Attending</span><b>{st['attending']}</b></div>
<div class="kpi"><span>Declined</span><b>{st['declined']}</b></div><div class="kpi"><span>Pending</span><b>{st['pending']}</b></div>
<div class="kpi"><span>Headcount</span><b>{st['headcount']}</b><small>{st['completion']}% replied</small></div></div>"""
    extend = f"""<section class="box"><div class="box__head"><h2>Hosting period</h2></div>
<form method="post" action="/admin/events/{esc(uid)}/extend" class="row">{csrf(req)}
<label class="sr-only" for="ext-m">Months</label><input class="input input--sm" id="ext-m" name="months" type="number" min="1" max="36" value="3" style="width:100px">
<button class="btn btn--secondary btn--sm" type="submit">Extend by months</button></form>
<p class="tiny muted" style="margin-top:8px">Guest details stay private: admins see counts only.</p></section>"""
    body = (f'<p><a class="arrow-link" href="/admin/events">{i("arrow-left")}<span>All events</span></a></p>'
            + page_head(ev["name"], f'{_pill(ev["status"], events.STATUS_LABELS.get(ev["status"]))}', "".join(actions))
            + kpis + f'<div class="cols cols--2"><div class="stack"><section class="box"><div class="box__head"><h2>Orders</h2></div>{ord_table}</section>'
            + f'{suspend_box}</div><div class="stack"><section class="box"><div class="box__head"><h2>Details</h2></div>{info}</section>{extend}</div></div>')
    return _page(req, ev["name"], body, "/admin/events")


@router.post("/admin/events/<uid>/suspend")
def event_suspend(req, uid):
    admin = auth.require_admin(req)
    ev = _load_event(uid)
    f = Form(req)
    reason = f.text("reason", "Reason", required=True, max=300)
    if not f.ok:
        req.flash("error", next(iter(f.errors.values())))
        return redirect(f"/admin/events/{uid}")
    events.touch(ev["id"], status="suspended", suspended_reason=reason)
    auth.audit(admin["id"], "event.suspend", uid, reason=reason, previous=ev["status"])
    req.flash("success", "Event suspended. Its website is offline.")
    return redirect(f"/admin/events/{uid}")


@router.post("/admin/events/<uid>/reactivate")
def event_reactivate(req, uid):
    admin = auth.require_admin(req)
    ev = _load_event(uid)
    status = "published" if ev["paid_package"] else "draft"
    events.touch(ev["id"], status=status, suspended_reason=None)
    auth.audit(admin["id"], "event.reactivate", uid, status=status)
    req.flash("success", f"Event reactivated as {events.STATUS_LABELS[status].lower()}.")
    return redirect(f"/admin/events/{uid}")


@router.post("/admin/events/<uid>/publish")
def event_publish(req, uid):
    admin = auth.require_admin(req)
    ev = _load_event(uid)
    ok, msg = notify.publish(ev, admin["id"])
    req.flash("success" if ok else "error", msg)
    return redirect(f"/admin/events/{uid}")


@router.post("/admin/events/<uid>/unpublish")
def event_unpublish(req, uid):
    admin = auth.require_admin(req)
    ev = _load_event(uid)
    notify.unpublish(ev, admin["id"])
    req.flash("success", "Website unpublished.")
    return redirect(f"/admin/events/{uid}")


@router.post("/admin/events/<uid>/extend")
def event_extend(req, uid):
    admin = auth.require_admin(req)
    ev = _load_event(uid)
    f = Form(req)
    months = f.integer("months", "Months", required=True, min=1, max=36)
    if not f.ok:
        req.flash("error", next(iter(f.errors.values())))
        return redirect(req.get("back") or f"/admin/events/{uid}")
    try:
        current = date.fromisoformat(ev["hosting_until"]) if ev["hosting_until"] else date.today()
    except ValueError:
        current = date.today()
    new = add_months(max(current, date.today()), months)
    events.touch(ev["id"], hosting_until=new.isoformat())
    auth.audit(admin["id"], "event.extend_hosting", uid, months=months, until=new.isoformat())
    req.flash("success", f"Hosting extended to {fmt_date(new.isoformat())}.")
    back = req.get("back")
    return redirect(back if back in ("/admin/hosting",) else f"/admin/events/{uid}")


# --- orders -----------------------------------------------------------------------------------------
@router.get("/admin/orders")
def orders_list(req):
    auth.require_admin(req)
    q, status, mode = req.arg("q"), req.arg("status"), req.arg("mode")
    where, params = ["1 = 1"], []
    if q:
        where.append("(o.uid LIKE ? OR o.invoice_no LIKE ? OR u.email LIKE ? OR e.name LIKE ?)")
        params += [f"%{q}%"] * 4
    if status in ("pending", "paid", "failed", "cancelled", "refunded"):
        where.append("o.status = ?")
        params.append(status)
    if mode in ("live", "sandbox"):
        where.append("o.mode = ?")
        params.append(mode)
    w = " AND ".join(where)
    base = "FROM orders o JOIN users u ON u.id = o.user_id JOIN events e ON e.id = o.event_id"
    total = db.val(f"SELECT COUNT(*) {base} WHERE {w}", params, 0)
    offset, pager = _pager(req, total)
    rows = db.q(f"SELECT o.*, u.email, e.name AS event_name, e.uid AS event_uid {base} WHERE {w} ORDER BY o.created_at DESC LIMIT ? OFFSET ?",
                params + [PER_PAGE, offset])
    pkg_names = {p["code"]: p["name"] for p in catalog.packages(active_only=False)}
    rev = revenue_stats()
    table = _table(["Order", "Customer", "Event", "Package", "Status", ">Amount", "Created"], [[
        f'<a href="/admin/orders/{esc(o["uid"])}">{esc(o["uid"])}</a><span class="table__sub">{esc(o["invoice_no"] or "No invoice")}</span>',
        _user_link(o["user_id"], o["email"]), _event_link(o["event_uid"], o["event_name"]),
        esc(pkg_names.get(o["package_code"], o["package_code"])),
        f'{_pill(o["status"])} {_pill("sandbox", "Sandbox") if o["mode"] == "sandbox" else ""}',
        f'<span class="mono">{catalog.money(o["amount_cents"])}</span>', esc(fmt_dt(o["created_at"]))] for o in rows],
        "No orders match these filters.")
    controls = (_search(q, "Order, invoice, email or event")
                + _sel("status", "Status", [("", "Any status"), ("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"),
                                            ("cancelled", "Cancelled"), ("refunded", "Refunded")], status)
                + _sel("mode", "Mode", [("", "Live and sandbox"), ("live", "Live only"), ("sandbox", "Sandbox only")], mode))
    summary = (f'<div class="notice" style="margin-bottom:16px">{i("info")}<div>Live revenue <b>{catalog.money(rev["live"]["cents"])}</b> '
               f'from {rev["live"]["count"]} orders. Sandbox orders are test payments: no money moved and they never count as revenue. '
               f'Orders become paid only from a verified gateway notification.</div></div>')
    body = page_head("Payments", "Orders and the gateway notifications behind them.") + summary + _filters(req, controls) + table + pager
    return _page(req, "Payments", body, "/admin/orders")


@router.get("/admin/orders/<uid>")
def order_detail(req, uid):
    auth.require_admin(req)
    o = db.one("""SELECT o.*, u.email, u.name AS customer, e.name AS event_name, e.uid AS event_uid FROM orders o
                  JOIN users u ON u.id = o.user_id JOIN events e ON e.id = o.event_id WHERE o.uid = ?""", (uid,))
    if not o:
        raise HTTPError(404)
    pays = db.q("SELECT * FROM payments WHERE order_id = ? ORDER BY created_at", (o["id"],))
    pay_rows = [[esc(fmt_dt(p["created_at"])), esc(p["gateway"]), esc(p["gateway_payment_id"] or "—"), _pill(p["status"].lower()),
                 _pill("ok", "Verified") if p["verified"] else _pill("failed", "Unverified"),
                 f'<span class="mono">{catalog.money(p["amount_cents"], True)}</span>',
                 f'<details><summary class="tiny">Raw</summary><pre class="admin-pre">{esc(p["raw"])}</pre></details>'] for p in pays]
    refund = ""
    if o["status"] == "paid":
        refund = f"""<section class="box"><div class="box__head"><h2>Record a refund</h2></div>
<p class="small muted" style="margin-bottom:12px">Process the refund in the payment gateway first. This only records it here; it does not move money.</p>
<form method="post" action="/admin/orders/{esc(uid)}/refund" class="form" data-confirm="Record this order as refunded?">{csrf(req)}
{field("note", "Note", "", attrs={"maxlength": 300})}{check("unpublish", "Also unpublish the event website")}
<div><button class="btn btn--danger btn--sm" type="submit">Mark as refunded</button></div></form></section>"""
    info = f"""<dl class="dl"><dt>Status</dt><dd>{_pill(o['status'])} {_pill('sandbox', 'Sandbox test') if o['mode'] == 'sandbox' else _pill('ok', 'Live')}</dd>
<dt>Customer</dt><dd>{_user_link(o['user_id'], o['email'])}</dd><dt>Event</dt><dd>{_event_link(o['event_uid'], o['event_name'])}</dd>
<dt>Description</dt><dd>{esc(o['description'])}</dd><dt>Amount</dt><dd class="mono">{catalog.money(o['amount_cents'], True)} {esc(o['currency'])}</dd>
<dt>Gateway</dt><dd>{esc(o['gateway'])} · ref {esc(o['gateway_ref'] or '—')}</dd><dt>Invoice</dt><dd>{esc(o['invoice_no'] or '—')}</dd>
<dt>Created</dt><dd>{esc(fmt_dt(o['created_at']))}</dd><dt>Paid</dt><dd>{esc(fmt_dt(o['paid_at']) or '—')}</dd>
<dt>Failure reason</dt><dd>{esc(o['failure_reason'] or '—')}</dd></dl>"""
    body = (f'<p><a class="arrow-link" href="/admin/orders">{i("arrow-left")}<span>All payments</span></a></p>'
            + page_head(f"Order {o['uid']}", esc(o["customer"]))
            + f'<div class="cols cols--2"><div class="stack"><section class="box"><div class="box__head"><h2>Gateway notifications</h2></div>'
              f'{_table(["Received", "Gateway", "Payment ID", "Status", "Signature", ">Amount", ""], pay_rows, "No notifications received for this order.")}</section>{refund}</div>'
              f'<section class="box"><div class="box__head"><h2>Order</h2></div>{info}</section></div>')
    return _page(req, f"Order {o['uid']}", body, "/admin/orders")


@router.post("/admin/orders/<uid>/refund")
def order_refund(req, uid):
    admin = auth.require_admin(req)
    o = db.one("SELECT * FROM orders WHERE uid = ?", (uid,))
    if not o:
        raise HTTPError(404)
    if o["status"] != "paid":
        req.flash("error", "Only paid orders can be recorded as refunded.")
        return redirect(f"/admin/orders/{uid}")
    db.run("UPDATE orders SET status = 'refunded', updated_at = ? WHERE id = ?", (db.now(), o["id"]))
    auth.audit(admin["id"], "order.refund", uid, note=req.get("note")[:300], amount_cents=o["amount_cents"])
    if req.get("unpublish"):
        ev = events.by_id(o["event_id"])
        if ev and ev["status"] == "published":
            notify.unpublish(ev, admin["id"])
    req.flash("success", "Order recorded as refunded.")
    return redirect(f"/admin/orders/{uid}")


# --- hosting ----------------------------------------------------------------------------------------
@router.get("/admin/hosting")
def hosting(req):
    auth.require_admin(req)
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=30)).isoformat()

    def rows_for(where: str, params: tuple):
        rs = db.q(f"""SELECT e.*, u.email FROM events e JOIN users u ON u.id = e.owner_id
                      WHERE e.hosting_until IS NOT NULL AND {where} ORDER BY e.hosting_until""", params)
        return [[_event_link(e["uid"], e["name"]) + (' <span class="tag">demo</span>' if e["is_demo"] else ""),
                 esc(e["email"]), _pill(e["status"], events.STATUS_LABELS.get(e["status"])),
                 f'<span class="mono">{esc(e["hosting_until"])}</span>',
                 f'<form method="post" action="/admin/events/{esc(e["uid"])}/extend" class="row" style="gap:6px">{csrf(req)}'
                 f'<input type="hidden" name="back" value="/admin/hosting"><label class="sr-only" for="m-{e["id"]}">Months</label>'
                 f'<input class="input input--sm" id="m-{e["id"]}" name="months" type="number" min="1" max="36" value="3" style="width:76px">'
                 f'<button class="btn btn--secondary btn--sm" type="submit">Extend</button></form>'] for e in rs]
    headers = ["Event", "Owner", "Status", "Hosted until", "Extend (months)"]
    body = (page_head("Hosting periods", "Each paid package includes a hosting period. Expired websites are unpublished automatically each day.")
            + f'<section class="box"><div class="box__head"><h2>Expiring in the next 30 days</h2></div>'
              f'{_table(headers, rows_for("e.hosting_until >= ? AND e.hosting_until <= ?", (today, soon)), "Nothing expires in the next 30 days.")}</section>'
            + f'<section class="box" style="margin-top:var(--gap)"><div class="box__head"><h2>Expired</h2></div>'
              f'{_table(headers, rows_for("e.hosting_until < ?", (today,)), "No expired websites.")}</section>'
            + f'<section class="box" style="margin-top:var(--gap)"><div class="box__head"><h2>Active, later than 30 days</h2></div>'
              f'{_table(headers, rows_for("e.hosting_until > ?", (soon,)), "No other hosted websites.")}</section>')
    return _page(req, "Hosting periods", body, "/admin/hosting")


# --- packages --------------------------------------------------------------------------------------
@router.get("/admin/packages")
def packages_list(req):
    auth.require_admin(req)
    rows = []
    for p in catalog.packages(active_only=False):
        lim = db.loads(p["limits"], {})
        sold = db.val("SELECT COUNT(*) FROM orders WHERE package_code = ? AND status = 'paid' AND mode = 'live'", (p["code"],), 0)
        rows.append([f'<a href="/admin/packages/{esc(p["code"])}">{esc(p["name"])}</a><span class="table__sub">{esc(p["code"])}</span>',
                     f'<span class="mono">{catalog.money(p["price_cents"])}</span>', str(len(db.loads(p["features"], []))),
                     esc(", ".join(f"{k.replace('_', ' ')} {v}" for k, v in lim.items())),
                     (_pill("ok", "Active") if p["active"] else _pill("cancelled", "Hidden")) + (" " + _pill("gold", "Highlighted") if p["highlight"] else ""),
                     str(sold)])
    body = (page_head("Packages", "Prices, features and limits. Changes apply immediately to the pricing page, checkout and feature access. "
                      "Existing paid orders keep the amount they paid.")
            + _table(["Package", ">Price", ">Features", "Limits", "Status", ">Sold (live)"], rows))
    return _page(req, "Packages", body, "/admin/packages")


def _package_form(req, p, errors: dict, values: Optional[dict] = None) -> str:
    v = values or {}
    feats = set(v.get("features", db.loads(p["features"], [])))
    lim = v.get("limits", db.loads(p["limits"], {}))
    bullets = v.get("bullets", "\n".join(db.loads(p["bullets"], [])))
    price = v.get("price", f'{p["price_cents"] / 100:.2f}')
    feat_boxes = "".join(check("features", esc(label), k in feats, value=k) for k, label in catalog.FEATURES.items())
    limit_fields = "".join(field(f"limit_{k}", label, lim.get(k, 0), type="number", errors=errors, attrs={"min": 0, "max": 100000})
                           for k, label in catalog.LIMIT_LABELS.items())
    return f"""{errors_summary(errors)}<form method="post" class="form">{csrf(req)}
<section class="box"><div class="box__head"><h2>Details</h2></div><div class="form">
<div class="form-row form-row--2">{field("name", "Name", v.get("name", p["name"]), required=True, errors=errors)}
{field("price", "Price in Rand (what the client pays)", price, required=True, errors=errors, hint="For example 12999 or 12 999.00", attrs={"inputmode": "decimal"})}</div>
{field("tagline", "Tagline", v.get("tagline", p["tagline"]), errors=errors)}
<div class="form-row form-row--3">{field("rank", "Rank (upgrade order)", v.get("rank", p["rank"]), type="number", errors=errors, attrs={"min": 0, "max": 100})}
<div class="field"><span class="label">Visibility</span>{switch("active", "Show on pricing page", bool(v.get("active", p["active"])))}</div>
<div class="field"><span class="label">Highlight</span>{switch("highlight", "Mark as most popular", bool(v.get("highlight", p["highlight"])))}</div></div></div></section>
<section class="box"><div class="box__head"><h2>Features</h2><span class="tiny muted">These switch tools on and off for events on this package</span></div>
<div class="admin-checks">{feat_boxes}</div></section>
<section class="box"><div class="box__head"><h2>Limits</h2></div><div class="form-row form-row--3">{limit_fields}</div>
<p class="tiny muted" style="margin-top:10px">Unlimited link sharing is never unlimited email: the email limit caps guest emails sent through the platform.</p></section>
<section class="box"><div class="box__head"><h2>Pricing page bullets</h2></div>
{field("bullets", "One line per bullet", bullets, type="textarea", errors=errors, attrs={"rows": 12})}</section>
<div class="btn-row"><button class="btn btn--primary" type="submit">Save package</button><a class="btn btn--ghost" href="/admin/packages">Cancel</a>
<a class="btn btn--ghost" href="/pricing" target="_blank" rel="noopener">View pricing page</a></div></form>"""


@router.route("/admin/packages/<code>", methods=("GET", "POST"))
def package_edit(req, code):
    admin = auth.require_admin(req)
    p = catalog.package(code)
    if not p:
        raise HTTPError(404)
    errors, values = {}, None
    if req.method == "POST":
        f = Form(req)
        name = f.text("name", "Name", required=True, max=80)
        tagline = f.text("tagline", "Tagline", max=200)
        cents = _cents(req.get("price"))
        if cents is None:
            f.error("price", "Enter a price in Rand between R0 and R1,000,000, like 12999 or 12 999.00.")
        features = [k for k in req.getlist("features") if k in catalog.FEATURES]
        bullets = [ln.strip() for ln in req.get("bullets").splitlines() if ln.strip()]
        limits = {k: f.integer(f"limit_{k}", label, min=0, max=100000) for k, label in catalog.LIMIT_LABELS.items()}
        rank = f.integer("rank", "Rank", min=0, max=100)
        active, highlight = f.flag("active"), f.flag("highlight")
        if f.ok:
            with db.transaction():
                if highlight:
                    db.run("UPDATE packages SET highlight = 0 WHERE code != ?", (code,))
                db.run("""UPDATE packages SET name = ?, tagline = ?, price_cents = ?, features = ?, bullets = ?, limits = ?,
                          rank = ?, active = ?, highlight = ?, updated_at = ? WHERE code = ?""",
                       (name, tagline, cents, db.dumps(features), db.dumps(bullets), db.dumps(limits), rank,
                        1 if active else 0, 1 if highlight else 0, db.now(), code))
            auth.audit(admin["id"], "package.update", code, price_cents=cents, previous_price_cents=p["price_cents"],
                       features=len(features), active=active)
            req.flash("success", f"{name} saved. The pricing page and checkout now use these values.")
            return redirect(f"/admin/packages/{code}")
        errors = f.errors
        values = {"name": name, "tagline": tagline, "price": req.get("price"), "features": features,
                  "bullets": req.get("bullets"), "limits": limits, "rank": rank, "active": active, "highlight": highlight}
    body = (f'<p><a class="arrow-link" href="/admin/packages">{i("arrow-left")}<span>All packages</span></a></p>'
            + page_head(p["name"], f"Code <span class=mono>{esc(p['code'])}</span> · last changed {esc(fmt_dt(p['updated_at']) or 'never')}")
            + _package_form(req, p, errors, values))
    resp = _page(req, p["name"], body, "/admin/packages")
    return Response(resp, status=400) if errors else resp


# --- templates -------------------------------------------------------------------------------------
@router.get("/admin/templates")
def templates_list(req):
    auth.require_admin(req)
    used = {r["template"]: r["n"] for r in db.q("SELECT template, COUNT(*) AS n FROM events GROUP BY template")}
    rows = [[f'<a href="/admin/templates/{esc(t["slug"])}">{esc(t["name"])}</a><span class="table__sub">{esc(t["slug"])} · design {esc(t["design"])}</span>',
             esc(t["direction"]), esc(", ".join(catalog.GROUPS.get(g, {}).get("name", g) for g in db.loads(t["groups"], []))),
             _pill("ok", "Active") if t["active"] else _pill("cancelled", "Hidden"), str(used.get(t["slug"], 0)), str(t["sort"]),
             f'<a class="arrow-link" href="/templates/{esc(t["slug"])}/preview" target="_blank" rel="noopener"><span>Preview</span>{i("external")}</a>']
            for t in catalog.templates(active_only=False)]
    body = (page_head("Templates", "Hidden templates disappear from the gallery and the wizard. Events already using them keep working.")
            + _table(["Template", "Direction", "Categories", "Status", ">Events", ">Order", ""], rows))
    return _page(req, "Templates", body, "/admin/templates")


@router.route("/admin/templates/<slug:slug>", methods=("GET", "POST"))
def template_edit(req, slug):
    admin = auth.require_admin(req)
    t = catalog.template(slug)
    if not t:
        raise HTTPError(404)
    errors = {}
    vals = {"name": t["name"], "direction": t["direction"], "description": t["description"],
            "groups": db.loads(t["groups"], []), "tags": ", ".join(db.loads(t["tags"], [])), "sort": t["sort"], "active": bool(t["active"])}
    if req.method == "POST":
        f = Form(req)
        vals = {"name": f.text("name", "Name", required=True, max=60),
                "direction": f.text("direction", "Design direction", required=True, max=80),
                "description": f.text("description", "Description", max=400),
                "groups": [g for g in req.getlist("groups") if g in catalog.GROUPS],
                "tags": req.get("tags"), "sort": f.integer("sort", "Order", min=0, max=1000), "active": f.flag("active")}
        if not vals["groups"]:
            f.error("groups", "Choose at least one event category group.")
        if f.ok:
            tags = [x.strip() for x in vals["tags"].split(",") if x.strip()][:12]
            db.run("""UPDATE templates SET name = ?, direction = ?, description = ?, groups = ?, tags = ?, sort = ?, active = ?,
                      updated_at = ? WHERE slug = ?""",
                   (vals["name"], vals["direction"], vals["description"], db.dumps(vals["groups"]), db.dumps(tags), vals["sort"],
                    1 if vals["active"] else 0, db.now(), slug))
            auth.audit(admin["id"], "template.update", slug, active=vals["active"])
            req.flash("success", f"{vals['name']} saved.")
            return redirect(f"/admin/templates/{slug}")
        errors = f.errors
    groups = "".join(check("groups", esc(g["name"]), k in vals["groups"], value=k) for k, g in catalog.GROUPS.items())
    form = f"""{errors_summary(errors)}<form method="post" class="form box">{csrf(req)}
<div class="form-row form-row--2">{field("name", "Name", vals["name"], required=True, errors=errors)}{field("direction", "Design direction", vals["direction"], required=True, errors=errors)}</div>
{field("description", "Description", vals["description"], type="textarea", errors=errors, attrs={"rows": 3})}
<fieldset><legend>Shown for</legend><div class="admin-checks">{groups}</div>{('<span class="field-error">' + esc(errors["groups"]) + "</span>") if "groups" in errors else ""}</fieldset>
<div class="form-row form-row--3">{field("tags", "Tags (comma separated)", vals["tags"], errors=errors)}{field("sort", "Order", vals["sort"], type="number", errors=errors)}
<div class="field"><span class="label">Visibility</span>{switch("active", "Show in gallery and wizard", vals["active"])}</div></div>
<div class="btn-row"><button class="btn btn--primary" type="submit">Save template</button>
<a class="btn btn--secondary" href="/templates/{esc(slug)}/preview" target="_blank" rel="noopener">{i("eye")}Preview</a></div></form>"""
    body = (f'<p><a class="arrow-link" href="/admin/templates">{i("arrow-left")}<span>All templates</span></a></p>'
            + page_head(t["name"], f"Renderer <span class=mono>{esc(t['design'])}</span>. Layout and styling live in code; names and visibility are managed here.")
            + form)
    resp = _page(req, t["name"], body, "/admin/templates")
    return Response(resp, status=400) if errors else resp


# --- categories ------------------------------------------------------------------------------------
def _category_fields(vals: dict, errors: dict, new: bool) -> str:
    slug_field = field("slug", "Slug (used in links, can't change later)", vals.get("slug", ""), required=True, errors=errors,
                       attrs={"pattern": "[a-z0-9-]+", "maxlength": 60}) if new else ""
    return f"""<div class="form-row form-row--2">{slug_field}{field("name", "Name", vals.get("name", ""), required=True, errors=errors)}
{select("group_slug", "Group", [(k, g["name"]) for k, g in catalog.GROUPS.items()], vals.get("group_slug", "weddings"), required=True, errors=errors)}
{field("sort", "Order", vals.get("sort", 0), type="number", errors=errors)}</div>
{field("description", "Description", vals.get("description", ""), errors=errors)}
{field("features", "Feature hints (comma separated)", vals.get("features", ""), errors=errors, hint="Known hints: family_sides, multi_function, seating, menu, registry")}
{switch("active", "Available for new events", bool(vals.get("active", True)))}"""


def _category_vals(req, f: Form, new: bool) -> dict:
    vals = {"name": f.text("name", "Name", required=True, max=60),
            "group_slug": f.choice("group_slug", catalog.GROUPS.keys(), "Group", required=True),
            "sort": f.integer("sort", "Order", min=0, max=1000), "description": f.text("description", "Description", max=300),
            "features": req.get("features"), "active": f.flag("active")}
    if new:
        slug = f.text("slug", "Slug", required=True, max=60).lower()
        vals["slug"] = slug
        if slug and not SLUG_RE.match(slug):
            f.error("slug", "Use lower-case letters, numbers and hyphens.")
        elif slug and catalog.category(slug):
            f.error("slug", "That slug is already used.")
    return vals


@router.route("/admin/categories", methods=("GET", "POST"))
def categories(req):
    admin = auth.require_admin(req)
    errors, vals = {}, {"active": True}
    if req.method == "POST":
        f = Form(req)
        vals = _category_vals(req, f, new=True)
        if f.ok:
            feats = [x.strip() for x in vals["features"].split(",") if x.strip()]
            db.insert("categories", {"slug": vals["slug"], "name": vals["name"], "group_slug": vals["group_slug"],
                                     "description": vals["description"], "features": db.dumps(feats), "sort": vals["sort"],
                                     "active": 1 if vals["active"] else 0})
            auth.audit(admin["id"], "category.create", vals["slug"])
            req.flash("success", f"{vals['name']} added.")
            return redirect("/admin/categories")
        errors = f.errors
    used = {r["category"]: r["n"] for r in db.q("SELECT category, COUNT(*) AS n FROM events GROUP BY category")}
    rows = [[f'<a href="/admin/categories/{esc(c["slug"])}">{esc(c["name"])}</a><span class="table__sub">{esc(c["slug"])}</span>',
             esc(catalog.GROUPS.get(c["group_slug"], {}).get("name", c["group_slug"])), esc(", ".join(db.loads(c["features"], [])) or "—"),
             _pill("ok", "Active") if c["active"] else _pill("cancelled", "Hidden"), str(used.get(c["slug"], 0)), str(c["sort"])]
            for c in catalog.categories(active_only=False)]
    body = (page_head("Event categories", "Categories drive the wizard's form hints and the category pages.")
            + _table(["Category", "Group", "Hints", "Status", ">Events", ">Order"], rows)
            + f'<section class="box" style="margin-top:var(--gap)" id="add"><div class="box__head"><h2>Add a category</h2></div>'
              f'{errors_summary(errors)}<form method="post" class="form" action="/admin/categories#add">{csrf(req)}{_category_fields(vals, errors, True)}'
              f'<div><button class="btn btn--primary" type="submit">Add category</button></div></form></section>')
    resp = _page(req, "Categories", body, "/admin/categories")
    return Response(resp, status=400) if errors else resp


@router.route("/admin/categories/<slug:slug>", methods=("GET", "POST"))
def category_edit(req, slug):
    admin = auth.require_admin(req)
    c = catalog.category(slug)
    if not c:
        raise HTTPError(404)
    errors = {}
    vals = {"name": c["name"], "group_slug": c["group_slug"], "sort": c["sort"], "description": c["description"],
            "features": ", ".join(db.loads(c["features"], [])), "active": bool(c["active"])}
    if req.method == "POST":
        f = Form(req)
        vals = _category_vals(req, f, new=False)
        if f.ok:
            feats = [x.strip() for x in vals["features"].split(",") if x.strip()]
            db.run("UPDATE categories SET name = ?, group_slug = ?, description = ?, features = ?, sort = ?, active = ? WHERE slug = ?",
                   (vals["name"], vals["group_slug"], vals["description"], db.dumps(feats), vals["sort"], 1 if vals["active"] else 0, slug))
            auth.audit(admin["id"], "category.update", slug)
            req.flash("success", f"{vals['name']} saved.")
            return redirect(f"/admin/categories/{slug}")
        errors = f.errors
    body = (f'<p><a class="arrow-link" href="/admin/categories">{i("arrow-left")}<span>All categories</span></a></p>'
            + page_head(c["name"], f"Slug <span class=mono>{esc(slug)}</span>")
            + f'{errors_summary(errors)}<form method="post" class="form box">{csrf(req)}{_category_fields(vals, errors, False)}'
              f'<div><button class="btn btn--primary" type="submit">Save category</button></div></form>')
    resp = _page(req, c["name"], body, "/admin/categories")
    return Response(resp, status=400) if errors else resp


# --- email templates -------------------------------------------------------------------------------
_VARS = re.compile(r"\{\{\{?\s*(\w+)\s*\}?\}\}")


def sample_vars() -> dict:
    base = config.BASE_URL
    dash = f"{base}/dashboard/events/sample"
    stats = {"invited": 150, "attending": 86, "declined": 9, "pending": 55, "plus_ones": 14, "children": 6, "headcount": 106}
    return {
        "first_name": "Thandi", "name": "Thandi", "event_name": "Sarah & John's Wedding", "hosts": "Sarah & John",
        "event_date": "Saturday, 12 December 2026", "start_time": "14:00", "venue_name": "The Glasshouse",
        "venue_address": "12 Oak Avenue, Johannesburg", "public_url": f"{base}/events/sarah-and-john",
        "dashboard_url": dash, "rsvp_url": dash + "/rsvps", "share_url": dash + "/share", "reports_url": dash + "/reports",
        "seating_url": dash + "/seating", "comms_url": dash + "/communications", "remind_url": dash + "/communications",
        "verify_url": f"{base}/verify/sample", "reset_url": f"{base}/reset-password/sample", "receipt_url": f"{base}/dashboard/billing",
        "guest_first": "Lerato", "guest_name": "Lerato Dlamini", "invite_url": f"{base}/events/sarah-and-john/i/sample",
        "unsubscribe_url": f"{base}/events/sarah-and-john/u/sample", "deadline": "Friday, 20 November 2026",
        "package": "Premium Experience", "amount": "R12,999.00", "invoice_no": "AUR-2026-0001", "order_ref": "ord_sample",
        "status_text": "is attending", "attending": 86, "declined": 9, "pending": 55, "completion": 63, "new_count": 12,
        "days_to_go": "26 days to go", "tables": 15, "seated": 142, "days_text": "7 days to go", "days_text_lower": "in 7 days",
        "hosting_until": "Saturday, 11 September 2027", "inviter": "Thandi Mokoena", "ref": "SR-1042", "priority_note": "",
        "message": "Could you help me change my event date?", "subject": "A note from Sarah & John",
        "message_html": "<p style='margin:0 0 18px'>We can't wait to celebrate with you.</p>",
        "details": "<table role='presentation' cellpadding='0' cellspacing='0' style='margin:0 0 18px'><tr><td style='padding:6px 12px 6px 0;color:#625D5E'>Meal</td><td>Roast lamb</td></tr></table>",
        "summary_table": notify.summary_table_html(stats),
        "steps": notify.steps_html([("Send your invitations", "150 guests haven't been sent their invitation yet. Send them on WhatsApp, one tap each.",
                                     dash + "/share/whatsapp", "Start sending")]),
    }


def _template_vars(*texts: str) -> list[str]:
    seen = []
    for t in texts:
        for m in _VARS.finditer(t or ""):
            if m.group(1) not in seen:
                seen.append(m.group(1))
    return seen


def _preview_vars(subject: str, body: str) -> dict:
    v = sample_vars()
    for name in _template_vars(subject, body):
        v.setdefault(name, f"[{name}]")
    return v


def _sandboxed(html: str) -> Response:
    r = Response(html)
    r.header("Content-Security-Policy", "sandbox; default-src 'none'; img-src * data:; style-src 'unsafe-inline'")
    r.header("X-Frame-Options", "SAMEORIGIN")
    r.header("Cache-Control", "no-store")
    return r


@router.get("/admin/emails")
def emails_list(req):
    auth.require_admin(req)
    sent = {r["template_key"]: r["n"] for r in db.q("SELECT template_key, COUNT(*) AS n FROM email_logs WHERE status = 'sent' GROUP BY template_key")}
    sections = []
    for aud, title in (("organiser", "To organisers"), ("guest", "To guests"), ("system", "System")):
        rows = [[f'<a href="/admin/emails/{esc(t["key"])}">{esc(t["name"])}</a><span class="table__sub mono">{esc(t["key"])}</span>',
                 esc(t["subject"]), _pill("ok", "On") if t["active"] else _pill("cancelled", "Off"), str(sent.get(t["key"], 0)),
                 esc(fmt_dt(t["updated_at"]))]
                for t in db.q("SELECT * FROM email_templates WHERE audience = ? ORDER BY name", (aud,))]
        if rows:
            sections.append(f'<section class="box" style="margin-bottom:var(--gap)"><div class="box__head"><h2>{title}</h2></div>'
                            f'{_table(["Email", "Subject", "Status", ">Sent", "Last edited"], rows)}</section>')
    provider = esc(config.EMAIL_PROVIDER)
    note = (f'<div class="notice" style="margin-bottom:16px">{i("info")}<div>Delivery provider: <b class="mono">{provider}</b>. '
            + ("Development mode: messages are written to the outbox folder, nothing is sent. Set EMAIL_PROVIDER and RESEND_API_KEY to send for real."
               if config.EMAIL_PROVIDER == "outbox" else "Messages are delivered through this provider.") + "</div></div>")
    body = page_head("Email templates", "Edit the wording of every automatic email. Switched-off templates are logged as skipped.") + note + "".join(sections)
    return _page(req, "Email templates", body, "/admin/emails")


@router.route("/admin/emails/<key>", methods=("GET", "POST"))
def email_edit(req, key):
    admin = auth.require_admin(req)
    t = mail.template(key)
    if not t:
        raise HTTPError(404)
    errors = {}
    subject, body_txt, active = t["subject"], t["body"], bool(t["active"])
    if req.method == "POST":
        f = Form(req)
        subject = f.text("subject", "Subject", required=True, max=200)
        body_txt = (req.form.get("body") or [""])[0].replace("\r\n", "\n").strip()
        if not body_txt:
            f.error("body", "Body is required.")
        elif len(body_txt) > 10000:
            f.error("body", "Body must be 10,000 characters or fewer.")
        active = f.flag("active")
        if f.ok:
            db.run("UPDATE email_templates SET subject = ?, body = ?, active = ?, updated_at = ? WHERE key = ?",
                   (subject, body_txt, 1 if active else 0, db.now(), key))
            auth.audit(admin["id"], "email_template.update", key, active=active)
            req.flash("success", "Email template saved.")
            return redirect(f"/admin/emails/{key}")
        errors = f.errors
    default = mail.DEFAULT_TEMPLATES.get(key)
    variables = _template_vars(default[2] + default[3] if default else "", subject, body_txt)
    var_list = "".join(f'<li><code class="mono">{{{{{esc(v)}}}}}</code></li>' for v in variables) or "<li>None</li>"
    reset = (_post_button(f"/admin/emails/{key}/reset", "Restore default wording", req, "btn btn--ghost btn--sm",
                          "Replace the current subject and body with the original wording?") if default else "")
    form = f"""{errors_summary(errors)}<form method="post" class="form" id="email-form">{csrf(req)}
{field("subject", "Subject", subject, required=True, errors=errors)}
{field("body", "Body", body_txt, type="textarea", required=True, errors=errors, attrs={"rows": 16, "spellcheck": "true"},
       hint="Blank lines start new paragraphs. Lines starting with '- ' become a list. A button is written as [button: Label | {{url}}].")}
{switch("active", "Send this email", active)}
<div class="btn-row"><button class="btn btn--primary" type="submit">Save</button>
<button class="btn btn--secondary" type="submit" formaction="/admin/emails/{esc(key)}/preview" formtarget="email-preview" formnovalidate>{i("eye")}Preview changes</button>
<button class="btn btn--secondary" type="submit" formaction="/admin/emails/{esc(key)}/test" formnovalidate>{i("send")}Send test to me</button></div></form>"""
    body = (f'<p><a class="arrow-link" href="/admin/emails">{i("arrow-left")}<span>All email templates</span></a></p>'
            + page_head(t["name"], f"<span class=mono>{esc(key)}</span> · to {esc(t['audience'])}s", reset)
            + f'<div class="cols cols--even"><div class="stack"><section class="box">{form}</section>'
              f'<section class="box"><div class="box__head"><h2>Variables</h2><span class="tiny muted">Filled in when the email is sent</span></div>'
              f'<ul class="admin-vars">{var_list}</ul></section></div>'
              f'<section class="box"><div class="box__head"><h2>Preview</h2><span class="tiny muted">Sample data</span></div>'
              f'<iframe class="admin-frame" name="email-preview" title="Email preview" sandbox src="/admin/emails/{esc(key)}/preview"></iframe></section></div>')
    resp = _page(req, t["name"], body, "/admin/emails")
    return Response(resp, status=400) if errors else resp


@router.route("/admin/emails/<key>/preview", methods=("GET", "POST"))
def email_preview(req, key):
    auth.require_admin(req)
    t = mail.template(key)
    if not t:
        raise HTTPError(404)
    subject = req.get("subject") if req.method == "POST" else t["subject"]
    body_txt = ((req.form.get("body") or [""])[0].replace("\r\n", "\n") if req.method == "POST" else t["body"]) or t["body"]
    msg = mail.compose(key, _preview_vars(subject, body_txt), subject_override=subject or t["subject"], body_override=body_txt)
    head = (f'<div style="font:13px/1.5 Helvetica,Arial,sans-serif;padding:10px 14px;background:#fff;border-bottom:1px solid #eee">'
            f'<b>Subject:</b> {esc(msg["subject"])}</div>')
    return _sandboxed(msg["html"].replace("<body style=\"margin:0;padding:0;background:#F5F5F4\">",
                                          "<body style=\"margin:0;padding:0;background:#F5F5F4\">" + head, 1))


@router.post("/admin/emails/<key>/test")
def email_test(req, key):
    admin = auth.require_admin(req)
    t = mail.template(key)
    if not t:
        raise HTTPError(404)
    subject = req.get("subject") or t["subject"]
    body_txt = (req.form.get("body") or [""])[0].replace("\r\n", "\n").strip() or t["body"]
    vars = {**_preview_vars(subject, body_txt), "first_name": mail.first_name(admin["name"])}
    result = mail.send(admin["email"], key, vars, user_id=admin["id"], subject_override="[Test] " + subject, body_override=body_txt)
    auth.audit(admin["id"], "email_template.test", key, status=result["status"])
    if result["status"] == "sent":
        req.flash("success", f"Test sent to {admin['email']}.")
    else:
        req.flash("error", f"Test {result['status']}: {result['error'] or 'see the email log'}")
    return redirect(f"/admin/emails/{key}")


@router.post("/admin/emails/<key>/reset")
def email_reset(req, key):
    admin = auth.require_admin(req)
    default = mail.DEFAULT_TEMPLATES.get(key)
    if not default:
        raise HTTPError(404)
    db.run("UPDATE email_templates SET subject = ?, body = ?, updated_at = ? WHERE key = ?", (default[2], default[3], db.now(), key))
    auth.audit(admin["id"], "email_template.reset", key)
    req.flash("success", "Default wording restored.")
    return redirect(f"/admin/emails/{key}")


# --- email log / outbox ----------------------------------------------------------------------------
@router.get("/admin/outbox")
def outbox(req):
    auth.require_admin(req)
    q, status, audience, tkey = req.arg("q"), req.arg("status"), req.arg("audience"), req.arg("template")
    where, params = ["1 = 1"], []
    if q:
        where.append("(l.to_email LIKE ? OR l.subject LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if status in ("sent", "failed", "skipped"):
        where.append("l.status = ?")
        params.append(status)
    if audience in ("organiser", "guest", "system"):
        where.append("l.audience = ?")
        params.append(audience)
    if tkey:
        where.append("l.template_key = ?")
        params.append(tkey)
    w = " AND ".join(where)
    total = db.val(f"SELECT COUNT(*) FROM email_logs l WHERE {w}", params, 0)
    offset, pager = _pager(req, total)
    rows = db.q(f"""SELECT l.*, e.uid AS event_uid, e.name AS event_name FROM email_logs l LEFT JOIN events e ON e.id = l.event_id
                    WHERE {w} ORDER BY l.created_at DESC, l.id DESC LIMIT ? OFFSET ?""", params + [PER_PAGE, offset])
    table = _table(["Sent", "To", "Email", "Event", "Status", "Provider"], [[
        esc(fmt_dt(r["created_at"])), esc(r["to_email"]) + f'<span class="table__sub">{esc(r["audience"])}</span>',
        f'<a href="/admin/outbox/{r["id"]}">{esc(r["subject"])}</a><span class="table__sub mono">{esc(r["template_key"])}</span>',
        _event_link(r["event_uid"], r["event_name"]) if r["event_uid"] else "—", _pill(r["status"]), esc(r["provider"])] for r in rows],
        "No emails match these filters.")
    keys = [(r["key"], r["name"]) for r in db.q("SELECT key, name FROM email_templates ORDER BY name")]
    controls = (_search(q, "Recipient or subject")
                + _sel("status", "Status", [("", "Any status"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], status)
                + _sel("audience", "Audience", [("", "Everyone"), ("organiser", "Organisers"), ("guest", "Guests")], audience)
                + _sel("template", "Template", [("", "Any email")] + keys, tkey))
    body = page_head("Email log", "Every email the platform has tried to send, with its delivery result.") + _filters(req, controls) + table + pager
    return _page(req, "Email log", body, "/admin/outbox")


_REF_RE = re.compile(r"^[A-Za-z0-9._+-]{6,80}$")


@router.get("/admin/outbox/<int:log_id>")
def outbox_detail(req, log_id):
    auth.require_admin(req)
    r = db.one("""SELECT l.*, e.uid AS event_uid, e.name AS event_name FROM email_logs l
                  LEFT JOIN events e ON e.id = l.event_id WHERE l.id = ?""", (log_id,))
    if not r:
        raise HTTPError(404)
    has_file = bool(r["outbox_file"]) and bool(_REF_RE.match(r["outbox_file"])) and (config.OUTBOX_DIR / f"{r['outbox_file']}.html").is_file()
    frame = (f'<iframe class="admin-frame" title="Stored email" sandbox src="/admin/outbox/{log_id}/view"></iframe>' if has_file
             else '<div class="empty"><p>The message body is only stored for the development outbox provider.</p></div>')
    info = f"""<dl class="dl"><dt>To</dt><dd>{esc(r['to_email'])}</dd><dt>Audience</dt><dd>{esc(r['audience'])}</dd>
<dt>Template</dt><dd><a class="text-link" href="/admin/emails/{esc(r['template_key'])}">{esc(r['template_key'])}</a></dd>
<dt>Event</dt><dd>{_event_link(r['event_uid'], r['event_name']) if r['event_uid'] else '—'}</dd>
<dt>Status</dt><dd>{_pill(r['status'])}</dd><dt>Provider</dt><dd>{esc(r['provider'])} · {esc(r['provider_id'] or '—')}</dd>
<dt>Error</dt><dd>{esc(r['error'] or '—')}</dd><dt>Batch</dt><dd class="mono">{esc(r['batch_id'] or '—')}</dd>
<dt>Created</dt><dd>{esc(fmt_dt(r['created_at']))}</dd></dl>"""
    body = (f'<p><a class="arrow-link" href="/admin/outbox">{i("arrow-left")}<span>Email log</span></a></p>' + page_head(r["subject"])
            + f'<div class="cols cols--2"><section class="box">{frame}</section><section class="box">{info}</section></div>')
    return _page(req, "Email", body, "/admin/outbox")


@router.get("/admin/outbox/<int:log_id>/view")
def outbox_view(req, log_id):
    auth.require_admin(req)
    r = db.one("SELECT outbox_file FROM email_logs WHERE id = ?", (log_id,))
    ref = r["outbox_file"] if r else None
    if not ref or not _REF_RE.match(ref):
        raise HTTPError(404)
    path = (config.OUTBOX_DIR / f"{ref}.html").resolve()
    try:
        path.relative_to(config.OUTBOX_DIR.resolve())
    except ValueError:
        raise HTTPError(404)
    if not path.is_file():
        raise HTTPError(404)
    return _sandboxed(path.read_text(encoding="utf-8"))


# --- support ---------------------------------------------------------------------------------------
SUPPORT_STATUSES = [("open", "Open"), ("in_progress", "In progress"), ("resolved", "Resolved")]
PRIORITIES = [("0", "Normal"), ("1", "High"), ("2", "Urgent")]


@router.get("/admin/support")
def support_list(req):
    auth.require_admin(req)
    status, q = req.arg("status"), req.arg("q")
    where, params = ["1 = 1"], []
    if status in dict(SUPPORT_STATUSES):
        where.append("s.status = ?")
        params.append(status)
    if q:
        where.append("(s.email LIKE ? OR s.name LIKE ? OR s.message LIKE ?)")
        params += [f"%{q}%"] * 3
    w = " AND ".join(where)
    total = db.val(f"SELECT COUNT(*) FROM support_requests s WHERE {w}", params, 0)
    offset, pager = _pager(req, total)
    rows = db.q(f"""SELECT s.* FROM support_requests s WHERE {w}
                    ORDER BY CASE s.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END, s.priority DESC, s.created_at DESC
                    LIMIT ? OFFSET ?""", params + [PER_PAGE, offset])
    pr = dict(PRIORITIES)
    table = _table(["Request", "From", "Priority", "Status", "Received"], [[
        f'<a href="/admin/support/{s["id"]}">SR-{s["id"]}: {esc(s["topic"].replace("_", " ").capitalize())}</a><span class="table__sub">{esc(s["message"][:90])}</span>',
        esc(s["name"]) + f'<span class="table__sub">{esc(s["email"])}</span>',
        _pill("failed" if s["priority"] >= 2 else ("pending" if s["priority"] == 1 else "info"), pr.get(str(s["priority"]), "Normal")),
        _pill(s["status"], dict(SUPPORT_STATUSES).get(s["status"])), esc(fmt_dt(s["created_at"]))] for s in rows], "No support requests.")
    controls = _search(q, "Name, email or message") + _sel("status", "Status", [("", "Any status")] + SUPPORT_STATUSES, status)
    body = page_head("Support", "Requests from the contact form and dashboards. Open and urgent requests come first.") + _filters(req, controls) + table + pager
    return _page(req, "Support", body, "/admin/support")


@router.route("/admin/support/<int:req_id>", methods=("GET", "POST"))
def support_detail(req, req_id):
    admin = auth.require_admin(req)
    s = db.one("SELECT * FROM support_requests WHERE id = ?", (req_id,))
    if not s:
        raise HTTPError(404)
    if req.method == "POST":
        f = Form(req)
        status = f.choice("status", dict(SUPPORT_STATUSES), "Status", required=True)
        priority = f.choice("priority", dict(PRIORITIES), "Priority", default="0")
        notes = f.text("admin_notes", "Notes", max=5000)
        if f.ok:
            db.run("UPDATE support_requests SET status = ?, priority = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
                   (status, int(priority), notes, db.now(), req_id))
            auth.audit(admin["id"], "support.update", f"SR-{req_id}", status=status, priority=priority)
            req.flash("success", "Support request updated.")
        else:
            req.flash("error", next(iter(f.errors.values())))
        return redirect(f"/admin/support/{req_id}")
    ev = events.by_id(s["event_id"]) if s["event_id"] else None
    info = f"""<dl class="dl"><dt>From</dt><dd>{esc(s['name'])}<br>{_user_link(s['user_id'], s['email'])}</dd>
<dt>Topic</dt><dd>{esc(s['topic'])}</dd><dt>Event</dt><dd>{_event_link(ev['uid'], ev['name']) if ev else '—'}</dd>
<dt>Received</dt><dd>{esc(fmt_dt(s['created_at']))}</dd><dt>Updated</dt><dd>{esc(fmt_dt(s['updated_at']))}</dd></dl>"""
    form = f"""<form method="post" class="form">{csrf(req)}<div class="form-row form-row--2">
{select("status", "Status", SUPPORT_STATUSES, s["status"], required=True)}{select("priority", "Priority", PRIORITIES, str(s["priority"]))}</div>
{field("admin_notes", "Internal notes (never shown to the customer)", s["admin_notes"], type="textarea", attrs={"rows": 6})}
<div class="btn-row"><button class="btn btn--primary" type="submit">Save</button>
<a class="btn btn--secondary" href="mailto:{esc(s['email'])}?subject={esc('Re: your request SR-' + str(req_id))}">{i("mail")}Reply by email</a></div></form>"""
    body = (f'<p><a class="arrow-link" href="/admin/support">{i("arrow-left")}<span>Support queue</span></a></p>'
            + page_head(f"SR-{req_id}", _pill(s["status"], dict(SUPPORT_STATUSES).get(s["status"])))
            + f'<div class="cols cols--2"><div class="stack"><section class="box"><div class="box__head"><h2>Message</h2></div>'
              f'<p style="white-space:pre-wrap">{esc(s["message"])}</p></section><section class="box">{form}</section></div>'
              f'<section class="box">{info}</section></div>')
    return _page(req, f"SR-{req_id}", body, "/admin/support")


# --- audit -----------------------------------------------------------------------------------------
@router.get("/admin/audit")
def audit_log(req):
    auth.require_admin(req)
    action, q = req.arg("action"), req.arg("q")
    where, params = ["1 = 1"], []
    if action:
        where.append("a.action LIKE ?")
        params.append(f"{action}%")
    if q:
        where.append("(u.email LIKE ? OR a.target LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    w = " AND ".join(where)
    base = "FROM audit_log a LEFT JOIN users u ON u.id = a.actor_id"
    total = db.val(f"SELECT COUNT(*) {base} WHERE {w}", params, 0)
    offset, pager = _pager(req, total)
    rows = db.q(f"SELECT a.*, u.email {base} WHERE {w} ORDER BY a.created_at DESC, a.id DESC LIMIT ? OFFSET ?", params + [PER_PAGE, offset])
    prefixes = [(r["p"], r["p"].capitalize()) for r in db.q("SELECT DISTINCT substr(action, 1, instr(action || '.', '.') - 1) AS p FROM audit_log ORDER BY p")]
    table = _table(["When", "Who", "Action", "Target", "Details"], [[
        esc(fmt_dt(a["created_at"])), _user_link(a["actor_id"], a["email"]) if a["actor_id"] else '<span class="muted">System</span>',
        f'<span class="mono small">{esc(a["action"])}</span>', esc(a["target"]),
        f'<span class="tiny muted mono">{esc(a["meta"] if a["meta"] != "{}" else "")}</span>'] for a in rows], "No audit entries.")
    controls = _search(q, "Actor email or target") + _sel("action", "Area", [("", "All areas")] + prefixes, action)
    body = page_head("Audit log", "Who changed what, and when.") + _filters(req, controls) + table + pager
    return _page(req, "Audit log", body, "/admin/audit")
