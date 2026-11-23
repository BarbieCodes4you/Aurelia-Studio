"""The eleven event-website designs.

Shared section builders turn the render context into semantic HTML (only for sections that are
visible and have content). Each design then arranges them in its own structure: a different
hero, different navigation, different section containers and ornaments. Styling lives in
static/css/eventsite.css, scoped by `.d-<design>`.
"""
from __future__ import annotations

from ..web import esc
from ..views.forms import fmt_date, fmt_time
from .. import events

ORDER = ["invitation", "countdown", "venue", "programme", "menu", "dress_code", "rsvp", "seating",
         "accommodation", "registry", "gallery", "contact"]

TITLES = {
    "invitation": "The invitation", "countdown": "Counting down", "venue": "Where and when",
    "programme": "Programme", "menu": "Menu", "dress_code": "Dress code", "rsvp": "RSVP",
    "seating": "Your table", "accommodation": "Where to stay", "registry": "Gifts",
    "gallery": "Gallery", "contact": "Questions",
}
NAV_LABELS = {"invitation": "Invitation", "countdown": "Countdown", "venue": "Venue", "programme": "Programme",
              "menu": "Menu", "dress_code": "Dress code", "rsvp": "RSVP", "seating": "Seating",
              "accommodation": "Stay", "registry": "Gifts", "gallery": "Gallery", "contact": "Contact"}


def p(text: str, cls: str = "") -> str:
    """Escaped text → paragraphs (blank lines) with line breaks."""
    if not text:
        return ""
    paras = [x.strip() for x in str(text).replace("\r", "").split("\n\n") if x.strip()]
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{esc(x).replace(chr(10), '<br>')}</p>" for x in paras)


def names_html(ctx, amp: str = "&amp;") -> str:
    n = ctx["names"]
    if len(n) == 2:
        return (f'<span class="ev-name">{esc(n[0])}</span><span class="ev-amp" aria-hidden="true">{amp}</span>'
                f'<span class="sr-only"> and </span><span class="ev-name">{esc(n[1])}</span>')
    return f'<span class="ev-name">{esc(n[0])}</span>'


def date_parts(ctx) -> dict:
    d = ctx["date"]
    if not d:
        return {"day": "", "dd": "", "month": "", "mon": "", "year": "", "weekday": ""}
    return {"day": str(d.day), "dd": f"{d.day:02d}", "month": d.strftime("%B"), "mon": d.strftime("%b"),
            "year": str(d.year), "weekday": d.strftime("%A")}


def btn(href: str, label: str, cls: str = "", external: bool = False) -> str:
    ext = ' target="_blank" rel="noopener"' if external else ""
    return f'<a class="ev-btn {cls}" href="{esc(href)}"{ext}>{esc(label)}</a>'


def hero_image(ctx, cls: str = "ev-photo", art: str = "") -> str:
    if ctx["hero"]:
        return f'<div class="{cls}"><img src="{esc(ctx["hero"])}" alt="" loading="eager"></div>'
    return f'<div class="{cls} ev-photo--art" aria-hidden="true">{art}</div>'


# --- section content builders -------------------------------------------------------------------
def s_invitation(ctx) -> str:
    w = ctx["wording"]
    out = f'<p class="ev-lead">{esc(w["invitation"])}</p>'
    if ctx["description"]:
        out += p(ctx["description"], "ev-text")
    return out


def when_list(ctx) -> str:
    v = ctx["venue"]
    rows = [("Date", ctx["date_text"])]
    if ctx["time_text"]:
        rows.append(("Time", ctx["time_text"]))
    if v.get("name"):
        rows.append(("Venue", v["name"]))
    return '<dl class="ev-when">' + "".join(f"<div><dt>{k}</dt><dd>{esc(x)}</dd></div>" for k, x in rows) + "</dl>"


def s_countdown(ctx) -> str:
    if not ctx["countdown_iso"]:
        return ""
    units = [("d", "Days"), ("h", "Hours"), ("m", "Minutes"), ("s", "Seconds")]
    cells = "".join(f'<div class="ev-count__cell"><b data-u="{u}">00</b><span>{lab}</span></div>' for u, lab in units)
    return (f'<div class="ev-count" data-countdown="{esc(ctx["countdown_iso"])}" role="timer" aria-live="off">{cells}</div>'
            f'<p class="ev-count__done" hidden>The celebration has begun.</p>')


def s_venue(ctx) -> str:
    v = ctx["venue"]
    funcs = ctx["functions"]
    out = ""
    if v.get("name") or v.get("address"):
        out += '<div class="ev-venue">'
        if v.get("name"):
            out += f'<h3 class="ev-venue__name">{esc(v["name"])}</h3>'
        if v.get("address"):
            out += f'<p class="ev-venue__addr">{esc(v["address"])}</p>'
        out += f'<p class="ev-venue__time">{esc(ctx["date_text"])}{(" · " + esc(ctx["time_text"])) if ctx["time_text"] else ""}</p>'
        if ctx["map_url"]:
            out += f'<div class="ev-actions">{btn(ctx["map_url"], "Open in Google Maps", "", True)}'
            if ctx["mode"] != "demo" and ctx["ev"].get("slug"):
                out += f'<a class="ev-btn ev-btn--ghost" href="{esc(ctx["path"])}/calendar.ics">Add to calendar</a>'
            out += "</div>"
        out += "</div>"
    extras = []
    if v.get("parking"):
        extras.append(("Parking", v["parking"]))
    if v.get("directions"):
        extras.append(("Directions", v["directions"]))
    if extras:
        out += '<div class="ev-notes">' + "".join(
            f'<div class="ev-note"><h4>{k}</h4>{p(x)}</div>' for k, x in extras) + "</div>"
    if len(funcs) > 1:
        out += '<ol class="ev-funcs">'
        for f in funcs:
            when = " · ".join(x for x in (fmt_date(f.get("func_date"), False) if f.get("func_date") else "",
                                          " – ".join(y for y in (fmt_time(f.get("start_time")), fmt_time(f.get("end_time"))) if y)) if x)
            murl = f.get("map_url") or (
                "https://www.google.com/maps/search/?api=1&query=" + __import__("urllib.parse").parse.quote_plus(
                    ", ".join(x for x in (f.get("venue_name"), f.get("address")) if x))
                if (f.get("venue_name") or f.get("address")) else "")
            out += (f'<li class="ev-func"><h3>{esc(f["name"])}</h3>'
                    f'{f"<p class=ev-func__when>{esc(when)}</p>" if when else ""}'
                    f'{("<p class=ev-func__venue>" + esc(f.get("venue_name") or "") + ("<br>" + esc(f["address"]) if f.get("address") else "") + "</p>") if (f.get("venue_name") or f.get("address")) else ""}'
                    f'{p(f.get("description") or "", "ev-small")}'
                    f'{("<p class=ev-small><b>Dress:</b> " + esc(f["dress_code"]) + "</p>") if f.get("dress_code") else ""}'
                    f'{btn(murl, "Map", "ev-btn--ghost ev-btn--sm", True) if murl else ""}</li>')
        out += "</ol>"
    return out


