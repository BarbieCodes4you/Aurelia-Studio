"""Event creation: /create (choose occasion and template) and the 10-step set-up wizard.

Each step is its own form at /dashboard/events/<uid>/setup/<n>. Saving never publishes
anything; the event stays a private draft until a verified payment (step 10).
"""
from __future__ import annotations

import json
import re

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
    (1, "Details", "calendar"), (2, "Design", "palette"), (3, "Guests", "users"), (4, "Programme", "list"),
    (5, "Food and drinks", "dish"), (6, "Seating", "seat"), (7, "Extras", "gift"), (8, "Review and pay", "card"),
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
CREATE_JS = """<script>(function(){var f=document.querySelector('[data-create]');if(!f)return;var grid=f.querySelector('[data-tpl-grid]'),more=f.querySelector('[data-show-all]'),all=false;
function sync(auto){var c=f.querySelector('input[name=category]:checked');var g=c?c.getAttribute('data-group'):'';var first=null,shown=0;
grid.querySelectorAll('.choice').forEach(function(l){var ok=!g||l.getAttribute('data-groups').split(' ').indexOf(g)>-1;l.hidden=!(ok||all);if(ok){shown++;if(!first)first=l;}});
if(more){more.hidden=!g||all;more.textContent='Show all '+grid.querySelectorAll('.choice').length+' templates';}
var picked=grid.querySelector('input[name=template]:checked');if(auto&&first&&(!picked||picked.closest('.choice').hidden)){first.querySelector('input').checked=true;}}
f.addEventListener('change',function(e){if(e.target.name==='category'){sync(true);var h=f.querySelector('[data-host-labels]');if(h){var g=e.target.getAttribute('data-group'),L=JSON.parse(h.getAttribute('data-host-labels'))[g];
if(L){var lab=f.querySelector('label[for='+h.id+']');if(lab)lab.firstChild.textContent=L[0];h.placeholder=L[1];}}}});
if(more)more.addEventListener('click',function(){all=true;sync(false);});sync(false);})();</script>"""


def _new_event(user_id: int, cat, tpl, hosts: str, pkg: str):
    hosts = (hosts or "").strip()[:120]
    name = suggestions.auto_event_name(cat["slug"], hosts) or cat["name"]
    ev = events.create(user_id, cat["slug"], tpl["slug"], name, hosts)
    events.touch(ev["id"], selected_package=pkg)
    return ev


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
        hosts = f.text("hosts", "Names", max=120)
        if not hosts:
            f.error("hosts", "Add the names to show on your website, e.g. Lerato & Sipho.")
        user = req.user
        if not user:
            if req.get("website"):                    # honeypot: bots fill every field
                return redirect("/")
            cname = f.text("contact_name", "Your name", required=True, max=120)
            cemail = f.email("contact_email", required=True)
            if cemail and not db.one("SELECT 1 FROM users WHERE email = ?", (cemail,)):
                from .accounts import _check_new_password
                _check_new_password(f, req.get("password"), req.get("password_confirm"), cemail)
            if not f.flag("terms"):
                f.error("terms", "Please accept the terms and privacy notice to continue.")
            if f.ok and auth.rate_limited(f"create-account:{req.ip}", 10, 3600):
                f.error("contact_email", "Too many new accounts from this connection. Try again in an hour.")
            if f.ok:
                existing = db.one("SELECT * FROM users WHERE email = ?", (cemail,))
                back = url("/create", category=cat_slug, template=tpl_slug, package=get("package"), hosts=hosts, go="1")
                if existing:
                    from .accounts import send_login_link
                    if existing["status"] == "active" and not auth.rate_limited(f"login-link:{cemail}", 5, 3600):
                        send_login_link(existing, back)
                    check_email = cemail
                else:
                    from ..services import email as mail
                    uid_ = db.insert("users", {"email": cemail, "name": cname, "password_hash": auth.hash_password(req.get("password")), "role": "customer",
                                               "marketing_consent": 0, "created_at": db.now()})
                    user = db.one("SELECT * FROM users WHERE id = ?", (uid_,))
                    mail.send(cemail, "welcome", {"first_name": mail.first_name(cname)}, user_id=uid_)
                    from .accounts import send_verification
                    send_verification(user)
                    auth.audit(uid_, "user.register", cemail, via="create")
        if f.ok and user and not check_email:
            ev = _new_event(user["id"], cat, tpl, hosts, pkg)
            auth.audit(user["id"], "event.create", ev["uid"], template=tpl["slug"])
            req.flash("success", "Your event is saved as a private draft. Let's add the details.")
            resp = redirect(step_url(ev, 1))
            if not req.user:
                from .accounts import login_session
                resp = login_session(resp, req, user["id"])
            return resp
    elif req.user and get("go") == "1" and cat and tpl:
        # back from an emailed sign-in link: create the event the visitor had chosen
        ev = _new_event(req.user["id"], cat, tpl, get("hosts"), pkg)
        auth.audit(req.user["id"], "event.create", ev["uid"], template=tpl["slug"])
        req.flash("success", "You're signed in and your event is saved as a private draft. Let's add the details.")
        return redirect(step_url(ev, 1))
    if check_email:
        body = f"""<section class="section" style="padding-top:calc(var(--header-h) + 48px)"><div class="container container--narrow"><div class="glass glass--strong panel" style="display:grid;gap:14px">
<span class="icon-tile icon-tile--soft">{i("mail")}</span><h1 style="font-size:clamp(1.8rem,1.3rem + 2vw,2.6rem)">You already have an account</h1>
<p class="lead" style="font-size:1.0625rem">We've emailed a sign-in link to <b>{esc(check_email)}</b>. Open it on this device and you'll come straight back here with your choices kept. The link expires in 2 hours.</p>
<p class="small muted">Rather use your password? <a class="text-link" href="{esc(url('/login', next=url('/create', category=cat_slug, template=tpl_slug, package=get('package'), hosts=get('hosts'), go='1')))}">Log in</a>.</p></div></div></section>"""
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
        from .accounts import new_password_fields
        about = f"""<div class="box"><h2 style="font-size:1.25rem;margin-bottom:6px">4. Where should we save it?</h2>
<p class="muted small" style="margin-bottom:16px">Create your account so your draft is saved and you can come back to it on any device. Already have an account? <a class="text-link" href="{esc(url('/login', next=url('/create', category=cat_slug, template=tpl_slug, package=pkg)))}">Log in</a>.</p>
<div class="form-row form-row--2">{field("contact_name", "Your name", f.data.get("contact_name", ""), required=True, errors=f.errors, attrs={"autocomplete": "name"})}
{field("contact_email", "Your email", f.data.get("contact_email", ""), type="email", required=True, errors=f.errors, attrs={"autocomplete": "email"})}</div>
<div class="form-row form-row--2">{new_password_fields(f)}</div>
<div class="field{' has-error' if 'terms' in f.errors else ''}" data-field="terms">{check("terms", 'I accept the <a class="text-link" href="/terms" target="_blank">terms of service</a> and the <a class="text-link" href="/privacy" target="_blank">privacy notice</a>.', bool(req.get("terms")))}</div>
{forms.honeypot()}</div>"""
    body = f"""<section class="page-hero"><div class="grid-texture"></div><div class="container">
<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">/</span><span>Create your event</span></nav>
<h1>Let's create your <span class="serif grad">event</span></h1><p class="lead">Three quick questions, then we build your website as you go. Nothing is published or charged until you're ready.</p>
<p class="small" style="margin-top:14px">Rather have us do it? <a class="text-link" href="/help-me-set-up">We can set it up for you</a>.</p></div></section>
<section class="section"><div class="container"><form class="form" method="post" novalidate data-create>{csrf(req)}
{errors_summary(f.errors)}
<div class="box"><h2 style="font-size:1.25rem;margin-bottom:16px">1. What are you celebrating?</h2>{"".join(cats_html)}</div>
<div class="box"><h2 style="font-size:1.25rem;margin-bottom:6px">2. Choose a starting template</h2><p class="muted small" style="margin-bottom:16px">These templates suit your occasion. You can switch any time in the design step.</p>
<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(230px,1fr))" data-tpl-grid>{"".join(tpl_html)}</div>
<button class="btn btn--ghost btn--sm" type="button" data-show-all hidden style="margin-top:12px">Show all templates</button></div>
<div class="box" data-field="hosts"><h2 style="font-size:1.25rem;margin-bottom:16px">3. Whose celebration is it?</h2>
{field("hosts", HOST_LABEL.get(group or "weddings", ("Names", ""))[0], f.data.get("hosts") or get("hosts"), required=True, errors=f.errors, attrs={"placeholder": HOST_LABEL.get(group or "weddings", ("", "e.g. Lerato & Sipho"))[1], "data-host-labels": json.dumps({k: list(v) for k, v in HOST_LABEL.items()})}, hint="Shown large on your website and used for your link. You can change it later.")}</div>
{about}
<div class="btn-row"><button class="btn btn--primary btn--lg" type="submit">Start setting up {i("arrow", "i--arrow")}</button></div></form></div></section>
{CREATE_JS}"""
    return page(req, "Create your event", body, "/create", noindex=True)


