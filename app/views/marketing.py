"""The customer-facing marketing website."""
from __future__ import annotations

from .. import auth, catalog, config, db, stock
from ..eventsite.invites import CREST
from ..icons import i
from ..services import email as mail
from ..web import HTTPError, esc, redirect, router, url
from . import forms
from .forms import Form, csrf, errors_summary, field, honeypot, select
from .layout import page

# --- shared pieces ---------------------------------------------------------------------------


def section_head(title: str, intro: str = "", side: str = "", variant: str = "") -> str:
    cls = "section-head" + (f" section-head--{variant}" if variant else "")
    intro_html = f'<p class="section-head__intro">{intro}</p>' if intro else ""
    if variant == "split":
        return f'<div class="{cls}"><div class="stack" style="--stack:14px"><h2>{title}</h2>{intro_html}</div>{side}</div>'
    if variant == "pair":
        return f'<div class="{cls}"><h2>{title}</h2>{intro_html}</div>'
    return f'<div class="{cls}"><h2>{title}</h2>{intro_html}</div>'


def category_art(group: str) -> str:
    """Line art in the accent colour over a soft wash (no stock photos needed)."""
    wash = {"weddings": "--glow-blush", "baby": "--glow-sky", "parties": "--glow-peach", "other": "--glow-mint"}.get(group, "--glow-accent")
    common = 'fill="none" stroke="var(--color-accent)" stroke-width="1.5" stroke-linecap="round"'
    art = {
        "weddings": f'<circle cx="150" cy="120" r="54" {common}/><circle cx="214" cy="120" r="54" {common}/>'
                    f'<path d="M110 250V170a72 72 0 0 1 144 0v80" {common} opacity=".55"/><path d="M182 52l10-14 10 14-10 12z" {common}/>',
        "baby": f'<path d="M226 72a58 58 0 1 0 40 88 46 46 0 1 1-40-88z" {common}/>'
                f'<path d="M110 70l4 12 12 4-12 4-4 12-4-12-12-4 12-4zM300 150l3 8 8 3-8 3-3 8-3-8-8-3 8-3zM140 190l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" {common}/>',
        "parties": f'<path d="M120 230l50-140 90 90z" {common}/><path d="M165 120c10 20 30 40 60 50" {common} opacity=".6"/>'
                   f'<circle cx="270" cy="70" r="6" {common}/><path d="M300 110l14-8M240 40l4-14M310 160h14M200 60l-10-10" {common}/>'
                   f'<rect x="90" y="80" width="12" height="12" rx="2" transform="rotate(20 96 86)" {common}/>',
        "other": f'<path d="M110 120l90-40 90 40-90 40z" {common}/><path d="M150 140v44c30 22 70 22 100 0v-44M290 120v58" {common}/>'
                 f'<path d="M100 240c30-30 70-36 100-30 30-6 70 0 100 30" {common} opacity=".55"/>',
    }.get(group, "")
    return (f'<svg class="cat-tile__art" viewBox="0 0 360 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<defs><radialGradient id="wash-{group}" cx="70%" cy="20%" r="80%"><stop offset="0" stop-color="rgb(var({wash}))" stop-opacity=".55"/>'
            f'<stop offset="1" stop-color="rgb(var({wash}))" stop-opacity="0"/></radialGradient></defs>'
            f'<rect width="360" height="300" fill="url(#wash-{group})"/>{art}</svg>')


def category_tiles() -> str:
    tiles = []
    for key, g in catalog.GROUPS.items():
        photo = stock.url(key)
        art = (f'<div class="cat-tile__photo"><img src="{photo}" alt="" loading="lazy" decoding="async"></div>' if photo else category_art(key))
        tiles.append(f"""<a class="cat-tile" href="{g['path']}" data-reveal>{art}
<h3>{esc(g['name'])}</h3><p>{esc(g['blurb'])}</p><span class="arrow-link"><span>Explore {esc(g['name'].lower())}</span>{i("arrow")}</span></a>""")
    return f'<div class="grid grid--4" data-stagger>{"".join(tiles)}</div>'


def template_card(t, group: str = "") -> str:
    groups = db.loads(t["groups"], [])
    g = group if group in groups else (groups[0] if groups else "weddings")
    tags = "".join(f'<span class="tag">{esc(x)}</span>' for x in db.loads(t["tags"], [])[:3])
    return f"""<article class="tpl-card" data-groups="{esc(' '.join(groups))}" data-reveal>
<div class="tpl-card__stage" data-fit><iframe src="/templates/{esc(t['slug'])}/preview?group={g}" width="1280" title="{esc(t['name'])} template preview" loading="lazy" tabindex="-1" aria-hidden="true"></iframe></div>
<div class="tpl-card__body"><div class="tpl-card__row"><h3><a href="/templates/{esc(t['slug'])}">{esc(t['name'])}</a></h3><span class="tpl-card__dir">{esc(t['direction'])}</span></div>
<p class="card__text">{esc(t['description'])}</p><div class="cluster">{tags}</div>
<div class="tpl-card__foot"><a class="btn btn--sm btn--secondary" href="/templates/{esc(t['slug'])}">{i("eye")} Preview</a>
<a class="btn btn--sm btn--primary" href="/create?template={esc(t['slug'])}">Use this template</a></div></div></article>"""


def price_cards(highlight_cta: bool = True) -> str:
    out = []
    for p in catalog.packages():
        bullets = db.loads(p["bullets"], [])
        limits = db.loads(p["limits"], {})
        items = "".join(
            f'<li class="{"is-first" if n == 0 and b.startswith("Everything") else ""}">{i("check")}<span>{esc(b)}</span></li>'
            for n, b in enumerate(bullets))
        lim = "".join(
            f'<div><span>{esc(label)}</span><b>{esc(limits.get(k, "-")) if limits.get(k, 0) else "Not included"}</b></div>'
            for k, label in catalog.LIMIT_LABELS.items())
        badge = '<span class="price__badge">Recommended</span>' if p["highlight"] else ""
        btn = "btn--primary" if p["highlight"] else "btn--secondary"
        out.append(f"""<article class="price{' price--highlight' if p['highlight'] else ''}" data-reveal>{badge}
<div><h3>{esc(p['name'])}</h3><p class="muted small" style="margin-top:6px">{esc(p['tagline'])}</p></div>
<div class="price__amount">{catalog.money(p['price_cents'])}<small>once-off{', VAT incl.' if config.VAT_REGISTERED else ''}</small></div>
<ul>{items}</ul><div class="price__limits">{lim}</div>
<a class="btn {btn} btn--block" href="/create?package={esc(p['code'])}">Choose {esc(p['name'].split()[0])}</a></article>""")
    return f'<div class="price-grid" data-stagger>{"".join(out)}</div>'