def s_programme(ctx) -> str:
    items = ctx["schedule"]
    if not items:
        return ""
    groups: list = []
    for it in items:
        name = it.get("function_name") or ""
        if not groups or groups[-1][0] != name:
            groups.append((name, [], it.get("function_date") or ""))
        groups[-1][1].append(it)
    out = ""
    for name, rows, day in groups:
        if name and len(groups) > 1:
            when = fmt_date(day, False) if day else ""
            out += f'<h3 class="ev-prog__group">{esc(name)}{(" <small>" + esc(when) + "</small>") if when else ""}</h3>'
        out += '<ol class="ev-prog">' + "".join(
            f'<li class="ev-prog__item ev-kind-{esc(it.get("kind") or "other")}"><time>{esc(fmt_time(it.get("item_time")))}</time>'
            f'<div><h4>{esc(it["title"])}</h4>{p(it.get("description") or "", "ev-small")}</div></li>' for it in rows) + "</ol>"
    return out


def s_menu(ctx) -> str:
    menus = ctx["menus"]
    info = ctx["info"]
    if not menus and not info.get("drinks"):
        return ""
    out = ""
    for m in menus:
        out += f'<div class="ev-menu"><h3 class="ev-menu__name">{esc(m["name"])}</h3>{p(m.get("description") or "", "ev-small ev-muted")}'
        course = None
        for it in m["items"]:
            if it.get("course") != course:
                if course is not None:
                    out += "</ul>"
                course = it.get("course")
                out += f'<h4 class="ev-menu__course">{esc(course or "")}</h4><ul class="ev-menu__items">'
            tags = it.get("tags") or []
            tag_html = "".join(f'<span class="ev-tag">{esc(t)}</span>' for t in tags)
            choice = '<span class="ev-tag ev-tag--choice">Choose on RSVP</span>' if it.get("selectable") else ""
            out += (f'<li><span class="ev-menu__dish">{esc(it["name"])}</span>{p(it.get("description") or "", "ev-small")}'
                    f'{("<span class=ev-tags>" + tag_html + choice + "</span>") if (tag_html or choice) else ""}</li>')
        if course is not None:
            out += "</ul>"
        out += "</div>"
    if info.get("drinks"):
        out += f'<div class="ev-note"><h4>Drinks</h4>{p(info["drinks"])}</div>'
    if info.get("catering_notes"):
        out += f'<div class="ev-note"><h4>Catering notes</h4>{p(info["catering_notes"])}</div>'
    return out


def s_dress(ctx) -> str:
    info = ctx["info"]
    if not info.get("dress_code"):
        return ""
    return f'<p class="ev-dress">{esc(info["dress_code"])}</p>{p(info.get("dress_code_notes") or "", "ev-text")}'


def s_seating(ctx) -> str:
    if not ctx["table"]:
        return ""
    who = esc(events.guest_name(ctx["guest"])) if ctx["guest"] is not None else "Your guest"
    return (f'<div class="ev-table"><span class="ev-table__label">{who}, you are seated at</span>'
            f'<strong class="ev-table__name">{esc(ctx["table"])}</strong>'
            f'<span class="ev-small ev-muted">Your seat is shown only on your personal invitation link.</span></div>')


def s_accommodation(ctx) -> str:
    v, info = ctx["venue"], ctx["info"]
    items = info.get("accommodation") or []
    if not v.get("accommodation") and not items:
        return ""
    out = p(v.get("accommodation") or "", "ev-text")
    if items:
        out += '<ul class="ev-list">' + "".join(
            f'<li><h4>{(("<a href=" + chr(34) + esc(a["url"]) + chr(34) + " target=_blank rel=noopener>" + esc(a.get("name") or "Link") + "</a>") if a.get("url") else esc(a.get("name") or ""))}</h4>{p(a.get("note") or "", "ev-small")}</li>'
            for a in items) + "</ul>"
    return out


def s_registry(ctx) -> str:
    info = ctx["info"]
    items = info.get("registry") or []
    if not items and not info.get("gift_note"):
        return ""
    out = p(info.get("gift_note") or "", "ev-text")
    if items:
        out += '<ul class="ev-list ev-list--reg">' + "".join(
            f'<li><h4>{esc(r.get("name") or "Registry")}</h4>{p(r.get("note") or "", "ev-small")}'
            f'{btn(r["url"], "View registry", "ev-btn--ghost ev-btn--sm", True) if r.get("url") else ""}</li>'
            for r in items) + "</ul>"
    return out


ART_TILES = 6


def s_gallery(ctx) -> str:
    imgs = ctx["gallery"]
    if not imgs:
        return ""
    cells = []
    for k, g in enumerate(imgs[:60]):
        if g.get("url"):
            cells.append(f'<figure class="ev-gal__item"><img src="{esc(g["url"])}" alt="{esc(g.get("caption") or "Event photo")}" loading="lazy">'
                         f'{("<figcaption>" + esc(g["caption"]) + "</figcaption>") if g.get("caption") else ""}</figure>')
        else:
            cells.append(f'<figure class="ev-gal__item ev-gal__art ev-art-{k % ART_TILES}" aria-hidden="true">'
                         f'{("<figcaption>" + esc(g.get("caption")) + "</figcaption>") if g.get("caption") else ""}</figure>')
    return f'<div class="ev-gal">{"".join(cells)}</div>'


