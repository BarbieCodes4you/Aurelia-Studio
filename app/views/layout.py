"""Page shells: the marketing site (header, drawer, footer), the app shell (dashboard and admin),
toasts, and the error page."""
from __future__ import annotations

from typing import Optional

from .. import config
from ..icons import i
from ..web import esc

FONTS = ("https://fonts.googleapis.com/css2?family=Geist:wght@300..700&family=Geist+Mono:wght@400..600"
         "&family=Instrument+Serif:ital@0;1&display=swap")

THEME_SCRIPT = """<script>(function(){try{var t=localStorage.getItem('aurelia-theme-v1');
if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}
document.documentElement.classList.add('js');})();</script>"""

BRAND_MARK = """<svg class="brand__mark" viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="bm" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#9F87E6"/><stop offset=".5" stop-color="#E58DB3"/><stop offset="1" stop-color="#F0A77E"/></linearGradient></defs>
<circle cx="12" cy="16" r="8.2" fill="none" stroke="url(#bm)" stroke-width="2"/><circle cx="20" cy="16" r="8.2" fill="none" stroke="url(#bm)" stroke-width="2"/>
<circle cx="16" cy="16" r="1.8" fill="#8B73D8"/></svg>"""

NAV = [
    ("Weddings", "/weddings"),
    ("Baby", "/baby-celebrations"),
    ("Parties", "/parties"),
    ("Other events", "/celebrations"),
    ("Templates", "/templates"),
    ("Pricing", "/pricing"),
    ("How it works", "/how-it-works"),
]


def brand(href: str = "/") -> str:
    first, _, rest = config.BRAND_NAME.partition(" ")
    name = esc(first) + (f' <span class="brand__sub">{esc(rest)}</span>' if rest else "")
    return f'<a class="brand" href="{href}" aria-label="{esc(config.BRAND_NAME)} home">{BRAND_MARK}<span class="brand__name">{name}</span></a>'


def head(title: str, description: str = "", extra: str = "", noindex: bool = False) -> str:
    full = title if config.BRAND_NAME in title else f"{title} · {config.BRAND_NAME}"
    desc = description or config.BRAND_TAGLINE
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!doctype html><html lang="en-ZA" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(full)}</title>
<meta name="description" content="{esc(desc)}">{robots}
<meta property="og:title" content="{esc(full)}"><meta property="og:description" content="{esc(desc)}">
<meta name="theme-color" content="#F8F6FC">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/static/css/app.css"><link rel="stylesheet" href="/static/css/icons.css">
{THEME_SCRIPT}{extra}</head>"""


def toasts(req) -> str:
    items = req.take_flashes() if hasattr(req, "take_flashes") else []
    if not items:
        return '<div class="toasts" aria-live="polite"></div>'
    icon = {"success": "check", "error": "alert", "info": "info"}
    html = "".join(
        f'<div class="toast toast--{esc(k)} glass glass--strong" role="status">{i(icon.get(k, "info"))}'
        f'<span>{esc(m)}</span><button type="button" aria-label="Dismiss" data-dismiss>×</button></div>'
        for k, m in items)
    return f'<div class="toasts" aria-live="polite">{html}</div>'


def theme_toggle() -> str:
    return (f'<button class="btn btn--ghost btn--icon theme-toggle" type="button" data-theme-toggle '
            f'aria-label="Switch light or dark theme">{i("sun", "i--sun")}{i("moon", "i--moon")}</button>')


def header(req, current: str = "") -> str:
    links = "".join(
        f'<li><a href="{href}"{" aria-current=page" if current == href else ""}>{esc(label)}</a></li>'
        for label, href in NAV)
    drawer_links = "".join(
        f'<a href="{href}"{" aria-current=page" if current == href else ""}>{esc(label)}</a>' for label, href in NAV)
    if req.user:
        account = (f'<a class="btn btn--ghost btn--sm" href="/dashboard">My events</a>')
        cta = '<a class="btn btn--primary btn--sm" href="/create">Create your event</a>'
        drawer_acc = '<a class="btn btn--secondary" href="/dashboard">My events</a>'
    else:
        account = '<a class="btn btn--ghost btn--sm" href="/login">Log in</a>'
        cta = '<a class="btn btn--primary btn--sm" href="/create">Create your event</a>'
        drawer_acc = '<a class="btn btn--secondary" href="/login">Log in</a>'
    return f"""<a class="btn btn--primary skip-link" href="#main">Skip to content</a>