FAQ = [
    ("Do guests need an app or an account?",
     "No. Guests open your event link in any browser on their phone or computer. They RSVP with a short form; nothing to download, no passwords."),
    ("Is it really one link for everything?",
     "Yes. Your invitation, venue and directions, programme, menu, dress code, registry and RSVP all live on one page. Every guest can also get a personal link that greets them by name and shows their table."),
    ("Do you charge per guest or per invitation?",
     "No. You pay once for your package and can share your link with as many people as you like. Email sending has a generous allowance per package, shown on the pricing page, because each email costs us to deliver."),
    ("Can I change details after publishing?",
     "Any time. Update the venue, programme, menu or wording from your dashboard and the website changes immediately. You can also email guests about the update."),
    ("How do payments work?",
     "Pay securely by card or instant EFT through a South African payment gateway. Your website goes live only after the gateway confirms the payment, and you receive a receipt by email."),
    ("How do you handle my guests' personal information?",
     "Guest details are private to your event, protected by your login and never sold or used for marketing. We process them under POPIA on your behalf, and guests can opt out of event emails at any time."),
    ("Can I send invitations on WhatsApp?",
     "Yes. Share your event link or each guest's personal link straight into WhatsApp from your dashboard, copy a ready-made invitation message, or download a QR code for printed signage."),
    ("What happens after the event?",
     "Your website stays online for your hosting period (6 to 18 months depending on package, counted from publishing), and never goes offline before a month after your event, so guests can revisit the gallery. You can download every report before it closes."),
    ("Can I upgrade later?",
     "Yes. Upgrade from your dashboard and pay only the difference between packages. Your content carries over."),
    ("What if I need help?",
     "Write to us from the contact page or your dashboard. Signature Experience customers get priority replies."),
]


def faq_list(items) -> str:
    return '<div class="faq">' + "".join(
        f'<details{" open" if n == 0 else ""}><summary>{esc(q)}</summary><div><p>{esc(a)}</p></div></details>'
        for n, (q, a) in enumerate(items)) + "</div>"


def cta_panel(title: str = "Your whole event, one beautiful link.",
              text: str = "Choose a template, add your details and share it with every guest today.") -> str:
    return f"""<section class="section"><div class="container"><div class="cta-panel" data-reveal>
<div><h2>{esc(title)}</h2><p>{esc(text)}</p></div>
<div class="btn-row"><a class="btn btn--primary btn--lg" href="/create">Create your event {i("arrow", "i--arrow")}</a>
<a class="btn btn--secondary btn--lg" href="/templates">Browse templates</a></div></div></div></section>"""


def page_hero(title: str, intro: str, crumbs: list, extra: str = "") -> str:
    bc = '<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a>' + "".join(
        f'<span aria-hidden="true">/</span>' + (f'<a href="{h}">{esc(t)}</a>' if h else f'<span aria-current="page">{esc(t)}</span>')
        for t, h in crumbs) + "</nav>"
    return f"""<section class="page-hero"><div class="grid-texture"></div><div class="container hero-enter">{bc}
<h1>{title}</h1><p class="lead">{intro}</p>{extra}</div></section>"""


# --- home --------------------------------------------------------------------------------------
# The invitation's crest (the Terracotta template's: a Nguni cow between two shields over crossed spears),
# with its colours written in because the homepage doesn't load the event-website styles.
HERO_CREST = (CREST.replace('class="crest"', 'class="invite__emblem"')
              .replace('class="cow-base"', 'fill="#F7F1E7"').replace('class="cow-a"', 'fill="#6B3F22"')
              .replace('class="cow-b"', 'fill="#241A14"').replace('class="cow-in"', 'fill="#E3BFA4"')
              .replace('class="cow-eye"', 'fill="#1E1611"').replace('class="cow-muzzle"', 'fill="#CFA392"')
              .replace('class="sh-spear" fill="none"', 'fill="none" stroke="#4A2E1C" stroke-width="1.7"')
              .replace('class="sh-tip"', 'fill="#8A5A2B"')
              .replace('class="sh-body"', 'fill="#F6E8CF" stroke="#4A2E1C" stroke-width="1.8"')
              .replace('class="sh-spots"', 'fill="#4A2E1C"').replace('class="sh-stick"', 'stroke="#4A2E1C" stroke-width="1.6"'))

HERO_VISUAL = f"""<div class="orbit" data-tilt aria-hidden="true">
<div class="orbit__ring"></div><div class="orbit__ring orbit__ring--2"></div>
<svg class="orbit__lines" viewBox="0 0 100 100" preserveAspectRatio="none">
<path d="M50 50 C 35 40, 22 30, 14 22"/><path d="M50 50 C 66 44, 78 40, 88 36"/><path d="M50 50 C 38 62, 26 72, 16 80"/><path d="M50 50 C 64 66, 76 78, 86 90"/>
<circle cx="14" cy="22" r=".9"/><circle cx="88" cy="36" r=".9"/><circle cx="16" cy="80" r=".9"/><circle cx="86" cy="90" r=".9"/></svg>
<div class="phone"><div class="phone__screen"><div class="phone__notch"></div>
<div class="invite"><span class="invite__beads"></span>
<svg class="invite__leaf" viewBox="0 0 60 80"><g fill="#7C8C5A"><path d="M58 2C40 10 30 26 28 46c10-14 22-24 30-44Z"/><path d="M60 22C46 30 40 44 40 60c8-10 16-22 20-38Z" opacity=".75"/></g><path d="M58 2 26 70" stroke="#5E6B42" stroke-width="1" fill="none"/></svg>
{HERO_CREST}
<p class="invite__title">Lobola</p><p class="invite__sub">Celebration</p>
<p class="invite__intro">You are warmly invited to celebrate with our families</p>
<p class="invite__names">Lerato <span>&amp;</span> Sipho</p>
<svg class="invite__orn" viewBox="0 0 120 10"><path d="M2 5h40M78 5h40" fill="none" stroke="#B07A3A" stroke-width=".8"/><path d="M50 5 53 2l3 3-3 3ZM64 5l3-3 3 3-3 3Z" fill="#B07A3A"/>
<path d="M60 8.5c-3-2.2-5-3.8-5-5.6 0-1.3 1-2.2 2.2-2.2.9 0 1.8.5 2.8 1.6 1-1.1 1.9-1.6 2.8-1.6 1.2 0 2.2.9 2.2 2.2 0 1.8-2 3.4-5 5.6Z" fill="#8E3B22"/></svg>
<p class="invite__line">as we celebrate our lobola and the joining of our families</p>
<div class="invite__facts">
<div><svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg><b>Date</b><span>13 March 2027</span></div>
<div><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg><b>Time</b><span>10:00</span></div>
<div><svg viewBox="0 0 24 24"><path d="M12 21s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.4-6 10-6 10Z"/><circle cx="12" cy="11" r="2.2"/></svg><b>Venue</b><span>Soweto</span></div></div>
<p class="invite__note">Your presence will make this day even more special</p>
<div class="invite__count"><div>118<small>days</small></div><div>06<small>hrs</small></div><div>42<small>min</small></div><div>09<small>sec</small></div></div>
<span class="invite__rsvp">RSVP by 1 February</span>
<svg class="invite__basket" viewBox="0 0 70 50"><path d="M4 14h62c0 18-12 32-31 32S4 32 4 14Z" fill="#C9A26B"/><ellipse cx="35" cy="14" rx="31" ry="6" fill="#DDBB85"/>
<path d="M8 24l6 6 6-6 6 6 6-6 6 6 6-6 6 6 6-6 6 6" fill="none" stroke="#3B2A1E" stroke-width="1.6"/><path d="M13 34l5 4 5-4 5 4 5-4 5 4 5-4 5 4 5-4" fill="none" stroke="#8E3B22" stroke-width="1.4"/></svg>
<svg class="invite__pot" viewBox="0 0 60 60"><path d="M14 18h32c-1 3-2 4-4 5 8 4 12 11 12 19 0 11-10 17-24 17S6 53 6 42c0-8 4-15 12-19-2-1-3-2-4-5Z" fill="#8E4A2A"/>
<path d="M9 36h42" stroke="#F3DDB8" stroke-width="1.4"/><path d="M10 40l4-4 4 4 4-4 4 4 4-4 4 4 4-4 4 4 4-4 4 4" fill="none" stroke="#2A1A10" stroke-width="1.2"/><path d="M16 18h28" stroke="#6E3520" stroke-width="2"/></svg>
</div></div></div>
<div class="float-tile float-tile--rsvp glass"><div class="ring-stat"><svg viewBox="0 0 40 40"><circle class="track" cx="20" cy="20" r="16"/><circle class="val" cx="20" cy="20" r="16" stroke-dasharray="79 101"/></svg>
<div><b>118 of 150</b><span class="muted">guests replied</span></div></div></div>
<div class="float-tile float-tile--seat glass"><span class="muted">Your table</span><b>Table 7 · Protea</b><span class="muted">with 9 others</span></div>
<div class="float-tile float-tile--menu glass"><span class="muted">Meal choices</span><b>64 beef · 38 fish · 16 veg</b></div>
<div class="float-tile float-tile--link glass"><span class="dot">{i("link")}</span><span class="mono small">/events/lerato-and-sipho</span></div>
</div>"""