# --- wizard shell -----------------------------------------------------------------------------
LAST_STEP = 8
OPTIONAL_STEPS = {3, 4, 5, 6, 7}
STEP_FEATURE = {4: "programme", 5: "menu", 6: "seating"}


def wizard_frame(req, ev, n: int, inner: str, wide_preview: bool = False, enctype: str = "") -> str:
    done = set(ev["wizard_done"] or [])

    def badge(s):
        if s in STEP_FEATURE and not catalog.has_feature(ev, STEP_FEATURE[s]):
            return f'<span class="stepper__tag" title="Not in your planned package">{i("lock")}</span>'
        return '<span class="stepper__tag">optional</span>' if s in OPTIONAL_STEPS else ""
    stepper = "".join(
        f'<li><a href="{step_url(ev, s)}" class="{"is-done" if s in done else ""}"{" aria-current=step" if s == n else ""} data-step-link>'
        f'<span class="n">{"✓" if s in done and s != n else s}</span>{esc(label)}{badge(s)}</a></li>' for s, label, _ in STEPS)
    pct = round(100 * len(done & set(range(1, LAST_STEP + 1))) / LAST_STEP)
    title, icon = STEPS[n - 1][1], STEPS[n - 1][2]
    skip = (f'<a class="btn btn--ghost" href="{step_url(ev, n + 1)}" data-step-link>Skip for now</a>' if n in OPTIONAL_STEPS else "")
    to_review = (f'<button class="btn btn--ghost" type="submit" name="nav" value="review">Save and go to review</button>' if 2 <= n <= 6 else "")
    nav = f"""<div class="wizard-actions">{f'<a class="btn btn--ghost" href="{step_url(ev, n - 1)}">{i("arrow-left")} Back</a>' if n > 1 else '<span></span>'}
<div class="btn-row">{to_review}{skip}<button class="btn btn--primary" type="submit" name="nav" value="next">Save and continue {i("arrow", "i--arrow")}</button></div></div>"""
    if n == LAST_STEP:   # the last step holds its own checkout form; forms can't be nested
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
    body = f"""<div class="page-head"><div><h1>Set up {esc(ev['name'])}</h1><p>Private draft. Saved as you go; nothing is shared until you publish.</p></div>
<a class="btn btn--secondary btn--sm" href="/dashboard/events/{ev['uid']}/preview" target="_blank" rel="noopener">{i("eye")} Full preview</a></div>
<div class="wizard-progress"><span>{pct}% complete</span><div class="progress"><span style="width:{pct}%"></span></div><span class="mono">Step {n} of {LAST_STEP}</span></div>
<div class="wizard"><nav aria-label="Set-up steps"><ol class="stepper">{stepper}</ol></nav><div>{content}</div></div>"""
    return organiser_page(req, ev, f"Set-up step {n}", body, f"/setup/{n}", extra_scripts=WIZARD_JS)