<header class="site-header" data-header><div class="site-header__bar">{brand()}
<nav class="nav" aria-label="Main"><ul>{links}</ul></nav>
<div class="header-actions">{theme_toggle()}<span class="hide-sm">{account}</span>{cta}
<button class="btn btn--ghost btn--icon menu-btn" type="button" data-drawer-open aria-label="Open menu" aria-controls="drawer">{i("menu")}</button></div></div></header>
<dialog class="drawer" id="drawer" aria-label="Menu"><div class="drawer__head">{brand()}<button class="btn btn--ghost btn--icon" type="button" data-drawer-close aria-label="Close menu" style="color:inherit">{i("close")}</button></div>
<nav aria-label="Mobile">{drawer_links}</nav><div class="drawer__foot on-dark"><a class="btn btn--primary" href="/create">Create your event</a>{drawer_acc}</div></dialog>"""


def footer() -> str:
    year = __import__("datetime").date.today().year
    wa = config.whatsapp_link()
    social = "".join(
        f'<a href="{esc(href)}" target="_blank" rel="noopener" aria-label="{label}">{i(icon)}</a>'
        for label, href, icon in [("Instagram", config.SOCIAL_INSTAGRAM, "image"), ("Facebook", config.SOCIAL_FACEBOOK, "users"),
                                  ("TikTok", config.SOCIAL_TIKTOK, "music"), ("WhatsApp", wa, "chat")] if href)
    chat = (f'<a class="wa-float" href="{esc(config.whatsapp_link("Hi " + config.BRAND_NAME + ", I have a question about my event."))}" target="_blank" rel="noopener">'
            f'{i("chat")}<span>Chat on WhatsApp</span></a>') if wa else ""
    return f"""<footer class="site-footer on-dark"><div class="container">
