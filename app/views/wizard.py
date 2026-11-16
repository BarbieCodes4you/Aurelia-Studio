"""Event creation: /create (choose occasion and template) and the 10-step set-up wizard.

Each step is its own form at /dashboard/events/<uid>/setup/<n>. Saving never publishes
anything; the event stays a private draft until a verified payment (step 10).
"""
from __future__ import annotations

import json

from .. import auth, catalog, config, db, events, suggestions
from ..eventsite import themes
from ..icons import i
from ..services import storage
from ..web import HTTPError, esc, json_response, redirect, router, url
from . import forms
from .forms import Form, check, csrf, errors_summary, field, select
from .layout import page
from .shell import organiser_page

STEPS = [
    (1, "Event details", "calendar"), (2, "Venue", "pin"), (3, "Design", "palette"), (4, "Guests", "users"),
    (5, "Programme", "list"), (6, "Food and drinks", "dish"), (7, "Seating", "seat"), (8, "Extras", "gift"),
    (9, "Review", "eye"), (10, "Package", "card"),
]
HOST_LABEL = {"weddings": ("Couple's names", "e.g. Lerato & Sipho"), "baby": ("Parents or honouree", "e.g. Naledi & Tumi"),
              "parties": ("Who are we celebrating?", "e.g. Kagiso's 40th"), "other": ("Host or organisation", "e.g. The Dlamini family")}
COURSES = ["Canapés", "Starter", "Main", "Dessert", "Late-night", "Drinks"]
KINDS = [("ceremony", "Ceremony"), ("reception", "Reception"), ("speech", "Speech"), ("entertainment", "Entertainment"),
         ("meal", "Meal"), ("activity", "Activity"), ("other", "Other")]
DRESS_CODES = ["", "Black tie", "Formal", "Cocktail", "Smart casual", "Traditional attire", "Cultural attire", "All white",
               "Garden party", "Casual", "Themed"]


def step_url(ev, n: int) -> str:
    return f"/dashboard/events/{ev['uid']}/setup/{n}"


def group_of(ev) -> str:
    c = catalog.category(ev["category"])
    return c["group_slug"] if c else "weddings"


def feature_note(ev, feature: str, what: str) -> str:
    if catalog.has_feature(ev, feature):
        return ""
    need = next((p["name"] for p in catalog.packages() if feature in catalog.package_features(p["code"])), "a higher package")
    return (f'<div class="notice notice--warn">{i("lock")}<span>{esc(what)} shows on your website with the {esc(need)}. '
            f'You can fill it in now and choose your package in step 10.</span></div>')


# --- /create -----------------------------------------------------------------------------------
def _package_picker(selected: str) -> str:
    opts = []
    for p in catalog.packages():
        opts.append(f'<label class="choice"><input type="radio" name="package" value="{esc(p["code"])}"{" checked" if p["code"] == selected else ""}>'
                    f'<span>{esc(p["name"])} · {catalog.money(p["price_cents"])}<small>{esc(p["tagline"])}</small></span></label>')
    return (f'<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">{"".join(opts)}</div>'
            '<p class="hint" style="margin-top:8px">You can change this any time before you pay. As you set up, we show what each package includes, '
            'so you don\'t fill in anything your package won\'t show. <a class="text-link" href="/pricing" target="_blank" rel="noopener">Compare packages</a></p>')


CREATE_JS = """<script>(function(){var f=document.querySelector('[data-create]');if(!f)return;var grid=f.querySelector('[data-tpl-grid]'),more=f.querySelector('[data-show-all]'),all=false;
function sync(auto){var c=f.querySelector('input[name=category]:checked');var g=c?c.getAttribute('data-group'):'';var first=null,shown=0;
grid.querySelectorAll('.choice').forEach(function(l){var ok=!g||l.getAttribute('data-groups').split(' ').indexOf(g)>-1;l.hidden=!(ok||all);if(ok){shown++;if(!first)first=l;}});
if(more){more.hidden=!g||all;more.textContent='Show all '+grid.querySelectorAll('.choice').length+' templates';}
var picked=grid.querySelector('input[name=template]:checked');if(auto&&first&&(!picked||picked.closest('.choice').hidden)){first.querySelector('input').checked=true;}}
f.addEventListener('change',function(e){if(e.target.name==='category')sync(true);});
if(more)more.addEventListener('click',function(){all=true;sync(false);});sync(false);})();</script>"""


@router.route("/create", methods=("GET", "POST"))
def create(req):
    src = req.form if req.method == "POST" else req.query
    get = (lambda k: (src.get(k) or [""])[0].strip())
    cat_slug = get("category")
    tpl_slug = get("template")
    group = get("group")
    cat = catalog.category(cat_slug) if cat_slug else None
    if cat:
        group = cat["group_slug"]
    tpl = catalog.template(tpl_slug) if tpl_slug else None
    if tpl and not group:
        group = (db.loads(tpl["groups"], []) or ["weddings"])[0]
    pkg = get("package") if catalog.package(get("package")) else "premium"
    f = Form(req)
    check_email = ""
    if req.method == "POST":
        if not cat or not cat["active"]:
            f.error("category", "Choose the type of event.")
        if not tpl or not tpl["active"]:
            f.error("template", "Choose a template. You can change it later.")
        user = req.user
        if not user:
            if req.get("website"):                    # honeypot: bots fill every field
                return redirect("/")
            cname = f.text("contact_name", "Your name", required=True, max=120)
            cemail = f.email("contact_email", required=True)
            if not f.flag("terms"):
                f.error("terms", "Please accept the terms and privacy notice to continue.")
            if f.ok and auth.rate_limited(f"create-account:{req.ip}", 10, 3600):
                f.error("contact_email", "Too many new accounts from this connection. Try again in an hour.")
            if f.ok:
                existing = db.one("SELECT * FROM users WHERE email = ?", (cemail,))
                back = url("/create", category=cat_slug, template=tpl_slug, package=pkg, go="1")
                if existing:
                    from .accounts import send_login_link
                    if existing["status"] == "active" and not auth.rate_limited(f"login-link:{cemail}", 5, 3600):
                        send_login_link(existing, back)
                    check_email = cemail
                else:
                    from ..services import email as mail
                    uid_ = db.insert("users", {"email": cemail, "name": cname, "password_hash": "", "role": "customer",
                                               "marketing_consent": 0, "created_at": db.now()})
                    user = db.one("SELECT * FROM users WHERE id = ?", (uid_,))
                    mail.send(cemail, "welcome", {"first_name": mail.first_name(cname)}, user_id=uid_)
                    from .accounts import send_verification
                    send_verification(user)
                    auth.audit(uid_, "user.register", cemail, via="create")
        if f.ok and user and not check_email:
            ev = events.create(user["id"], cat["slug"], tpl["slug"], cat["name"])
            events.touch(ev["id"], selected_package=pkg)
            auth.audit(user["id"], "event.create", ev["uid"], template=tpl["slug"])
            req.flash("success", "Your event is saved as a private draft. Let's add the details.")
            resp = redirect(step_url(ev, 1))
            if not req.user:
                from .accounts import login_session
                resp = login_session(resp, req, user["id"])
            return resp
    elif req.user and get("go") == "1" and cat and tpl:
        # back from an emailed sign-in link: create the event the visitor had chosen
        ev = events.create(req.user["id"], cat["slug"], tpl["slug"], cat["name"])
        events.touch(ev["id"], selected_package=pkg)
        auth.audit(req.user["id"], "event.create", ev["uid"], template=tpl["slug"])
        req.flash("success", "You're signed in and your event is saved as a private draft. Let's add the details.")
        return redirect(step_url(ev, 1))
    if check_email:
        body = f"""<section class="section" style="padding-top:calc(var(--header-h) + 48px)"><div class="container container--narrow"><div class="glass glass--strong panel" style="display:grid;gap:14px">
<span class="icon-tile icon-tile--soft">{i("mail")}</span><h1 style="font-size:clamp(1.8rem,1.3rem + 2vw,2.6rem)">You already have an account</h1>
<p class="lead" style="font-size:1.0625rem">We've emailed a sign-in link to <b>{esc(check_email)}</b>. Open it on this device and you'll come straight back here with your choices kept. The link expires in 2 hours.</p>
<p class="small muted">Rather use your password? <a class="text-link" href="{esc(url('/login', next=url('/create', category=cat_slug, template=tpl_slug, package=pkg, go='1')))}">Log in</a>.</p></div></div></section>"""
        return page(req, "Check your email", body, "/create", noindex=True)
    # occasion picker
    cats_html = []
    for gkey, g in catalog.GROUPS.items():
        opts = "".join(
            f'<label class="choice"><input type="radio" name="category" value="{esc(c["slug"])}"{" checked" if c["slug"] == cat_slug else ""} required data-group="{gkey}">'
            f'<span>{esc(c["name"])}<small>{esc(c["description"])}</small></span></label>'
            for c in catalog.categories() if c["group_slug"] == gkey)
        cats_html.append(f'<fieldset style="margin-bottom:22px"><legend>{esc(g["name"])}</legend><div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">{opts}</div></fieldset>')
    tpl_html = []
    for t in catalog.templates():
        d = themes.design(t["design"])
        sw = "".join(f'<i style="background:{c}"></i>' for c in list(d["palettes"][0][2].values())[:4])
        tpl_html.append(
            f'<label class="choice" data-groups="{esc(" ".join(db.loads(t["groups"], [])))}"><input type="radio" name="template" value="{esc(t["slug"])}"{" checked" if t["slug"] == tpl_slug else ""} required>'
            f'<span><span class="row row--between" style="gap:8px"><b>{esc(t["name"])}</b><span class="palette-swatches">{sw}</span></span><small>{esc(t["direction"])}</small>'
            f'<a class="text-link tiny" href="/templates/{esc(t["slug"])}" target="_blank" rel="noopener" style="position:relative;z-index:2">Preview</a></span></label>')
    about = ""
    if not req.user:
        about = f"""<div class="box"><h2 style="font-size:1.25rem;margin-bottom:6px">4. About you</h2>
<p class="muted small" style="margin-bottom:16px">So your draft is saved and you can come back to it on any device. No password needed: we email you a sign-in link whenever you want one. Already have an account? <a class="text-link" href="{esc(url('/login', next=url('/create', category=cat_slug, template=tpl_slug, package=pkg)))}">Log in</a>.</p>
<div class="form-row form-row--2">{field("contact_name", "Your name", f.data.get("contact_name", ""), required=True, errors=f.errors, attrs={"autocomplete": "name"})}
{field("contact_email", "Your email", f.data.get("contact_email", ""), type="email", required=True, errors=f.errors, attrs={"autocomplete": "email"})}</div>
<div class="field{' has-error' if 'terms' in f.errors else ''}" data-field="terms">{check("terms", 'I accept the <a class="text-link" href="/terms" target="_blank">terms of service</a> and the <a class="text-link" href="/privacy" target="_blank">privacy notice</a>.', bool(req.get("terms")))}</div>
{forms.honeypot()}</div>"""
    body = f"""<section class="page-hero"><div class="grid-texture"></div><div class="container">
<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">/</span><span>Create your event</span></nav>
<h1>Let's create your <span class="serif grad">event</span></h1><p class="lead">Pick the occasion, a starting template and a package. Nothing is published or charged until you're ready.</p>
<p class="small" style="margin-top:14px">Rather have us do it? <a class="text-link" href="/help-me-set-up">We can set it up for you</a>.</p></div></section>
<section class="section"><div class="container"><form class="form" method="post" novalidate data-create>{csrf(req)}
{errors_summary(f.errors)}
<div class="box"><h2 style="font-size:1.25rem;margin-bottom:16px">1. What are you celebrating?</h2>{"".join(cats_html)}</div>
<div class="box"><h2 style="font-size:1.25rem;margin-bottom:6px">2. Choose a starting template</h2><p class="muted small" style="margin-bottom:16px">These templates suit your occasion. You can switch any time in the design step.</p>
<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(230px,1fr))" data-tpl-grid>{"".join(tpl_html)}</div>
<button class="btn btn--ghost btn--sm" type="button" data-show-all hidden style="margin-top:12px">Show all templates</button></div>
<div class="box"><h2 style="font-size:1.25rem;margin-bottom:16px">3. Which package are you thinking of?</h2>{_package_picker(pkg)}</div>
{about}
<div class="btn-row"><button class="btn btn--primary btn--lg" type="submit">Start setting up {i("arrow", "i--arrow")}</button></div></form></div></section>
{CREATE_JS}"""
    return page(req, "Create your event", body, "/create", noindex=True)