def _card_head(n, title, icon):
    intros = {
        1: "Who, when and where. The essentials guests see first.", 2: "Make the template yours. Changes show in the preview as you go.",
        3: "Who's coming. Add them however suits you, or skip and let guests reply through your link.",
        4: "The running order of your day, or of each day.", 5: "Menus, meal choices and dietary needs.",
        6: "Choose your table layout. You seat guests once replies are in.", 7: "Dress code, gifts, places to stay and photos.",
        8: "Check what's left, choose your package and pay. Your website goes live as soon as payment is confirmed.",
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
    if n in (9, 10):                    # old links, from when set-up had 10 steps
        return redirect(step_url(ev, LAST_STEP))
    if n < 1 or n > LAST_STEP:
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
        events.touch(ev["id"], wizard_done=db.dumps(sorted(done)), wizard_step=max(ev["wizard_step"], min(n + 1, LAST_STEP)))
        if req.is_htmx:
            return json_response({"ok": True})
        if req.get("nav") == "next":
            return redirect(step_url(ev, n + 1))
        if req.get("nav") == "review":
            return redirect(step_url(ev, LAST_STEP))
        req.flash("success", "Saved.")
        return redirect(step_url(ev, n))
    return None


# --- step 1: details (names, date, venue) -------------------------------------------------------
def step_details(req, ev):
    f = Form(req)
    g = group_of(ev)
    if req.method == "POST":
        cat = f.choice("category", [c["slug"] for c in catalog.categories()], "occasions", default=ev["category"])
        c_row = catalog.category(cat)
        g = c_row["group_slug"] if c_row else g
        hosts = f.text("hosts", HOST_LABEL.get(g, ("Hosts",))[0], required=True, max=120)
        name = f.text("name", "Event name", max=120) or suggestions.auto_event_name(cat, hosts) or catalog.category_name(cat)
        if name == ev["name"] and ev["name"] in (suggestions.auto_event_name(ev["category"], ev["hosts"]), ev["hosts"], catalog.category_name(ev["category"])):
            name = suggestions.auto_event_name(cat, hosts) or name           # keep the automatic name in step with the names
        desc = f.text("description", "Description", max=1500)
        d = f.date("event_date", "Event date", required=True, future=not ev["paid_package"])
        st = f.time("start_time", "Start time")
        et = f.time("end_time", "End time")
        if st and et and et <= st and not req.get("ends_next_day"):
            f.error("end_time", "End time must be after the start time (tick “ends after midnight” if it does).")
        venue = {
            "name": f.text("venue_name", "Venue name", required=True, max=160),
            "address": f.text("address", "Address", required=True, max=300),
            "map_url": f.url("map_url", "Map link"),
            "parking": f.text("parking", "Parking", max=1000),
            "directions": f.text("directions", "Directions", max=2000),
            "accommodation": f.text("accommodation", "Accommodation", max=2000),
        }
        if f.ok:
            events.touch(ev["id"], name=name, category=cat, hosts=hosts, description=desc, event_date=d, start_time=st, end_time=et)
            events.save_json(ev["id"], "venue", venue)
            gs = dict(ev["guest_settings"] or {})
            if d and not gs.get("rsvp_deadline") and events.suggested_rsvp_deadline(d):
                gs["rsvp_deadline"] = events.suggested_rsvp_deadline(d)     # a sensible default the client can change in Guests
                events.save_json(ev["id"], "guest_settings", gs)
            if not ev["published_at"] and hosts and not ev["slug"].startswith(forms.slugify(hosts, 50)):
                events.touch(ev["id"], slug=events.unique_slug(hosts, ev["id"]))
            events.keep_online_past_event(events.by_id(ev["id"]))
        r = finish_step(req, events.by_id(ev["id"]), 1, f)
        if r:
            return r
    d = {**ev, **f.data}
    v = {**(ev["venue"] or {}), **{k.replace("venue_name", "name"): val for k, val in f.data.items() if k in ("venue_name", "address", "map_url", "parking", "directions", "accommodation")}}
    label, ph = HOST_LABEL.get(g, ("Hosts", ""))
    cats = [(c["slug"], f'{catalog.GROUPS[c["group_slug"]]["name"]}: {c["name"]}') for c in catalog.categories()]
    more_open = " open" if any(v.get(k) for k in ("parking", "directions", "accommodation")) or d.get("description") or (f.errors.keys() & {"map_url"}) else ""
    inner = f"""{errors_summary(f.errors)}
{field("hosts", label, d.get("hosts"), required=True, errors=f.errors, attrs={"placeholder": ph, "autofocus": not d.get("hosts")}, hint="Shown large on your website and used for your link, e.g. /events/lerato-and-sipho.")}
<div class="form-row form-row--3">{field("event_date", "Date", d.get("event_date"), type="date", required=True, errors=f.errors)}
{field("start_time", "Starts", d.get("start_time"), type="time", errors=f.errors)}{field("end_time", "Ends", d.get("end_time"), type="time", errors=f.errors)}</div>
{check("ends_next_day", "Ends after midnight", bool(req.get("ends_next_day")))}
<div class="form-row form-row--2">{field("venue_name", "Venue", v.get("name"), required=True, errors=f.errors, attrs={"placeholder": "Oakhaven Wine Estate"})}
{field("address", "Address", v.get("address"), required=True, errors=f.errors, hint="Guests get directions and a map from this.")}</div>
<p class="tiny muted">More than one day, or a second venue? Add each day in the Programme step.</p>
<details class="box" style="padding:14px 16px"{more_open}><summary style="cursor:pointer;font-weight:500">More details (optional): map pin, parking, directions, a short welcome</summary><div style="display:grid;gap:16px;margin-top:16px">
{field("map_url", "Google Maps link", v.get("map_url"), type="url", errors=f.errors, hint="For an exact pin, e.g. a farm gate. Paste the share link from Google Maps.")}
{field("parking", "Parking", v.get("parking"), type="textarea", errors=f.errors, attrs={"rows": 2}, hint="Where to park, security, drop-off.")}
{field("directions", "Directions", v.get("directions"), type="textarea", errors=f.errors, attrs={"rows": 2}, hint="Landmarks, gate codes, the last turn that GPS gets wrong.")}
{field("description", "A short welcome", d.get("description"), type="textarea", errors=f.errors, attrs={"rows": 2}, hint="One or two sentences guests read first.")}
<div class="form-row form-row--2">{field("name", "Event name", d.get("name"), errors=f.errors, hint="Used in invitation messages. Filled in from your names.")}
{select("category", "Occasion", cats, d.get("category"), errors=f.errors)}</div></div></details>"""
    return wizard_frame(req, ev, 1, inner)


# --- step 2: design ------------------------------------------------------------------------------
def step_design(req, ev):
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
            return redirect(step_url(ev, 2))
        r = finish_step(req, ev, 2, f)
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
    html = wizard_frame(req, ev, 2, inner, wide_preview=True, enctype="multipart/form-data")
    return html.replace("data-wizard-form", "data-wizard-form data-autosave", 1)


# --- step 3: guests --------------------------------------------------------------------------------
def _move_deadline_in_wording(ev, old: str, new: str) -> None:
    """Ready-made wording has the RSVP date written in; keep it in step when the deadline changes."""
    design = dict(ev["design"] or {})
    wording = dict(design.get("wording") or {})
    changed = False
    for long_ in (True, False):
        a, b = forms.fmt_date(old, long_), forms.fmt_date(new, long_)
        for k, v in wording.items():
            if a and isinstance(v, str) and a in v:
                wording[k] = v.replace(a, b)
                changed = True
    if changed:
        design["wording"] = wording
        events.touch(ev["id"], design=db.dumps(design))


GUESTS_JS = """<script>(function(){var box=document.querySelector('[data-guest-add]');if(!box)return;var ta=box.querySelector('textarea[name=guest_paste]'),
nm=box.querySelector('[data-qa-name]'),ph=box.querySelector('[data-qa-phone]'),cnt=box.querySelector('[data-pending-count]'),det=box.querySelector('[data-paste-box]');
function count(){var n=ta.value.split(/\\n/).filter(function(l){l=l.trim();return l&&!/:$/.test(l);}).length;cnt.textContent=n?'('+n+' ready to add when you continue)':'';}
function add(line){ta.value=(ta.value.trim()?ta.value.replace(/\\s+$/,'')+'\\n':'')+line;count();ta.dispatchEvent(new Event('input',{bubbles:true}));}
function quick(){var n=nm.value.trim();if(!n)return;add(n+(ph.value.trim()?', '+ph.value.trim():''));nm.value='';ph.value='';nm.focus();if(window.Aurelia)Aurelia.toast(n+' added. Saved when you continue.');}
box.querySelector('[data-qa-add]').addEventListener('click',quick);
[nm,ph].forEach(function(el){el.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();if(el===nm&&!ph.value&&nm.value.trim())quick();else if(el===ph)quick();else ph.focus();}});});
ta.addEventListener('input',count);count();
var pick=box.querySelector('[data-pick-contacts]');if('contacts' in navigator&&'ContactsManager' in window){pick.hidden=false;pick.addEventListener('click',function(){
navigator.contacts.select(['name','tel','email'],{multiple:true}).then(function(list){list.forEach(function(c){var n=(c.name&&c.name[0])||'';if(!n)return;
add(n+(c.tel&&c.tel[0]?', '+c.tel[0]:'')+(c.email&&c.email[0]?', '+c.email[0]:''));});if(list.length){det.open=true;if(window.Aurelia)Aurelia.toast(list.length+' contacts added. Saved when you continue.');}}).catch(function(){});});}
var file=box.querySelector('[data-guest-file]'),fname=box.querySelector('[data-guest-file-name]');file.addEventListener('change',function(){if(file.files[0]){fname.hidden=false;fname.textContent=file.files[0].name+' will be read when you continue.';}});})();</script>"""


def step_guests(req, ev):
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
        up = req.file("guest_file")
        if up is not None and up.data:
            if up.size > 3 * 1024 * 1024:
                f.error("guest_paste", "That file is bigger than 3 MB. Save just the guest list as Excel or CSV and try again.")
            else:
                try:
                    pasted += suggestions.parse_sheet(suggestions.read_sheet_file(up.data, up.filename or ""))
                except Exception:          # a damaged or unusual file: say so plainly
                    f.error("guest_paste", "We couldn't read that file. Save it as Excel (.xlsx) or CSV and try again, or paste the names instead.")
        if pasted and not catalog.has_feature(ev, "guest_management"):
            f.error("guest_paste", "Adding a guest list is part of the Premium package. Change the package you're planning with, or let guests reply through your one link.")
        if f.ok:
            old_deadline = (ev["guest_settings"] or {}).get("rsvp_deadline")
            events.save_json(ev["id"], "guest_settings", gs)
            if old_deadline and gs["rsvp_deadline"] and old_deadline != gs["rsvp_deadline"]:
                _move_deadline_in_wording(ev, old_deadline, gs["rsvp_deadline"])
            if pasted:
                added = events.add_pasted_guests(ev, pasted)
                req.flash("success", f"Added {added} guest{'s' if added != 1 else ''} to your list." + (f" {len(pasted) - added} were already on it." if added < len(pasted) else ""))
        r = finish_step(req, ev, 3, f)
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
        listed = (f'<p class="small"><b>{have} guest{"s" if have != 1 else ""}</b> on your list. '
                  f'<a class="text-link" href="/dashboard/events/{ev["uid"]}/guests">Open the guest list</a> to edit them, mark VIPs or add families.</p>') if have else ""
        paste = f"""<fieldset class="guest-add" data-guest-add><legend>Your guest list</legend>{listed}
<div class="quick-add"><input class="input" data-qa-name placeholder="Guest's name" aria-label="Guest's name" autocomplete="off">
<input class="input" data-qa-phone type="tel" placeholder="Mobile (optional)" aria-label="Guest's mobile" autocomplete="off">
<button class="btn btn--secondary" type="button" data-qa-add>{i("plus")} Add</button></div>
<p class="tiny muted" style="margin-top:-4px">Type a name, press Enter, type the next one. Couples can go on one line, e.g. “Thabo & Lindi Mokoena”.</p>
<div class="btn-row"><button class="btn btn--ghost btn--sm" type="button" data-pick-contacts hidden>{i("phone")} Choose from my phone contacts</button>
<label class="btn btn--ghost btn--sm" style="position:relative">{i("upload")} Upload Excel or CSV<input type="file" name="guest_file" accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" style="position:absolute;inset:0;opacity:0;cursor:pointer" data-guest-file></label></div>
<p class="small" data-guest-file-name hidden></p>
<details data-paste-box{" open" if req.get("guest_paste") or f.errors.get("guest_paste") else ""}><summary class="small" style="cursor:pointer;font-weight:500">Paste a list <span class="muted" data-pending-count></span></summary>
{field("guest_paste", "Names to add", req.get("guest_paste") if f.errors else "", type="textarea", errors=f.errors, attrs={"rows": 7, "placeholder": "Mokoena family:" + chr(10) + "Thandi Mokoena, 082 123 4567" + chr(10) + "Gogo Nomsa" + chr(10) + "Friends:" + chr(10) + "Sipho Dlamini, sipho@example.com"}, hint="One guest per line, with a mobile or email if you have it. A line ending in a colon, like “Mokoena family:”, groups the names below it. Copying a column from Excel, Google Sheets or your phone's notes works too.")}</details>
<p class="small muted">No list yet? That's fine. Skip this step: when guests reply through your link, they're added to your list for you.</p></fieldset>"""
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
    return wizard_frame(req, ev, 3, inner + GUESTS_JS, enctype="multipart/form-data")


# --- step 4: programme ------------------------------------------------------------------------------
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


def _indexed(req, prefix: str, fields: list) -> list:
    """Repeated rows posted as prefix-<i>-<field>, with their index kept (unlike req.rows)."""
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)-")
    idx = sorted({int(m.group(1)) for k in req.form for m in [pat.match(k)] if m})
    return [(n, {f: req.get(f"{prefix}-{n}-{f}") for f in fields}) for n in idx]


