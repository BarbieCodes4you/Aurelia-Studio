#!/usr/bin/env python3
"""Build the shareable, server-free version of the Aurelia site (published as a Claude Artifact).

It renders the public pages from the real app, turns links into in-page routes, and adds the
browser-side customer journey (preview_site/journey.js + eventrender.js): choose occasion and
template, the 10-step set-up with live preview, package choice and booking request. Drafts are
saved in the visitor's browser; the booking ends with a summary to email and an optional payment
link per package (preview_site/payment_links.json).

    python3 tools/export_preview.py OUT_DIR                # for a Claude Artifact
    python3 tools/export_preview.py OUT_DIR --standalone   # for Netlify / any static host
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
# --standalone: write index.html as a complete HTML document, for static hosts (Netlify, Cloudflare
# Pages, GitHub Pages). Without it, index.html is a fragment for a Claude Artifact, which adds the shell.
STANDALONE = "--standalone" in sys.argv[1:]
OUT = os.path.abspath(ARGS[0] if ARGS else os.path.join(SRC, "preview_build"))
sys.path.insert(0, SRC)
from tests.helpers import Client, fresh_app  # noqa: E402  (uses a temporary data folder)
from app import catalog, config, db, events, suggestions  # noqa: E402
from app.eventsite import designs, render as ev_render, themes  # noqa: E402
from app.views import wizard  # noqa: E402

app = fresh_app("export")
c = Client(app)
EMAIL = config.SUPPORT_EMAIL

if os.path.isdir(OUT):
    shutil.rmtree(OUT)
for d in ("static/css", "static/js", "static/img"):
    os.makedirs(os.path.join(OUT, d))
for f in ["css/app.css", "css/icons.css", "css/eventsite.css", "js/eventsite.js", "img/favicon.svg"]:
    shutil.copy(os.path.join(SRC, "static", f), os.path.join(OUT, "static", f))
for f in ("eventrender.js", "journey.js"):
    shutil.copy(os.path.join(SRC, "preview_site", f), os.path.join(OUT, "static/js", f))

js = open(os.path.join(SRC, "static/js/app.js")).read()
js = js.replace('doc.querySelectorAll("[data-groups]").forEach(function (card) {',
                '(filterBar.closest("section") || doc).querySelectorAll("[data-groups]").forEach(function (card) {')
js = re.sub(r'\s*if \(history\.replaceState\) history\.replaceState\([^;]*\);', "", js)
open(os.path.join(OUT, "static/js/app.js"), "w").write(js)

# --- data for the browser journey ----------------------------------------------------------------
links_file = os.path.join(SRC, "preview_site", "payment_links.json")
payment_links = json.load(open(links_file)) if os.path.isfile(links_file) else {}
PAY_HOSTS = ("payfast.io", "payfast.co.za", "payf.st")


def _pay_host_ok(url: str) -> bool:
    m = re.match(r"^https://([^/?#]+)", url or "")
    return bool(m) and any(m.group(1) == h or m.group(1).endswith("." + h) for h in PAY_HOSTS)


def payment_option(value):
    """A package's payment set-up: a PayFast link, or the HTML of a PayFast "Pay Now" button pasted as it
    was generated. The button's form is rebuilt from its action and hidden fields only, and only for
    PayFast addresses, so nothing else from the pasted code reaches the page."""
    value = (value or "").strip() if isinstance(value, str) else ""
    if not value:
        return ""
    if "<form" in value.lower():
        action = re.search(r'<form[^>]*\saction=["\']([^"\']+)', value, re.I)
        if not action or not _pay_host_ok(action.group(1)):
            sys.exit("payment_links.json: a pasted button must post to a PayFast address (payfast.io or payfast.co.za).")
        fields = {}
        for tag in re.findall(r"<input[^>]*>", value, re.I):
            name = re.search(r'\sname=["\']([^"\']+)', tag, re.I)
            val = re.search(r'\svalue=["\']([^"\']*)', tag, re.I)
            kind = re.search(r'\stype=["\']([^"\']+)', tag, re.I)
            if name and (not kind or kind.group(1).lower() == "hidden"):
                fields[name.group(1)] = val.group(1) if val else ""
        if not fields:
            sys.exit("payment_links.json: the pasted button has no hidden fields. Paste the whole code PayFast gives you.")
        return {"action": action.group(1), "fields": fields}
    if not _pay_host_ok(value):
        sys.exit(f"payment_links.json: {value[:60]} isn't a PayFast link (https://...payfast.io or payfast.co.za).")
    return value
data = {
    "brand": config.BRAND_NAME, "email": EMAIL,
    "groups": {k: {"name": g["name"]} for k, g in catalog.GROUPS.items()},
    "categories": [{"slug": r["slug"], "name": r["name"], "group": r["group_slug"], "description": r["description"],
                    "features": db.loads(r["features"], [])} for r in catalog.categories()],
    "templates": [{"slug": r["slug"], "name": r["name"], "design": r["design"], "direction": r["direction"],
                   "groups": db.loads(r["groups"], []), "description": r["description"]} for r in catalog.templates()],
    "packages": [{"code": p["code"], "name": p["name"], "tagline": p["tagline"], "price_cents": p["price_cents"],
                  "features": db.loads(p["features"], []), "bullets": db.loads(p["bullets"], []),
                  "limits": db.loads(p["limits"], {}), "highlight": p["highlight"]} for p in catalog.packages()],
    "limit_labels": catalog.LIMIT_LABELS,
    "themes": {"designs": {k: {"font_pair": v["font_pair"], "fonts": v["fonts"], "backgrounds": v["backgrounds"],
                               "background": v["background"], "palettes": [list(p) for p in v["palettes"]]}
                           for k, v in themes.DESIGNS.items()},
               "font_pairs": {k: list(v) for k, v in themes.FONT_PAIRS.items()},
               "fonts": themes.FONTS, "backgrounds": themes.BACKGROUND_LABELS},
    "sections": [list(s) for s in events.SECTION_KEYS], "dietary": events.DIETARY_OPTIONS,
    "group_wording": ev_render.GROUP_WORDING,
    "ornaments": {"sprig": designs.SPRIG, "fan": designs.FAN, "deco": designs.DECO_RULE, "crest": designs.CREST,
                  "moon": designs.MOON, "star": designs.STAR},
    "host_label": {k: list(v) for k, v in wizard.HOST_LABEL.items()},
    "courses": wizard.COURSES, "kinds": [list(k) for k in wizard.KINDS], "dress_codes": wizard.DRESS_CODES,
    "payment_links": {k: payment_option(v) for k, v in payment_links.items() if not k.startswith("_")},
    "suggest": {"wording": suggestions.WORDING, "programmes": {k: [list(x) for x in v] for k, v in suggestions.PROGRAMMES.items()},
                "programme_for": suggestions.PROGRAMME_FOR, "default_start": suggestions.DEFAULT_START, "name_noun": suggestions.NAME_NOUN},
    # Netlify Forms only exist on a standalone (Netlify) build; elsewhere the booking falls back to email.
    "forms": STANDALONE,
}
open(os.path.join(OUT, "static/js/data.js"), "w").write("window.AURELIA_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")

# --- pages -----------------------------------------------------------------------------------------
PAGES = {"/": "home", "/weddings": "weddings", "/baby-celebrations": "baby-celebrations", "/parties": "parties",
         "/celebrations": "celebrations", "/templates": "templates", "/pricing": "pricing",
         "/how-it-works": "how-it-works", "/faq": "faq", "/contact": "contact", "/privacy": "privacy",
         "/terms": "terms", "/refunds": "refunds", "/help-me-set-up": "help-me-set-up"}
TPLS = {t["slug"]: db.loads(t["groups"], []) for t in catalog.templates()}
ACCOUNT = ("/login", "/register", "/dashboard", "/account", "/forgot-password")
previews = set()


def route_for(href: str) -> str:
    path, _, query = href.partition("?")
    q = dict(p.split("=", 1) for p in query.replace("&amp;", "&").split("&") if "=" in p)
    if path in PAGES:
        return "#" + PAGES[path]
    m = re.match(r"^/templates/([a-z0-9-]+)$", path)
    if m and m.group(1) in TPLS:
        groups = TPLS[m.group(1)]
        g = q.get("group") if q.get("group") in groups else groups[0]
        return f"#tpl-{m.group(1)}-{g}"
    if path == "/create":
        for key, tag in (("template", "tpl"), ("category", "cat"), ("package", "pkg"), ("group", "grp")):
            if q.get(key):
                return f"#create-{tag}-{q[key]}"
        return "#create"
    if path.startswith(ACCOUNT):
        return "#my-events"
    return "#home"


def rewrite(html: str) -> str:
    html = html.replace(config.BASE_URL + "/events/", "aureliastudio.co.za/events/").replace(config.BASE_URL, "")

    def iframe(m):
        previews.add((m.group(1), m.group(2)))
        return f'src="pv-{m.group(1)}-{m.group(2)}.html"'
    html = re.sub(r'src="/templates/([a-z0-9-]+)/preview\?group=([a-z]+)"', iframe, html)
    html = html.replace("<iframe ", '<iframe loading="lazy" ').replace('loading="lazy" loading="lazy"', 'loading="lazy"')
    html = re.sub(r'(src|href)="/static/', r'\1="static/', html)
    html = html.replace('href="/favicon.svg"', 'href="static/img/favicon.svg"')
    html = re.sub(r'href="(/[^"]*)"', lambda m: f'href="{route_for(m.group(1))}"', html)
    return html


def main_of(html: str) -> str:
    return html.split('<main id="main">', 1)[1].rsplit("</main>", 1)[0]


views = {}
home = c.get("/").text
for path, vid in PAGES.items():
    r = c.get(path)
    assert r.status == 200, (path, r.status)
    views[vid] = main_of(r.text)
for slug, groups in TPLS.items():
    for g in groups:
        r = c.get(f"/templates/{slug}?group={g}")
        assert r.status == 200, (slug, g)
        views[f"tpl-{slug}-{g}"] = main_of(r.text)

views["home"] = views["home"].replace('id="pricing"', 'id="home-pricing"')
for v in ("weddings", "baby-celebrations", "parties", "celebrations"):
    views[v] = views[v].replace('href="#templates"', 'href="#cat-templates"').replace('id="templates"', 'id="cat-templates"')
notice = (f'<div class="notice" style="max-width:520px"><i class="i i--mail" aria-hidden="true"></i><div><b>Email us</b><br>'
          f'<span class="mono" style="user-select:all">{EMAIL}</span><br>'
          f'<button class="btn btn--sm btn--secondary" type="button" data-copy="{EMAIL}" data-copied="Email address copied" style="margin-top:10px">Copy email address</button></div></div>')
if STANDALONE:
    # Real forms on Netlify: journey.js posts them to Netlify Forms and shows the reference.
    for vid, name in (("contact", "contact"), ("help-me-set-up", "setup-help")):
        views[vid] = re.sub(r'<form class="form box" method="post" novalidate><input type="hidden" name="_csrf" value="[^"]*">',
                            f'<form class="form box" novalidate data-no-busy data-static-form="{name}">', views[vid], count=1)
        assert f'data-static-form="{name}"' in views[vid], vid
else:
    views["contact"] = re.sub(r'<form class="form box".*?</form>', notice, views["contact"], flags=re.S)
    views["help-me-set-up"] = re.sub(r'<form class="form box".*?</form>',
                                     notice.replace("<b>Email us</b>", "<b>Email us your date, occasion and how to reach you</b>"),
                                     views["help-me-set-up"], flags=re.S)

head_links = rewrite(re.search(r'(<link rel="preconnect".*?)<script>', home, re.S).group(1))
theme_script = re.search(r"(<script>\(function\(\)\{try.*?</script>)", home, re.S).group(1)
chrome_start = home.split('<meta name="csrf"', 1)[1].split(">", 1)[1].split('<main id="main">')[0]
chrome_start = chrome_start.replace(">Log in</a>", ">My events</a>")
footer = home.split("</main>", 1)[1].split('<div class="toasts"')[0]

sections = "".join(f'<div class="view" data-view="{vid}"{"" if vid == "home" else " hidden"}>{rewrite(html)}</div>'
                   for vid, html in views.items())
sections += '<div class="view" data-view="journey" hidden><div id="journey-root"></div></div>'
router = """<script>(function(){var views=document.querySelectorAll('[data-view]');var navs=document.querySelectorAll('.nav a, .drawer nav a');
function show(){var id=(location.hash||'#home').slice(1);var J=window.AureliaJourney;var target;
if(J&&J.handles(id)){target=document.querySelector('[data-view="journey"]');}else{target=document.querySelector('[data-view="'+id+'"]');}
if(!target){var cur=document.querySelector('[data-view]:not([hidden])');var el=cur&&cur.querySelector('#'+CSS.escape(id));if(el){el.scrollIntoView({behavior:'smooth'});}return;}
views.forEach(function(v){v.hidden=v!==target;});window.scrollTo(0,0);
navs.forEach(function(a){var on=a.getAttribute('href')==='#'+id||(id.indexOf('tpl-')===0&&a.getAttribute('href')==='#templates');if(on)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
var d=document.getElementById('drawer');if(d&&d.open)d.close();
if(J&&J.handles(id)){J.route(id);}
var t=target.querySelector('h1');document.title=(t?t.textContent.trim()+' · ':'')+'""" + config.BRAND_NAME + """';
setTimeout(function(){window.dispatchEvent(new Event('resize'));target.querySelectorAll('[data-reveal]').forEach(function(e){e.classList.add('is-visible');});},60);}
window.addEventListener('hashchange',show);show();})();</script>"""
def _netlify_form(name: str, fields: list, files: list = ()) -> str:
    inputs = "".join(f'<textarea name="{f[1:]}"></textarea>' if f.startswith("~") else f'<input name="{f}">' for f in fields)
    inputs += "".join(f'<input type="file" name="{f}">' for f in files)
    return f'<form name="{name}" data-netlify="true" netlify-honeypot="website"><input name="website">{inputs}</form>'


# Netlify reads these at upload time to set up the forms; journey.js submits them with fetch.
netlify_forms = ('<div hidden aria-hidden="true">'
                 + _netlify_form("booking", ["kind", "ref", "package", "amount", "name", "email", "phone", "event", "occasion", "date",
                                             "guests", "~details", "~guest_list", "~draft"], ["hero", "logo", "background"])
                 + _netlify_form("booking-photos", ["ref", "email", "batch"], [f"photo{n}" for n in range(1, 9)])
                 + _netlify_form("contact", ["name", "email", "topic", "~message"])
                 + _netlify_form("setup-help", ["name", "email", "phone", "reach", "occasion", "event_date", "package", "~message"])
                 + "</div>") if STANDALONE else ""
scripts = ''.join(f'<script src="static/js/{n}"></script>' for n in ("app.js", "data.js", "eventrender.js", "journey.js"))
index = (f'<title>{config.BRAND_NAME}</title>\n{head_links}\n{theme_script}\n<script>document.body.classList.add("site");</script>\n'
         f'{rewrite(chrome_start)}<main id="main">{sections}</main>{rewrite(footer)}'
         f'<div class="toasts" aria-live="polite"></div>{netlify_forms}{scripts}{router}')
index = index.replace("<body", "<div").replace("</body>", "")
if STANDALONE:
    desc = ("Personalised event websites for South African weddings, baby celebrations and parties: "
            "RSVPs, guest list, seating, menus and reports in one link.")
    index = index.replace('<script>document.body.classList.add("site");</script>\n', "", 1)
    head_end = index.index(theme_script) + len(theme_script)
    index = ('<!doctype html><html lang="en-ZA"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1">'
             f'<meta name="description" content="{desc}">'
             '<link rel="icon" href="static/img/favicon.svg" type="image/svg+xml">\n'
             + index[:head_end] + '</head><body class="site">' + index[head_end:] + "</body></html>\n")
open(os.path.join(OUT, "index.html"), "w").write(index)

for slug, g in sorted(previews):
    html = c.get(f"/templates/{slug}/preview?group={g}").text
    html = re.sub(r'(src|href)="/static/', r'\1="static/', html)
    html = re.sub(r'href="/[^"]*"', 'href="#"', html)
    html = html.replace("</head>", "<script>document.addEventListener('submit',function(e){e.preventDefault();},true);</script></head>", 1)
    open(os.path.join(OUT, f"pv-{slug}-{g}.html"), "w").write(html)

leftover = re.findall(r'(?:href|src)="/[^"]*"', index)
print(f"{OUT}: {len(views)} pages + journey, {len(previews)} template samples, leftover absolute links: {len(leftover)}")