# --- wizard shell -----------------------------------------------------------------------------
OPTIONAL_STEPS = {4, 5, 6, 7, 8}
STEP_FEATURE = {5: "programme", 6: "menu", 7: "seating"}


def wizard_frame(req, ev, n: int, inner: str, wide_preview: bool = False, enctype: str = "") -> str:
    done = set(ev["wizard_done"] or [])

    def badge(s):
        if s in STEP_FEATURE and not catalog.has_feature(ev, STEP_FEATURE[s]):
            return f'<span class="stepper__tag" title="Not in your planned package">{i("lock")}</span>'
        return '<span class="stepper__tag">optional</span>' if s in OPTIONAL_STEPS else ""
    stepper = "".join(
        f'<li><a href="{step_url(ev, s)}" class="{"is-done" if s in done else ""}"{" aria-current=step" if s == n else ""} data-step-link>'
        f'<span class="n">{"✓" if s in done and s != n else s}</span>{esc(label)}{badge(s)}</a></li>' for s, label, _ in STEPS)
    pct = round(100 * len(done & set(range(1, 11))) / 10)
    title, icon = STEPS[n - 1][1], STEPS[n - 1][2]
    skip = (f'<a class="btn btn--ghost" href="{step_url(ev, n + 1)}" data-step-link>Skip for now</a>' if n in OPTIONAL_STEPS else "")
    to_review = (f'<button class="btn btn--ghost" type="submit" name="nav" value="review">Save and go to review</button>' if 3 <= n <= 7 else "")
    nav = f"""<div class="wizard-actions">{f'<a class="btn btn--ghost" href="{step_url(ev, n - 1)}">{i("arrow-left")} Back</a>' if n > 1 else '<span></span>'}
<div class="btn-row">{to_review}{skip}<button class="btn btn--secondary" type="submit" name="nav" value="stay">Save draft</button>
<button class="btn btn--primary" type="submit" name="nav" value="next">Save and continue {i("arrow", "i--arrow")}</button></div></div>"""
    if n == 10:   # step 10 holds its own checkout form; forms can't be nested
        form = inner
    else:
        form = (f'<form class="form" method="post" novalidate data-wizard-form{(" enctype=" + chr(34) + enctype + chr(34)) if enctype else ""}>'
                f'{csrf(req)}{inner}{nav}</form>')
    preview = ""
    if wide_preview:
        preview = f"""<div class="preview-frame" data-preview data-device="desktop"><div class="preview-frame__bar"><span class="preview-frame__url">/events/{esc(ev['slug'])}</span>
<div class="row" style="gap:6px"><div class="seg"><button type="button" data-device="desktop" aria-pressed="true">Desktop</button><button type="button" data-device="mobile" aria-pressed="false">Mobile</button></div>
<button class="btn btn--ghost btn--icon btn--sm" type="button" data-refresh aria-label="Refresh preview">{i("refresh")}</button></div></div>
<div class="preview-frame__stage" style="height:640px"><iframe src="/dashboard/events/{ev['uid']}/preview" title="Live preview" data-live-preview></iframe></div></div>"""
        content = f'<div class="wizard-split"><div class="glass wizard-card glass--strong">{_card_head(n, title, icon)}{form}</div>{preview}</div>'
    else:
        content = f'<div class="glass glass--strong wizard-card">{_card_head(n, title, icon)}{form}</div>'
    plan = ""
    if not ev["paid_package"]:
        opts = "".join(f'<option value="{esc(p["code"])}"{" selected" if p["code"] == catalog.planning_package(ev) else ""}>{esc(p["name"])} · {catalog.money(p["price_cents"])}</option>'
                       for p in catalog.packages())
        plan = (f'<form class="plan-package" method="post" action="/dashboard/events/{ev["uid"]}/plan-package" data-plan-package>{csrf(req)}'
                f'<input type="hidden" name="back" value="{n}"><label class="tiny muted" for="plan-pkg">Planning with</label>'
                f'<select class="select select--sm" id="plan-pkg" name="package">{opts}</select>'
                f'<button class="btn btn--ghost btn--sm" type="submit" data-plan-submit>Change</button></form>')
    body = f"""<div class="page-head"><div><h1>Set up {esc(ev['name'])}</h1><p>Private draft. Saved as you go; nothing is shared until you publish.</p></div>
<div class="btn-row">{plan}<a class="btn btn--secondary btn--sm" href="/dashboard/events/{ev['uid']}/preview" target="_blank" rel="noopener">{i("eye")} Full preview</a></div></div>
<div class="wizard-progress"><span>{pct}% complete</span><div class="progress"><span style="width:{pct}%"></span></div><span class="mono">Step {n} of 10</span></div>
<div class="wizard"><nav aria-label="Set-up steps"><ol class="stepper">{stepper}</ol></nav><div>{content}</div></div>"""
    return organiser_page(req, ev, f"Set-up step {n}", body, f"/setup/{n}", extra_scripts=WIZARD_JS)


@router.post("/dashboard/events/<uid>/plan-package")
def plan_package(req, uid):
    ev = events.parse(auth.event_for(req, uid))
    code = req.get("package")
    back = req.get("back")
    n = int(back) if back.isdigit() and 1 <= int(back) <= 10 else 1
    if catalog.package(code) and not ev["paid_package"]:
        events.touch(ev["id"], selected_package=code)
        req.flash("success", f"Now planning with {catalog.package(code)['name']}. You can change this until you pay.")
    return redirect(step_url(ev, n))


def _card_head(n, title, icon):
    intros = {
        1: "The essentials guests see first.", 2: "Where it's happening and how to get there.",
        3: "Make the template yours. Changes show in the preview as you go.", 4: "Your guest list and how replies work.",
        5: "Ceremonies, receptions and the running order.", 6: "Menus, meal choices and dietary needs.",
        7: "Decide when to plan your tables.", 8: "Dress code, gifts, contacts, accommodation and photos.",
        9: "Check everything before you choose a package.", 10: "Choose a package. Your website goes live once payment is confirmed.",
    }
    opt = ('<p class="small muted" style="margin-top:6px">Optional. Skip it now and add it any time, before or after your website is live.</p>'
           if n in OPTIONAL_STEPS else "")
    return (f'<div class="row" style="gap:14px;margin-bottom:6px"><span class="icon-tile icon-tile--soft">{i(icon)}</span>'
            f'<div><span class="tiny muted mono">STEP {n}</span><h2>{esc(title)}</h2></div></div><p class="lead">{intros[n]}</p>{opt}<hr>')