def s_contact(ctx) -> str:
    info = ctx["info"]
    contacts = info.get("contacts") or []
    if not contacts and not info.get("instructions"):
        return ""
    out = ""
    if info.get("instructions"):
        out += f'<div class="ev-note"><h4>Good to know</h4>{p(info["instructions"])}</div>'
    if contacts:
        out += '<ul class="ev-contacts">'
        for c in contacts:
            links = ""
            if c.get("phone"):
                tel = "".join(ch for ch in c["phone"] if ch.isdigit() or ch == "+")
                wa = tel.lstrip("+")
                if wa.startswith("0"):
                    wa = "27" + wa[1:]
                links += f'<a class="ev-btn ev-btn--ghost ev-btn--sm" href="tel:{esc(tel)}">Call {esc(c["phone"])}</a>'
                links += f'<a class="ev-btn ev-btn--ghost ev-btn--sm" href="https://wa.me/{esc(wa)}" target="_blank" rel="noopener">WhatsApp</a>'
            if c.get("email"):
                links += f'<a class="ev-btn ev-btn--ghost ev-btn--sm" href="mailto:{esc(c["email"])}">Email</a>'
            out += (f'<li><h4>{esc(c.get("name") or "")}</h4>'
                    f'{("<p class=ev-small>" + esc(c["role"]) + "</p>") if c.get("role") else ""}'
                    f'<div class="ev-actions">{links}</div></li>')
        out += "</ul>"
    return out


# --- RSVP ------------------------------------------------------------------------------------
def _val(ctx, name: str, default=""):
    vals = (ctx["form"] or {}).get("values") or {}
    if name in vals:
        return vals[name]
    g = ctx["guest"]
    if g is not None:
        try:
            v = g[name]
            return default if v is None else v
        except (KeyError, IndexError):
            return default
    return default


def _err(ctx, name: str) -> str:
    e = ((ctx["form"] or {}).get("errors") or {}).get(name)
    return f'<span class="ev-err" id="err-{name}">{esc(e)}</span>' if e else ""


def _field(ctx, name, label, type_="text", required=False, auto="", hint="") -> str:
    req = " required" if required else ""
    ac = f' autocomplete="{auto}"' if auto else ""
    inv = ' aria-invalid="true"' if ((ctx["form"] or {}).get("errors") or {}).get(name) else ""
    return (f'<div class="ev-field"><label for="r-{name}">{esc(label)}{" <span aria-hidden=true>*</span>" if required else ""}</label>'
            f'<input class="ev-input" id="r-{name}" name="{name}" type="{type_}" value="{esc(_val(ctx, name))}"{req}{ac}{inv}>'
            f'{("<span class=ev-hint>" + esc(hint) + "</span>") if hint else ""}{_err(ctx, name)}</div>')


def _number_select(ctx, name, label, maximum) -> str:
    cur = str(_val(ctx, name, 0) or 0)
    opts = "".join(f'<option value="{n}"{" selected" if str(n) == cur else ""}>{n}</option>' for n in range(maximum + 1))
    return (f'<div class="ev-field"><label for="r-{name}">{esc(label)}</label>'
            f'<select class="ev-input" id="r-{name}" name="{name}">{opts}</select>{_err(ctx, name)}</div>')


