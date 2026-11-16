"""Registration, login, logout, password reset, email verification and the account page."""
from __future__ import annotations

import json

from .. import auth, config, db
from ..icons import i
from ..services import email as mail
from ..web import Response, download, esc, redirect, router, safe_next, url
from . import forms
from .forms import Form, csrf, errors_summary, field, honeypot
from .layout import bare
from .shell import account_page, page_head

AUTH_QUOTES = [
    "One event. One platform. One link.",
    "Invitations, RSVPs, menus and seating, organised in one place.",
]


def auth_layout(req, title: str, inner: str, quote: str = AUTH_QUOTES[0]) -> str:
    body = f"""<div class="auth"><div class="auth__form"><div>{inner}</div></div>
<div class="auth__art"><div class="grid-texture"></div><div class="auth__quote">
<p class="serif">{esc(quote)}</p><p class="muted" style="margin-top:18px">Everything for your event, in one place: the website, RSVPs, guest list, seating, menus and reports.</p>
<div class="glass panel" style="margin-top:32px;display:grid;gap:10px;max-width:360px">
<div class="row row--between small"><span>RSVPs</span><b class="mono">118 / 150</b></div>
<div class="progress"><span style="width:79%"></span></div>
<div class="row row--between tiny muted"><span>94 attending</span><span>24 declined</span><span>32 to reply</span></div></div>
</div></div></div>"""
    return bare(req, title, body)


def login_session(resp: Response, req, user_id: int) -> Response:
    token = auth.create_session(user_id, req.ip, req.headers.get("user-agent", ""))
    resp.set_cookie(auth.SESSION_COOKIE, token, max_age=config.SESSION_DAYS * 86400)
    return resp


def send_verification(user) -> None:
    token = auth.issue_token(user["id"], "verify", 48)
    mail.send(user["email"], "verify_email", {"first_name": mail.first_name(user["name"]),
                                              "verify_url": f"{config.BASE_URL}/verify/{token}"},
              user_id=user["id"])


# --- register --------------------------------------------------------------------------------
@router.route("/register", methods=("GET", "POST"))
def register(req):
    nxt = safe_next(req.arg("next") or req.get("next"), "/create")
    if req.user:
        return redirect(nxt)
    f = Form(req)
    if req.method == "POST":
        if req.get("website"):
            return redirect("/")
        if auth.rate_limited(f"register:{req.ip}", 10, 3600):
            f.error("email", "Too many sign-ups from this connection. Please try again in an hour.")
        name = f.text("name", "Your name", required=True, max=120, min=2)
        email = f.email("email", required=True)
        pw = req.get("password")
        if not pw:
            f.error("password", "Choose a password.")
        else:
            for p in auth.password_problems(pw, email):
                f.error("password", p)
                break
        if pw and req.get("password_confirm") != pw:
            f.error("password_confirm", "The passwords don't match.")
        if not f.flag("terms"):
            f.error("terms", "Please accept the terms and privacy notice to create an account.")
        if email and not f.errors.get("email") and db.one("SELECT 1 FROM users WHERE email = ?", (email,)):
            f.error("email", "An account with this email already exists. Log in or reset your password.")
        if f.ok:
            uid = db.insert("users", {"email": email, "name": name, "password_hash": auth.hash_password(pw),
                                      "role": "customer", "marketing_consent": 1 if req.get("marketing") else 0,
                                      "created_at": db.now()})
            user = db.one("SELECT * FROM users WHERE id = ?", (uid,))
            mail.send(email, "welcome", {"first_name": mail.first_name(name)}, user_id=uid)
            send_verification(user)
            auth.audit(uid, "user.register", email)
            req.flash("success", f"Welcome, {mail.first_name(name)}. We've sent a link to confirm your email.")
            return login_session(redirect(nxt), req, uid)
    d = f.data
    inner = f"""<h1>Create your account</h1><p class="lead" style="margin:10px 0 28px;font-size:1rem">Save your event as you go and come back any time. Already registered? <a class="text-link" href="{url('/login', next=nxt)}">Log in</a>.</p>
<form class="form" method="post" novalidate>{csrf(req)}{honeypot()}<input type="hidden" name="next" value="{esc(nxt)}">
{errors_summary(f.errors)}
{field("name", "Your name", d.get("name", ""), required=True, errors=f.errors, attrs={"autocomplete": "name"})}
{field("email", "Email", d.get("email", ""), type="email", required=True, errors=f.errors, attrs={"autocomplete": "email"})}
{field("password", "Password", "", type="password", required=True, errors=f.errors, hint="At least 10 characters, with upper- and lower-case letters and a number.", attrs={"autocomplete": "new-password"})}
{field("password_confirm", "Confirm password", "", type="password", required=True, errors=f.errors, attrs={"autocomplete": "new-password"})}
<div class="field{' has-error' if 'terms' in f.errors else ''}">{forms.check("terms", 'I accept the <a class="text-link" href="/terms" target="_blank">terms of service</a> and the <a class="text-link" href="/privacy" target="_blank">privacy notice</a>.', bool(d.get("terms")))}</div>
{forms.check("marketing", "Send me occasional tips and new templates (optional).", bool(req.get("marketing")))}
<button class="btn btn--primary btn--lg btn--block" type="submit">Create account {i("arrow", "i--arrow")}</button></form>"""
    return auth_layout(req, "Create your account", inner)