FEATURES = [
    ("globe", "A website for your event", "Animated invitation designs, made for phones first and filled with your details and photos."),
    ("check", "RSVPs that count themselves", "Attending, declined and pending at a glance, with plus-ones, children and meal choices."),
    ("users", "Guest list and families", "Import a spreadsheet, group families, mark VIPs and send personal invitation links."),
    ("seat", "Drag-and-drop seating", "Build your floor plan, seat parties at tables, and print the final chart."),
    ("dish", "Menus and dietary needs", "Guests choose meals and tell you about allergies. Your caterer gets a clean report."),
    ("list", "Programme and functions", "Ceremony, reception and every speech, across one day or several venues."),
    ("mail", "Emails you control", "Invitations, reminders and updates with a preview before anything is sent."),
    ("file", "Reports in one click", "Guest list, RSVPs, seating, dietary and final reports as PDF or Excel-ready CSV."),
]

# Real customer reviews only: (quote, "Name · occasion, city"). The section is hidden while this is empty.
TESTIMONIALS: list = []


def why_digital() -> str:
    """Printed cards versus one link, for 300 guests. Printing estimate: R30 to R50 per printed invitation
    in South Africa (Bridebook, 2025 guide), before envelopes, RSVP cards and delivery."""
    low = min((p["price_cents"] for p in catalog.packages()), default=0)
    rows = [("Cost", "About R9,000 to R15,000 to print 300 cards, before envelopes, RSVP cards and delivery",
             f"From {catalog.money(low)} once-off, however many guests you invite"),
            ("Sending", "Weeks of hand-delivering and posting", "On WhatsApp in minutes, to everyone"),
            ("Changes", "A new venue or time means reprinting", "Change it once and every guest sees it"),
            ("Replies", "Phone calls, messages and a spreadsheet", "RSVPs, meal choices and dietary needs arrive in one place"),
            ("On the day", "Separate menus, programmes and seating lists to print", "Programme, menu, map and their table on their phone")]
    body = "".join(f'<div class="vs-row"><span class="vs-label mono tiny">{esc(k)}</span><span class="vs-old">{i("close")}<span><span class="vs-tag">Printed: </span>{esc(a)}</span></span>'
                   f'<span class="vs-new">{i("check")}<span><span class="vs-tag">{esc(config.BRAND_NAME)}: </span>{esc(b)}</span></span></div>' for k, a, b in rows)
    return (f'<section class="section"><div class="container">{section_head("Why send your invitations this way", "Say you are inviting 300 people.")}'
            f'<div class="vs box"><div class="vs-row vs-head"><span></span><b>Printed cards</b><b>One {esc(config.BRAND_NAME)} link</b></div>{body}</div>'
            f'<p class="tiny muted" style="margin-top:10px">Printing estimate based on South African prices of about R30 to R50 per printed invitation.</p></div></section>')


SITEMAP_PATHS = ["/", "/weddings", "/baby-celebrations", "/parties", "/celebrations", "/templates", "/pricing",
                 "/how-it-works", "/faq", "/help-me-set-up", "/contact", "/privacy", "/terms", "/refunds"]


@router.get("/robots.txt")
def robots(req):
    """Marketing pages may be indexed; event websites, accounts and admin may not."""
    from ..web import Response
    body = ("User-agent: *\nDisallow: /events/\nDisallow: /dashboard\nDisallow: /admin\nDisallow: /media/\n"
            "Disallow: /login\nDisallow: /register\nDisallow: /pay/\n"
            f"Sitemap: {config.BASE_URL}/sitemap.xml\n")
    return Response(body, content_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml")
def sitemap(req):
    from ..web import Response
    paths = SITEMAP_PATHS + [f"/templates/{t['slug']}" for t in db.q("SELECT slug FROM templates WHERE active = 1 ORDER BY sort, id")]
    urls = "".join(f"<url><loc>{esc(config.BASE_URL + p)}</loc></url>" for p in paths)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                    content_type="application/xml; charset=utf-8")


@router.get("/healthz")
def healthz(req):
    """For the host's health check: answers once the database is reachable."""
    from ..web import Response
    db.val("SELECT 1")
    r = Response("ok", content_type="text/plain; charset=utf-8")
    r.header("Cache-Control", "no-store")
    return r