def _prog_row(k, d, it=None) -> str:
    it = it or {}
    g = lambda key: (it.get(key) if isinstance(it, dict) else it[key]) or ""
    return (f'<div class="prog-row"><input type="hidden" name="si-{k}-day" value="{d}">'
            + _in(f"si-{k}-time", g("item_time"), "time", label="Time") + _in(f"si-{k}-title", g("title"), ph="Ceremony", label="What happens")
            + _in(f"si-{k}-description", g("description"), ph="Optional detail", label="Detail")
            + f'<button class="btn btn--ghost btn--icon" type="button" data-remove-item aria-label="Remove item">{i("trash")}</button></div>')


def _day_block(d, fn, rows: list, single_hint: bool) -> str:
    fn = fn or {}
    g = lambda key: (fn.get(key) if isinstance(fn, dict) else fn[key]) or ""
    has_place = bool(g("venue_name") or g("address") or g("map_url"))
    return f"""<section class="day-block" data-day="{d}"><input type="hidden" name="fn-{d}-id" value="{g("id")}">
<div class="day-head"><div class="row row--between"><h3 data-day-title>Day</h3>
<button class="btn btn--ghost btn--sm" type="button" data-remove-day>{i("trash")} Remove day</button></div>
<div class="form-row form-row--4">{_in(f"fn-{d}-name", g("name"), ph="e.g. Negotiations, or Ceremony", label="What's on this day")}{_in(f"fn-{d}-date", g("func_date"), "date", label="Date")}
{_in(f"fn-{d}-start", g("start_time"), "time", label="Starts")}{_in(f"fn-{d}-end", g("end_time"), "time", label="Ends")}</div>
<details{" open" if has_place else ""}><summary class="small" style="cursor:pointer">Different venue for this day?</summary>
<div class="form-row form-row--3" style="margin-top:10px">{_in(f"fn-{d}-venue", g("venue_name"), ph="Leave empty for the main venue", label="Venue")}
{_in(f"fn-{d}-address", g("address"), ph="Address", label="Address")}{_in(f"fn-{d}-map", g("map_url"), "url", ph="Google Maps link", label="Map link")}</div></details></div>
<div data-items>{"".join(rows)}</div>
<div><button class="btn btn--sm btn--secondary" type="button" data-add-item>{i("plus")} Add to this day</button></div></section>"""