WIZARD_JS = """<script>(function(){
var plan=document.querySelector('[data-plan-package]');if(plan){var b=plan.querySelector('[data-plan-submit]');if(b)b.hidden=true;plan.querySelector('select').addEventListener('change',function(){plan.submit();});}
var f=document.querySelector('[data-wizard-form]');if(!f)return;var dirty=false;
function fire(el){el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}
f.addEventListener('input',function(e){dirty=true;if(e.target.name==='name')e.target.setAttribute('data-autoname','0');
if(e.target.name==='hosts'||e.target.name==='category'){var n=f.querySelector('[data-autoname="1"]');if(n){var h=f.querySelector('[name=hosts]').value.trim(),c=f.querySelector('[name=category]');
var nn=JSON.parse(n.getAttribute('data-nouns')||'{}')[c?c.value:''];n.value=!h||!nn?h:h+(/s$/.test(h)&&!/'s$/.test(h)?"' ":"'s ")+nn;}}});
f.addEventListener('change',function(e){if(e.target.name==='category')f.dispatchEvent(new Event('input'));});
f.addEventListener('submit',function(){dirty=false;});
document.querySelectorAll('[data-step-link]').forEach(function(a){a.addEventListener('click',function(e){if(dirty&&!confirm('You have unsaved changes on this step. Leave without saving?'))e.preventDefault();});});
f.addEventListener('click',function(e){var t=e.target.closest('[data-fill],[data-surprise],[data-confirm]');if(!t)return;
if(t.hasAttribute('data-confirm')&&!confirm(t.getAttribute('data-confirm'))){e.preventDefault();return;}
if(t.hasAttribute('data-fill')){var v=JSON.parse(t.getAttribute('data-fill'));Object.keys(v).forEach(function(k){var el=f.querySelector('[name="'+k+'"]');if(el){el.value=v[k];fire(el);}});
if(window.Aurelia&&Aurelia.toast)Aurelia.toast(t.getAttribute('data-done')||'Added. Edit it as you like.');}
if(t.hasAttribute('data-surprise')){var pals=f.querySelectorAll('input[name=palette]');if(pals.length){var p=pals[Math.floor(Math.random()*pals.length)];p.checked=true;fire(p);}
['font_pair','background'].forEach(function(k){var s=f.querySelector('select[name='+k+']');if(s&&s.options.length){s.selectedIndex=Math.floor(Math.random()*Math.min(s.options.length,k==='font_pair'?4:s.options.length));fire(s);}});}});
var live=document.querySelector('[data-live-preview]');if(!live||!f.hasAttribute('data-autosave'))return;var t=0;
f.addEventListener('change',function(e){if(e.target.type==='file')return;clearTimeout(t);t=setTimeout(function(){var fd=new FormData(f);fd.set('nav','autosave');
['hero','logo','background'].forEach(function(k){fd.delete(k);});
fetch(location.pathname,{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'fetch','Accept':'application/json'}}).then(function(r){return r.json();}).then(function(j){if(j.ok){dirty=false;live.src=live.src;}else{Aurelia.toast(j.error||'Could not save','error');}});},500);});})();</script>"""


@router.route("/dashboard/events/<uid>/setup/<int:n>", methods=("GET", "POST"))
def wizard(req, uid, n):
    row = auth.event_for(req, uid)
    ev = events.parse(row)
    if n < 1 or n > 10:
        raise HTTPError(404)
    handler = STEP_HANDLERS[n]
    result = handler(req, ev)
    return result


def finish_step(req, ev, n: int, f: Form):
    """Common post-save behaviour."""
    if req.is_htmx and req.get("nav") == "autosave":
        if not f.ok:
            return json_response({"ok": False, "error": next(iter(f.errors.values()))}, 400)
    done = set(ev["wizard_done"] or [])
    if f.ok:
        done.add(n)
        events.touch(ev["id"], wizard_done=db.dumps(sorted(done)), wizard_step=max(ev["wizard_step"], min(n + 1, 10)))
        if req.is_htmx:
            return json_response({"ok": True})
        if req.get("nav") == "next":
            return redirect(step_url(ev, n + 1))
        if req.get("nav") == "review":
            return redirect(step_url(ev, 9))
        req.flash("success", "Saved.")
        return redirect(step_url(ev, n))
    return None


# --- step 1: event details ----------------------------------------------------------------------
def step1(req, ev):
    f = Form(req)
    g = group_of(ev)
    if req.method == "POST":
        name = f.text("name", "Event name", max=120)
        cat = f.choice("category", [c["slug"] for c in catalog.categories()], "event types", required=True)
        hosts = f.text("hosts", HOST_LABEL.get(g, ("Hosts",))[0], required=True, max=120)
        name = name or suggestions.auto_event_name(cat or ev["category"], hosts) or catalog.category_name(cat or ev["category"])
        desc = f.text("description", "Description", max=1500)
        d = f.date("event_date", "Event date", required=True, future=not ev["paid_package"])
        st = f.time("start_time", "Start time")
        et = f.time("end_time", "End time")
        if st and et and et <= st and not req.get("ends_next_day"):
            f.error("end_time", "End time must be after the start time (tick “ends after midnight” if it does).")
        if f.ok:
            events.touch(ev["id"], name=name, category=cat, hosts=hosts, description=desc, event_date=d,
                         start_time=st, end_time=et)
            if not ev["published_at"] and hosts and ev["slug"].startswith(forms.slugify(ev["name"], 50)):
                events.touch(ev["id"], slug=events.unique_slug(hosts, ev["id"]))
            events.keep_online_past_event(events.by_id(ev["id"]))
        r = finish_step(req, events.by_id(ev["id"]), 1, f)
        if r:
            return r
    d = {**ev, **f.data}
    label, ph = HOST_LABEL.get(g, ("Hosts", ""))
    cats = [(c["slug"], f'{catalog.GROUPS[c["group_slug"]]["name"]}: {c["name"]}') for c in catalog.categories()]
    auto = "1" if (not d.get("name") or d.get("name") in (d.get("hosts"), catalog.category_name(d.get("category")),
                                                           suggestions.auto_event_name(d.get("category"), d.get("hosts")))) else "0"
    nouns = esc(json.dumps(suggestions.NAME_NOUN))
    inner = f"""{errors_summary(f.errors)}
{field("hosts", label, d.get("hosts"), required=True, errors=f.errors, attrs={"placeholder": ph, "autofocus": not d.get("hosts")}, hint="Shown large on your website and used for your link, e.g. /events/lerato-and-sipho.")}
<div class="form-row form-row--2">{field("name", "Event name", d.get("name"), errors=f.errors, attrs={"data-autoname": auto, "data-nouns": nouns}, hint="Used in your invitation messages, e.g. “You're invited to Lerato & Sipho's wedding”. Filled in from the names above.")}
{select("category", "Type of event", cats, d.get("category"), required=True, errors=f.errors)}</div>
{field("description", "A short welcome or description", d.get("description"), type="textarea", errors=f.errors, hint="Optional. One or two sentences guests read first.")}
<div class="form-row form-row--3">{field("event_date", "Date", d.get("event_date"), type="date", required=True, errors=f.errors)}
{field("start_time", "Starts", d.get("start_time"), type="time", errors=f.errors)}{field("end_time", "Ends", d.get("end_time"), type="time", errors=f.errors)}</div>
{check("ends_next_day", "Ends after midnight", bool(req.get("ends_next_day")))}
<p class="tiny muted">Several ceremonies or days? Add each one in the Programme step.</p>"""
    return wizard_frame(req, ev, 1, inner)


# --- step 2: venue -------------------------------------------------------------------------------
def step2(req, ev):
    f = Form(req)
    if req.method == "POST":
        venue = {
            "name": f.text("venue_name", "Venue name", required=True, max=160),
            "address": f.text("address", "Address", required=True, max=300),
            "map_url": f.url("map_url", "Map link"),
            "parking": f.text("parking", "Parking", max=1000),
            "directions": f.text("directions", "Directions", max=2000),
            "accommodation": f.text("accommodation", "Accommodation", max=2000),
        }
        if f.ok:
            events.save_json(ev["id"], "venue", venue)
        r = finish_step(req, ev, 2, f)
        if r:
            return r
    v = {**(ev["venue"] or {}), **{k.replace("venue_name", "name"): val for k, val in f.data.items()}}
    inner = f"""{errors_summary(f.errors)}
<div class="form-row form-row--2">{field("venue_name", "Venue name", v.get("name"), required=True, errors=f.errors)}
{field("address", "Street address", v.get("address"), required=True, errors=f.errors, hint="Guests get a Google Maps link built from this.")}</div>
{field("map_url", "Google Maps link (optional)", v.get("map_url"), type="url", errors=f.errors, hint="Paste a share link from Google Maps for an exact pin, e.g. a farm gate or a specific entrance.")}
{field("parking", "Parking", v.get("parking"), type="textarea", errors=f.errors, attrs={"rows": 3}, hint="Where to park, security, valet, drop-off.")}
{field("directions", "Directions", v.get("directions"), type="textarea", errors=f.errors, attrs={"rows": 3}, hint="Landmarks, gate codes, the last turn that GPS gets wrong.")}
{field("accommodation", "Accommodation nearby", v.get("accommodation"), type="textarea", errors=f.errors, attrs={"rows": 3}, hint="Optional. Add specific places with links in the Extras step.")}"""
    return wizard_frame(req, ev, 2, inner)


