"""Turn an event (from the database or a demo dict) into a complete event website.

`render(ev, mode, guest, req, notice)` is the single entry point used by the public site, the
organiser preview and the template gallery. It builds a context of everything the page may show
(respecting section visibility and the package), then hands it to the design's layout function
in designs.py.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from urllib.parse import quote_plus

from .. import catalog, config, db, events
from ..views.forms import fmt_date, fmt_time
from ..web import esc
from . import themes

GROUP_WORDING = {
    "weddings": {"welcome": "We're getting married",
                 "invitation": "Together with their families, {hosts} invite you to share in the joy of their celebration.",
                 "rsvp_note": "Kindly reply by {deadline} so we can plan every detail.",
                 "closing": "We can't wait to celebrate with you."},
    "baby": {"welcome": "A little one is on the way",
             "invitation": "Please join us to celebrate {hosts} and the newest member of the family.",
             "rsvp_note": "Let us know by {deadline} if you can make it.",
             "closing": "With love and gratitude."},
    "parties": {"welcome": "Let's celebrate",
                "invitation": "{hosts} would love you to join the celebration.",
                "rsvp_note": "Reply by {deadline} so we save you a seat.",
                "closing": "See you there."},
    "other": {"welcome": "You're invited",
              "invitation": "{hosts} request the pleasure of your company.",
              "rsvp_note": "Please respond by {deadline}.",
              "closing": "We look forward to welcoming you."},
}

SAST = "+02:00"


def _group(ev) -> str:
    if ev.get("_group"):
        return ev["_group"]
    c = catalog.category(ev.get("category") or "")
    return c["group_slug"] if c else "other"


def design_key(ev) -> str:
    if ev.get("_design"):
        return ev["_design"]
    t = catalog.template(ev.get("template") or "")
    key = t["design"] if t else (ev.get("template") or "atelier")
    return key if key in themes.DESIGNS else "atelier"


def split_names(text: str) -> list[str]:
    for sep in (" & ", " and ", " + "):
        if sep in text:
            a, b = text.split(sep, 1)
            return [a.strip(), b.strip()]
    return [text.strip()]


def maps_link(name: str, address: str, url: str = "") -> str:
    if url:
        return url
    q = ", ".join(x for x in (name, address) if x)
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(q) if q else ""


def _related(ev) -> dict:
    """Functions, schedule, menus and images, from demo keys or the database."""
    if ev.get("_demo"):
        menus = ev.get("_menus", [])
        meals = [it for m in menus for it in m["items"] if it.get("selectable")]
        return {"functions": ev.get("_functions", []), "schedule": ev.get("_schedule", []), "menus": menus,
                "meals": meals, "hero": ev.get("_hero", ""), "logo": "", "background": "",
                "gallery": ev.get("_gallery", [])}
    eid = ev["id"]
    first = lambda kind: (events.uploads(eid, kind) or [None])[0]  # noqa: E731
    hero, logo, bg = first("hero"), first("logo"), first("background")
    menus = events.menus(eid)
    return {
        "functions": [dict(r) for r in events.functions(eid)],
        "schedule": [dict(r) for r in events.schedule(eid)],
        "menus": menus,
        "meals": [dict(r) for r in events.meal_options(eid)],
        "hero": events.upload_url(hero), "logo": events.upload_url(logo), "background": events.upload_url(bg),
        "gallery": [{"url": events.upload_url(u), "caption": u["caption"]} for u in events.uploads(eid, "gallery")],
    }


def guest_table(ev, guest) -> str:
    if not guest or ev.get("_demo"):
        return ""
    row = db.one("""SELECT t.name FROM seat_assignments a JOIN seating_tables t ON t.id = a.table_id
                    WHERE a.guest_id = ?""", (guest["id"],))
    return row["name"] if row else ""


def rsvp_closed(ev) -> str:
    """Reason RSVPs are closed, or '' when open."""
    if not ev.get("rsvp_open", 1):
        return "RSVPs for this event are closed."
    deadline = (ev.get("guest_settings") or {}).get("rsvp_deadline")
    if deadline:
        try:
            if date.today() > date.fromisoformat(deadline):
                return f"RSVPs closed on {fmt_date(deadline)}."
        except ValueError:
            pass
    return ""


def allowances(ev, guest=None) -> dict:
    """Plus-ones and children a guest may bring."""
    gs = ev.get("guest_settings") or {}
    policy = gs.get("plus_one_policy", "per_guest")
    default_plus = int(gs.get("plus_ones_default") or 0)
    if policy == "none":
        plus = 0
    elif guest is not None:
        plus = int(guest["plus_ones_allowed"] or 0)
        if policy == "open":
            plus = max(plus, default_plus, 1)
    else:
        plus = max(default_plus, 1) if policy == "open" else default_plus
    kids = 0
    if gs.get("children_allowed"):
        kids = int(gs.get("max_children") or 0)
        if guest is not None and int(guest["children_allowed"] or 0) > 0:
            kids = int(guest["children_allowed"])
    return {"plus_ones": max(0, min(plus, 10)), "children": max(0, min(kids, 10))}


def build_context(ev, mode: str = "public", guest=None, req=None, notice: str = "", form: Optional[dict] = None) -> dict:
    public = mode != "preview"
    group = _group(ev)
    dkey = design_key(ev)
    design = ev.get("design") or {}
    theme = themes.resolve(dkey, design)
    rel = _related(ev)
    show = events.visible_sections(ev, public=public)
    if mode == "demo":
        show = {k: True for k in show}
    feat = lambda key: mode == "demo" or catalog.has_feature(ev, key, public=public)  # noqa: E731
    gs = ev.get("guest_settings") or {}
    venue = ev.get("venue") or {}
    info = ev.get("info") or {}
    hosts = events.title(ev)
    deadline = fmt_date(gs.get("rsvp_deadline")) if gs.get("rsvp_deadline") else "the date on your invitation"
    defaults = GROUP_WORDING.get(group, GROUP_WORDING["other"])
    raw_w = design.get("wording") or {}
    wording = {}
    for k, v in defaults.items():
        text = (raw_w.get(k) or "").strip() or v
        wording[k] = text.replace("{hosts}", hosts).replace("{deadline}", deadline)
    d = None
    if ev.get("event_date"):
        try:
            d = date.fromisoformat(ev["event_date"])
        except ValueError:
            d = None
    start = ev.get("start_time") or "12:00"
    countdown_iso = f"{d.isoformat()}T{start}:00{SAST}" if d else ""
    functions = rel["functions"]
    meals = rel["meals"] if (show.get("menu") or mode == "demo") and feat("menu") else []
    ctx = {
        "ev": ev, "mode": mode, "guest": guest, "req": req, "notice": notice, "form": form or {},
        "design": dkey, "theme": theme, "group": group, "show": show, "feat": feat,
        "hosts": hosts, "names": split_names(hosts), "title": ev.get("name") or hosts,
        "description": ev.get("description") or "",
        "date": d, "date_text": fmt_date(ev.get("event_date")) if d else "Date to be announced",
        "time_text": " – ".join(x for x in (fmt_time(ev.get("start_time")), fmt_time(ev.get("end_time"))) if x),
        "countdown_iso": countdown_iso, "venue": venue, "info": info, "gs": gs,
        "map_url": maps_link(venue.get("name", ""), venue.get("address", ""), venue.get("map_url", "")),
        "functions": functions, "schedule": rel["schedule"], "menus": rel["menus"], "meals": meals,
        "hero": rel["hero"], "logo": rel["logo"], "background": rel["background"], "gallery": rel["gallery"],
        "monogram": (design.get("monogram") or "").strip() or "".join(n[:1] for n in split_names(hosts) if n)[:3].upper(),
        "wording": wording, "deadline_text": deadline,
        "table": guest_table(ev, guest) if guest else ("Table 4 · Jacaranda" if mode == "demo" else ""),
        "closed": "" if mode == "demo" else rsvp_closed(ev),
        "allow": allowances(ev, guest),
        "csrf": getattr(req, "csrf", "") if req is not None else "",
        "thanks": bool(req is not None and req.arg("rsvp") == "thanks"),
        "path": f"/events/{ev.get('slug', '')}",
    }
    ctx["guest_functions"] = {}
    if guest is not None and not ev.get("_demo"):
        ctx["guest_functions"] = {r["function_id"]: r["attending"] for r in
                                  db.q("SELECT * FROM guest_functions WHERE guest_id = ?", (guest["id"],))}
    return ctx


def render(ev: dict, mode: str = "public", guest=None, req=None, notice: str = "", form: Optional[dict] = None) -> str:
    from . import designs
    ctx = build_context(ev, mode, guest, req, notice, form)
    body = designs.LAYOUTS.get(ctx["design"], designs.LAYOUTS["atelier"])(ctx)
    return document(ctx, body)


# --- colour contrast (keeps buttons and accent text at WCAG AA whatever palette is chosen) ----
def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def luminance(h: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def ink(color: str, against: str, target: float = 4.5) -> str:
    """Shift `color` toward black or white until it reaches `target` contrast with `against`."""
    toward = "#000000" if luminance(against) > 0.25 else "#FFFFFF"
    t = 0.0
    out = color
    while contrast(out, against) < target and t < 1:
        t += 0.05
        out = mix(color, toward, t)
    return out


def contrast_vars(c: dict) -> str:
    try:
        dark = luminance(c["bg"]) < 0.2
        if dark:
            btn = c["accent"]
            btn_text = c["bg"] if contrast(btn, c["bg"]) >= 4.5 else "#111111"
        else:
            btn = ink(c["accent"], "#FFFFFF")
            btn_text = "#FFFFFF"
        acc_ink = ink(c["accent"], c["bg"])
        acc_ink_s = ink(c["accent"], c["surface"])
        muted = ink(c["muted"], c["bg"])
        return (f"--ev-btn:{btn};--ev-btn-text:{btn_text};--ev-ink:{acc_ink};--ev-ink-s:{acc_ink_s};"
                f"--ev-muted:{muted};")
    except (KeyError, ValueError):
        return ""


def banner(ctx) -> str:
    if ctx["mode"] == "preview":
        ev = ctx["ev"]
        status = "Draft" if ev.get("status") == "draft" else events.STATUS_LABELS.get(ev.get("status"), "")
        return (f'<div class="ev-banner" role="note">Preview · {esc(status)} · not visible to guests'
                f'{(" · " + esc(ctx["notice"])) if ctx["notice"] else ""}</div>')
    if ctx["mode"] == "demo":
        return '<div class="ev-ribbon" role="note">Sample content</div>'
    if ctx["notice"]:
        return f'<div class="ev-banner ev-banner--notice" role="status">{esc(ctx["notice"])}</div>'
    return ""


def document(ctx, body: str) -> str:
    t = ctx["theme"]
    ev = ctx["ev"]
    title = f"{ctx['title']} · {ctx['date_text']}" if ctx["date"] else ctx["title"]
    desc = (ctx["wording"]["invitation"] or "")[:180]
    robots = '<meta name="robots" content="noindex">'  # event pages are private by default
    bg_img = ctx["background"] or (ctx["hero"] if t["background"] == "image" else "")
    style = themes.css_vars(t) + contrast_vars(t["colors"]) + (f"--ev-bg-image:url('{esc(bg_img)}');" if bg_img else "")
    classes = f"ev d-{ctx['design']} bg-{t['background']} grp-{ctx['group']}" + (" has-hero" if ctx["hero"] else "")
    return f"""<!doctype html><html lang="en-ZA"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">{robots}
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta name="theme-color" content="{esc(t['colors']['bg'])}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{esc(themes.fonts_url(t['display'], t['body']))}">
<link rel="stylesheet" href="/static/css/eventsite.css">
</head><body class="{classes}" style="{style}">
<a class="ev-skip" href="#ev-main">Skip to content</a>{banner(ctx)}
<main id="ev-main">{body}</main>
<footer class="ev-foot"><p>{esc(ctx['wording']['closing'])}</p>
<p class="ev-made"><a href="/" target="_blank" rel="noopener">Made with {esc(config.BRAND_NAME)}</a></p></footer>
<script src="/static/js/eventsite.js" defer></script></body></html>"""