PROGRAMME_JS = """<script>(function(){var box=document.querySelector('[data-days]');if(!box)return;var form=box.closest('form');
var nd=+box.getAttribute('data-next-day'),nk=+box.getAttribute('data-next-item'),max=+box.getAttribute('data-max-days');
var dayT=document.querySelector('template[data-day-template]').innerHTML,itemT=document.querySelector('template[data-item-template]').innerHTML;
function fill(t,d,k){return t.split('__D__').join(d).split('__K__').join(k);}
function sync(){var days=box.querySelectorAll('.day-block');box.classList.toggle('is-single',days.length===1);
days.forEach(function(d,n){var t=d.querySelector('[data-day-title]');if(t)t.textContent='Day '+(n+1);});
var add=document.querySelector('[data-add-day]'),lock=document.querySelector('[data-day-limit]');if(add)add.hidden=days.length>=max;if(lock)lock.hidden=days.length<max;}
form.addEventListener('click',function(e){var t=e.target.closest('[data-add-day],[data-add-item],[data-remove-day],[data-remove-item]');if(!t)return;
if(t.hasAttribute('data-add-day')){box.insertAdjacentHTML('beforeend',fill(dayT,nd,nk));nd++;nk++;sync();var b=box.lastElementChild.querySelector('input[name$="-name"]');if(b)b.focus();}
else if(t.hasAttribute('data-add-item')){var d=t.closest('.day-block'),list=d.querySelector('[data-items]');list.insertAdjacentHTML('beforeend',fill(itemT,d.getAttribute('data-day'),nk));nk++;list.lastElementChild.querySelector('input').focus();}
else if(t.hasAttribute('data-remove-day')){if(!confirm('Remove this day and everything planned for it?'))return;t.closest('.day-block').remove();sync();}
else{t.closest('.prog-row').remove();}
form.dispatchEvent(new Event('input'));});sync();})();</script>"""


def step_programme(req, ev):
    f = Form(req)
    max_days = catalog.limit(ev, "functions", 1) if catalog.has_feature(ev, "multi_functions") else 1
    funcs = events.functions(ev["id"])
    if req.method == "POST" and req.get("nav") == "sample":
        items = suggestions.sample_programme(ev["category"], (funcs[0]["start_time"] if funcs and funcs[0]["start_time"] else ev["start_time"]) or "", group_of(ev))
        first = funcs[0]["id"] if funcs else None
        with db.transaction():
            db.run("DELETE FROM schedule_items WHERE event_id = ? AND (function_id IS ? OR function_id IS NULL)", (ev["id"], first))
            for n, it in enumerate(items):
                db.insert("schedule_items", {"event_id": ev["id"], "function_id": first, "item_time": it["item_time"], "title": it["title"],
                                             "description": it["description"], "kind": it["kind"], "sort": n})
        req.flash("success", "Sample programme added" + (f" to {funcs[0]['name']}" if funcs else "") + ". Change the times and titles to match your day.")
        return redirect(step_url(ev, 4))
    if req.method == "POST":
        days = _indexed(req, "fn", ["id", "name", "date", "start", "end", "venue", "address", "map"])
        rows = [(k, r) for k, r in _indexed(req, "si", ["time", "title", "description", "day"]) if r["time"] or r["title"] or r["description"]]
        single = len(days) <= 1 and not any(days[0][1][x] for x in ("name", "date", "venue", "address", "map")) if days else True
        if not single and len(days) > max_days:
            f.error("functions", f"Your package includes {max_days} day{'s' if max_days != 1 else ''}. Choose a bigger package at the last step for more.")
        for _, r in days:
            for k in ("start", "end"):
                if r[k] and not forms.TIME_RE.match(r[k]):
                    f.error("functions", "Times must look like 14:30.")
        for _, r in rows:
            if not r["title"]:
                f.error("schedule", "Each programme item needs a short description of what happens, e.g. Ceremony or Dinner.")
            if r["time"] and not forms.TIME_RE.match(r["time"]):
                f.error("schedule", "Programme times must look like 14:30.")
        if f.ok:
            from datetime import date, timedelta
            with db.transaction():
                fid_for, keep = {}, []
                if not single:
                    for n, (d, r) in enumerate(days):
                        day_date = r["date"] or None
                        if not day_date and ev["event_date"]:
                            try:
                                day_date = (date.fromisoformat(ev["event_date"]) + timedelta(days=n)).isoformat()
                            except ValueError:
                                day_date = None
                        data = {"name": (r["name"] or f"Day {n + 1}")[:100], "func_date": day_date, "start_time": r["start"], "end_time": r["end"],
                                "venue_name": r["venue"][:160], "address": r["address"][:300], "map_url": r["map"][:600], "sort": n}
                        if r["id"].isdigit() and db.one("SELECT 1 FROM event_functions WHERE id = ? AND event_id = ?", (int(r["id"]), ev["id"])):
                            db.update("event_functions", int(r["id"]), data)
                            fid_for[d] = int(r["id"])
                        else:
                            fid_for[d] = db.insert("event_functions", {"event_id": ev["id"], **data})
                        keep.append(fid_for[d])
                marks = ",".join("?" * len(keep)) or "NULL"
                db.run(f"DELETE FROM event_functions WHERE event_id = ? AND id NOT IN ({marks})", [ev["id"], *keep])
                db.run("DELETE FROM schedule_items WHERE event_id = ?", (ev["id"],))
                first = keep[0] if keep else None
                for n, (_, r) in enumerate(rows):
                    fid = fid_for.get(int(r["day"])) if r["day"].isdigit() else None
                    db.insert("schedule_items", {"event_id": ev["id"], "function_id": fid if fid else first, "item_time": r["time"],
                                                 "title": r["title"][:160], "description": r["description"][:600],
                                                 "kind": suggestions.guess_kind(r["title"]), "sort": n})
        r = finish_step(req, ev, 4, f)
        if r:
            return r
    sched = events.schedule(ev["id"])
    k = 0
    blocks = []
    if funcs:
        for d, fn in enumerate(funcs):
            mine = [s_ for s_ in sched if s_["function_id"] == fn["id"] or (d == 0 and s_["function_id"] not in {x["id"] for x in funcs})]
            rows_html = []
            for it in mine:
                rows_html.append(_prog_row(k, d, it)); k += 1
            if not rows_html:
                rows_html.append(_prog_row(k, d)); k += 1
            blocks.append(_day_block(d, fn, rows_html, False))
        nd = len(funcs)
    else:
        rows_html = []
        for it in sched:
            rows_html.append(_prog_row(k, 0, it)); k += 1
        if not rows_html:
            rows_html = [_prog_row(k, 0), _prog_row(k + 1, 0)]; k += 2
        blocks.append(_day_block(0, None, rows_html, True))
        nd = 1
    multi = "multi_function" in catalog.category_features(ev["category"]) or ev["category"] == "lobola"
    tip = ("Lobola, traditional and multi-day weddings often run over more than one day. Add each day and plan what happens on it. "
           if multi else "")
    occasion = esc(catalog.category_name(ev["category"]).lower())
    inner = f"""{errors_summary(f.errors)}{feature_note(ev, "programme", "The programme")}
<div class="notice" style="margin-bottom:6px">{i("wand")}<div><span>Start from a typical {occasion} programme{" timed from " + esc(ev["start_time"]) if ev["start_time"] else ""}, then change the times and titles.</span>
<div style="margin-top:10px"><button class="btn btn--secondary btn--sm" type="submit" name="nav" value="sample" formnovalidate{' data-confirm="This replaces the items for the first day with a sample. Continue?"' if sched else ""}>Use a sample programme</button></div></div></div>
<div class="days" data-days data-next-day="{nd}" data-next-item="{k}" data-max-days="{max_days}">{"".join(blocks)}</div>
<div class="row" style="gap:12px;flex-wrap:wrap"><button class="btn btn--secondary btn--sm" type="button" data-add-day>{i("calendar")} Add another day</button>
<p class="small muted" style="margin:0">{tip}{f"Your package includes up to {max_days} days." if max_days > 1 else ""}</p>
<p class="small muted" data-day-limit hidden style="margin:0">{"You've reached the number of days your package includes." if max_days > 1 else "Events over more than one day are part of Premium and Signature. Choose one at the last step."}</p></div>
<template data-day-template>{_day_block("__D__", None, [_prog_row("__K__", "__D__")], False)}</template>
<template data-item-template>{_prog_row("__K__", "__D__")}</template>{PROGRAMME_JS}"""
    return wizard_frame(req, ev, 4, inner)