# --- step 3: design ------------------------------------------------------------------------------
def step3(req, ev):
    f = Form(req)
    g = group_of(ev)
    upload_errors = []
    if req.method == "POST":
        tpl = f.choice("template", [t["slug"] for t in catalog.templates()], "templates", required=True, default=ev["template"])
        t_row = catalog.template(tpl)
        dkey = t_row["design"] if t_row else "atelier"
        dsg = themes.design(dkey)
        design = dict(ev["design"] or {})
        if tpl != ev["template"]:
            design.pop("palette", None)
            design.pop("font_pair", None)
            design.pop("background", None)
            design.pop("colors", None)
        else:
            design["palette"] = f.choice("palette", [p[0] for p in dsg["palettes"]], "palettes", default=dsg["palettes"][0][0])
            design["font_pair"] = f.choice("font_pair", list(themes.FONT_PAIRS), "fonts", default=dsg["font_pair"])
            design["background"] = f.choice("background", list(themes.BACKGROUND_LABELS), "backgrounds", default=dsg["background"])
            if req.get("custom_colors") and catalog.has_feature(ev, "advanced_design"):
                base = themes.resolve(dkey, {"palette": design["palette"]})["colors"]
                design["colors"] = {k: f.color(f"color_{k}", base[k]) for k in ("bg", "text", "accent", "accent2")}
            else:
                design.pop("colors", None)
        design["monogram"] = f.text("monogram", "Monogram", max=12)
        design["wording"] = {
            "welcome": f.text("w_welcome", "Welcome line", max=160),
            "invitation": f.text("w_invitation", "Invitation wording", max=1200),
            "rsvp_note": f.text("w_rsvp_note", "RSVP note", max=400),
            "closing": f.text("w_closing", "Closing line", max=300),
        }
        for kind in ("hero", "logo", "background"):
            up = req.file(kind)
            if up:
                try:
                    for old in events.uploads(ev["id"], kind):
                        storage.delete_upload(old["id"], ev["id"])
                    storage.save_image(up, ev, req.user["id"], kind)
                except storage.UploadError as e:
                    upload_errors.append(f"{kind.capitalize()} image: {e}")
        rm = req.get("remove_upload")
        if rm.isdigit():
            storage.delete_upload(int(rm), ev["id"])
        for msg in upload_errors:
            f.error("upload", msg)
        if f.ok or (upload_errors and len(f.errors) == len(upload_errors)):
            events.touch(ev["id"], template=tpl, design=db.dumps(design))
        if rm.isdigit() and f.ok:
            req.flash("success", "Image removed.")
            return redirect(step_url(ev, 3))
        r = finish_step(req, ev, 3, f)
        if r:
            return r
        ev = events.get(ev["uid"])
    t_row = catalog.template(ev["template"]) or catalog.templates()[0]
    dkey = t_row["design"]
    dsg = themes.design(dkey)
    res = themes.resolve(dkey, ev["design"])
    w = (ev["design"] or {}).get("wording", {})
    tpl_opts = []
    for t in sorted(catalog.templates(), key=lambda t: g not in db.loads(t["groups"], [])):
        p = themes.design(t["design"])["palettes"][0][2]
        sw = "".join(f'<i style="background:{c}"></i>' for c in (p["bg"], p["text"], p["accent"], p["accent2"]))
        tpl_opts.append(f'<label class="choice"><input type="radio" name="template" value="{esc(t["slug"])}"{" checked" if t["slug"] == ev["template"] else ""}>'
                        f'<span><span class="row row--between"><b>{esc(t["name"])}</b><span class="palette-swatches">{sw}</span></span><small>{esc(t["direction"])}</small></span></label>')
    pal_opts = "".join(
        f'<label class="choice"><input type="radio" name="palette" value="{esc(k)}"{" checked" if k == res["palette"] else ""}>'
        f'<span><span class="palette-swatches">{"".join(f"<i style=background:{c[x]}></i>" for x in ("bg", "text", "accent", "accent2"))}</span>{esc(label)}</span></label>'
        for k, label, c in dsg["palettes"])
    fonts = [(k, themes.FONT_PAIRS[k][0] + f" ({themes.FONT_PAIRS[k][1]} + {themes.FONT_PAIRS[k][2]})") for k in dsg["fonts"]]
    fonts += [(k, v[0] + f" ({v[1]} + {v[2]})") for k, v in themes.FONT_PAIRS.items() if k not in dsg["fonts"]]
    bgs = [(k, themes.BACKGROUND_LABELS[k]) for k in dsg["backgrounds"]]
    custom = bool((ev["design"] or {}).get("colors"))
    adv = catalog.has_feature(ev, "advanced_design")
    color_fields = "".join(forms.color(f"color_{k}", label, res["colors"][k]) for k, label in
                           (("bg", "Background"), ("text", "Text"), ("accent", "Accent"), ("accent2", "Second accent")))

    def thumb(kind, label, hint):
        ups = events.uploads(ev["id"], kind)
        cur = ""
        if ups:
            cur = (f'<div class="row" style="gap:10px"><img src="{events.upload_url(ups[0])}" alt="" style="width:72px;height:54px;object-fit:cover;border-radius:8px">'
                   f'<button class="btn btn--sm btn--ghost" type="submit" name="remove_upload" value="{ups[0]["id"]}" formnovalidate>{i("trash")} Remove</button></div>')
        return (f'<div class="field"><span class="label">{esc(label)}</span>{cur}<label class="file-drop" style="position:relative">{i("upload")}'
                f'<span>{"Replace" if ups else "Upload"} {esc(label.lower())}</span><span class="hint">{esc(hint)}</span><span class="tiny" data-files></span>'
                f'<input type="file" name="{kind}" accept="image/jpeg,image/png,image/webp,image/gif"></label></div>')

    deadline = forms.fmt_date((ev["guest_settings"] or {}).get("rsvp_deadline")) if (ev["guest_settings"] or {}).get("rsvp_deadline") else ""
    cards = []
    for opt in suggestions.wording_options(ev["category"]):
        filled = {k: suggestions.fill_wording(opt[k], ev["hosts"] or "", deadline) for k in ("welcome", "invitation", "rsvp_note", "closing")}
        payload = esc(json.dumps({"w_" + k: v for k, v in filled.items()}))
        cards.append(f'<div class="suggest-card"><b>{esc(opt["label"])}</b><p>{esc(filled["welcome"])}</p><p>{esc(filled["invitation"])}</p>'
                     f'<button class="btn btn--secondary btn--sm" type="button" data-fill="{payload}" data-done="Wording added. Edit it as you like.">Use this wording</button></div>')
    inner = f"""{errors_summary(f.errors)}
<fieldset><legend>Template</legend><div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">{"".join(tpl_opts)}</div>
<p class="hint" style="margin-top:8px">Switching template resets colours and fonts to that template's defaults. Your content stays.</p></fieldset>
<fieldset><legend>Colour palette</legend><div class="choice-grid">{pal_opts}</div>
<button class="btn btn--ghost btn--sm" type="button" data-surprise style="margin-top:10px">{i("sparkle")} Try another look</button></fieldset>
<div class="box" style="padding:16px">{check("custom_colors", "Use my own colours" + ("" if adv else " <span class='pill pill--gold pill--plain'>Premium</span>"), custom, attrs={"data-reveals": "#custom-colors", "disabled": not adv})}
<div id="custom-colors" class="form-row form-row--4" style="margin-top:12px"{"" if custom else " hidden"}>{color_fields}</div></div>
<div class="form-row form-row--2">{select("font_pair", "Typography", fonts, res["font_pair"])}{select("background", "Background", bgs, res["background"])}</div>
<div class="form-row form-row--3">{thumb("hero", "Main photo", "Landscape, at least 1600px wide.")}{thumb("background", "Background image", "Used when Background is set to your photo.")}{thumb("logo", "Logo or crest", "PNG with transparency works best.")}</div>
{field("monogram", "Monogram or initials", (ev["design"] or {}).get("monogram", ""), errors=f.errors, attrs={"maxlength": 12, "placeholder": "L & S"}, hint="Shown where the template uses a monogram, if you don't upload a logo.")}
<fieldset><legend>Your wording</legend><p class="hint" style="margin-bottom:12px">Pick ready-made wording for your occasion, then change anything you like. Leave a box empty to use the template's own wording.</p>
<div class="suggest-grid">{"".join(cards)}</div><div class="form-row">
{field("w_welcome", "Welcome line", w.get("welcome", ""), attrs={"placeholder": "Together with their families"})}
{field("w_invitation", "Invitation wording", w.get("invitation", ""), type="textarea", attrs={"rows": 4, "placeholder": "Request the pleasure of your company as they celebrate their marriage."})}
<div class="form-row form-row--2">{field("w_rsvp_note", "RSVP note", w.get("rsvp_note", ""), attrs={"placeholder": "Kindly reply by 1 February."})}
{field("w_closing", "Closing line", w.get("closing", ""), attrs={"placeholder": "We can't wait to celebrate with you."})}</div></div></fieldset>"""
    html = wizard_frame(req, ev, 3, inner, wide_preview=True, enctype="multipart/form-data")
    return html.replace("data-wizard-form", "data-wizard-form data-autosave", 1)