<div class="footer-grid"><div class="stack" style="--stack:14px">{brand()}<p class="muted" style="max-width:38ch">{esc(config.BRAND_TAGLINE)} {esc(config.BRAND_LINE)}</p>
<p class="small muted">{esc(config.COMPANY_ADDRESS)}<br><a class="text-link" href="mailto:{esc(config.SUPPORT_EMAIL)}">{esc(config.SUPPORT_EMAIL)}</a></p></div>
<div><h3>Events</h3><ul><li><a href="/weddings">Weddings</a></li><li><a href="/baby-celebrations">Baby celebrations</a></li><li><a href="/parties">Parties</a></li><li><a href="/celebrations">Other events</a></li></ul></div>
<div><h3>Platform</h3><ul><li><a href="/templates">Templates</a></li><li><a href="/pricing">Pricing</a></li><li><a href="/how-it-works">How it works</a></li><li><a href="/help-me-set-up">We'll set it up for you</a></li><li><a href="/faq">FAQ</a></li></ul></div>
<div><h3>Company</h3><ul><li><a href="/contact">Contact &amp; support</a></li><li><a href="/privacy">Privacy (POPIA)</a></li><li><a href="/terms">Terms of service</a></li><li><a href="/refunds">Refund policy</a></li></ul></div></div>
<div class="footer-bottom"><span>© {year} {esc(config.BRAND_NAME)}. Prices in South African Rand, VAT inclusive.</span><div class="socials">{social}</div></div>
<div class="wordmark-giant" aria-hidden="true"><span>A</span>urelia</div></div></footer>{chat}"""


def page(req, title: str, body: str, current: str = "", description: str = "", body_class: str = "site",
         noindex: bool = False, extra_head: str = "") -> str:
    return (head(title, description, extra_head, noindex) +
            f'<body class="{body_class}"><meta name="csrf" content="{esc(req.csrf)}">' + header(req, current) +
            f'<main id="main">{body}</main>' + footer() + toasts(req) +
            '<script src="/static/js/app.js" defer></script></body></html>')


def bare(req, title: str, body: str, noindex: bool = True, body_class: str = "site", extra_head: str = "") -> str:
    """Header without footer (auth pages)."""
    return (head(title, "", extra_head, noindex) + f'<body class="{body_class}"><meta name="csrf" content="{esc(req.csrf)}">'
            + header(req) + f'<main id="main">{body}</main>' + toasts(req)
            + '<script src="/static/js/app.js" defer></script></body></html>')


# --- app shell ---------------------------------------------------------------------------------
def app_shell(req, title: str, body: str, nav_html: str, current_event=None, extra_head: str = "",
              extra_scripts: str = "") -> str:
    user = req.user
    initials = "".join(p[0] for p in (user["name"] or "?").split()[:2]).upper() if user else ""
    return (head(title, "", extra_head, True) +
            f'<body class="app-body"><meta name="csrf" content="{esc(req.csrf)}">'
            f'<a class="btn btn--primary skip-link" href="#main">Skip to content</a><div class="app">'
            f'<aside class="sidebar" aria-label="App">{brand("/dashboard")}{nav_html}'
            f'<div class="sidebar__foot"><div class="row" style="gap:10px;padding:6px 8px">'
            f'<span class="icon-tile" style="width:36px;height:36px;border-radius:50%;font-size:.8rem;font-weight:600">{esc(initials)}</span>'
            f'<span class="small" style="line-height:1.3"><b>{esc(user["name"] if user else "")}</b><br><span class="muted tiny">{esc(user["email"] if user else "")}</span></span></div>'
            f'<form method="post" action="/logout">{_csrf(req)}<button class="side-link" style="width:100%;border:0;background:none;cursor:pointer" type="submit">{i("logout")}Log out</button></form></div></aside>'
            f'<div class="app-main"><header class="topbar">{brand("/dashboard")}<div class="topbar__actions">'
            f'{theme_toggle()}<a class="btn btn--ghost btn--sm" href="/" >View site</a>'
            f'<button class="btn btn--ghost btn--icon menu-btn-app" type="button" data-drawer-open aria-controls="drawer" aria-label="Open menu" style="display:var(--show-menu,inline-flex)">{i("menu")}</button></div></header>'
            f'<dialog class="drawer" id="drawer" aria-label="Menu"><div class="drawer__head">{brand("/dashboard")}'
            f'<button class="btn btn--ghost btn--icon" type="button" data-drawer-close aria-label="Close menu" style="color:inherit">{i("close")}</button></div>'
            f'<div class="app-drawer-nav on-dark" style="padding:12px">{nav_html}'
            f'<form method="post" action="/logout" style="margin-top:12px">{_csrf(req)}<button class="btn btn--secondary btn--block" type="submit">Log out</button></form></div></dialog>'
            f'<main id="main" class="app-content">{body}</main></div></div>{toasts(req)}'
            f'<style>@media (min-width:1024px){{.menu-btn-app{{display:none!important}}}}</style>'
            f'<script src="/static/js/app.js" defer></script>{extra_scripts}</body></html>')


def _csrf(req) -> str:
    return f'<input type="hidden" name="_csrf" value="{esc(req.csrf)}">'


def side_link(href: str, label: str, icon: str, current: str, locked: bool = False) -> str:
    cur = ' aria-current="page"' if current == href else ""
    lock = i("lock", "lock") if locked else ""
    return f'<a class="side-link" href="{href}"{cur}>{i(icon)}<span>{esc(label)}</span>{lock}</a>'


def error_page(req, status: int, message: str) -> str:
    titles = {403: "Not allowed", 404: "Page not found", 405: "Not allowed", 500: "Something went wrong"}
    title = titles.get(status, "Error")
    body = f"""<section class="page-hero" style="min-height:70vh;display:grid;align-content:center"><div class="grid-texture"></div>
<div class="container"><p class="mono muted">Error {status}</p><h1 style="margin-top:10px">{esc(title)}</h1>
<p class="lead">{esc(message if status != 404 else "The page you were looking for isn't here. It may have moved, or the link may be private.")}</p>
<div class="btn-row" style="margin-top:28px"><a class="btn btn--primary" href="/">Go to the home page</a><a class="btn btn--secondary" href="/contact">Contact support</a></div></div></section>"""
    return page(req, title, body, noindex=True)