# --- login / logout ---------------------------------------------------------------------------
@router.route("/login", methods=("GET", "POST"))
def login(req):
    nxt = safe_next(req.arg("next") or req.get("next"), "/dashboard")
    if req.user:
        return redirect(nxt)
    f = Form(req)
    if req.method == "POST":
        email = f.email("email", required=True)
        pw = req.get("password")
        key = f"login:{req.ip}:{email}"
        if auth.rate_limited(key, 8, 900) or auth.rate_limited(f"login-ip:{req.ip}", 40, 900):
            f.error("email", "Too many attempts. Wait 15 minutes or reset your password.")
        elif f.ok:
            user = db.one("SELECT * FROM users WHERE email = ?", (email,))
            if user and auth.verify_password(pw, user["password_hash"]):
                if user["status"] != "active":
                    f.error("email", "This account is suspended. Contact support for help.")
                else:
                    auth.reset_rate(key)
                    return login_session(redirect(nxt), req, user["id"])
            else:
                f.error("password", "That email and password don't match an account.")
    inner = f"""<h1>Welcome back</h1><p class="lead" style="margin:10px 0 28px;font-size:1rem">Log in to continue your event. New here? <a class="text-link" href="{url('/register', next=nxt if nxt != '/dashboard' else '')}">Create an account</a>.</p>
<form class="form" method="post" novalidate>{csrf(req)}<input type="hidden" name="next" value="{esc(nxt)}">{errors_summary(f.errors)}
{field("email", "Email", f.data.get("email", ""), type="email", required=True, errors=f.errors, attrs={"autocomplete": "email", "autofocus": True})}
{field("password", "Password", "", type="password", required=True, errors=f.errors, attrs={"autocomplete": "current-password"})}
<div class="row row--between"><a class="text-link small" href="/forgot-password">Forgot your password?</a></div>
<button class="btn btn--primary btn--lg btn--block" type="submit">Log in {i("arrow", "i--arrow")}</button></form>"""
    return auth_layout(req, "Log in", inner, AUTH_QUOTES[1])


@router.post("/logout")
def logout(req):
    auth.destroy_session(req.cookies.get(auth.SESSION_COOKIE, ""))
    resp = redirect("/")
    resp.set_cookie(auth.SESSION_COOKIE, "", max_age=0)
    return resp


# --- password reset ---------------------------------------------------------------------------
@router.route("/forgot-password", methods=("GET", "POST"))
def forgot(req):
    sent = False
    f = Form(req)
    if req.method == "POST":
        email = f.email("email", required=True)
        if f.ok and not auth.rate_limited(f"forgot:{req.ip}", 6, 3600):
            user = db.one("SELECT * FROM users WHERE email = ?", (email,))
            if user and user["status"] == "active":
                token = auth.issue_token(user["id"], "reset", 1)
                mail.send(email, "password_reset", {"first_name": mail.first_name(user["name"]),
                                                    "reset_url": f"{config.BASE_URL}/reset-password/{token}"},
                          user_id=user["id"])
            sent = True
        elif f.ok:
            sent = True
    if sent:
        inner = (f'<h1>Check your email</h1><p class="lead" style="margin:10px 0 24px;font-size:1rem">If an account exists for '
                 f'<b>{esc(f.data.get("email"))}</b>, we\'ve sent a link to choose a new password. It works once and expires in one hour.</p>'
                 f'<a class="btn btn--secondary" href="/login">Back to log in</a>')
    else:
        inner = f"""<h1>Reset your password</h1><p class="lead" style="margin:10px 0 28px;font-size:1rem">Enter the email you registered with and we'll send you a reset link.</p>
<form class="form" method="post" novalidate>{csrf(req)}{errors_summary(f.errors)}
{field("email", "Email", f.data.get("email", ""), type="email", required=True, errors=f.errors, attrs={"autocomplete": "email"})}
<button class="btn btn--primary btn--lg btn--block" type="submit">Send reset link</button></form>
<p class="small muted" style="margin-top:18px"><a class="text-link" href="/login">Back to log in</a></p>"""
    return auth_layout(req, "Reset your password", inner)