# --- step 5: food ------------------------------------------------------------------------------------
def step_food(req, ev):
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
                    return redirect(step_url(ev, 5))
        r = finish_step(req, ev, 5, f)
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
    return wizard_frame(req, ev, 5, inner)


# --- step 6: seating -----------------------------------------------------------------------------------
SEATING_HOWTO = ('<div class="box" style="display:grid;gap:12px"><h3 style="font-size:1.0625rem">How you\'ll seat your guests</h3>'
                 '<ol class="how-list" style="list-style:none;margin:0;padding:0;display:grid;gap:12px">'
                 '<li><span class="mono">01</span><div><b>Guests reply on your website</b><p class="small muted" style="margin-top:4px">Their names, plus-ones and meal choices come into your dashboard.</p></div></li><li><span class="mono">02</span><div><b>Tap “Seat everyone automatically”</b><p class="small muted" style="margin-top:4px">In your dashboard\'s seating chart. Families and groups stay together at the tables you chose, and nobody is put at the top table.</p></div></li><li><span class="mono">03</span><div><b>Move anyone you like</b><p class="small muted" style="margin-top:4px">Drag a guest to another table, or tap a guest and then a table. Then print the plan or download it for your venue.</p></div></li>'
                 '</ol></div>')

TOP_CHOICES = {
    "weddings": ("Where will the couple sit?", [("sweetheart", "Sweetheart table", "Just the two of you, facing your guests."),
                                                ("head", "Head table", "The couple with the bridal party, along one side, facing guests."),
                                                ("none", "With your guests", "No top table. You sit at a table among family and friends.")]),
    "other": ("A top table for the hosts?", [("sweetheart", "Small top table", "For the hosts only, facing guests."),
                                            ("head", "Top table", "Hosts and special guests, along one side, facing the room."),
                                            ("none", "No top table", "Hosts sit among their guests.")]),
}
GUEST_CHOICES = [("round", "Round tables", "Easy conversation. 8 to 10 per table."),
                 ("long", "Long tables", "Family style, in rows. Seats more in the same space."),
                 ("mixed", "A mix", "Round tables with a few long ones for big families.")]

SEATING_STEP_JS = """<script src="/static/js/floorplan.js"></script><script>(function(){var f=document.querySelector('[data-wizard-form]');if(!f||!window.AureliaFloor)return;
f.querySelectorAll('[data-fp-icon]').forEach(function(el){el.innerHTML=AureliaFloor.icon(el.getAttribute('data-fp-icon'));});
var box=f.querySelector('[data-plan-preview]');function v(n){var el=f.querySelector('[name='+n+']:checked')||f.querySelector('[name='+n+']');return el?el.value:'';}
function draw(){box.innerHTML=AureliaFloor.plan({top:v('top_table'),guest:v('guest_tables'),count:v('table_count'),cap:v('capacity'),dance:box.getAttribute('data-dance')==='1'});}
f.addEventListener('input',draw);f.addEventListener('change',draw);draw();})();</script>"""


def _layout_choices(name, options, value):
    return ('<div class="choice-grid layout-choice" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">' + "".join(
        f'<label class="choice"><input type="radio" name="{name}" value="{k}"{" checked" if k == value else ""}><span><span data-fp-icon="{"none" if name == "top_table" and k == "none" else k}"></span>'
        f'<b>{esc(t)}</b><small>{esc(d)}</small></span></label>' for k, t, d in options) + "</div>")