@router.get("/")
def home(req):
    featured = ["nguni", "ribbon", "weave", "terracotta", "glitter", "matcha"]   # weddings first
    templates = sorted(catalog.templates(), key=lambda t: featured.index(t["slug"]) if t["slug"] in featured else 99)[:6]
    tpl_cards = "".join(template_card(t) for t in templates)
    feats = "".join(f'<div class="feature card" data-reveal><span class="icon-tile">{i(ic)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></div>'
                    for ic, t, d in FEATURES)
    quotes = "".join(f'<figure class="card quote" data-reveal><blockquote>“{esc(q)}”</blockquote><figcaption>{esc(c)}</figcaption></figure>'
                     for q, c in TESTIMONIALS)
    reviews = (f'<section class="section"><div class="container">{section_head("What hosts say", "From hosts who used " + esc(config.BRAND_NAME) + " for their events.")}'
               f'<div class="grid grid--3" data-stagger>{quotes}</div></div></section>') if TESTIMONIALS else ""
    reviews += f"""<section class="section"><div class="container"><div class="cta-panel"><div><h2 style="font-size:1.6rem">Short on time? We'll set it up for you.</h2>
<p>Send us your details on WhatsApp or by email and our team builds your website. You check it, we change anything you like, and you pay once you're happy.</p></div>
<div class="btn-row"><a class="btn btn--primary btn--lg" href="/help-me-set-up">Ask us to set it up</a></div></div></div></section>"""
    body = f"""
<section class="hero"><div class="grid-texture"></div><div class="hero__haze"></div>
<div class="container hero-grid"><div class="hero-enter">
<h1 class="hero__title">Everything for your event, in <span class="serif grad">one link.</span></h1>
<p class="hero__sub">Choose a template, add your details and get a personalised event website with RSVPs, guest list, seating, menus and reports. Pay once. Share everywhere.</p>
<div class="btn-row hero__actions"><a class="btn btn--primary btn--lg" href="/create">Create your event {i("arrow", "i--arrow")}</a>
<a class="btn btn--secondary btn--lg" href="/templates">See the templates</a></div>
<div class="hero__note"><span>{i("check")} No app for guests</span><span>{i("check")} No per-guest fees</span><span>{i("check")} From {catalog.money(min((p['price_cents'] for p in catalog.packages()), default=0))} once-off</span></div>
</div>{HERO_VISUAL}</div></section>

<section class="section"><div class="container">{section_head("Made for every celebration", "Pick your occasion. Each one comes with templates and tools that fit it, from family delegations at a lobola to meal choices at a gala.")}
{category_tiles()}</div></section>

{why_digital()}

<section class="section section--surface"><div class="container">
{section_head("Finished event websites", "Each one opens like a real invitation, then carries on as the full event website. This is what your guests open on their phones.", '<a class="arrow-link" href="/templates"><span>All templates</span>' + i("arrow") + '</a>', "split")}
<div class="showcase">
<figure data-reveal><div class="device device--browser"><div class="device__screen" data-fit><iframe src="/templates/nguni/preview?group=weddings" width="1280" title="Nguni traditional wedding sample" loading="lazy" tabindex="-1" aria-hidden="true"></iframe></div></div><figcaption>Nguni · a traditional wedding</figcaption></figure>
<figure data-reveal><div class="device device--phone"><div class="device__screen" data-fit><iframe src="/templates/ribbon/preview?group=weddings" width="390" title="Ribbon wedding sample" loading="lazy" tabindex="-1" aria-hidden="true"></iframe></div></div><figcaption>Ribbon · a white wedding</figcaption></figure>
<figure data-reveal><div class="device device--phone"><div class="device__screen" data-fit><iframe src="/templates/glitter/preview?group=parties" width="390" title="Glitter 21st birthday sample" loading="lazy" tabindex="-1" aria-hidden="true"></iframe></div></div><figcaption>Glitter · a 21st birthday</figcaption></figure>
</div></div></section>

<section class="section"><div class="container">{section_head("How it works", "From blank page to RSVPs in an afternoon.")}
<ol class="steps list-plain" data-stagger>
<li class="step" data-reveal><h3>Choose your event</h3><p>Pick the occasion and a template you love. Preview it on desktop and mobile.</p></li>
<li class="step" data-reveal><h3>Add your details</h3><p>A guided set-up for venue, programme, menu, seating and the little things.</p></li>
<li class="step" data-reveal><h3>Pay once, publish</h3><p>Choose a package and pay securely. Your website goes live straight after.</p></li>
<li class="step" data-reveal><h3>Share one link</h3><p>Send it on WhatsApp or email. Watch RSVPs arrive and seat everyone.</p></li>
</ol></div></section>

<section class="section section--surface"><div class="container">
{section_head("Templates with their own character", "Invitations that move: an envelope that unseals, a ribbon that ties itself, balloons that float. Each has its own layout, typography and details.", '<a class="arrow-link" href="/templates"><span>Browse all ' + str(len(catalog.templates())) + '</span>' + i("arrow") + '</a>', "split")}
<div class="grid grid--3" data-stagger>{tpl_cards}</div></div></section>

<section class="section"><div class="container">{section_head("One platform for the whole event", "Everything you would otherwise print, chase or put in a spreadsheet.")}
<div class="grid grid--4" data-stagger>{feats}</div></div></section>

<section class="section section--surface" id="pricing"><div class="container">
{section_head("Affordable luxury, priced once", "No per-guest charges, no per-invitation fees. One payment covers your website, your guests and your tools.", '<a class="arrow-link" href="/pricing"><span>Compare every feature</span>' + i("arrow") + '</a>', "split")}
{price_cards()}</div></section>

{reviews}

<section class="section section--surface"><div class="container container--narrow">{section_head("Questions, answered")}{faq_list(FAQ[:6])}
<p style="margin-top:24px"><a class="arrow-link" href="/faq"><span>More questions</span>{i("arrow")}</a></p></div></section>
{cta_panel()}"""
    return page(req, f"{config.BRAND_NAME} · Digital event websites, RSVPs and seating", body, "/",
                description="Create a premium event website for your wedding, baby shower or party with RSVPs, guest list, seating, menus and reports. One link, priced once in Rand.")


# --- category pages ----------------------------------------------------------------------------
CATEGORY_COPY = {
    "weddings": ("Wedding websites that do the organising", "Invitations, RSVPs, family guest lists, seating and menus for white weddings, traditional ceremonies, lobola and engagements.",
                 [("users", "Both families, one list", "Group guests by family and side, and give each delegation its own arrival time."),
                  ("calendar", "Several ceremonies", "Traditional ceremony, white wedding and reception on one page, each with its own venue."),
                  ("seat", "Seating that adds up", "Seat parties with plus-ones and children, and see every table's occupancy."),
                  ("dish", "Meals and dietary needs", "Guests choose their meal and tell you about allergies before the caterer asks.")]),
    "baby": ("Baby celebrations, beautifully organised", "Showers, gender reveals and welcome-baby gatherings with RSVPs, registry links and a gentle reminder for anyone who forgets.",
             [("gift", "Registry in one place", "Link every registry and add a note about gift preferences."),
              ("chat", "Made for WhatsApp", "Share one link in the family group and watch the replies arrive."),
              ("image", "A gallery for after", "Add photos after the day so everyone can revisit it."),
              ("bell", "Reminders, kindly", "Send a reminder to guests who haven't replied, with a preview first.")]),
    "parties": ("Party pages people actually read", "Birthdays, anniversaries and private celebrations with a countdown, dress code, directions and RSVPs that count themselves.",
                [("clock", "A live countdown", "Build anticipation with a countdown at the top of the page."),
                 ("dress", "Dress code, clearly", "Tell guests what to wear, with notes and colours."),
                 ("pin", "Directions and parking", "A map link, parking notes and directions for the gate code."),
                 ("check", "RSVPs with plus-ones", "Know exactly how many are coming, including partners and kids.")]),
    "other": ("Graduations, corporate and family events", "Agendas, catering choices and seating for formal functions, reunions, unveilings and graduations.",
              [("list", "A proper agenda", "Sessions, speakers and times, across one day or several."),
               ("dish", "Catering choices", "Collect meal selections and dietary needs, then export the catering report."),
               ("users", "Guest categories", "VIPs, families, colleagues and clients, each with their own view in your list."),
               ("file", "Reports for the venue", "Guest list, seating and final reports as PDF or Excel-ready CSV.")]),
}
GROUP_BY_PATH = {g["path"]: k for k, g in catalog.GROUPS.items()}