@router.route("/reset-password/<token>", methods=("GET", "POST"))
def reset_password(req, token):
    user_id = auth.peek_token(token, "reset")
    if not user_id:
        inner = ('<h1>This link has expired</h1><p class="lead" style="margin:10px 0 24px;font-size:1rem">Reset links work once '
                 'and last one hour. Request a new one.</p><a class="btn btn--primary" href="/forgot-password">Request a new link</a>')
        return auth_layout(req, "Link expired", inner)
    user = db.one("SELECT * FROM users WHERE id = ?", (user_id,))
    f = Form(req)
    if req.method == "POST":
        pw = req.get("password")
        for p in auth.password_problems(pw, user["email"]):
            f.error("password", p)
            break
        if req.get("password_confirm") != pw:
            f.error("password_confirm", "The passwords don't match.")
        if f.ok and auth.consume_token(token, "reset"):
            db.run("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(pw), user_id))
            auth.destroy_user_sessions(user_id)
            auth.audit(user_id, "user.password_reset", user["email"])
            req.flash("success", "Your password is updated. Log in with your new password.")
            return redirect("/login")
    inner = f"""<h1>Choose a new password</h1><p class="lead" style="margin:10px 0 28px;font-size:1rem">For {esc(user["email"])}. You'll be signed out on other devices.</p>
<form class="form" method="post" novalidate>{csrf(req)}{errors_summary(f.errors)}
{field("password", "New password", "", type="password", required=True, errors=f.errors, hint="At least 10 characters, with upper- and lower-case letters and a number.", attrs={"autocomplete": "new-password"})}
{field("password_confirm", "Confirm new password", "", type="password", required=True, errors=f.errors, attrs={"autocomplete": "new-password"})}
<button class="btn btn--primary btn--lg btn--block" type="submit">Save new password</button></form>"""
    return auth_layout(req, "Choose a new password", inner)


# --- email verification -----------------------------------------------------------------------
@router.get("/verify/<token>")
def verify(req, token):
    user_id = auth.consume_token(token, "verify")
    if user_id:
        db.run("UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?", (db.now(), user_id))
        req.flash("success", "Thank you. Your email address is confirmed.")
        return redirect("/dashboard" if req.user else "/login")
    req.flash("error", "That confirmation link has expired or was already used.")
    return redirect("/account" if req.user else "/login")


@router.post("/account/verify")
def resend_verification(req):
    user = auth.require_user(req)
    if user["email_verified_at"]:
        req.flash("info", "Your email is already confirmed.")
    elif auth.rate_limited(f"verify:{user['id']}", 3, 3600):
        req.flash("error", "We've sent a few links already. Check your spam folder, or try again in an hour.")
    else:
        send_verification(user)
        req.flash("success", f"We've sent a new confirmation link to {user['email']}.")
    return redirect("/account")


# --- account page -----------------------------------------------------------------------------
@router.route("/account", methods=("GET", "POST"))
def account(req):
    user = auth.require_user(req)
    f = Form(req)
    pw = Form(req)
    action = req.get("action")
    if req.method == "POST" and action == "profile":
        name = f.text("name", "Your name", required=True, max=120, min=2)
        phone = f.phone("phone")
        if f.ok:
            db.run("UPDATE users SET name = ?, phone = ?, marketing_consent = ? WHERE id = ?",
                   (name, phone, 1 if req.get("marketing") else 0, user["id"]))
            req.flash("success", "Your details are saved.")
            return redirect("/account")
    if req.method == "POST" and action == "password":
        if not auth.verify_password(req.get("current"), user["password_hash"]):
            pw.error("current", "Your current password isn't right.")
        new = req.get("new")
        for p in auth.password_problems(new, user["email"]):
            pw.error("new", p)
            break
        if pw.ok:
            db.run("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(new), user["id"]))
            db.run("DELETE FROM sessions WHERE user_id = ? AND id != ?",
                   (user["id"], auth._sha(req.cookies.get(auth.SESSION_COOKIE, ""))))
            auth.audit(user["id"], "user.password_change", user["email"])
            req.flash("success", "Password changed. Other devices have been signed out.")
            return redirect("/account")
    if req.method == "POST" and action == "delete":
        if req.get("confirm_email", "").lower() != user["email"].lower():
            req.flash("error", "Type your email address exactly to confirm deletion.")
            return redirect("/account#delete")
        paid = db.val("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'paid'", (user["id"],), 0)
        if paid:
            db.insert("support_requests", {"user_id": user["id"], "name": user["name"], "email": user["email"],
                                           "topic": "privacy", "message": "Account deletion requested (has paid orders; "
                                           "keep invoices for tax records, delete the rest).", "priority": 1,
                                           "created_at": db.now(), "updated_at": db.now()})
            req.flash("info", "We've logged your deletion request. Because you have paid orders, we keep invoices "
                              "for tax law and delete everything else within 30 days.")
            return redirect("/account")
        auth.audit(user["id"], "user.delete", user["email"])
        db.run("DELETE FROM users WHERE id = ?", (user["id"],))
        resp = redirect("/")
        resp.set_cookie(auth.SESSION_COOKIE, "", max_age=0)
        return resp
    verified = (f'<span class="pill pill--ok">Confirmed</span>' if user["email_verified_at"] else
                f'<form method="post" action="/account/verify" class="row">{csrf(req)}<span class="pill pill--pending">Not confirmed</span>'
                f'<button class="btn btn--sm btn--secondary" type="submit">Resend link</button></form>')
    body = page_head("Account", "Your details, password and privacy choices.") + f"""
<div class="cols cols--even">
<section class="box"><div class="box__head"><h2>Your details</h2></div>
<form class="form" method="post" novalidate>{csrf(req)}<input type="hidden" name="action" value="profile">{errors_summary(f.errors)}
{field("name", "Name", f.data.get("name", user["name"]), required=True, errors=f.errors)}
<div class="field"><span class="label">Email</span><div class="row"><span>{esc(user["email"])}</span>{verified}</div></div>
{field("phone", "Phone (optional)", f.data.get("phone", user["phone"] or ""), type="tel", errors=f.errors)}
{forms.check("marketing", "Send me occasional tips and new templates.", bool(user["marketing_consent"]))}
<div><button class="btn btn--primary" type="submit">Save details</button></div></form></section>
<section class="box"><div class="box__head"><h2>Change password</h2></div>
<form class="form" method="post" novalidate>{csrf(req)}<input type="hidden" name="action" value="password">{errors_summary(pw.errors)}
{field("current", "Current password", "", type="password", required=True, errors=pw.errors, attrs={"autocomplete": "current-password"})}
{field("new", "New password", "", type="password", required=True, errors=pw.errors, hint="At least 10 characters, mixed case and a number.", attrs={"autocomplete": "new-password"})}
<div><button class="btn btn--secondary" type="submit">Change password</button></div></form></section>
<section class="box"><div class="box__head"><h2>Your data (POPIA)</h2></div>
<p class="muted small">You can download everything we hold about you and your events, or ask us to delete it. Guest information you add stays private to your events and is never sold or shared for marketing.</p>
<div class="btn-row" style="margin-top:16px"><a class="btn btn--secondary" href="/account/export">{i("download")} Download my data</a><a class="text-link small" href="/privacy">Read the privacy notice</a></div></section>
<section class="box" id="delete"><div class="box__head"><h2>Delete account</h2></div>
<p class="muted small">This removes your account, your events, guest lists and uploads. Published event websites go offline immediately.</p>
<form class="form" method="post" style="margin-top:14px" data-confirm="Delete your account and all events? This can't be undone.">{csrf(req)}<input type="hidden" name="action" value="delete">
{field("confirm_email", "Type your email to confirm", "", type="email")}
<div><button class="btn btn--danger" type="submit">{i("trash")} Delete my account</button></div></form></section>
</div>"""
    return account_page(req, "Account", body, "/account")


@router.get("/account/export")
def export_data(req):
    user = auth.require_user(req)
    out = {"user": {k: user[k] for k in user.keys() if k != "password_hash"}, "events": [], "orders": []}
    for ev in db.q("SELECT * FROM events WHERE owner_id = ?", (user["id"],)):
        e = dict(ev)
        e["guests"] = [dict(g) for g in db.q("SELECT * FROM guests WHERE event_id = ?", (ev["id"],))]
        e["functions"] = [dict(r) for r in db.q("SELECT * FROM event_functions WHERE event_id = ?", (ev["id"],))]
        e["schedule"] = [dict(r) for r in db.q("SELECT * FROM schedule_items WHERE event_id = ?", (ev["id"],))]
        e["tables"] = [dict(r) for r in db.q("SELECT * FROM seating_tables WHERE event_id = ?", (ev["id"],))]
        out["events"].append(e)
    out["orders"] = [dict(o) for o in db.q("SELECT * FROM orders WHERE user_id = ?", (user["id"],))]
    auth.audit(user["id"], "user.export", user["email"])
    return download(json.dumps(out, indent=2, ensure_ascii=False), "aurelia-my-data.json", "application/json")