def rsvp_form(ctx) -> str:
    ev, guest, mode = ctx["ev"], ctx["guest"], ctx["mode"]
    w = ctx["wording"]
    errors = (ctx["form"] or {}).get("errors") or {}
    if ctx["thanks"]:
        if guest is not None:
            status = guest["status"]
            msg = ("Thank you, we can't wait to see you." if status == "attending"
                   else "Thank you for letting us know. You'll be missed." if status == "declined" else "Thank you.")
            change = f'<a class="ev-btn ev-btn--ghost" href="{esc(ctx["path"])}/i/{esc(guest["token"])}#rsvp">Change my answer</a>'
        else:
            msg, change = "Thank you, your reply has been sent to the hosts.", ""
        conf = " A confirmation is on its way to your inbox." if (guest is not None and guest["email"]) else ""
        return f'<div class="ev-thanks" role="status" tabindex="-1" data-focus-me><h3>Reply received</h3><p>{esc(msg)}{conf}</p>{change}</div>'
    if ctx["closed"]:
        return f'<div class="ev-thanks"><p>{esc(ctx["closed"])}</p><p class="ev-small">Please contact the hosts if your plans have changed.</p></div>'
    demo = mode == "demo"
    allow = ctx["allow"]
    status = str(_val(ctx, "status", ""))
    if status == "pending":
        status = ""
    parts = [f'<p class="ev-rsvp__note">{esc(w["rsvp_note"])}</p>']
    if errors:
        parts.append('<div class="ev-errors" role="alert"><b>Please check the highlighted fields.</b><ul>'
                     + "".join(f"<li>{esc(m)}</li>" for m in errors.values()) + "</ul></div>")
    if guest is not None:
        replied = ""
        if guest["status"] in ("attending", "declined") and guest["responded_at"]:
            replied = f' You replied <b>{"attending" if guest["status"] == "attending" else "not attending"}</b>; you can change it below.'
        parts.append(f'<p class="ev-rsvp__as">Replying as <b>{esc(events.guest_name(guest))}</b>.{replied}</p>'
                     f'<input type="hidden" name="token" value="{esc(guest["token"])}">')
    else:
        parts.append('<div class="ev-grid2">' + _field(ctx, "first_name", "First name", required=True, auto="given-name")
                     + _field(ctx, "last_name", "Surname", required=True, auto="family-name") + "</div>"
                     + '<div class="ev-grid2">' + _field(ctx, "email", "Email", "email", True, "email",
                                                          "We'll send your confirmation here.")
                     + _field(ctx, "phone", "Mobile (optional)", "tel", False, "tel") + "</div>")
    a_chk = " checked" if status == "attending" else ""
    d_chk = " checked" if status == "declined" else ""
    parts.append(f'<fieldset class="ev-choice"><legend>Will you attend?</legend>'
                 f'<label class="ev-radio"><input type="radio" name="status" value="attending" required{a_chk}><span>Joyfully accepts</span></label>'
                 f'<label class="ev-radio"><input type="radio" name="status" value="declined"{d_chk}><span>Regretfully declines</span></label>'
                 f'{_err(ctx, "status")}</fieldset>')
    att = []
    if allow["plus_ones"]:
        att.append('<div class="ev-grid2">' + _number_select(ctx, "plus_ones", f"Guests joining you (up to {allow['plus_ones']})", allow["plus_ones"])
                   + _field(ctx, "plus_one_names", "Their names") + "</div>")
    if allow["children"]:
        att.append(_number_select(ctx, "children", f"Children attending (up to {allow['children']})", allow["children"]))
    funcs = ctx["functions"]
    if len(funcs) > 1 and ctx["feat"]("multi_functions"):
        sel = ctx["guest_functions"]
        boxes = "".join(
            f'<label class="ev-check"><input type="checkbox" name="functions" value="{esc(f.get("id", k))}"'
            f'{" checked" if (sel.get(f.get("id"), 1) if sel else True) else ""}><span>{esc(f["name"])}'
            f'{(" · " + esc(fmt_date(f.get("func_date"), False))) if f.get("func_date") else ""}</span></label>'
            for k, f in enumerate(funcs))
        att.append(f'<fieldset class="ev-choice"><legend>Which parts will you attend?</legend>{boxes}</fieldset>')
    if ctx["meals"]:
        cur = str(_val(ctx, "meal_item_id", "") or "")
        opts = '<option value="">Choose a meal</option>' + "".join(
            f'<option value="{esc(m.get("id", k))}"{" selected" if str(m.get("id", k)) == cur else ""}>{esc(m["name"])}</option>'
            for k, m in enumerate(ctx["meals"]))
        att.append(f'<div class="ev-field"><label for="r-meal">Meal choice</label><select class="ev-input" id="r-meal" name="meal_item_id">{opts}</select>{_err(ctx, "meal_item_id")}</div>')
    if ctx["feat"]("dietary"):
        chosen = {x.strip() for x in str(_val(ctx, "dietary", "")).split(",") if x.strip()}
        offered = ctx["info"].get("dietary_options") or events.DIETARY_OPTIONS
        boxes = "".join(f'<label class="ev-check"><input type="checkbox" name="dietary" value="{esc(o)}"{" checked" if o in chosen else ""}><span>{esc(o)}</span></label>'
                        for o in offered)
        att.append(f'<fieldset class="ev-choice ev-choice--wrap"><legend>Dietary requirements</legend>{boxes}</fieldset>'
                   + _field(ctx, "allergies", "Allergies we should know about"))
    if att:
        parts.append('<div class="ev-attending" data-attending>' + "".join(att) + "</div>")
    parts.append(f'<div class="ev-field"><label for="r-req">Message or special requests</label>'
                 f'<textarea class="ev-input" id="r-req" name="special_requests" rows="3" maxlength="1000">{esc(_val(ctx, "special_requests"))}</textarea></div>')
    parts.append('<div class="ev-hp" aria-hidden="true"><label>Leave empty <input name="website" tabindex="-1" autocomplete="off"></label></div>')
    privacy = ('<p class="ev-small ev-muted">Your reply is shared only with the hosts. '
               'It is never shown to other guests.</p>')
    if demo:
        return (f'<form class="ev-rsvp" onsubmit="return false"><fieldset disabled>{"".join(parts)}'
                f'<button class="ev-btn ev-btn--wide" type="button">Send my reply</button></fieldset>'
                f'<p class="ev-small ev-muted">This is a sample. RSVPs work on your own published event.</p></form>')
    action = f'{ctx["path"]}/rsvp'
    disabled = ""
    if mode == "preview":
        disabled = " disabled"
        privacy += '<p class="ev-small ev-muted">Preview only: guests can reply once the website is published.</p>'
    return (f'<form class="ev-rsvp" method="post" action="{esc(action)}" novalidate>'
            f'<input type="hidden" name="_csrf" value="{esc(ctx["csrf"])}">{"".join(parts)}'
            f'<button class="ev-btn ev-btn--wide" type="submit"{disabled}>Send my reply</button>{privacy}</form>')


BUILDERS = {
    "invitation": s_invitation, "countdown": s_countdown, "venue": s_venue, "programme": s_programme,
    "menu": s_menu, "dress_code": s_dress, "rsvp": rsvp_form, "seating": s_seating,
    "accommodation": s_accommodation, "registry": s_registry, "gallery": s_gallery, "contact": s_contact,
}


def collect(ctx, order=None) -> list:
    """[(key, inner_html)] for visible sections that have content."""
    out = []
    for key in order or ORDER:
        if not ctx["show"].get(key):
            continue
        html = BUILDERS[key](ctx)
        if html:
            out.append((key, html))
    return out


def head(key: str, title: str, kicker: str = "", tag: str = "h2") -> str:
    k = f'<p class="ev-kicker">{esc(kicker)}</p>' if kicker else ""
    return f'<header class="ev-h">{k}<{tag} id="{key}-h">{esc(title)}</{tag}></header>'


def section(key: str, inner: str, title: str = "", kicker: str = "", cls: str = "", heading: bool = True) -> str:
    h = head(key, title or TITLES[key], kicker) if heading else f'<h2 id="{key}-h" class="sr-only">{esc(title or TITLES[key])}</h2>'
    return (f'<section class="ev-sec ev-sec--{key} {cls}" id="{key}" aria-labelledby="{key}-h">'
            f'<div class="ev-sec__in">{h}<div class="ev-sec__body">{inner}</div></div></section>')


def nav(ctx, secs, cls: str = "ev-nav", numbered: bool = False) -> str:
    if len(secs) < 3:
        return ""
    items = "".join(
        f'<li><a href="#{k}">{f"<span class=ev-nav__n>{n:02d}</span>" if numbered else ""}{esc(NAV_LABELS[k])}</a></li>'
        for n, (k, _) in enumerate(secs, 1) if k != "countdown")
    return f'<nav class="{cls}" aria-label="Event sections"><ul>{items}</ul></nav>'


def rsvp_cta(ctx, label: str = "RSVP") -> str:
    if ctx["show"].get("rsvp"):
        return f'<a class="ev-btn" href="#rsvp">{esc(label)}</a>'
    return ""


def greeting(ctx) -> str:
    g = ctx["guest"]
    if g is None:
        return ""
    return f'<p class="ev-greet">Dear {esc(g["first_name"])},</p>'