def category_page(req, group: str):
    g = catalog.GROUPS[group]
    title, intro, feats = CATEGORY_COPY[group]
    cats = [c for c in catalog.categories() if c["group_slug"] == group]
    cat_cards = "".join(f"""<article class="card card--link" data-reveal><h3 class="card__title"><a href="/create?category={esc(c['slug'])}">{esc(c['name'])}</a></h3>
<p class="card__text">{esc(c['description'])}</p><div class="card__foot"><span class="arrow-link"><span>Start a {esc(c['name'].lower())}</span>{i("arrow")}</span></div></article>""" for c in cats)
    tpls = "".join(template_card(t, group) for t in catalog.templates(group))
    feat_html = "".join(f'<div class="feature" data-reveal><span class="icon-tile icon-tile--soft">{i(ic)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></div>'
                        for ic, t, d in feats)
    extra = (f'<div class="btn-row" style="margin-top:28px"><a class="btn btn--primary btn--lg" href="/create?group={group}">'
             f'Create your {esc(g["name"].lower().rstrip("s"))} website {i("arrow", "i--arrow")}</a>'
             f'<a class="btn btn--secondary btn--lg" href="#templates">See templates</a></div>')
    grid_cls = "grid--3" if len(cats) % 3 == 0 else "grid--2" if len(cats) % 2 == 0 else "grid--3"
    body = (page_hero(esc(title), esc(intro), [(g["name"], "")], extra) + f"""
<section class="section"><div class="container">{section_head("Choose your occasion")}<div class="grid {grid_cls}" data-stagger>{cat_cards}</div></div></section>
<section class="section section--surface" id="templates"><div class="container">{section_head(f"Templates for {esc(g['name'].lower())}", "Preview any design with sample content, on desktop and mobile.")}
<div class="grid grid--3" data-stagger>{tpls}</div></div></section>
<section class="section"><div class="container">{section_head("Made for this kind of event")}<div class="grid grid--4" data-stagger>{feat_html}</div></div></section>
{cta_panel()}""")
    return page(req, g["name"], body, g["path"], description=intro)


def _cat_route(path, group):
    router.get(path, name=f"category_{group}")(lambda req: category_page(req, group))


for _k, _g in catalog.GROUPS.items():
    _cat_route(_g["path"], _k)


# --- templates ----------------------------------------------------------------------------------
@router.get("/templates")
def templates_gallery(req):
    current = req.arg("category")
    rows = catalog.templates()
    counts = {k: sum(1 for t in rows if k in db.loads(t["groups"], [])) for k in catalog.GROUPS}
    chips = [f'<button class="chip" type="button" data-filter="all" aria-pressed="{"false" if current in catalog.GROUPS else "true"}">All <span class="count">{len(rows)}</span></button>']
    chips += [f'<button class="chip" type="button" data-filter="{k}" aria-pressed="{"true" if current == k else "false"}">{esc(g["name"])} <span class="count">{counts[k]}</span></button>'
              for k, g in catalog.GROUPS.items()]
    cards = []
    for t in rows:
        groups = db.loads(t["groups"], [])
        hidden = current in catalog.GROUPS and current not in groups
        card = template_card(t, current if current in catalog.GROUPS else "")
        if hidden:
            card = card.replace('<article class="tpl-card"', '<article class="tpl-card" hidden', 1)
        cards.append(card)
    body = (page_hero('Event website <span class="serif grad">templates</span>',
                      "Invitations that open, draw and sparkle, then carry on as your full event website. Filter by occasion, preview on desktop and mobile, then make it yours.",
                      [("Templates", "")]) + f"""
<section class="section"><div class="container"><div class="chips-scroll" data-filter-bar role="group" aria-label="Filter by event type" style="margin-bottom:28px">{"".join(chips)}</div>
<div class="grid grid--3">{"".join(cards)}</div></div></section>{cta_panel("Found the one?", "Start with any template. You can switch designs at any time before and after publishing.")}""")
    return page(req, "Templates", body, "/templates", description="Browse premium event website templates for weddings, baby showers, parties and corporate events.")


@router.get("/templates/<slug:slug>")
def template_detail(req, slug):
    t = catalog.template(slug)
    if not t or not t["active"]:
        raise HTTPError(404)
    groups = db.loads(t["groups"], [])
    group = req.arg("group") if req.arg("group") in groups else (groups[0] if groups else "weddings")
    from ..eventsite import themes
    d = themes.design(t["design"])
    swatches = "".join(
        f'<div class="row" style="gap:10px"><span class="palette-swatches">{"".join(f"<i style=background:{c}></i>" for c in (p[2]["bg"], p[2]["text"], p[2]["accent"], p[2]["accent2"]))}</span><span class="small">{esc(p[1])}</span></div>'
        for p in d["palettes"])
    fonts = ", ".join(themes.FONT_PAIRS[f][0] for f in d["fonts"])
    group_links = "".join(
        f'<a href="{url("/templates/" + slug, group=k)}"{" aria-current=page" if k == group else ""}>{esc(catalog.GROUPS[k]["name"])}</a>'
        for k in groups)
    others = "".join(template_card(x) for x in catalog.templates() if x["slug"] != slug and set(db.loads(x["groups"], [])) & set(groups))
    cults = d.get("cultures") or []
    style = req.arg("style") if req.arg("style") in cults else ""
    culture_row = ""
    if cults:
        links = [f'<a href="{url("/templates/" + slug, group=group)}"{"" if style else " aria-current=page"}>Classic</a>']
        links += [f'<a href="{url("/templates/" + slug, group=group, style=k)}"{" aria-current=page" if k == style else ""}>{esc(themes.CULTURES[k][0])}</a>'
                  for k in cults]
        culture_row = (f'<div class="culture-pick"><span class="small">Cultural style</span><div class="seg seg--wrap" role="group" '
                       f'aria-label="Cultural style">{"".join(links)}</div>'
                       + (f'<span class="tiny muted">{esc(themes.CULTURES[style][1])}</span>' if style else "") + '</div>')
    body = page_hero(f'{esc(t["name"])} <span class="serif grad">template</span>', esc(t["description"]),
                     [("Templates", "/templates"), (t["name"], "")],
                     f'<div class="btn-row" style="margin-top:24px"><a class="btn btn--primary btn--lg" href="/create?template={esc(slug)}&group={group}{"&amp;palette=" + esc(style) if style else ""}">Use this template {i("arrow", "i--arrow")}</a></div>') + f"""
<section class="section"><div class="container">{culture_row}<div class="cols cols--2" style="grid-template-columns:minmax(0,1fr)">
<div class="preview-frame" data-preview data-device="desktop"><div class="preview-frame__bar"><span class="preview-frame__url">{esc(config.BASE_URL)}/events/sample</span>
<div class="row" style="gap:8px"><div class="seg" role="group" aria-label="Sample content">{group_links}</div>
<div class="seg" role="group" aria-label="Device"><button type="button" data-device="desktop" aria-pressed="true">{i("monitor")}<span class="sr-only">Desktop</span></button><button type="button" data-device="mobile" aria-pressed="false">{i("phone")}<span class="sr-only">Mobile</span></button></div></div></div>
<div class="preview-frame__stage" style="height:min(78vh,820px)"><iframe src="/templates/{esc(slug)}/preview?group={group}{"&amp;palette=" + esc(style) if style else ""}" title="{esc(t['name'])} preview with sample content"></iframe></div></div>
</div>
<div class="grid grid--3" style="margin-top:var(--gap)">
<div class="box"><h3 style="font-size:1rem;margin-bottom:12px">Design direction</h3><p class="muted small">{esc(t["direction"])}. Sample content shown; your names, photos and wording replace it.</p></div>
<div class="box"><h3 style="font-size:1rem;margin-bottom:12px">Colour palettes</h3><div class="stack" style="--stack:8px">{swatches}</div><p class="tiny muted" style="margin-top:10px">Or set your own colours.</p></div>
<div class="box"><h3 style="font-size:1rem;margin-bottom:12px">Typography</h3><p class="muted small">{esc(fonts)}</p></div>
</div></div></section>
<section class="section section--surface"><div class="container">{section_head("You might also like")}<div class="grid grid--3">{others}</div></div></section>"""
    return page(req, f"{t['name']} template", body, "/templates", description=t["description"])