# --- step 4: guests --------------------------------------------------------------------------------
def step4(req, ev):
    f = Form(req)
    gs = dict(ev["guest_settings"] or {})
    if req.method == "POST":
        gs["estimated"] = f.integer("estimated", "Estimated guests", min=0, max=5000)
        cats = [c for c in req.getlist("categories") if c] + [c.strip() for c in req.get("categories_other").split(",") if c.strip()]
        gs["categories"] = list(dict.fromkeys(c[:40] for c in cats))[:20]
        gs["family_groups"] = [l.strip()[:60] for l in req.get("family_groups").splitlines() if l.strip()][:100]
        sides = [s for s in (f.text("side_a", "First family", max=60), f.text("side_b", "Second family", max=60)) if s]
        if sides:
            gs["sides"] = sides
        else:
            gs.pop("sides", None)
        gs["vip_note"] = f.text("vip_note", "VIP note", max=500)
        gs["children_allowed"] = f.flag("children_allowed")
        gs["max_children"] = f.integer("max_children", "Children per invitation", min=0, max=10)
        gs["plus_one_policy"] = f.choice("plus_one_policy", ["none", "per_guest", "open"], "plus-one policies", default="per_guest")
        gs["plus_ones_default"] = f.integer("plus_ones_default", "Plus-ones", min=0, max=10)
        gs["rsvp_deadline"] = f.date("rsvp_deadline", "RSVP deadline")
        if gs["rsvp_deadline"] and ev["event_date"] and gs["rsvp_deadline"] > ev["event_date"]:
            f.error("rsvp_deadline", "The RSVP deadline should be on or before the event date.")
        pasted = suggestions.parse_guest_list(req.get("guest_paste"))
        if pasted and not catalog.has_feature(ev, "guest_management"):
            f.error("guest_paste", "Adding a guest list is part of the Premium package. Change the package you're planning with, or let guests reply through your one link.")
        if f.ok:
            events.save_json(ev["id"], "guest_settings", gs)
            if pasted:
                added = events.add_pasted_guests(ev, pasted)
                req.flash("success", f"Added {added} guest{'s' if added != 1 else ''} to your list." + (f" {len(pasted) - added} were already on it." if added < len(pasted) else ""))
        r = finish_step(req, ev, 4, f)
        if r:
            return r
    feats = catalog.category_features(ev["category"])
    preset = ["Family", "Friends", "Colleagues", "VIP", "Church", "Neighbours", "Partners", "Clients"]
    chosen = gs.get("categories", [])
    cat_checks = "".join(
        f'<label class="choice"><input type="checkbox" name="categories" value="{c}"{" checked" if c in chosen else ""}><span>{c}</span></label>' for c in preset)
    other = ", ".join(c for c in chosen if c not in preset)
    sides = gs.get("sides") or (["Bride's family", "Groom's family"] if "family_sides" in feats else ["", ""])
    sides = (sides + ["", ""])[:2]
    gcat_note = feature_note(ev, "guest_categories", "Using several guest categories")
    have = db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (ev["id"],), 0)
    if catalog.has_feature(ev, "guest_management"):
        listed = (f'<p class="small" style="margin-bottom:10px"><b>{have} guest{"s" if have != 1 else ""}</b> on your list. '
                  f'<a class="text-link" href="/dashboard/events/{ev["uid"]}/guests">Open the guest list</a> to edit them, mark VIPs or add families.</p>') if have else ""
        paste = f"""<fieldset><legend>Your guest list</legend>{listed}
{field("guest_paste", "Paste names (optional)", req.get("guest_paste") if f.errors else "", type="textarea", errors=f.errors, attrs={"rows": 6, "placeholder": "Thandi Mokoena, 082 123 4567" + chr(10) + "Sipho Dlamini, sipho@example.com" + chr(10) + "Gogo Nomsa"}, hint="One guest per line. Add a mobile number or email if you have it. You can copy a column straight from Excel, Google Sheets or your phone's notes. Each guest gets a personal RSVP link.")}</fieldset>"""
    else:
        paste = (f'<div class="notice">{i("users")}<span>With Essential, guests reply through your one link and appear in your dashboard as they do. '
                 f'Keeping your own guest list, with a personal link for each guest, is part of Premium.</span></div>')
    more_open = " open" if (f.errors.keys() - {"guest_paste"}) else ""
    inner = f"""{errors_summary(f.errors)}
<div class="form-row form-row--2">{field("estimated", "Estimated number of guests", gs.get("estimated") or "", type="number", errors=f.errors, attrs={"min": 0})}
{field("rsvp_deadline", "RSVP deadline", gs.get("rsvp_deadline", ""), type="date", errors=f.errors, hint="Replies close at the end of this day.")}</div>
{paste}
<details class="box" style="padding:14px 16px"{more_open}><summary style="cursor:pointer;font-weight:500">More options: plus-ones, children, families and guest groups</summary><div style="display:grid;gap:18px;margin-top:16px">
<fieldset><legend>Guest categories</legend>{gcat_note}<div class="choice-grid">{cat_checks}</div>
{field("categories_other", "Other categories", other, hint="Comma-separated, e.g. Book club, Soccer team")}</fieldset>
<fieldset><legend>Families</legend><div class="form-row form-row--2">{field("side_a", "First family or side", sides[0], attrs={"placeholder": "Bride's family"})}
{field("side_b", "Second family or side", sides[1], attrs={"placeholder": "Groom's family"})}</div>
{field("family_groups", "Family groups", chr(10).join(gs.get("family_groups", [])), type="textarea", attrs={"rows": 4, "placeholder": "Mokoena family" + chr(10) + "Dlamini family"}, hint="One per line. Use them to group guests and seat families together.")}</fieldset>
{field("vip_note", "VIP guests", gs.get("vip_note", ""), type="textarea", attrs={"rows": 2}, hint="Who needs special attention, e.g. grandparents, dignitaries. You'll mark individual guests as VIP in your guest list.")}
<fieldset><legend>Plus-ones</legend><div class="choice-grid">
{"".join(f'<label class="choice"><input type="radio" name="plus_one_policy" value="{k}"{" checked" if gs.get("plus_one_policy", "per_guest") == k else ""}><span>{t}<small>{s}</small></span></label>' for k, t, s in (("none", "No plus-ones", "Invitations are for the named guest only."), ("per_guest", "Set per guest", "You decide for each guest in your list."), ("open", "Everyone may bring", "Guests on the general link can add plus-ones.")))}</div>
{field("plus_ones_default", "Plus-ones allowed by default", gs.get("plus_ones_default", 0), type="number", attrs={"min": 0, "max": 10}, errors=f.errors)}</fieldset>
<fieldset><legend>Children</legend>{check("children_allowed", "Children are welcome", bool(gs.get("children_allowed")), attrs={"data-reveals": "#kids"})}
<div id="kids"{"" if gs.get("children_allowed") else " hidden"}>{field("max_children", "Children per invitation (maximum)", gs.get("max_children", 0), type="number", attrs={"min": 0, "max": 10}, errors=f.errors)}</div></fieldset>
</div></details>"""
    return wizard_frame(req, ev, 4, inner)


# --- step 5: programme ------------------------------------------------------------------------------
def _repeat(prefix: str, cols: str, rows_html: list, template_html: str, add_label: str, max_rows: int = 200) -> str:
    return (f'<div class="repeat" data-repeat="{prefix}" data-next="{len(rows_html) + 1}" data-max="{max_rows}" style="--cols:{cols}">'
            f'<div class="repeat" data-rows>{"".join(rows_html)}</div><template>{template_html}</template>'
            f'<div><button class="btn btn--sm btn--secondary" type="button" data-add-row>{i("plus")} {esc(add_label)}</button></div></div>')


def _rm():
    return f'<button class="btn btn--ghost btn--icon" type="button" data-remove-row aria-label="Remove row">{i("trash")}</button>'


def _in(name, value="", type="text", ph="", label=""):
    return (f'<div class="field"><label class="tiny muted" for="{name}">{esc(label)}</label><input class="input input--sm" id="{name}" name="{name}" type="{type}" '
            f'value="{esc(value)}" placeholder="{esc(ph)}"></div>')


def _sel(name, options, value, label):
    o = "".join(f'<option value="{esc(v)}"{" selected" if str(v) == str(value) else ""}>{esc(t)}</option>' for v, t in options)
    return f'<div class="field"><label class="tiny muted" for="{name}">{esc(label)}</label><select class="select select--sm" id="{name}" name="{name}">{o}</select></div>'


def step5(req, ev):
    f = Form(req)
    max_funcs = catalog.limit(ev, "functions", 1) if catalog.has_feature(ev, "multi_functions") else 1
    if req.method == "POST" and req.get("nav") == "sample":
        items = suggestions.sample_programme(ev["category"], ev["start_time"] or "", group_of(ev))
        with db.transaction():
            db.run("DELETE FROM schedule_items WHERE event_id = ?", (ev["id"],))
            for n, it in enumerate(items):
                db.insert("schedule_items", {"event_id": ev["id"], "function_id": None, "item_time": it["item_time"], "title": it["title"],
                                             "description": it["description"], "kind": it["kind"], "sort": n})
        req.flash("success", "Sample programme added. Change the times and titles to match your day.")
        return redirect(step_url(ev, 5))
    if req.method == "POST":
        frows = req.rows("fn", ["id", "name", "date", "start", "end", "venue", "address", "map"])
        if len(frows) > max_funcs:
            f.error("functions", f"Your package includes {max_funcs} event function{'s' if max_funcs != 1 else ''}. Upgrade for more.")
        srows = req.rows("si", ["id", "time", "title", "description", "kind", "function"])
        for r in frows:
            if not r["name"]:
                f.error("functions", "Each function needs a name, e.g. Ceremony or Reception.")
            for k in ("start", "end"):
                if r[k] and not forms.TIME_RE.match(r[k]):
                    f.error("functions", "Function times must look like 14:30.")
        for r in srows:
            if not r["title"]:
                f.error("schedule", "Each programme item needs a title.")
            if r["time"] and not forms.TIME_RE.match(r["time"]):
                f.error("schedule", "Programme times must look like 14:30.")
        if f.ok:
            with db.transaction():
                keep = []
                for n, r in enumerate(frows):
                    data = {"name": r["name"][:100], "func_date": r["date"] or None, "start_time": r["start"], "end_time": r["end"],
                            "venue_name": r["venue"][:160], "address": r["address"][:300], "map_url": r["map"][:600], "sort": n}
                    if r["id"].isdigit() and db.one("SELECT 1 FROM event_functions WHERE id = ? AND event_id = ?", (int(r["id"]), ev["id"])):
                        db.update("event_functions", int(r["id"]), data)
                        keep.append(int(r["id"]))
                    else:
                        keep.append(db.insert("event_functions", {"event_id": ev["id"], **data}))
                marks = ",".join("?" * len(keep)) or "NULL"
                db.run(f"DELETE FROM event_functions WHERE event_id = ? AND id NOT IN ({marks})", [ev["id"], *keep])
                db.run("DELETE FROM schedule_items WHERE event_id = ?", (ev["id"],))
                valid_fids = {r["id"] for r in events.functions(ev["id"])}
                for n, r in enumerate(srows):
                    fid = int(r["function"]) if r["function"].isdigit() and int(r["function"]) in valid_fids else None
                    db.insert("schedule_items", {"event_id": ev["id"], "function_id": fid, "item_time": r["time"],
                                                 "title": r["title"][:160], "description": r["description"][:600],
                                                 "kind": r["kind"] if r["kind"] in dict(KINDS) else "other", "sort": n})
        r = finish_step(req, ev, 5, f)
        if r:
            return r
    funcs = events.functions(ev["id"])
    sched = events.schedule(ev["id"])
    fopts = [("", "Whole event")] + [(fn["id"], fn["name"]) for fn in funcs]

    def frow(i_, fn=None):
        fn = fn or {}
        g = lambda k: fn[k] if fn and fn[k] is not None else ""
        return (f'<div class="repeat__row" style="--cols:repeat(4,minmax(0,1fr))"><input type="hidden" name="fn-{i_}-id" value="{g("id")}">'
                + _in(f"fn-{i_}-name", g("name"), ph="Ceremony", label="Name") + _in(f"fn-{i_}-date", g("func_date"), "date", label="Date")
                + _in(f"fn-{i_}-start", g("start_time"), "time", label="Starts") + _in(f"fn-{i_}-end", g("end_time"), "time", label="Ends")
                + _in(f"fn-{i_}-venue", g("venue_name"), ph="Venue (if different)", label="Venue") + _in(f"fn-{i_}-address", g("address"), ph="Address", label="Address")
                + _in(f"fn-{i_}-map", g("map_url"), "url", ph="Map link", label="Map link") + "<span></span>" + _rm() + "</div>")

    def srow(i_, s=None):
        s = s or {}
        g = lambda k: s[k] if s and s[k] is not None else ""
        return (f'<div class="repeat__row" style="--cols:110px minmax(0,1.3fr) minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr)"><input type="hidden" name="si-{i_}-id" value="{g("id")}">'
                + _in(f"si-{i_}-time", g("item_time"), "time", label="Time") + _in(f"si-{i_}-title", g("title"), ph="Arrival and welcome drinks", label="Title")
                + _in(f"si-{i_}-description", g("description"), ph="Optional detail", label="Detail")
                + _sel(f"si-{i_}-kind", KINDS, g("kind") or "other", "Type") + _sel(f"si-{i_}-function", fopts, g("function_id"), "Part of") + _rm() + "</div>")

    fn_rows = [frow(n, fn) for n, fn in enumerate(funcs)] or [frow(0)]
    s_rows = [srow(n, s) for n, s in enumerate(sched)] or [srow(0), srow(1)]
    multi = "multi_function" in catalog.category_features(ev["category"])
    inner = f"""{errors_summary(f.errors)}{feature_note(ev, "programme", "The programme")}
<fieldset><legend>Event functions</legend><p class="hint" style="margin-bottom:12px">{"Traditional and multi-day events often have several parts, each with its own venue. " if multi else ""}Add each ceremony or reception. Leave venue blank to use the main venue. Your package allows {max_funcs}.</p>
{_repeat("fn", "repeat(4,minmax(0,1fr))", fn_rows, frow("__i__"), "Add a function", max_funcs)}</fieldset>
<fieldset><legend>Programme</legend><p class="hint" style="margin-bottom:12px">The running order guests see: arrival, ceremony, speeches, first dance, entertainment.</p>
<div class="notice" style="margin-bottom:14px">{i("wand")}<div><span>Start from a typical {esc(catalog.category_name(ev["category"]).lower())} programme{" timed from " + esc(ev["start_time"]) if ev["start_time"] else ""}, then adjust it.</span>
<div style="margin-top:10px"><button class="btn btn--secondary btn--sm" type="submit" name="nav" value="sample" formnovalidate{' data-confirm="This replaces the programme items below with a sample. Continue?"' if sched else ""}>Use a sample programme</button></div></div></div>
{_repeat("si", "", s_rows, srow("__i__"), "Add an item")}</fieldset>"""
    return wizard_frame(req, ev, 5, inner)