def step_seating(req, ev):
    f = Form(req)
    info = dict(ev["info"] or {})
    existing = events.tables(ev["id"])
    layout = events.seating_layout(ev)
    est = (ev["guest_settings"] or {}).get("estimated") or db.val("SELECT COUNT(*) FROM guests WHERE event_id = ?", (ev["id"],), 0) or 0
    if req.method == "POST":
        layout = {"top": f.choice("top_table", ["sweetheart", "head", "none"], "top tables", default=layout["top"]),
                  "guest": f.choice("guest_tables", ["round", "long", "mixed"], "table types", default=layout["guest"]),
                  "capacity": f.integer("capacity", "Seats per table", min=2, max=40, default=10)}
        count = f.integer("table_count", "Number of tables", min=0, max=120, default=10)
        layout["count"] = count
        info["seating_layout"] = layout
        info["seating_notes"] = f.text("seating_notes", "Special seating requirements", max=1500)
        plan_now = f.flag("plan_now")
        if plan_now and any(t["parties"] for t in existing):
            f.error("plan_now", "Some tables already have guests. Change the tables in the seating editor instead.")
        if f.ok:
            with db.transaction():
                events.save_json(ev["id"], "info", info)
                if plan_now:
                    db.run("DELETE FROM seating_tables WHERE event_id = ?", (ev["id"],))
                    events.create_layout_tables(ev, layout, count)
        r = finish_step(req, ev, 6, f)
        if r:
            return r
    group = group_of(ev)
    top_q, top_opts = TOP_CHOICES["weddings" if group == "weddings" else "other"]
    suggested = max(1, -(-int(est) // int(layout.get("capacity") or 10))) if est else 10
    guest_tables = [t for t in existing if t["notes"] != events.TOP_TABLE_NOTE]
    inner = f"""{errors_summary(f.errors)}{feature_note(ev, "seating", "The seating chart")}
<div class="notice">{i("seat")}<span>Most hosts plan seating once replies are in. Then the seating editor in your dashboard can seat everyone automatically, keeping families and groups together, and you drag people to fine-tune.</span></div>
<fieldset><legend>{esc(top_q)}</legend>{_layout_choices("top_table", top_opts, layout["top"])}</fieldset>
<fieldset><legend>Guest tables</legend>{_layout_choices("guest_tables", GUEST_CHOICES, layout["guest"])}</fieldset>
<div class="form-row form-row--2">{field("capacity", "Seats per table", layout.get("capacity") or 10, type="number", errors=f.errors, attrs={"min": 2, "max": 40})}
{field("table_count", "Number of guest tables", len(guest_tables) or suggested, type="number", errors=f.errors, attrs={"min": 0, "max": 120}, hint=f"About {suggested} for {est} guests." if est else "We'll adjust this once you know your numbers.")}</div>
<div class="fp-plan-box"><p class="tiny muted mono" style="margin-bottom:8px">YOUR ROOM, ROUGHLY</p><div data-plan-preview data-dance="{1 if group in ("weddings", "parties") else 0}"></div></div>
{SEATING_HOWTO}
<div class="field{' has-error' if 'plan_now' in f.errors else ''}">{check("plan_now", "Create these tables now", bool(req.get("plan_now")), hint="Optional. Otherwise we create them from this layout when you open the seating editor. You can rename and move tables there.")}</div>
{field("seating_notes", "Special seating requirements", info.get("seating_notes", ""), type="textarea", attrs={"rows": 3, "placeholder": "Grandparents near the front and away from the speakers; wheelchair access at Table 3."})}{SEATING_STEP_JS}"""
    return wizard_frame(req, ev, 6, inner)


# --- step 7: extras -------------------------------------------------------------------------------------
def step_extras(req, ev):
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
            return redirect(step_url(ev, 7))
        r = finish_step(req, ev, 7, f)
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
<details class="box" style="padding:14px 16px"{" open" if info.get("contacts") else ""}><summary style="cursor:pointer;font-weight:500">Someone guests can call on the day (optional)</summary>
<p class="hint" style="margin:10px 0 12px">For guests who are lost, running late or need help on the day, e.g. your planner, MC or a cousin. It shows on your website, so you're not the one answering calls. Leave it empty if you don't need it.</p>
{_repeat("ct", "", ct_rows, crow("__i__"), "Add a person", 8)}</details>
<fieldset><legend>Accommodation</legend>{_repeat("ac", "", ac_rows, ac_t, "Add a place to stay", 10)}</fieldset>
{field("instructions", "Special instructions", info.get("instructions", ""), type="textarea", attrs={"rows": 3, "placeholder": "Unplugged ceremony: please keep phones away until the reception."})}
<fieldset><legend>Photo gallery</legend>{feature_note(ev, "gallery", "The photo gallery")}
<p class="hint" style="margin-bottom:12px">Add a few photos now, like your engagement shoot, or come back after the event and add photos from the day. Guests see them on the same link they already have.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px;margin-bottom:12px">{thumbs}</div>
{('<label class="file-drop" style="position:relative">' + i("image") + f'<span>Add photos ({len(gallery)} of {glimit})</span><span class="hint">JPG, PNG or WebP up to {config.MAX_UPLOAD_BYTES // 1048576} MB each.</span><span class="tiny" data-files></span><input type="file" name="gallery" multiple accept="image/jpeg,image/png,image/webp,image/gif"></label>') if glimit else '<p class="hint">Your current package has no gallery. Premium includes 40 photos.</p>'}</fieldset>"""
    return wizard_frame(req, ev, 7, inner, enctype="multipart/form-data")


def _join(parts: list) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " or " + parts[-1]


def _q(text: str) -> str:
    from urllib.parse import quote
    return quote(text)


# --- step 8: review and pay ------------------------------------------------------------------------------
def step_review_pay(req, ev):
    """One page to check and pay: what's still needed, the packages with a Pay button each, a draft link to
    show family, and everything entered so far (folded away)."""
    from ..services import payments
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
    paid = catalog.package(ev["paid_package"])
    pending = db.one("SELECT * FROM orders WHERE event_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (ev["id"],))
    needed = [(bool(ev["hosts"] and ev["event_date"]), "Names and date", 1), (bool(venue.get("name") and venue.get("address")), "Venue and address", 1)]
    nice = [(bool(events.uploads(ev["id"], "hero")), "A main photo", 2), (any(wording.values()), "Your own wording (or keep the template's)", 2),
            (bool(gs.get("rsvp_deadline")), "An RSVP deadline", 3)]
    if catalog.has_feature(ev, "guest_management"):
        nice.append((bool(n_guests), "Your guest list (you can add it after paying too)", 3))
    if catalog.has_feature(ev, "programme"):
        nice.append((bool(sched), "The programme", 4))
    if catalog.has_feature(ev, "menu"):
        nice.append((bool(items), "The menu", 5))
    missing_needed = [x for x in needed if not x[0]]

    def li(done, label, n, must=False):
        icon_ = i("check") if done else i("alert" if must else "plus")
        text = esc(label) if done else f'<a class="text-link" href="{step_url(ev, n)}">{esc(label)}</a>'
        return f'<li class="{"is-done" if done else ""}">{icon_}<span>{text}{"" if done or not must else " <b>(needed)</b>"}</span></li>'
    checklist = (f'<details class="box"{" open" if missing_needed else ""} style="padding:14px 16px"><summary style="cursor:pointer;font-weight:500">'
                 f'{"Two things are needed before you pay" if len(missing_needed) == 2 else "One thing is needed before you pay" if missing_needed else "Ready to go. Optional extras you can still add"}</summary>'
                 f'<ul class="checklist" style="margin-top:12px">{"".join(li(d, l, n, True) for d, l, n in needed)}{"".join(li(d, l, n) for d, l, n in nice)}</ul>'
                 f'<p class="tiny muted" style="margin-top:8px">Everything except the first two can be added after your website is live.</p></details>')

    cards = []
    for p in catalog.packages():
        is_paid = paid and p["code"] == paid["code"]
        if paid and p["rank"] < paid["rank"]:
            continue
        price = p["price_cents"] - (paid["price_cents"] if paid and not is_paid else 0)
        bullets = db.loads(p["bullets"], [])
        limits = db.loads(p["limits"], {})
        bl = "".join(f'<li>{i("check")}<span>{esc(b)}</span></li>' for b in bullets)
        lim = "".join(f'<div><span>{esc(label)}</span><b>{esc(limits.get(k, 0)) or "—"}</b></div>' for k, label in catalog.LIMIT_LABELS.items())
        p_gaps = [] if is_paid else events.package_gaps(ev, p["code"])
        gap_html = (f'<p class="small price__gap">{i("lock")} Won\'t show {esc(_join(p_gaps))}.</p>' if p_gaps else "")
        if is_paid:
            action = '<span class="pill pill--paid">Your current package</span>'
        else:
            label = f"Upgrade for {catalog.money(price)}" if paid else f"Pay {catalog.money(price)}"
            action = (f'<button class="btn {"btn--primary" if p["highlight"] else "btn--secondary"} btn--block" type="submit" name="package" value="{esc(p["code"])}"'
                      f'{" disabled" if missing_needed else ""}>{label}</button>')
        cards.append(f"""<article class="price{' price--highlight' if p['highlight'] and not paid else ''}">{'<span class="price__badge">Recommended</span>' if p['highlight'] and not paid else ''}
<div><h3>{esc(p['name'])}</h3><p class="muted small" style="margin-top:6px">{esc(p['tagline'])}</p></div>
<div class="price__amount">{catalog.money(p['price_cents'])}<small>{"paid" if is_paid else ("VAT incl." if config.VAT_REGISTERED else "once-off")}</small></div>{action}<ul>{bl}</ul>
<details><summary class="small" style="cursor:pointer">Limits</summary><div class="price__limits" style="margin-top:8px">{lim}</div></details>{gap_html}</article>""")
    sandbox = ""
    if payments.gateway().mode == "sandbox":
        sandbox = (f'<div class="notice notice--warn">{i("info")}<span><b>Test mode.</b> Payments use the {esc(payments.gateway().label)}; '
                   f'no real money moves and test payments are marked as sandbox everywhere.</span></div>')
    status = ""
    if paid:
        status = f'<div class="notice notice--success">{i("check")}<span>Paid: <b>{esc(paid["name"])}</b>. Your website is {"live" if events.is_live(ev) else "ready to publish from Settings"}.</span></div>'
    elif pending:
        status = (f'<div class="notice">{i("clock")}<span>A payment for {catalog.money(pending["amount_cents"])} was started and hasn\'t been confirmed yet. '
                  f'<a class="text-link" href="/dashboard/events/{ev["uid"]}/payment/{pending["uid"]}">Check its status</a> or start again below.</span></div>')
    share = (f'<div class="box" style="display:grid;gap:10px"><h3 style="font-size:1.0625rem">Show someone before you pay</h3>'
             f'<p class="small muted">Send this link to your partner or family for their opinion. They see your website as it is now, marked “Preview: not published”, with replies switched off. Guests can only use it once you\'ve paid.</p>'
             f'<div class="row" style="gap:8px;flex-wrap:wrap"><input class="input input--sm mono" style="flex:1;min-width:0" readonly value="{esc(events.draft_url(ev))}" aria-label="Draft preview link">'
             f'<button class="btn btn--secondary btn--sm" type="button" data-copy="{esc(events.draft_url(ev))}" data-copied="Draft link copied">{i("copy")} Copy link</button>'
             f'<a class="btn btn--ghost btn--sm" href="https://wa.me/?text={esc(_q("Have a look at our event website draft: " + events.draft_url(ev)))}" target="_blank" rel="noopener">{i("chat")} WhatsApp</a></div></div>')

    def sec(n, title, rows):
        dl = "".join(f"<dt>{esc(k)}</dt><dd>{v if v else '<span class=muted>Not added</span>'}</dd>" for k, v in rows)
        return (f'<div class="review-section"><div class="review-section__head"><h3>{esc(title)}</h3>'
                f'<a class="btn btn--sm btn--ghost" href="{step_url(ev, n)}">{i("edit")} Edit</a></div><dl class="dl">{dl}</dl></div>')
    review = "".join([
        sec(1, "Details", [("Names", esc(ev["hosts"])), ("Occasion", esc(catalog.category_name(ev["category"]))),
                           ("Date", esc(forms.fmt_date(ev["event_date"]))), ("Time", esc(" – ".join(x for x in (ev["start_time"], ev["end_time"]) if x))),
                           ("Venue", esc(venue.get("name"))), ("Address", esc(venue.get("address")))]),
        sec(2, "Design", [("Template", esc(t_row["name"] if t_row else ev["template"])), ("Photos", str(len(events.uploads(ev["id"]))) + " uploaded"),
                          ("Welcome", esc(wording.get("welcome")))]),
        sec(3, "Guests", [("Guest list", f"{n_guests} guests" if n_guests else ""), ("RSVP deadline", esc(forms.fmt_date(gs.get("rsvp_deadline")))),
                          ("Children", "Welcome" if gs.get("children_allowed") else "Adults only")]),
        sec(4, "Programme", [("Days", esc(", ".join(fn["name"] for fn in funcs)) if funcs else "One day"), ("Programme items", str(len(sched)) if sched else "")]),
        sec(5, "Food and drinks", [("Menu items", str(items) if items else ""), ("Dietary options", esc(", ".join(info.get("dietary_options", []))))]),
        sec(6, "Seating", [("Tables", f"{len(tables)} tables, {sum(t['capacity'] for t in tables)} seats" if tables else "Planned after RSVPs")]),
        sec(7, "Extras", [("Dress code", esc(info.get("dress_code"))), ("Registry", str(len(info.get("registry", []))) if info.get("registry") else ""),
                          ("Gallery", str(len(events.uploads(ev["id"], "gallery"))) + " photos" if events.uploads(ev["id"], "gallery") else "")]),
    ])
    pay_note = ("Finish the details marked “needed” above, then pay." if missing_needed else
                "Secure payment by card or instant EFT. Your website goes live as soon as the payment is confirmed, and you get a receipt by email.")
    inner = f"""{status}{sandbox}{checklist}
<form method="post" action="/dashboard/events/{ev['uid']}/checkout" class="form" novalidate>{csrf(req)}<input type="hidden" name="accept" value="1">
<div class="price-grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">{"".join(cards)}</div>
<p class="small muted">{pay_note} By paying, you accept the <a class="text-link" href="/terms" target="_blank">terms of service</a> and <a class="text-link" href="/refunds" target="_blank">refund policy</a>.</p></form>
{share}
<details class="box" style="padding:14px 16px"><summary style="cursor:pointer;font-weight:500">See everything you've entered</summary><div style="display:grid;gap:16px;margin-top:16px">
<div class="notice">{i("link")}<span>Your website address will be <b class="mono">{esc(events.public_url(ev))}</b>. Change it in Settings.</span></div>
<div class="preview-frame" data-preview data-device="desktop"><div class="preview-frame__bar"><span class="preview-frame__url">/events/{esc(ev['slug'])}</span>
<div class="seg"><button type="button" data-device="desktop" aria-pressed="true">Desktop</button><button type="button" data-device="mobile" aria-pressed="false">Mobile</button></div></div>
<div class="preview-frame__stage"><iframe loading="lazy" src="/dashboard/events/{ev['uid']}/preview" title="Preview of your event website"></iframe></div></div>
{review}</div></details>
<p class="small muted" style="margin-top:14px">Questions before you pay, or rather have us finish the set-up? <a class="text-link" href="/help-me-set-up">Ask us to help</a>.</p>"""
    return wizard_frame(req, ev, 8, inner)


STEP_HANDLERS = {1: step_details, 2: step_design, 3: step_guests, 4: step_programme, 5: step_food, 6: step_seating, 7: step_extras,
                 8: step_review_pay}