# --- pricing ------------------------------------------------------------------------------------
@router.get("/pricing")
def pricing(req):
    pkgs = list(catalog.packages())
    head = "".join(f'<th scope="col">{esc(p["name"].replace(" Experience", ""))}<br><span class="muted tiny mono">{catalog.money(p["price_cents"])}</span></th>' for p in pkgs)
    rows = []
    for key, label in catalog.FEATURES.items():
        cells = "".join(
            f'<td class="{"yes" if key in db.loads(p["features"], []) else "no"}">'
            f'{i("check") if key in db.loads(p["features"], []) else "—"}<span class="sr-only">{"Included" if key in db.loads(p["features"], []) else "Not included"}</span></td>'
            for p in pkgs)
        rows.append(f"<tr><th scope='row' style='font-weight:400'>{esc(label)}</th>{cells}</tr>")
    for key, label in catalog.LIMIT_LABELS.items():
        cells = "".join(f'<td class="mono">{esc(db.loads(p["limits"], {}).get(key, 0)) or "—"}</td>' for p in pkgs)
        rows.append(f"<tr><th scope='row' style='font-weight:400'>{esc(label)}</th>{cells}</tr>")
    notes = [
        ("Unlimited link sharing", "Share your event link with as many people as you like, on any channel. It is not unlimited email: each package includes the guest email allowance shown above."),
        ("Pay once", "One payment per event. No subscriptions, no per-guest or per-invitation charges."),
        ("Upgrade any time", "Move to a bigger package from your dashboard and pay only the difference."),
        ("Hosting period", "Your website stays online for the months shown, counted from when it is published, and never goes offline before a month after your event. Extensions are available."),
    ]
    note_html = "".join(f'<div class="box"><h3 style="font-size:1rem">{esc(t)}</h3><p class="muted small" style="margin-top:8px">{esc(d)}</p></div>' for t, d in notes)
    body = page_hero('Simple pricing, <span class="serif grad">paid once</span>',
                     "Every package includes your personalised event website, a premium template and unlimited link sharing. Choose the tools you need.",
                     [("Pricing", "")]) + f"""
<section class="section"><div class="container">{price_cards()}
<div class="notice" style="margin-top:22px">{i("wand")}<span>Short on time? <a class="text-link" href="/help-me-set-up">We can set it up for you</a>. Tell us about your event and we'll send you a quote.</span></div></div></section>
<section class="section section--surface"><div class="container">{section_head("Compare every feature")}
<div class="table-wrap table-wrap--sticky"><table class="compare"><thead><tr><th scope="col">Feature</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div></section>
<section class="section"><div class="container">{section_head("Good to know")}<div class="grid grid--4">{note_html}</div></div></section>
<section class="section section--surface"><div class="container container--narrow">{section_head("Pricing questions")}{faq_list([FAQ[2], FAQ[4], FAQ[8], FAQ[7]])}</div></section>
{cta_panel()}"""
    return page(req, "Pricing", body, "/pricing", description="Essential, Premium and Signature event packages in South African Rand. Pay once, no per-guest fees.")


# --- how it works / FAQ --------------------------------------------------------------------------
@router.get("/how-it-works")
def how_it_works(req):
    steps = [
        ("Choose your event and template", "Pick from weddings, baby celebrations, parties and other events, then a template. Preview it with sample content on desktop and mobile before you commit.", "layout"),
        ("Complete the guided set-up", "Ten short steps: event details, venue, design, guests, programme, food, seating, extra information, a full preview, then your package. Save at any point and come back later.", "wand"),
        ("Pay securely and publish", "Pay by card or instant EFT through a South African gateway. When the gateway confirms payment, your website goes live at its own address.", "card"),
        ("Share one link", "Send the link on WhatsApp or email, or print the QR code. Each guest can also have a personal link that greets them and shows their table.", "chat"),
        ("Manage the replies", "See who's attending, declined or still to reply. Add guests, import a spreadsheet and send reminders after a preview.", "check"),
        ("Seat, feed and report", "Drag guests onto tables, check meal choices and dietary needs, and download the final report for your venue and caterer.", "file"),
    ]
    rows = "".join(f"""<div class="split split--57" style="padding:28px 0;border-top:1px solid var(--color-line)" data-reveal>
<div class="row" style="gap:16px;align-items:flex-start"><span class="icon-tile">{i(ic)}</span><h2 style="font-size:1.5rem">{esc(t)}</h2></div><p class="lead" style="font-size:1.0625rem">{esc(d)}</p></div>"""
                   for t, d, ic in steps)
    guest = [("No app, no account", "Guests tap the link and see everything."), ("RSVP in under a minute", "Name, attendance, plus-ones, meal choice and dietary needs."),
             ("Always up to date", "Change the venue or programme and the page updates for everyone."), ("Private by design", "Guests never see who else is invited.")]
    gcards = "".join(f'<div class="card" data-reveal><h3 class="card__title">{esc(t)}</h3><p class="card__text">{esc(d)}</p></div>' for t, d in guest)
    body = page_hero('How it <span class="serif grad">works</span>', "From choosing a template to downloading your final guest report, everything happens in one place.",
                     [("How it works", "")]) + f"""
<section class="section"><div class="container">{rows}</div></section>
<section class="section section--surface"><div class="container">{section_head("What your guests experience")}<div class="grid grid--4" data-stagger>{gcards}</div></div></section>
{cta_panel()}"""
    return page(req, "How it works", body, "/how-it-works")


@router.get("/faq")
def faq(req):
    body = page_hero("Frequently asked <span class=\"serif grad\">questions</span>", "If your question isn't here, write to us. We usually reply within one working day.",
                     [("FAQ", "")]) + f"""<section class="section"><div class="container container--narrow">{faq_list(FAQ)}
<div class="notice" style="margin-top:28px">{i("support")}<span>Still unsure? <a class="text-link" href="/contact">Contact support</a>.</span></div></div></section>"""
    return page(req, "FAQ", body, "/faq")


# --- contact & support ---------------------------------------------------------------------------
TOPICS = [("general", "General question"), ("event", "Help with my event"), ("setup_help", "Set up my event for me"),
          ("payment", "Payments and receipts"), ("technical", "Something isn't working"), ("privacy", "Privacy or data request"),
          ("partnership", "Partnerships")]
REACH = [("whatsapp", "WhatsApp"), ("phone", "Phone call"), ("email", "Email")]