# --- ornaments ------------------------------------------------------------------------------
SPRIG = """<svg class="orn orn-sprig" viewBox="0 0 220 220" aria-hidden="true"><g fill="none" stroke-linecap="round">
<path class="o-stem" d="M14 206C60 160 98 120 150 40" stroke-width="1.6"/>
<path class="o-stem" d="M60 160c-6-24 4-44 22-52M84 132c22-4 40 6 46 26M100 104c-8-22 0-40 18-50M122 76c20 0 34 12 38 30M136 58c-2-20 8-34 26-40"/>
<g class="o-leaf"><path d="M58 160c-22-6-34-22-34-40 18 4 32 18 34 40Z"/><path d="M86 130c18-16 38-18 52-8-14 14-34 16-52 8Z"/>
<path d="M100 104c-20-10-26-28-20-44 16 8 24 26 20 44Z"/><path d="M124 76c16-14 34-14 46-4-12 12-30 14-46 4Z"/><path d="M136 58c-14-14-14-32-4-44 12 10 14 28 4 44Z"/></g>
<g class="o-bud"><circle cx="152" cy="36" r="7"/><circle cx="168" cy="22" r="4.5"/><circle cx="40" cy="186" r="5"/></g></g></svg>"""

FAN = """<svg class="orn orn-fan" viewBox="0 0 400 210" aria-hidden="true"><g fill="none" stroke-width="1">
<path d="M10 205a190 190 0 0 1 380 0"/><path d="M50 205a150 150 0 0 1 300 0"/><path d="M90 205a110 110 0 0 1 220 0"/><path d="M130 205a70 70 0 0 1 140 0"/>
<path d="M200 205V15M200 205 66 71M200 205 334 71M200 205 10 205M200 205 390 205M200 205 108 34M200 205 292 34M200 205 28 125M200 205 372 125"/></g></svg>"""

DECO_RULE = """<svg class="orn orn-deco" viewBox="0 0 240 20" aria-hidden="true"><g fill="none" stroke-width="1"><path d="M0 10h96M144 10h96"/><path d="m120 1 9 9-9 9-9-9Z"/><path d="m104 10 4-4 4 4-4 4ZM128 10l4-4 4 4-4 4Z"/></g></svg>"""


def _row(y, cls, w, step, size=4):
    return "".join(f'<rect class="{cls}" x="{x}" y="{y}" width="{size}" height="{size}"/>' for x in range(2, w, step))


# Border patterns for the Heritage cultural styles: (tile width, SVG shapes). Shapes use classes m1..m6,
# filled from the culture's motif colours (themes.CULTURES), so one tile serves every colour change.
MOTIFS = {
    "ndebele": (72, '<rect class="m6" width="72" height="26"/><rect class="m5" width="72" height="3"/><rect class="m5" y="23" width="72" height="3"/>'
                    '<rect class="m5" x="2" y="5" width="22" height="16"/><rect class="m2" x="4" y="7" width="18" height="12"/><rect class="m5" x="11" y="7" width="4" height="12"/>'
                    '<rect class="m5" x="26" y="5" width="22" height="16"/><rect class="m1" x="28" y="7" width="18" height="12"/><path class="m6" d="M29 19 37 9l8 10Z"/>'
                    '<rect class="m5" x="50" y="5" width="20" height="16"/><rect class="m3" x="52" y="7" width="16" height="12"/><rect class="m4" x="55" y="10" width="10" height="6"/>'),
    "zulu": (48, '<rect class="m6" width="48" height="26"/><path class="m1" d="M0 21 12 5l12 16Z"/><path class="m3" d="M24 21 36 5l12 16Z"/>'
                 '<path class="m5" d="M12 5h24L24 21Z"/><path class="m2" d="M36 5h24L48 21Z"/><path class="m2" d="M-12 5h24L0 21Z"/>'
                 + "".join(f'<circle class="m5" cx="{x}" cy="2.2" r="1.1"/><circle class="m5" cx="{x}" cy="23.8" r="1.1"/>' for x in range(2, 48, 4))),
    "xhosa": (40, '<rect class="m2" width="40" height="26"/><rect class="m5" y="2" width="40" height="1.5"/><rect class="m5" y="5" width="40" height="4"/>'
                  '<rect class="m5" y="17" width="40" height="4"/><rect class="m5" y="22.5" width="40" height="1.5"/>'
                  '<rect class="m3" x="2" y="11" width="4" height="4"/><rect class="m6" x="10" y="11" width="4" height="4"/><rect class="m1" x="18" y="11" width="4" height="4"/>'
                  '<rect class="m6" x="26" y="11" width="4" height="4"/><rect class="m4" x="34" y="11" width="4" height="4"/>'),
    "pedi": (36, '<rect class="m1" width="6" height="26"/><rect class="m6" x="6" width="6" height="26"/><rect class="m3" x="12" width="6" height="26"/>'
                 '<rect class="m2" x="18" width="6" height="26"/><rect class="m5" x="24" width="6" height="26"/><rect class="m4" x="30" width="6" height="26"/>'
                 '<rect class="m6" y="10" width="36" height="6"/>' + "".join(f'<path class="m5" d="M{x} 16 {x + 3} 10l3 6Z"/>' for x in range(0, 36, 6))),
    "venda": (36, '<rect class="m5" width="36" height="26"/><rect class="m1" y="2" width="36" height="2"/><rect class="m2" y="5" width="36" height="2"/>'
                  '<rect class="m4" y="19" width="36" height="2"/><rect class="m3" y="22" width="36" height="2"/>'
                  '<path class="m6" d="M0 17 6 9l6 8Z"/><path class="m2" d="M6 9h12l-6 8Z"/><path class="m1" d="M12 17 18 9l6 8Z"/>'
                  '<path class="m6" d="M18 9h12l-6 8Z"/><path class="m4" d="M24 17 30 9l6 8Z"/><path class="m2" d="M30 9h12l-6 8Z"/><path class="m2" d="M-6 9H6l-6 8Z"/>'),
    "tsonga": (24, '<rect class="m1" width="4" height="18"/><rect class="m2" x="4" width="4" height="18"/><rect class="m3" x="8" width="4" height="18"/>'
                   '<rect class="m6" x="12" width="4" height="18"/><rect class="m4" x="16" width="4" height="18"/><rect class="m5" x="20" width="4" height="18"/>'
                   '<path class="m5" d="M0 18 3 26 6 18Z"/><path class="m3" d="M6 18 9 26 12 18Z"/><path class="m1" d="M12 18 15 26 18 18Z"/><path class="m4" d="M18 18 21 26 24 18Z"/>'),
    "swati": (40, '<rect class="m1" width="40" height="26"/><rect class="m5" width="40" height="3"/><rect class="m5" y="23" width="40" height="3"/>'
                  '<ellipse class="m6" cx="10" cy="13" rx="4.5" ry="7.5"/><rect class="m5" x="9.4" y="6" width="1.2" height="14"/>'
                  '<circle class="m5" cx="8" cy="10" r=".9"/><circle class="m5" cx="12" cy="16" r=".9"/><path class="m2" d="M20 9l3 4-3 4-3-4Z"/>'
                  '<ellipse class="m5" cx="30" cy="13" rx="4.5" ry="7.5"/><rect class="m6" x="29.4" y="6" width="1.2" height="14"/>'
                  '<circle class="m6" cx="28" cy="16" r=".9"/><circle class="m6" cx="32" cy="10" r=".9"/>'),
}