# --- step 6: food ------------------------------------------------------------------------------------
def step6(req, ev):
    f = Form(req)
    info = dict(ev["info"] or {})
    if req.method == "POST":
        rows = req.rows("mi", ["id", "course", "name", "description", "tags", "selectable"])
        for r in rows:
            if not r["name"]:
                f.error("menu", "Each menu item needs a name.")
        pasted = suggestions.parse_menu(req.get("menu_paste"))
        rows += [{"id": "", "course": it["course"], "name": it["name"], "description": it["description"], "tags": "", "selectable": ""}
                 for it in pasted]
        info["dietary_options"] = [d for d in req.getlist("dietary_options") if d in events.DIETARY_OPTIONS]
        info["drinks"] = f.text("drinks", "Drinks", max=1500)
        info["catering_notes"] = f.text("catering_notes", "Catering notes", max=1500)
        menu_name = f.text("menu_name", "Menu name", max=100) or "Menu"
        if f.ok:
            with db.transaction():
                menu = db.one("SELECT * FROM menus WHERE event_id = ? ORDER BY sort, id LIMIT 1", (ev["id"],))
                if menu is None and rows:
                    mid = db.insert("menus", {"event_id": ev["id"], "name": menu_name, "sort": 0})
                elif menu:
                    mid = menu["id"]
                    db.run("UPDATE menus SET name = ? WHERE id = ?", (menu_name, mid))
                else:
                    mid = None
                if mid:
                    keep = []
                    for n, r in enumerate(rows):
                        data = {"course": r["course"] if r["course"] in COURSES else "Main", "name": r["name"][:140],
                                "description": r["description"][:400],
                                "tags": db.dumps([t.strip() for t in r["tags"].split(",") if t.strip()][:6]),
                                "selectable": 1 if r["selectable"] else 0, "sort": n}
                        if r["id"].isdigit() and db.one("SELECT 1 FROM menu_items WHERE id = ? AND menu_id = ?", (int(r["id"]), mid)):
                            db.update("menu_items", int(r["id"]), data)
                            keep.append(int(r["id"]))
                        else:
                            keep.append(db.insert("menu_items", {"menu_id": mid, "event_id": ev["id"], **data}))
                    marks = ",".join("?" * len(keep)) or "NULL"
                    db.run(f"DELETE FROM menu_items WHERE menu_id = ? AND id NOT IN ({marks})", [mid, *keep])
                events.save_json(ev["id"], "info", info)
            if pasted:
                req.flash("success", f"Added {len(pasted)} dish{'es' if len(pasted) != 1 else ''} from your pasted menu. Check the courses below.")
                if req.get("nav") == "next":
                    return redirect(step_url(ev, 6))
        r = finish_step(req, ev, 6, f)
        if r:
            return r
    menu = db.one("SELECT * FROM menus WHERE event_id = ? ORDER BY sort, id LIMIT 1", (ev["id"],))
    items = db.q("SELECT * FROM menu_items WHERE menu_id = ? ORDER BY sort, id", (menu["id"],)) if menu else []

    def mrow(i_, it=None):
        g = lambda k: (it[k] if it is not None and it[k] is not None else "")
        tags = ", ".join(db.loads(it["tags"], [])) if it is not None else ""
        sel = ' checked' if it is not None and it["selectable"] else ""
        return (f'<div class="repeat__row" style="--cols:140px minmax(0,1.2fr) minmax(0,1.6fr) minmax(0,1fr) 130px"><input type="hidden" name="mi-{i_}-id" value="{g("id")}">'
                + _sel(f"mi-{i_}-course", [(c, c) for c in COURSES], g("course") or "Main", "Course")
                + _in(f"mi-{i_}-name", g("name"), ph="Slow-roasted lamb", label="Dish") + _in(f"mi-{i_}-description", g("description"), ph="Rosemary jus, crushed potatoes", label="Description")
                + _in(f"mi-{i_}-tags", tags, ph="Halal, Gluten-free", label="Tags")
                + f'<label class="check" style="padding-top:22px"><input type="checkbox" name="mi-{i_}-selectable" value="1"{sel}><span class="small">Guests choose</span></label>'
                + _rm() + "</div>")

    rows = [mrow(n, it) for n, it in enumerate(items)] or [mrow(0), mrow(1)]
    diet = info.get("dietary_options") or ["Vegetarian", "Vegan", "Halal", "Gluten-free", "Nut allergy"]
    diet_html = "".join(f'<label class="choice"><input type="checkbox" name="dietary_options" value="{d}"{" checked" if d in diet else ""}><span>{d}</span></label>'
                        for d in events.DIETARY_OPTIONS)
    inner = f"""{errors_summary(f.errors)}{feature_note(ev, "menu", "The digital menu")}
{field("menu_name", "Menu name", menu["name"] if menu else "Reception menu")}
<fieldset><legend>Menu</legend><p class="hint" style="margin-bottom:12px">Tick “Guests choose” on main-course options to ask for a meal choice in the RSVP. Add more menus (e.g. kids' menu) from <b>Menu</b> in the dashboard.</p>
{_repeat("mi", "", rows, mrow("__i__"), "Add a dish")}
<details style="margin-top:14px"{" open" if not items else ""}><summary class="small" style="cursor:pointer;font-weight:500">Have the menu from your caterer? Paste it here</summary>
{field("menu_paste", "Paste the menu", "", type="textarea", attrs={"rows": 7, "placeholder": "Starters" + chr(10) + "Butternut soup with toasted seeds" + chr(10) + "Main: Lamb shank - rosemary jus" + chr(10) + "Dessert: Malva pudding"}, hint="One dish per line. A line with only a course name (Starters, Mains, Dessert) applies to the dishes below it. Text after a dash becomes the description. We add the dishes when you save.")}</details></fieldset>
<fieldset><legend>Dietary requirements guests can tell you about</legend>{feature_note(ev, "dietary", "Collecting dietary requirements")}<div class="choice-grid">{diet_html}</div>
<p class="hint" style="margin-top:8px">Guests can always add allergies in their own words.</p></fieldset>
<div class="form-row form-row--2">{field("drinks", "Drinks", info.get("drinks", ""), type="textarea", attrs={"rows": 3, "placeholder": "Welcome bubbles, open bar until 23:00, mocktails for kids"})}
{field("catering_notes", "Notes for guests about food", info.get("catering_notes", ""), type="textarea", attrs={"rows": 3})}</div>"""
    return wizard_frame(req, ev, 6, inner)