@router.route("/help-me-set-up", methods=("GET", "POST"))
def setup_help(req):
    """Done-for-you set-up: a free request; the team replies with a quote."""
    f = Form(req)
    sent = None
    user = req.user
    if req.method == "POST":
        if req.get("website"):
            return redirect("/help-me-set-up")
        if auth.rate_limited(f"setup-help:{req.ip}", 5, 3600):
            f.error("message", "You've sent several requests already. Please wait a little before sending another.")
        name = f.text("name", "Your name", required=True, max=120)
        email_addr = f.email("email", required=True)
        phone = f.text("phone", "Mobile", max=40)
        reach = f.choice("reach", [k for k, _ in REACH], "contact options", default="email")
        if reach in ("whatsapp", "phone") and not phone:
            f.error("phone", "Add a mobile number so we can contact you on " + dict(REACH)[reach] + ".")
        occasion = f.choice("occasion", [c["slug"] for c in catalog.categories()], "occasions", required=True)
        if "occasion" in f.errors:
            f.errors["occasion"] = "Choose what you're celebrating."
        when = f.date("event_date", "Event date")
        pkg = f.choice("package", ["", *[p["code"] for p in catalog.packages()]], "packages", default="")
        message = f.text("message", "Anything else", max=3000)
        if f.ok:
            lines = [f"Occasion: {catalog.category_name(occasion)}", f"Date: {forms.fmt_date(when) if when else 'not set yet'}",
                     f"Package: {catalog.package(pkg)['name'] if pkg else 'not sure yet'}", f"Mobile: {phone or '-'}",
                     f"Contact by: {dict(REACH)[reach]}", "", message or "(no message)"]
            sid = db.insert("support_requests", {"user_id": user["id"] if user else None, "event_id": None, "name": name,
                                                 "email": email_addr, "topic": "setup_help", "message": "\n".join(lines), "priority": 1,
                                                 "created_at": db.now(), "updated_at": db.now()})
            sent = f"S-{sid:05d}"
            mail.send(email_addr, "setup_help_received", {"first_name": mail.first_name(name), "reference": sent},
                      user_id=user["id"] if user else None)
    if sent:
        form_html = (f'<div class="notice notice--success">{i("check")}<div><b>Thank you. Your reference is {esc(sent)}.</b>'
                     f'<p class="small" style="margin-top:4px">We\'ve emailed you a copy. We\'ll contact you within one working day to go through '
                     f'the details and send you a quote.</p></div></div>')
    else:
        d = f.data
        occ = [(c["slug"], f'{catalog.GROUPS[c["group_slug"]]["name"]}: {c["name"]}') for c in catalog.categories()]
        pk = [(p["code"], f'{p["name"]} ({catalog.money(p["price_cents"])})') for p in catalog.packages()]
        form_html = f"""<form class="form box" method="post" novalidate>{csrf(req)}{honeypot()}{errors_summary(f.errors)}
<div class="form-row form-row--2">{field("name", "Your name", d.get("name", user["name"] if user else ""), required=True, errors=f.errors, attrs={"autocomplete": "name"})}
{field("email", "Email", d.get("email", user["email"] if user else ""), type="email", required=True, errors=f.errors, attrs={"autocomplete": "email"})}</div>
<div class="form-row form-row--2">{field("phone", "Mobile (optional)", d.get("phone", ""), type="tel", errors=f.errors, attrs={"autocomplete": "tel"})}
{select("reach", "Best way to reach you", REACH, d.get("reach") or "whatsapp")}</div>
<div class="form-row form-row--2">{select("occasion", "What are you celebrating?", occ, d.get("occasion") or req.arg("occasion"), required=True, blank="Choose one", errors=f.errors)}
{field("event_date", "Date (if you know it)", d.get("event_date", ""), type="date", errors=f.errors)}</div>
{select("package", "Package you're thinking of", pk, d.get("package") or req.arg("package") or "", blank="Not sure yet")}
{field("message", "Anything we should know? (optional)", d.get("message", ""), type="textarea", errors=f.errors, attrs={"rows": 4, "placeholder": "Venue, number of guests, the look you like, or questions."})}
<p class="tiny muted">We use these details only to help you with your event. See our <a class="text-link" href="/privacy">privacy notice</a>.</p>
<div><button class="btn btn--primary" type="submit">Ask us to set it up {i("send")}</button></div></form>"""
    steps = "".join(f'<li><span class="mono">{n}</span><div><b>{esc(t)}</b><p class="small muted" style="margin-top:4px">{esc(x)}</p></div></li>'
                    for n, t, x in (("01", "Tell us about your event", "Send this short form. It takes a minute."),
                                    ("02", "We contact you", "Within one working day, on WhatsApp, by phone or email, whichever you prefer."),
                                    ("03", "Send us your details and photos", "Names, date, venue, wording and photos. Voice notes are fine."),
                                    ("04", "We build it, you approve it", "You get a preview link to check. We change anything you like."),
                                    ("05", "Pay and share", "Once you're happy, pay for your package and share your link.")))
    body = page_hero('We\'ll set it up <span class="serif grad">for you</span>',
                     "Short on time? Tell us about your event and our team builds your website for you. You check it, we change anything you like, and you pay only once you're happy.",
                     [("Set-up help", "")]) + f"""<section class="section"><div class="container"><div class="split split--57" style="align-items:start">
<div class="stack" style="--stack:18px"><ol class="how-list" style="list-style:none;margin:0;padding:0;display:grid;gap:16px">{steps}</ol>
<div class="notice">{i("info")}<span>We send you a quote for the set-up with your package. Asking costs nothing and doesn't commit you.</span></div></div>
<div>{form_html}</div></div></div></section>"""
    return page(req, "We'll set it up for you", body, "/help-me-set-up",
                description=f"Let the {config.BRAND_NAME} team build your event website for you. Free request, quote within one working day.")