def beads(cls: str = "", culture: str = "") -> str:
    if culture in MOTIFS:
        width, tile = MOTIFS[culture]
        pid = f"bd-{culture}-{cls or 'x'}"
        return (f'<div class="orn-beads orn-beads--{culture} {cls}" aria-hidden="true"><svg width="100%" height="26"><defs>'
                f'<pattern id="{pid}" width="{width}" height="26" patternUnits="userSpaceOnUse">{tile}</pattern></defs>'
                f'<rect width="100%" height="26" fill="url(#{pid})"/></svg></div>')
    tri = "".join(
        f'<path class="{"bd-a" if k % 3 == 0 else "bd-b" if k % 3 == 1 else "bd-c"}" d="M{k*24} 22l12-18 12 18Z"/>'
        f'<path class="bd-d" d="M{k*24+12} 4l6 9-6 9-6-9Z"/>' for k in range(4))
    return (f'<div class="orn-beads {cls}" aria-hidden="true"><svg width="100%" height="26"><defs>'
            f'<pattern id="bd{cls or "x"}" width="96" height="26" patternUnits="userSpaceOnUse">{tri}'
            f'<rect class="bd-c" y="23" width="96" height="3"/></pattern></defs>'
            f'<rect width="100%" height="26" fill="url(#bd{cls or "x"})"/></svg></div>')


CREST = """<svg class="orn orn-crest" viewBox="0 0 160 170" aria-hidden="true"><g fill="none" stroke-width="1.4">
<path class="o-shield" d="M80 18 128 34v44c0 32-20 54-48 66-28-12-48-34-48-66V34Z"/>
<path d="M80 26 120 39v39c0 27-16 46-40 56-24-10-40-29-40-56V39Z" opacity=".5"/>
<g class="o-laurel"><path d="M28 70c-8 30 6 62 40 80M132 70c8 30-6 62-40 80"/>
<path d="M26 86c-8-2-12-8-12-14 8 2 12 8 12 14ZM28 104c-8 0-14-5-15-11 8 0 13 5 15 11ZM36 121c-8 2-14-2-17-8 8-1 14 3 17 8ZM48 136c-7 4-14 2-18-3 7-3 14-1 18 3Z"/>
<path d="M134 86c8-2 12-8 12-14-8 2-12 8-12 14ZM132 104c8 0 14-5 15-11-8 0-13 5-15 11ZM124 121c8 2 14-2 17-8-8-1-14 3-17 8ZM112 136c7 4 14 2 18-3-7-3-14-1-18 3Z"/></g>
<path d="M62 8h36M70 4h20" stroke-linecap="round"/></g></svg>"""

MOON = """<svg class="orn orn-moon" viewBox="0 0 200 160" aria-hidden="true"><g fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
<path class="o-moon" d="M116 22a52 52 0 1 0 50 72 44 44 0 1 1-50-72Z"/>
<path class="o-star" d="m40 30 3 8 8 3-8 3-3 8-3-8-8-3 8-3Z"/><path class="o-star" d="m170 18 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z"/>
<path class="o-star" d="m26 112 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z"/><circle cx="182" cy="64" r="1.6"/><circle cx="58" cy="76" r="1.6"/><circle cx="150" cy="140" r="1.6"/>
<path d="M60 150c14-10 30-10 44 0s30 10 44 0" opacity=".6"/></g></svg>"""

STAR = """<svg class="orn orn-star" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 2.6 7.4L22 12l-7.4 2.6L12 22l-2.6-7.4L2 12l7.4-2.6Z"/></svg>"""

CONFETTI = "".join(f'<i class="cf cf-{k}" aria-hidden="true"></i>' for k in range(14))


def monogram_ring(ctx, cls: str = "ev-mono") -> str:
    if ctx["logo"]:
        return f'<div class="{cls} {cls}--logo"><img src="{esc(ctx["logo"])}" alt="{esc(ctx["hosts"])} logo"></div>'
    return f'<div class="{cls}" aria-hidden="true"><span>{esc(ctx["monogram"])}</span></div>'