# --- step 7: seating -----------------------------------------------------------------------------------
def step7(req, ev):
    f = Form(req)
    info = dict(ev["info"] or {})
    existing = events.tables(ev["id"])
    if req.method == "POST":
        count = f.integer("table_count", "Number of tables", min=0, max=200)
        cap = f.integer("capacity", "Seats per table", min=1, max=40, default=10)
        shape = f.choice("shape", ["round", "long"], "shapes", default="round")
        names = [n.strip()[:40] for n in req.get("table_names").splitlines() if n.strip()]
        info["seating_notes"] = f.text("seating_notes", "Special seating requirements", max=1500)
        apply_cap = f.flag("apply_capacity")
        plan_now = f.flag("plan_now")
        if plan_now and count < len([t for t in existing if t["parties"]]):
            f.error("table_count", "Some tables already have guests. Move them before removing tables.")
        if f.ok and not plan_now:
            events.save_json(ev["id"], "info", info)
        elif f.ok:
            with db.transaction():
                cur = events.tables(ev["id"])
                # remove empty tables from the end until we reach the target
                for t in reversed(cur):
                    if len(cur) <= count:
                        break
                    if not t["parties"]:
                        db.run("DELETE FROM seating_tables WHERE id = ?", (t["id"],))
                        cur.remove(t)
                for n in range(len(cur), count):
                    col, rowi = n % 5, n // 5
                    db.insert("seating_tables", {"event_id": ev["id"], "name": f"Table {n + 1}", "capacity": cap, "shape": shape,
                                                 "pos_x": 12 + col * 19, "pos_y": 18 + rowi * 22, "sort": n})
                cur = events.tables(ev["id"])
                for n, t in enumerate(cur):
                    upd = {}
                    if n < len(names):
                        upd["name"] = names[n]
                    if apply_cap:
                        upd["capacity"] = cap
                        upd["shape"] = shape
                    if upd:
                        db.update("seating_tables", t["id"], upd)
                events.save_json(ev["id"], "info", info)
        r = finish_step(req, ev, 7, f)
        if r:
            return r
    tables = events.tables(ev["id"])
    est = (ev["guest_settings"] or {}).get("estimated") or 0
    suggested = max(1, -(-est // 10)) if est else 10
    cap = tables[0]["capacity"] if tables else 10
    now = bool(tables) or bool(f.errors) or bool(req.get("plan_now"))
    inner = f"""{errors_summary(f.errors)}{feature_note(ev, "seating", "The seating chart")}
<div class="notice">{i("seat")}<span>Most hosts plan seating once replies are in. Then the <a class="text-link" href="/dashboard/events/{ev['uid']}/seating">seating editor</a> can seat everyone automatically, keeping families and groups together, and you drag people to fine-tune.</span></div>
{check("plan_now", "Set up my tables now", now, attrs={"data-reveals": "#tables-now"})}
<div id="tables-now" style="display:grid;gap:18px"{"" if now else " hidden"}>
<div class="form-row form-row--3">{field("table_count", "Number of tables", len(tables) or suggested, type="number", errors=f.errors, attrs={"min": 0, "max": 200}, hint=f"About {suggested} for {est} guests at 10 a table." if est else "")}
{field("capacity", "Seats per table", cap, type="number", errors=f.errors, attrs={"min": 1, "max": 40})}
{select("shape", "Table shape", [("round", "Round"), ("long", "Long / banquet")], tables[0]["shape"] if tables else "round")}</div>
{check("apply_capacity", "Apply seats and shape to existing tables too", not tables)}
{field("table_names", "Table names (optional)", chr(10).join(t["name"] for t in tables), type="textarea", attrs={"rows": 5, "placeholder": "Head table" + chr(10) + "Protea" + chr(10) + "Baobab"}, hint="One per line, in order. Leave blank for Table 1, Table 2 and so on.")}
<p class="small muted">{len(tables)} table{"s" if len(tables) != 1 else ""} set up so far.</p></div>
{field("seating_notes", "Special seating requirements", info.get("seating_notes", ""), type="textarea", attrs={"rows": 3, "placeholder": "Grandparents near the front and away from the speakers; wheelchair access at Table 3."})}"""
    return wizard_frame(req, ev, 7, inner)


# --- step 8: extras -------------------------------------------------------------------------------------
def step8(req, ev):
    f = Form(req)
    info = dict(ev["info"] or {})
    if req.method == "POST":
        info["dress_code"] = f.text("dress_code", "Dress code", max=80)
        info["dress_code_notes"] = f.text("dress_code_notes", "Dress code notes", max=600)
        info["registry"] = [r for r in req.rows("rg", ["name", "url", "note"])][:10]
        info["gift_note"] = f.text("gift_note", "Gift preferences", max=800)
        info["contacts"] = [r for r in req.rows("ct", ["name", "role", "phone", "email"])][:8]
        info["accommodation"] = [r for r in req.rows("ac", ["name", "url", "note"])][:10]
        info["instructions"] = f.text("instructions", "Special instructions", max=2000)
        for r in info["registry"] + info["accommodation"]:
            if r["url"] and not r["url"].lower().startswith(("http://", "https://")):
                r["url"] = "https://" + r["url"]
            if not r["name"]:
                f.error("registry", "Each registry or accommodation entry needs a name.")
        for c in info["contacts"]:
            if c["email"] and not forms.EMAIL_RE.match(c["email"]):
                f.error("contacts", f"Check the email for {c['name'] or 'a contact'}.")
        rm = req.get("remove_upload")
        if rm.isdigit():
            storage.delete_upload(int(rm), ev["id"])
        gallery_limit = catalog.limit(ev, "gallery_photos", 0)
        have = len(events.uploads(ev["id"], "gallery"))
        for up in req.files.get("gallery", []):
            if have >= gallery_limit:
                f.error("gallery", f"Your package includes {gallery_limit} gallery photos.")
                break
            try:
                storage.save_image(up, ev, req.user["id"], "gallery")
                have += 1
            except storage.UploadError as e:
                f.error("gallery", f"{up.filename}: {e}")
        if f.ok or set(f.errors) <= {"gallery"}:
            events.save_json(ev["id"], "info", info)
        if rm.isdigit() and f.ok:
            req.flash("success", "Photo removed.")
            return redirect(step_url(ev, 8))
        r = finish_step(req, ev, 8, f)
        if r:
            return r
    def rows3(prefix, items, fields, phs):
        def one(i_, it=None):
            it = it or {}
            return ('<div class="repeat__row" style="--cols:repeat(3,minmax(0,1fr))">'
                    + "".join(_in(f"{prefix}-{i_}-{k}", it.get(k, ""), "url" if k == "url" else "email" if k == "email" else "text", ph=ph, label=lab)
                              for (k, lab), ph in zip(fields, phs)) + _rm() + "</div>")
        return [one(n, it) for n, it in enumerate(items)] or [one(0)], one("__i__")

    rg_rows, rg_t = rows3("rg", info.get("registry", []), [("name", "Registry"), ("url", "Link"), ("note", "Note")], ["Yuppiechef", "https://", "Optional"])
    ac_rows, ac_t = rows3("ac", info.get("accommodation", []), [("name", "Place"), ("url", "Link"), ("note", "Note")], ["Guest farm", "https://", "Use code SIPHO10"])
    def crow(i_, c=None):
        c = c or {}
        return ('<div class="repeat__row" style="--cols:repeat(4,minmax(0,1fr))">' + _in(f"ct-{i_}-name", c.get("name", ""), label="Name", ph="Zanele")
                + _in(f"ct-{i_}-role", c.get("role", ""), label="Role", ph="Maid of honour") + _in(f"ct-{i_}-phone", c.get("phone", ""), "tel", label="Phone", ph="+27 82 000 0000")
                + _in(f"ct-{i_}-email", c.get("email", ""), "email", label="Email") + _rm() + "</div>")
    ct_rows = [crow(n, c) for n, c in enumerate(info.get("contacts", []))] or [crow(0)]
    gallery = events.uploads(ev["id"], "gallery")
    glimit = catalog.limit(ev, "gallery_photos", 0)
    thumbs = "".join(f'<div style="position:relative"><img src="{events.upload_url(g)}" alt="" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:10px">'
                     f'<button class="btn btn--sm btn--glass" style="position:absolute;right:6px;bottom:6px" type="submit" name="remove_upload" value="{g["id"]}" formnovalidate aria-label="Remove photo">{i("trash")}</button></div>'
                     for g in gallery)
    dc_opts = [(d, d or "No dress code") for d in DRESS_CODES]
    inner = f"""{errors_summary(f.errors)}
<div class="form-row form-row--2">{select("dress_code", "Dress code", dc_opts, info.get("dress_code", ""))}
{field("dress_code_notes", "Dress code notes", info.get("dress_code_notes", ""), attrs={"placeholder": "Shades of emerald and gold; comfortable shoes for the lawn"})}</div>
<fieldset><legend>Gift registry</legend>{_repeat("rg", "", rg_rows, rg_t, "Add a registry", 10)}
{field("gift_note", "Gift preferences", info.get("gift_note", ""), type="textarea", attrs={"rows": 2, "placeholder": "Your presence is our present. If you'd like to give, a contribution to our honeymoon fund is welcome."})}</fieldset>
<fieldset><legend>Contacts for guests</legend>{_repeat("ct", "", ct_rows, crow("__i__"), "Add a contact", 8)}</fieldset>
<fieldset><legend>Accommodation</legend>{_repeat("ac", "", ac_rows, ac_t, "Add a place to stay", 10)}</fieldset>
{field("instructions", "Special instructions", info.get("instructions", ""), type="textarea", attrs={"rows": 3, "placeholder": "Unplugged ceremony: please keep phones away until the reception."})}
<fieldset><legend>Photo gallery</legend>{feature_note(ev, "gallery", "The photo gallery")}
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px;margin-bottom:12px">{thumbs}</div>
{('<label class="file-drop" style="position:relative">' + i("image") + f'<span>Add photos ({len(gallery)} of {glimit})</span><span class="hint">JPG, PNG or WebP up to {config.MAX_UPLOAD_BYTES // 1048576} MB each.</span><span class="tiny" data-files></span><input type="file" name="gallery" multiple accept="image/jpeg,image/png,image/webp,image/gif"></label>') if glimit else '<p class="hint">Your current package has no gallery. Premium includes 40 photos.</p>'}</fieldset>"""
    return wizard_frame(req, ev, 8, inner, enctype="multipart/form-data")


def _join(parts: list) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " or " + parts[-1]


def _q(text: str) -> str:
    from urllib.parse import quote
    return quote(text)


# --- step 9: review --------------------------------------------------------------------------------------
def step9(req, ev):
    if req.method == "POST":
        f = Form(req)
        return finish_step(req, ev, 9, f) or redirect(step_url(ev, 10))
    venue = ev["venue"] or {}
    gs = ev["guest_settings"] or {}
    info = ev["info"] or {}
    funcs = events.functions(ev["id"])
    sched = events.schedule(ev["id"])
    items = db.val("SELECT COUNT(*) FROM menu_items WHERE event_id = ?", (ev["id"],), 0)
    tables = events.tables(ev["id"])
    t_row = catalog.template(ev["template"])
    n_guests = db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (ev["id"],), 0)
    wording = (ev["design"] or {}).get("wording") or {}
    has_photo = bool(events.uploads(ev["id"], "hero"))
    needed = [  # (done, label, step, needed before paying)
        (bool(ev["hosts"] and ev["event_date"]), "Names and date", 1, True),
        (bool(venue.get("name") and venue.get("address")), "Venue and address", 2, True),
    ]
    nice = [
        (has_photo, "A main photo", 3), (any(wording.values()), "Your own wording (or keep the template's)", 3),
        (bool(gs.get("rsvp_deadline")), "An RSVP deadline", 4),
    ]
    if catalog.has_feature(ev, "guest_management"):
        nice.append((bool(n_guests), "Your guest list (you can add it after paying too)", 4))
    if catalog.has_feature(ev, "programme"):
        nice.append((bool(sched), "The programme", 5))
    if catalog.has_feature(ev, "menu"):
        nice.append((bool(items), "The menu", 6))
    nice.append((bool(info.get("dress_code") or info.get("contacts")), "Dress code or contact people", 8))

    def li(done, label, n, must=False):
        icon_ = i("check") if done else i("alert" if must else "plus")
        text = esc(label) if done else f'<a class="text-link" href="{step_url(ev, n)}">{esc(label)}</a>'
        return f'<li class="{"is-done" if done else ""}">{icon_}<span>{text}{"" if done or not must else " <b>(needed)</b>"}</span></li>'
    gaps = events.package_gaps(ev, catalog.planning_package(ev))
    gap_note = ""
    if gaps:
        gap_note = (f'<div class="notice notice--warn">{i("lock")}<span>Your planned package, {esc(catalog.package(catalog.planning_package(ev))["name"])}, '
                    f'won\'t show {esc(_join(gaps))}. Choose a package that includes them in the next step, or remove them.</span></div>')
    checklist = (f'<div class="box" style="display:grid;gap:12px"><h3 style="font-size:1.0625rem">Before you choose a package</h3>'
                 f'<ul class="checklist">{"".join(li(d, l, n, True) for d, l, n, _ in needed)}{"".join(li(d, l, n) for d, l, n in nice)}</ul>'
                 f'<p class="tiny muted">Only the first two are needed. Everything else can be added after your website is live.</p></div>')
    share = (f'<div class="box" style="display:grid;gap:10px"><h3 style="font-size:1.0625rem">Show someone before you pay</h3>'
             f'<p class="small muted">Send this link to your partner or family. They see your website as it is now, with RSVPs switched off. It never appears in search engines.</p>'
             f'<div class="row" style="gap:8px;flex-wrap:wrap"><input class="input input--sm mono" style="flex:1;min-width:0" readonly value="{esc(events.draft_url(ev))}" aria-label="Draft preview link">'
             f'<button class="btn btn--secondary btn--sm" type="button" data-copy="{esc(events.draft_url(ev))}" data-copied="Draft link copied">{i("copy")} Copy link</button>'
             f'<a class="btn btn--ghost btn--sm" href="https://wa.me/?text={esc(_q("Have a look at our event website draft: " + events.draft_url(ev)))}" target="_blank" rel="noopener">{i("chat")} WhatsApp</a></div></div>')

    def sec(n, title, rows):
        dl = "".join(f"<dt>{esc(k)}</dt><dd>{v if v else '<span class=muted>Not added</span>'}</dd>" for k, v in rows)
        return (f'<div class="review-section"><div class="review-section__head"><h3>{esc(title)}</h3>'
                f'<a class="btn btn--sm btn--ghost" href="{step_url(ev, n)}">{i("edit")} Edit</a></div><dl class="dl">{dl}</dl></div>')
    review = "".join([
        sec(1, "Event details", [("Event", esc(ev["name"])), ("Type", esc(catalog.category_name(ev["category"]))), ("Hosts", esc(ev["hosts"])),
                                 ("Date", esc(forms.fmt_date(ev["event_date"]))), ("Time", esc(" – ".join(x for x in (ev["start_time"], ev["end_time"]) if x)))]),
        sec(2, "Venue", [("Venue", esc(venue.get("name"))), ("Address", esc(venue.get("address"))), ("Parking", esc(venue.get("parking"))),
                         ("Directions", esc(venue.get("directions")))]),
        sec(3, "Design", [("Template", esc(t_row["name"] if t_row else ev["template"])), ("Photos", str(len(events.uploads(ev["id"]))) + " uploaded"),
                          ("Welcome", esc((ev["design"] or {}).get("wording", {}).get("welcome")))]),
        sec(4, "Guests", [("Estimated", esc(gs.get("estimated") or "")), ("RSVP deadline", esc(forms.fmt_date(gs.get("rsvp_deadline")))),
                          ("Plus-ones", esc({"none": "Not allowed", "per_guest": "Set per guest", "open": "Allowed"}.get(gs.get("plus_one_policy"), ""))),
                          ("Children", "Welcome" if gs.get("children_allowed") else "Adults only")]),
        sec(5, "Programme", [("Functions", esc(", ".join(fn["name"] for fn in funcs))), ("Programme items", str(len(sched)) if sched else "")]),
        sec(6, "Food and drinks", [("Menu items", str(items) if items else ""), ("Dietary options", esc(", ".join(info.get("dietary_options", []))))]),
        sec(7, "Seating", [("Tables", f"{len(tables)} tables, {sum(t['capacity'] for t in tables)} seats" if tables else "")]),
        sec(8, "Extras", [("Dress code", esc(info.get("dress_code"))), ("Registry", str(len(info.get("registry", []))) if info.get("registry") else ""),
                          ("Contacts", str(len(info.get("contacts", []))) if info.get("contacts") else "")]),
    ])
    inner = f"""{gap_note}{checklist}{share}
<div class="notice">{i("link")}<span>Your website address will be <b class="mono">{esc(events.public_url(ev))}</b>. Change it in Settings.</span></div>
<div class="preview-frame" data-preview data-device="desktop" style="margin:18px 0"><div class="preview-frame__bar"><span class="preview-frame__url">/events/{esc(ev['slug'])}</span>
<div class="seg"><button type="button" data-device="desktop" aria-pressed="true">Desktop</button><button type="button" data-device="mobile" aria-pressed="false">Mobile</button></div></div>
<div class="preview-frame__stage"><iframe src="/dashboard/events/{ev['uid']}/preview" title="Preview of your event website"></iframe></div></div>
{review}"""
    html = wizard_frame(req, ev, 9, inner)
    return html.replace("Save and continue", "Looks good, choose a package", 1)


# --- step 10: package -----------------------------------------------------------------------------------
def step10(req, ev):
    paid = catalog.package(ev["paid_package"])
    pending = db.one("SELECT * FROM orders WHERE event_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (ev["id"],))
    cards = []
    for p in catalog.packages():
        is_paid = paid and p["code"] == paid["code"]
        if paid and p["rank"] < paid["rank"]:
            continue
        price = p["price_cents"] - (paid["price_cents"] if paid and not is_paid else 0)
        bullets = db.loads(p["bullets"], [])
        limits = db.loads(p["limits"], {})
        items = "".join(f'<li>{i("check")}<span>{esc(b)}</span></li>' for b in bullets)
        lim = "".join(f'<div><span>{esc(label)}</span><b>{esc(limits.get(k, 0)) or "—"}</b></div>' for k, label in catalog.LIMIT_LABELS.items())
        selected = (ev["selected_package"] == p["code"]) and not is_paid
        p_gaps = [] if is_paid else events.package_gaps(ev, p["code"])
        gap_html = (f'<p class="small price__gap">{i("lock")} Won\'t show {esc(_join(p_gaps))}.</p>' if p_gaps else "")
        if is_paid:
            action = '<span class="pill pill--paid">Your current package</span>'
        else:
            label = f"Upgrade for {catalog.money(price)}" if paid else f"Pay {catalog.money(price)}"
            action = (f'<button class="btn {"btn--primary" if p["highlight"] or selected else "btn--secondary"} btn--block" type="submit" name="package" value="{esc(p["code"])}">{label}</button>')
        cards.append(f"""<article class="price{' price--highlight' if p['highlight'] and not paid else ''}">{'<span class="price__badge">Most chosen</span>' if p['highlight'] and not paid else ''}
<div><h3>{esc(p['name'])}</h3><p class="muted small" style="margin-top:6px">{esc(p['tagline'])}</p></div>
<div class="price__amount">{catalog.money(p['price_cents'])}<small>{"paid" if is_paid else "VAT incl."}</small></div><ul>{items}</ul><div class="price__limits">{lim}</div>{gap_html}{action}</article>""")
    sandbox = ""
    from ..services import payments
    if payments.gateway().mode == "sandbox":
        sandbox = (f'<div class="notice notice--warn">{i("info")}<span><b>Test mode.</b> Payments use the {esc(payments.gateway().label)}; '
                   f'no real money moves and test payments are marked as sandbox everywhere.</span></div>')
    status = ""
    if paid:
        status = f'<div class="notice notice--success">{i("check")}<span>Paid: <b>{esc(paid["name"])}</b>. Your website is {"live" if events.is_live(ev) else "ready to publish from Settings"}.</span></div>'
    elif pending:
        status = (f'<div class="notice">{i("clock")}<span>A payment for {catalog.money(pending["amount_cents"])} was started and hasn\'t been confirmed yet. '
                  f'<a class="text-link" href="/dashboard/events/{ev["uid"]}/payment/{pending["uid"]}">Check its status</a> or start again below.</span></div>')
    inner = f"""{status}{sandbox}
<form method="post" action="/dashboard/events/{ev['uid']}/checkout" class="form" novalidate>{csrf(req)}
<div class="price-grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">{"".join(cards)}</div>
<label class="check"><input type="checkbox" name="accept" value="1" required><span>I accept the <a class="text-link" href="/terms" target="_blank">terms of service</a> and <a class="text-link" href="/refunds" target="_blank">refund policy</a>. My website is published only after the payment gateway confirms payment.</span></label>
<p class="tiny muted">Secure payment by card or instant EFT. Prices include 15% VAT. You'll get a receipt by email.</p></form>
<p class="small muted" style="margin-top:14px">Questions before you pay, or rather have us finish the set-up? <a class="text-link" href="/help-me-set-up">Ask us to help</a>.</p>"""
    return wizard_frame(req, ev, 10, inner)


STEP_HANDLERS = {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6, 7: step7, 8: step8, 9: step9, 10: step10}