@router.route("/contact", methods=("GET", "POST"))
def contact(req):
    f = Form(req)
    sent = None
    user = req.user
    if req.method == "POST":
        if req.get("website"):
            return redirect("/contact")
        if auth.rate_limited(f"contact:{req.ip}", 6, 3600):
            f.error("message", "You've sent several messages already. Please wait a little before sending another.")
        name = f.text("name", "Your name", required=True, max=120)
        email_addr = f.email("email", required=True)
        topic = f.choice("topic", [k for k, _ in TOPICS], "topic", default="general")
        message = f.text("message", "Message", required=True, max=4000, min=10)
        event_id = None
        priority = 0
        if user:
            ev_uid = req.get("event")
            if ev_uid:
                row = db.one("SELECT id, paid_package FROM events WHERE uid = ? AND owner_id = ?", (ev_uid, user["id"]))
                if row:
                    event_id = row["id"]
                    priority = 1 if "priority_support" in catalog.package_features(row["paid_package"]) else 0
        if f.ok:
            sid = db.insert("support_requests", {"user_id": user["id"] if user else None, "event_id": event_id, "name": name,
                                                 "email": email_addr, "topic": topic, "message": message, "priority": priority,
                                                 "created_at": db.now(), "updated_at": db.now()})
            ref = f"S-{sid:05d}"
            mail.send(email_addr, "support_received", {"name": mail.first_name(name), "ref": ref, "message": message,
                                                       "priority_note": " (priority support)" if priority else ""},
                      user_id=user["id"] if user else None, event_id=event_id)
            sent = ref
    if sent:
        form_html = (f'<div class="notice notice--success">{i("check")}<div><b>Thank you. Your reference is {esc(sent)}.</b>'
                     f'<p class="small" style="margin-top:4px">We\'ve emailed you a copy and usually reply within one working day.</p></div></div>')
    else:
        ev_select = ""
        if user:
            evs = db.q("SELECT uid, name FROM events WHERE owner_id = ? ORDER BY created_at DESC", (user["id"],))
            if evs:
                ev_select = select("event", "Which event is this about? (optional)", [(e["uid"], e["name"]) for e in evs],
                                   req.get("event") or req.arg("event"), blank="Not about a specific event")
        d = f.data
        form_html = f"""<form class="form box" method="post" novalidate>{csrf(req)}{honeypot()}{errors_summary(f.errors)}
<div class="form-row form-row--2">{field("name", "Your name", d.get("name", user["name"] if user else ""), required=True, errors=f.errors)}
{field("email", "Email", d.get("email", user["email"] if user else ""), type="email", required=True, errors=f.errors)}</div>
{select("topic", "Topic", TOPICS, d.get("topic") or req.arg("topic") or "general")}{ev_select}
{field("message", "How can we help?", d.get("message", ""), type="textarea", required=True, errors=f.errors)}
<p class="tiny muted">We use these details only to answer you. See our <a class="text-link" href="/privacy">privacy notice</a>.</p>
<div><button class="btn btn--primary" type="submit">Send message {i("send")}</button></div></form>"""
    body = page_hero('Contact and <span class="serif grad">support</span>', "Questions before you start, help with your event, or a privacy request. We're here.",
                     [("Contact", "")]) + f"""<section class="section"><div class="container"><div class="split split--57" style="align-items:start">
<div class="stack" style="--stack:18px"><div class="notice">{i("mail")}<div><b>Email</b><br><a class="text-link" href="mailto:{esc(config.SUPPORT_EMAIL)}">{esc(config.SUPPORT_EMAIL)}</a></div></div>
{f'<div class="notice">{i("chat")}<div><b>WhatsApp</b><br><a class="text-link" href="{esc(config.whatsapp_link())}" target="_blank" rel="noopener">{esc(config.WHATSAPP_NUMBER)}</a></div></div>' if config.WHATSAPP_NUMBER else ""}
<div class="notice">{i("shield")}<div><b>Information officer (POPIA)</b><br><a class="text-link" href="mailto:{esc(config.INFORMATION_OFFICER)}">{esc(config.INFORMATION_OFFICER)}</a></div></div></div>
<div>{form_html}</div></div></div></section>"""
    return page(req, "Contact", body, "/contact")


# --- legal ---------------------------------------------------------------------------------------
LEGAL_NOTE = '<p class="demo-flag" style="margin-bottom:24px">Draft for legal review before launch</p>'


def legal(req, title, path, html):
    body = page_hero(esc(title), "Last updated 16 November 2026.", [(title, "")]) + \
        f'<section class="section"><div class="container"><article class="prose">{LEGAL_NOTE}{html}</article></div></section>'
    return page(req, title, body, path)


@router.get("/privacy")
def privacy(req):
    b = esc(config.BRAND_NAME)
    return legal(req, "Privacy notice", "/privacy", f"""
<p>{b} ("we") is the responsible party for the personal information of our customers, and an operator for the guest information our customers add to their events. We process personal information in line with the Protection of Personal Information Act, 2013 (POPIA).</p>
<h2>What we collect</h2><ul><li><b>Customers:</b> name, email, phone (optional), password (stored only as a salted hash), event details and payment records. Card details are handled by our payment gateway; we never see or store them.</li>
<li><b>Guests:</b> the details an organiser adds or a guest submits when replying: name, email or phone, attendance, plus-ones, children, meal choice, dietary needs and special requests.</li>
<li><b>Technical:</b> a session cookie to keep you signed in, a security cookie that protects forms, and basic server logs. We use no advertising or tracking cookies.</li></ul>
<h2>Why we use it</h2><ul><li>To provide the service you asked for: your event website, RSVPs, guest management, reports and emails.</li><li>To process payments and keep tax records.</li><li>To answer support requests and keep the platform secure.</li><li>To send product news only if you opt in.</li></ul>
<h2>Guest information</h2><p>Guest details belong to the organiser's event. They are visible only to that event's organiser and administrators, never to other guests, and never sold or used for our own marketing. Organisers must have a lawful reason to add guests and to email them. Every guest email includes a link to stop event emails.</p>
<h2>Sharing</h2><p>We share information only with service providers who help run the platform (hosting, email delivery, payment processing), under agreements that require them to protect it, or when the law requires it.</p>
<h2>How long we keep it</h2><p>Event data is kept for the hosting period plus 90 days so you can download reports, then deleted. Invoices are kept for five years for tax purposes.</p>
<h2>Your rights</h2><p>You can access, correct or delete your information, object to processing, and complain to the Information Regulator (inforegulator.org.za). Download your data or delete your account from your account page, or contact our information officer at <a href="mailto:{esc(config.INFORMATION_OFFICER)}">{esc(config.INFORMATION_OFFICER)}</a>.</p>
<h2>Security</h2><p>Passwords are hashed, sessions expire, every event is isolated to its organisers, uploads are checked, and access to administration is restricted and logged.</p>""")


@router.get("/terms")
def terms(req):
    b = esc(config.BRAND_NAME)
    return legal(req, "Terms of service", "/terms", f"""
<p>These terms apply when you create an account or buy a package from {b}.</p>
<h2>The service</h2><p>We provide tools to create an event website and manage guests, RSVPs, seating, menus, programmes, communication and reports. Features and limits depend on the package you buy, as shown on the pricing page at the time of purchase.</p>
<h2>Your account</h2><p>Keep your password safe. You are responsible for activity on your account and for the content you publish, including photos you upload, which must be yours to use.</p>
<h2>Guests and communication</h2><p>You confirm you have a lawful basis to add each guest's details and to email them about your event. Don't use the platform for marketing, spam or anything unlawful. We may suspend events that break these terms.</p>
<h2>Payments</h2><p>Prices are in South African Rand{' and include VAT' if config.VAT_REGISTERED else ''}. Your website is published only once our payment gateway confirms payment. Upgrades are charged as the difference between packages.</p>
<h2>Hosting period</h2><p>Your event website stays online for the hosting period of your package from the date it is first published. Whenever you book, it never goes offline before one month after your event date, including if you move the date. We'll remind you before it ends.</p>
<h2>Email allowance</h2><p>Unlimited link sharing means you can share your link as often as you like. Emails sent through the platform are limited to your package's allowance.</p>
<h2>Liability</h2><p>We work hard to keep the service available, but we can't guarantee it will be uninterrupted. To the extent the law allows, our liability is limited to the amount you paid for the event concerned. Nothing in these terms limits your rights under the Consumer Protection Act.</p>
<h2>Changes</h2><p>We'll tell you about material changes to these terms by email before they take effect.</p>""")


@router.get("/refunds")
def refunds(req):
    return legal(req, "Refund policy", "/refunds", """
<p>We want you to be happy with your event website.</p>
<h2>Before you publish</h2><p>If you've paid but haven't published your website or emailed any guests, you can ask for a full refund within 14 days of payment.</p>
<h2>After you publish</h2><p>Once your website is live or guest emails have been sent, the service has been delivered and payments aren't refundable, except where the law requires it or the service failed because of a fault on our side.</p>
<h2>Cancelled or postponed events</h2><p>Change your date and details at any time at no cost. If your event is postponed beyond your hosting period, ask us about a free extension.</p>
<h2>How to ask</h2><p>Use the contact page and choose "Payments and receipts". Approved refunds go back to the original payment method within 10 working days.</p>""")