# --- layouts ----------------------------------------------------------------------------------
def atelier(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    hero = (f'<header class="at-hero" id="welcome">{monogram_ring(ctx)}'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="at-names">{names_html(ctx, "&amp;")}</h1>'
            f'<div class="at-rule" aria-hidden="true"></div>'
            f'<p class="at-date">{esc(dp["weekday"])}{", " if dp["weekday"] else ""}{esc(dp["day"])} {esc(dp["month"])} {esc(dp["year"])}</p>'
            f'<p class="at-place">{esc(ctx["venue"].get("name") or "")}</p>{rsvp_cta(ctx, "Reply")}</header>')
    body = "".join(section(k, html, cls="at-sec") for k, html in secs)
    photo = f'<div class="at-photo">{hero_image(ctx)}</div>' if ctx["hero"] else ""
    return hero + nav(ctx, secs, "ev-nav at-nav") + photo + f'<div class="at-col">{body}</div>'


def folio(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    issue = {"weddings": "The Wedding Issue", "baby": "The Baby Issue", "parties": "The Party Issue"}.get(ctx["group"], "The Occasion Issue")
    art = '<span class="fo-art__mark">' + esc(ctx["monogram"]) + "</span>"
    hero = (f'<header class="fo-hero" id="welcome"><div class="fo-mast"><span>{esc(issue)}</span>'
            f'<span class="mono">{esc(dp["dd"])}.{esc(dp["mon"]).upper()}.{esc(dp["year"])}</span></div>'
            f'<div class="fo-hero__grid"><div class="fo-hero__text"><p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="fo-title">{names_html(ctx, "&amp;")}</h1>'
            f'<p class="fo-deck">{esc(ctx["wording"]["invitation"])}</p>'
            f'<div class="ev-actions">{rsvp_cta(ctx, "Reply to the invitation")}</div></div>'
            f'<figure class="fo-hero__fig">{hero_image(ctx, "ev-photo fo-photo", art)}'
            f'<figcaption>{esc(ctx["venue"].get("name") or ctx["title"])} · {esc(ctx["date_text"])}</figcaption></figure></div></header>')
    body = "".join(section(k, html, kicker=f"{n:02d}", cls="fo-sec") for n, (k, html) in enumerate(secs, 1))
    return hero + f'<div class="fo-body">{nav(ctx, secs, "ev-nav fo-index", numbered=True)}<div class="fo-main">{body}</div></div>'


def bloom(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    hero = (f'<header class="bl-hero" id="welcome">{SPRIG.replace("orn-sprig", "orn-sprig bl-tl")}{SPRIG.replace("orn-sprig", "orn-sprig bl-br")}'
            f'<div class="bl-hero__in"><p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<div class="bl-arch">{hero_image(ctx, "ev-photo bl-arch__img", SPRIG)}</div>'
            f'<h1 class="bl-names">{names_html(ctx, "&amp;")}</h1>'
            f'<p class="bl-date"><span>{esc(dp["weekday"])}</span><b>{esc(dp["day"])}</b><span>{esc(dp["month"])} {esc(dp["year"])}</span></p>'
            f'{rsvp_cta(ctx, "Kindly reply")}</div></header>')
    body = "".join(section(k, html, cls="bl-sec") + ('<div class="bl-div" aria-hidden="true">❀</div>' if n < len(secs) else "")
                   for n, (k, html) in enumerate(secs, 1))
    return hero + nav(ctx, secs, "ev-nav bl-nav") + f'<div class="bl-body">{body}</div>'


def heritage(ctx) -> str:
    from . import themes
    cult = themes.culture("heritage", ctx["theme"]["palette"])
    dp = date_parts(ctx)
    secs = collect(ctx)
    sides = (ctx["gs"].get("sides") or [])
    fam = ""
    if sides and ctx["group"] in ("weddings", "other"):
        fam_items = "".join(f'<li><span class="hr-fam__mark" aria-hidden="true">◆</span><h3>{esc(s)}</h3></li>' for s in sides[:4])
        fam = (f'<section class="ev-sec hr-fam" aria-labelledby="fam-h"><div class="ev-sec__in">{head("fam", "Two families, one celebration", "Umndeni")}'
               f'<p class="ev-text">{esc(ctx["wording"].get("families") or "With the blessing of our elders and the joy of both families, we welcome you.")}</p>'
               f'<ul class="hr-fam__list">{fam_items}</ul></div></section>')
    hero = (f'{beads("hr-top", cult)}<header class="hr-hero" id="welcome"><div class="hr-hero__text">'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}<h1 class="hr-names">{names_html(ctx, "&amp;")}</h1>'
            f'<p class="hr-date">{esc(dp["day"])} · {esc(dp["month"])} · {esc(dp["year"])}</p>'
            f'<p class="ev-text">{esc(ctx["venue"].get("name") or "")}</p><div class="ev-actions">{rsvp_cta(ctx, "Respond")}</div></div>'
            f'<div class="hr-hero__mark"><div class="hr-diamond">{hero_image(ctx, "ev-photo hr-photo", "<span>" + esc(ctx["monogram"]) + "</span>")}</div></div></header>{beads("hr-mid", cult)}')
    body = ""
    for n, (k, html) in enumerate(secs):
        if k == "venue" and len(ctx["functions"]) > 1:
            title = "The ceremonies"
        else:
            title = TITLES[k]
        body += section(k, html, title=title, cls="hr-sec" + (" hr-sec--alt" if n % 2 else ""))
        if k in ("invitation",) and fam:
            body += fam
            fam = ""
    return hero + nav(ctx, secs, "ev-nav hr-nav") + fam + body + beads("hr-bottom", cult)


def champagne(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    hero = (f'<header class="ch-hero" id="welcome">{FAN}<div class="ch-hero__in">'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="ch-names foil">{names_html(ctx, "&amp;")}</h1>{DECO_RULE}'
            f'<p class="ch-date"><span>{esc(dp["weekday"])}</span><b class="foil">{esc(dp["dd"])}</b><span>{esc(dp["month"])} {esc(dp["year"])}</span></p>'
            f'<p class="ch-place">{esc(ctx["venue"].get("name") or "")}</p>{rsvp_cta(ctx, "RSVP")}</div></header>')
    body = "".join(section(k, html, cls="ch-sec ch-glass") for k, html in secs)
    photo = f'<div class="ch-photo">{hero_image(ctx)}</div>' if ctx["hero"] else ""
    return hero + nav(ctx, secs, "ev-nav ch-nav") + photo + f'<div class="ch-body">{body}</div>'


def linea(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    v = ctx["venue"]
    meta = (f'<dl class="li-meta"><div><dt>Date</dt><dd>{esc(dp["day"])} {esc(dp["month"])} {esc(dp["year"])}</dd></div>'
            f'<div><dt>Time</dt><dd>{esc(ctx["time_text"] or "To be confirmed")}</dd></div>'
            f'<div><dt>Place</dt><dd>{esc(v.get("name") or "To be confirmed")}</dd></div></dl>')
    hero = (f'<header class="li-hero" id="welcome"><div class="li-hero__top"><span class="li-mono">{esc(ctx["monogram"])}</span>'
            f'{nav(ctx, secs, "ev-nav li-nav")}</div>'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}<h1 class="li-names">{names_html(ctx, "+")}</h1>{meta}'
            f'{("<div class=li-photo>" + hero_image(ctx) + "</div>") if ctx["hero"] else ""}</header>')
    rows = "".join(
        f'<section class="ev-sec li-row ev-sec--{k}" id="{k}" aria-labelledby="{k}-h"><div class="li-row__label">'
        f'<span class="li-row__n">{n:02d}</span><h2 id="{k}-h">{esc(TITLES[k])}</h2></div>'
        f'<div class="li-row__body ev-sec__body">{html}</div></section>'
        for n, (k, html) in enumerate(secs, 1))
    return hero + f'<div class="li-body">{rows}</div>'


def confetti(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    hero = (f'<header class="cf-hero" id="welcome"><div class="cf-sky">{CONFETTI}</div><div class="cf-card">'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="cf-names">{names_html(ctx, "&amp;")}</h1>'
            f'<div class="cf-sticker"><b>{esc(dp["day"])}</b><span>{esc(dp["mon"])}</span></div>'
            f'<p class="cf-when">{esc(ctx["date_text"])}{(" · " + esc(ctx["time_text"])) if ctx["time_text"] else ""}</p>'
            f'{rsvp_cta(ctx, "Count me in")}</div></header>')
    cards = "".join(section(k, html, cls=f"cf-sec cf-tone-{n % 4}") for n, (k, html) in enumerate(secs))
    photo = f'<div class="cf-photo">{hero_image(ctx)}</div>' if ctx["hero"] else ""
    return hero + nav(ctx, secs, "ev-nav cf-nav") + photo + f'<div class="cf-board">{cards}</div>'


def pulse(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    tick_items = [ctx["hosts"], ctx["date_text"], ctx["venue"].get("name") or "", "RSVP by " + ctx["deadline_text"]]
    tick = " ✦ ".join(esc(x) for x in tick_items if x)
    hero = (f'<header class="pu-hero" id="welcome"><p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="pu-names">{names_html(ctx, "+")}</h1>'
            f'<div class="pu-date"><b>{esc(dp["dd"])}</b><span>{esc(dp["month"])}<br>{esc(dp["year"])}</span>'
            f'<div class="ev-actions">{rsvp_cta(ctx, "I am in")}</div></div></header>'
            f'<div class="pu-ticker" aria-hidden="true"><div class="pu-ticker__track"><span>{tick} ✦ </span><span>{tick} ✦ </span><span>{tick} ✦ </span></div></div>')
    blocks = "".join(section(k, html, title=TITLES[k], kicker=f"{n:02d}/{len(secs):02d}", cls=f"pu-sec pu-tone-{n % 3}")
                     for n, (k, html) in enumerate(secs, 1))
    photo = f'<div class="pu-photo">{hero_image(ctx)}</div>' if ctx["hero"] else ""
    return hero + photo + nav(ctx, secs, "ev-nav pu-nav") + blocks


def aurora(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    field = '<div class="au-field" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'
    chips = "".join(f'<span class="au-chip">{esc(x)}</span>' for x in
                    (f'{dp["weekday"]} {dp["day"]} {dp["month"]} {dp["year"]}'.strip(), ctx["time_text"],
                     ctx["venue"].get("name") or "") if x)
    hero = (f'<header class="au-hero" id="welcome"><div class="au-glass au-hero__card">'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="au-names">{names_html(ctx, "&amp;")}</h1><div class="au-chips">{chips}</div>'
            f'<div class="ev-actions">{rsvp_cta(ctx, "RSVP")}</div></div></header>')
    wide = {"invitation", "rsvp", "programme", "gallery", "menu", "venue"}
    cards = "".join(section(k, html, cls="au-glass au-card" + (" au-card--wide" if k in wide else "")) for k, html in secs)
    photo = f'<div class="au-glass au-photo">{hero_image(ctx)}</div>' if ctx["hero"] else ""
    return field + hero + nav(ctx, secs, "ev-nav au-nav au-glass") + f'<div class="au-bento">{photo}{cards}</div>'


def laureate(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    crest = (f'<div class="la-crest">{CREST}<span class="la-crest__mono">{esc(ctx["monogram"])}</span></div>'
             if not ctx["logo"] else monogram_ring(ctx, "la-logo"))
    hero = (f'<header class="la-hero" id="welcome"><div class="la-frame">{crest}'
            f'<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="la-names">{names_html(ctx, "&amp;")}</h1>'
            f'<p class="la-formal">{esc(ctx["wording"]["invitation"])}</p>'
            f'<p class="la-date">{esc(dp["weekday"])} the {esc(dp["day"])} of {esc(dp["month"])}, {esc(dp["year"])}</p>'
            f'{rsvp_cta(ctx, "Respond")}</div></header>')
    main_keys = {"invitation", "programme", "menu", "rsvp", "gallery", "countdown"}
    main = "".join(section(k, html, cls="la-sec") for k, html in secs if k in main_keys and k != "invitation")
    inv = next((html for k, html in secs if k == "invitation"), "")
    side = "".join(section(k, html, cls="la-sec la-side") for k, html in secs if k not in main_keys)
    photo = f'<div class="la-photo">{hero_image(ctx)}</div>' if ctx["hero"] else ""
    invsec = section("invitation", inv, title="With pleasure", cls="la-sec la-inv") if inv else ""
    return (hero + nav(ctx, secs, "ev-nav la-nav") + photo + invsec +
            f'<div class="la-cols"><div class="la-main">{main}</div><aside class="la-aside" aria-label="Details">{side}</aside></div>')


def cradle(ctx) -> str:
    dp = date_parts(ctx)
    secs = collect(ctx)
    hero = (f'<header class="cr-hero cr-page" id="welcome">{MOON}<p class="ev-kicker">{esc(ctx["wording"]["welcome"])}</p>{greeting(ctx)}'
            f'<h1 class="cr-names">{names_html(ctx, "&amp;")}</h1>'
            f'<p class="cr-date">{esc(dp["weekday"])}, {esc(dp["day"])} {esc(dp["month"])} {esc(dp["year"])}</p>'
            f'{("<div class=cr-photo>" + hero_image(ctx) + "</div>") if ctx["hero"] else ""}'
            f'{rsvp_cta(ctx, "Reply")}<span class="cr-pageno">i</span></header>')
    pages = "".join(
        section(k, html, kicker=f"Chapter {n}", cls="cr-page cr-sec").replace(
            "</div></section>", f'</div><span class="cr-pageno">{n}</span>{STAR}</section>', 1)
        for n, (k, html) in enumerate(secs, 1))
    return hero + nav(ctx, secs, "ev-nav cr-nav") + f'<div class="cr-book">{pages}</div>'


LAYOUTS = {
    "atelier": atelier, "folio": folio, "bloom": bloom, "heritage": heritage, "champagne": champagne,
    "linea": linea, "confetti": confetti, "pulse": pulse, "aurora": aurora, "laureate": laureate, "cradle": cradle,
}
