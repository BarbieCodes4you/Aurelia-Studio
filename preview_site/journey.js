/* Aurelia customer journey for the shareable site: choose occasion and template, the 10-step set-up,
   live preview, package choice and booking request. Runs entirely in the visitor's browser; drafts are
   kept in localStorage. Mirrors the fields and rules of app/views/wizard.py.
   Exposes window.AureliaJourney.route(hashId). */
(function () {
  "use strict";
  var D = window.AURELIA_DATA, R = window.AureliaRender, esc = R.esc;
  var KEY = "aurelia-journey-v1";
  var root = function () { return document.getElementById("journey-root"); };
  var state = load();
  var currentHash = "";
  var previewTimer = 0;

  // --- storage ---------------------------------------------------------------------------------
  function load() {
    var s = { events: {}, order: [], current: null };
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) s = Object.assign(s, JSON.parse(raw));
      s.order.forEach(function (id) {
        var img = localStorage.getItem(KEY + "-img-" + id);
        if (img && s.events[id]) s.events[id].images = JSON.parse(img);
      });
    } catch (e) { /* storage unavailable: keep this visit in memory */ }
    return s;
  }
  var warnedImages = false;
  function save() {
    try {
      var copy = { events: {}, order: state.order, current: state.current };
      state.order.forEach(function (id) {
        var ev = state.events[id];
        if (!ev) return;
        copy.events[id] = Object.assign({}, ev, { images: undefined });
      });
      localStorage.setItem(KEY, JSON.stringify(copy));
      var ev = cur();
      if (ev) {
        try { localStorage.setItem(KEY + "-img-" + ev.id, JSON.stringify(ev.images || {})); }
        catch (e) {
          if (!warnedImages) { toast("Your photos are too large to keep after you close this page. They stay for this visit.", "error"); warnedImages = true; }
        }
      }
    } catch (e) { /* private mode: the draft lives for this visit */ }
  }
  function cur() { return state.current ? state.events[state.current] : null; }
  function toast(msg, kind) { if (window.Aurelia && Aurelia.toast) Aurelia.toast(msg, kind); }
  function uid(prefix) { return (prefix || "") + Math.random().toString(36).slice(2, 8); }

  // --- catalogue helpers -----------------------------------------------------------------------
  function cat(slug) { return D.categories.filter(function (c) { return c.slug === slug; })[0]; }
  function tpl(slug) { return D.templates.filter(function (t) { return t.slug === slug; })[0]; }
  function pkg(code) { return D.packages.filter(function (p) { return p.code === code; })[0]; }
  function money(c) { return "R" + Math.round(c / 100).toLocaleString("en-US"); }
  function groupOf(ev) { var c = cat(ev.category); return c ? c.group : "weddings"; }
  function feature(ev, key) { return R.hasFeature(ev, key); }
  function limit(ev, key) { var p = pkg(ev.selected_package || "premium"); return p ? (p.limits[key] || 0) : 0; }
  function icon(n) { return '<i class="i i--' + n + '" aria-hidden="true"></i>'; }
  function todayIso() { var d = new Date(); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }

  // --- form helpers (same markup as app/views/forms.py) -------------------------------------------
  function attrs(a) { return Object.keys(a || {}).map(function (k) { return a[k] === true ? " " + k : (a[k] === false || a[k] == null ? "" : " " + k + '="' + esc(a[k]) + '"'); }).join(""); }
  function field(name, label, value, o) {
    o = o || {};
    var id = "f-" + name, req = o.required ? ' <span class="req" aria-hidden="true">*</span>' : "";
    var ctrl = o.type === "textarea"
      ? '<textarea class="textarea" id="' + id + '" name="' + name + '"' + attrs(o.attrs) + ">" + esc(value) + "</textarea>"
      : '<input class="input" id="' + id + '" name="' + name + '" type="' + (o.type || "text") + '" value="' + esc(value == null ? "" : value) + '"' + attrs(o.attrs) + ">";
    return '<div class="field" data-field="' + name + '"><label for="' + id + '">' + esc(label) + req + "</label>" + ctrl +
      (o.hint ? '<span class="hint">' + o.hint + "</span>" : "") + "</div>";
  }
  function select(name, label, options, value, o) {
    o = o || {};
    var opts = options.map(function (x) { var v = Array.isArray(x) ? x[0] : x, t = Array.isArray(x) ? x[1] : x;
      return '<option value="' + esc(v) + '"' + (String(v) === String(value == null ? "" : value) ? " selected" : "") + ">" + esc(t) + "</option>"; }).join("");
    return '<div class="field" data-field="' + name + '"><label for="f-' + name + '">' + esc(label) + (o.required ? ' <span class="req" aria-hidden="true">*</span>' : "") +
      '</label><select class="select" id="f-' + name + '" name="' + name + '">' + opts + "</select>" + (o.hint ? '<span class="hint">' + o.hint + "</span>" : "") + "</div>";
  }
  function check(name, label, checked, o) {
    o = o || {};
    return '<label class="check"><input type="' + (o.type || "checkbox") + '" name="' + name + '" value="' + esc(o.value || "1") + '"' + (checked ? " checked" : "") + attrs(o.attrs) +
      "><span>" + label + (o.hint ? '<span class="hint" style="display:block">' + o.hint + "</span>" : "") + "</span></label>";
  }
  function color(name, label, value) {
    return '<div class="field"><label for="f-' + name + '">' + esc(label) + '</label><div class="color-field"><input type="color" id="f-' + name + '" value="' + esc(value) + '" data-sync="' + name + '" aria-label="' + esc(label) + '">' +
      '<input type="text" name="' + name + '" value="' + esc(value) + '" maxlength="7" aria-label="' + esc(label) + ' hex value"></div></div>';
  }
  function mini(name, value, type, ph, label) {
    return '<div class="field"><label class="tiny muted" for="' + name + '">' + esc(label) + '</label><input class="input input--sm" id="' + name + '" name="' + name + '" type="' + (type || "text") +
      '" value="' + esc(value == null ? "" : value) + '" placeholder="' + esc(ph || "") + '"></div>';
  }
  function miniSel(name, options, value, label) {
    return '<div class="field"><label class="tiny muted" for="' + name + '">' + esc(label) + '</label><select class="select select--sm" id="' + name + '" name="' + name + '">' +
      options.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(value == null ? "" : value) ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("") + "</select></div>";
  }
  function rm() { return '<button class="btn btn--ghost btn--icon" type="button" data-remove-row aria-label="Remove row">' + icon("trash") + "</button>"; }
  function repeat(prefix, rows, tplFn, addLabel, max) {
    return '<div class="repeat" data-repeat="' + prefix + '" data-max="' + (max || 200) + '"><div class="repeat" data-rows>' + rows.join("") + "</div>" +
      '<div><button class="btn btn--sm btn--secondary" type="button" data-add-row>' + icon("plus") + " " + esc(addLabel) + "</button></div></div>";
  }
  function readRows(fd, prefix, fields) {
    var idx = {}, re = new RegExp("^" + prefix + "-(\\d+)-");
    fd.forEach(function (v, k) { var m = re.exec(k); if (m) idx[m[1]] = 1; });
    return Object.keys(idx).map(Number).sort(function (a, b) { return a - b; }).map(function (i) {
      var row = {};
      fields.forEach(function (f) { row[f] = (fd.get(prefix + "-" + i + "-" + f) || "").toString().trim(); });
      return row;
    }).filter(function (r) { return Object.keys(r).some(function (k) { return k !== "id" && r[k]; }); });
  }
  function featureNote(ev, key, what) {
    if (feature(ev, key)) return "";
    var need = D.packages.filter(function (p) { return p.features.indexOf(key) > -1; })[0];
    return '<div class="notice notice--warn">' + icon("lock") + "<span>" + esc(what) + " shows on your website with the " + esc(need ? need.name : "a higher package") +
      ". You can fill it in now and choose your package in step 10.</span></div>";
  }

  // --- new event model --------------------------------------------------------------------------
  function newEvent(category, template, name) {
    var feats = (cat(category) || {}).features || [];
    var gs = { estimated: "", categories: ["Family", "Friends"], family_groups: [], children_allowed: false, max_children: 0,
      plus_one_policy: "per_guest", plus_ones_default: 0, rsvp_deadline: "" };
    if (feats.indexOf("family_sides") > -1) gs.sides = ["Bride's family", "Groom's family"];
    var id = uid("e");
    return { id: id, created: new Date().toISOString(), updated: new Date().toISOString(), category: category, template: template, name: name,
      hosts: "", description: "", event_date: "", start_time: "", end_time: "", contact: { name: "", email: "", phone: "" },
      venue: {}, design: {}, images: { gallery: [] }, guest_settings: gs, functions: [], schedule: [], menu: { name: "Reception menu", items: [] },
      info: { dietary_options: ["Vegetarian", "Vegan", "Halal", "Gluten-free", "Nut allergy"] }, tables: { count: "", capacity: 10, shape: "round", names: [] },
      selected_package: "premium", wizard_done: [], booking: null };
  }

  // --- views: create ------------------------------------------------------------------------------
  function viewCreate(param) {
    var pre = { category: "", template: "", group: "", pkg: "" };
    var m = /^create-(tpl|cat|grp|pkg)-(.+)$/.exec(param || "");
    if (m) pre[{ tpl: "template", cat: "category", grp: "group", pkg: "pkg" }[m[1]]] = m[2];
    if (pre.template && !pre.group) pre.group = (tpl(pre.template) || { groups: ["weddings"] }).groups[0];
    var groups = Object.keys(D.groups).map(function (g) {
      var opts = D.categories.filter(function (c) { return c.group === g; }).map(function (c) {
        return '<label class="choice"><input type="radio" name="category" value="' + c.slug + '" data-group="' + g + '"' + (c.slug === pre.category ? " checked" : "") + "><span>" + esc(c.name) +
          "<small>" + esc(c.description) + "</small></span></label>"; }).join("");
      return '<fieldset style="margin-bottom:22px"><legend>' + esc(D.groups[g].name) + '</legend><div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">' + opts + "</div></fieldset>";
    }).join("");
    var tpls = D.templates.map(function (t) {
      var pal = D.themes.designs[t.design].palettes[0][2];
      var sw = ["bg", "text", "accent", "accent2"].map(function (k) { return '<i style="background:' + pal[k] + '"></i>'; }).join("");
      return '<label class="choice" data-groups="' + t.groups.join(" ") + '"><input type="radio" name="template" value="' + t.slug + '"' + (t.slug === pre.template ? " checked" : "") + ">" +
        '<span><span class="row row--between" style="gap:8px"><b>' + esc(t.name) + '</b><span class="palette-swatches">' + sw + "</span></span><small>" + esc(t.direction) + "</small></span></label>";
    }).join("");
    root().innerHTML = '<section class="page-hero"><div class="grid-texture"></div><div class="container"><nav class="breadcrumbs" aria-label="Breadcrumb"><a href="#home">Home</a><span aria-hidden="true">/</span><span>Create your event</span></nav>' +
      '<h1>Let\'s create your <span class="serif grad">event</span></h1><p class="lead">Pick the occasion and a starting template. Everything is saved in this browser as you go; nothing is charged until you choose a package at the end.</p>' +
      (state.order.length ? '<p style="margin-top:14px"><a class="arrow-link" href="#my-events"><span>Continue an event you started</span>' + icon("arrow") + "</a></p>" : "") + "</div></section>" +
      '<section class="section"><div class="container"><form class="form" data-create data-no-busy novalidate><input type="hidden" name="pkg" value="' + esc(pre.pkg) + '"><div data-errors></div>' +
      '<div class="box"><h2 style="font-size:1.25rem;margin-bottom:16px">1. What are you celebrating?</h2>' + groups + "</div>" +
      '<div class="box"><h2 style="font-size:1.25rem;margin-bottom:6px">2. Choose a starting template</h2><p class="muted small" style="margin-bottom:16px">Templates that suit your occasion are shown first. You can switch any time in the design step. <a class="text-link" href="#templates">Preview the templates</a></p>' +
      '<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(230px,1fr))" data-tpl-grid>' + tpls + "</div></div>" +
      '<div class="box"><h2 style="font-size:1.25rem;margin-bottom:16px">3. Name it</h2>' + field("name", "Event name", "", { required: true, hint: "Just for you, e.g. “Our wedding” or “Amahle's baby shower”. Guests see the names you add next." }) + "</div>" +
      '<div class="btn-row"><button class="btn btn--primary btn--lg" type="submit">Start setting up ' + icon("arrow") + "</button></div></form></div></section>";
    var form = root().querySelector("[data-create]");
    function sync() {
      var c = form.querySelector("input[name=category]:checked"), g = c ? c.getAttribute("data-group") : pre.group;
      form.querySelectorAll("[data-tpl-grid] .choice").forEach(function (l) {
        var ok = !g || l.getAttribute("data-groups").split(" ").indexOf(g) > -1;
        l.style.order = ok ? 0 : 1; l.style.opacity = ok ? 1 : 0.55;
      });
    }
    form.addEventListener("change", sync); sync();
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData(form), errs = {};
      if (!fd.get("category")) errs.category = "Choose the type of event.";
      if (!fd.get("template")) errs.template = "Choose a template. You can change it later.";
      if (!(fd.get("name") || "").trim()) errs.name = "Event name is required.";
      if (showErrors(form, errs)) return;
      var ev = newEvent(fd.get("category"), fd.get("template"), fd.get("name").trim());
      if (pkg(fd.get("pkg"))) ev.selected_package = fd.get("pkg");
      state.events[ev.id] = ev; state.order.unshift(ev.id); state.current = ev.id; save();
      toast("Your event is saved in this browser as a private draft. Let's add the details.");
      location.hash = "#setup-1";
    });
  }

  function showErrors(form, errs) {
    form.querySelectorAll(".field.has-error").forEach(function (f) { f.classList.remove("has-error"); var e = f.querySelector(".field-error"); if (e) e.remove(); });
    var box = form.querySelector("[data-errors]"), keys = Object.keys(errs);
    if (!keys.length) { if (box) box.innerHTML = ""; return false; }
    keys.forEach(function (k) {
      var f = form.querySelector('[data-field="' + k + '"]');
      if (f) { f.classList.add("has-error"); f.insertAdjacentHTML("beforeend", '<span class="field-error">' + esc(errs[k]) + "</span>"); }
    });
    if (box) {
      box.innerHTML = '<div class="form-errors" role="alert" tabindex="-1"><b>Please fix ' + (keys.length === 1 ? "this item" : "these " + keys.length + " items") + ":</b><ul>" +
        keys.map(function (k) { return "<li>" + esc(errs[k]) + "</li>"; }).join("") + "</ul></div>";
      box.firstChild.focus();
      box.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return true;
  }

  // --- views: my events ---------------------------------------------------------------------------
  function viewMyEvents() {
    var cards = state.order.map(function (id) {
      var ev = state.events[id]; if (!ev) return "";
      var pct = Math.round(100 * ev.wizard_done.filter(function (n) { return n <= 9; }).length / 9);
      var c = cat(ev.category), status = ev.booking ? '<span class="pill pill--ok">Booking requested</span>' : '<span class="pill pill--draft">Draft</span>';
      return '<article class="box event-card"><div class="event-card__top"><div><h2 style="font-size:1.25rem">' + esc(ev.name) + '</h2><div class="event-card__meta"><span>' + esc(c ? c.name : "") + "</span>" +
        (ev.event_date ? "<span>" + esc(R.fmtDate(ev.event_date, false)) + "</span>" : "") + "<span>" + esc((tpl(ev.template) || {}).name || "") + " template</span></div></div>" + status + "</div>" +
        '<div class="progress"><span style="width:' + pct + '%"></span></div><div class="btn-row">' +
        '<button class="btn btn--primary btn--sm" type="button" data-open="' + id + '" data-to="' + (ev.booking ? "booked" : "setup-" + Math.min(10, (Math.max.apply(null, [0].concat(ev.wizard_done)) + 1))) + '">' + (ev.booking ? "View booking" : "Continue set-up") + "</button>" +
        '<button class="btn btn--secondary btn--sm" type="button" data-open="' + id + '" data-to="preview-event">' + icon("eye") + " Preview website</button>" +
        '<button class="btn btn--ghost btn--sm" type="button" data-delete="' + id + '">' + icon("trash") + " Delete</button></div></article>";
    }).join("");
    root().innerHTML = '<section class="page-hero"><div class="grid-texture"></div><div class="container"><h1>My <span class="serif grad">events</span></h1>' +
      '<p class="lead">Events you\'ve started are saved in this browser on this device. Finish set-up and request your booking when you\'re ready.</p></div></section>' +
      '<section class="section"><div class="container" style="display:grid;gap:var(--gap)">' + (cards ||
        '<div class="empty"><span class="icon-tile">' + icon("calendar") + '</span><h2 style="font-size:1.25rem">No events yet</h2><p>Start with the occasion and a template. It takes a few minutes, and you can stop and come back.</p><a class="btn btn--primary" href="#create">Create your event</a></div>') +
      (cards ? '<div><a class="btn btn--primary" href="#create">' + icon("plus") + " Create another event</a></div>" : "") + "</div></section>";
  }

  // --- wizard frame -------------------------------------------------------------------------------
  var STEPS = [[1, "Event details", "calendar"], [2, "Venue", "pin"], [3, "Design", "palette"], [4, "Guests", "users"], [5, "Programme", "list"],
    [6, "Food and drinks", "dish"], [7, "Seating", "seat"], [8, "Extras", "gift"], [9, "Review", "eye"], [10, "Package", "card"]];
  var INTROS = { 1: "The essentials guests see first, and how we reach you.", 2: "Where it's happening and how to get there.", 3: "Make the template yours. The preview updates as you go.",
    4: "Who's invited and how replies work. You'll add the guest list itself after publishing.", 5: "Ceremonies, receptions and the running order.", 6: "Menus, meal choices and dietary needs.",
    7: "Start your seating plan. You'll seat guests once RSVPs arrive.", 8: "Dress code, gifts, contacts, accommodation and photos.", 9: "Check everything before you choose a package.",
    10: "Choose your package and request your booking." };

  function frame(ev, n, inner, opts) {
    opts = opts || {};
    var done = ev.wizard_done;
    var stepper = STEPS.map(function (s) {
      return '<li><a href="#setup-' + s[0] + '" class="' + (done.indexOf(s[0]) > -1 ? "is-done" : "") + '"' + (s[0] === n ? ' aria-current="step"' : "") + '><span class="n">' +
        (done.indexOf(s[0]) > -1 && s[0] !== n ? "✓" : s[0]) + "</span>" + esc(s[1]) + "</a></li>"; }).join("");
    var pct = Math.round(100 * done.filter(function (x) { return x <= 10; }).length / 10);
    var nav = n < 10 ? '<div class="wizard-actions">' + (n > 1 ? '<a class="btn btn--ghost" href="#setup-' + (n - 1) + '">' + icon("arrow-left") + " Back</a>" : "<span></span>") +
      '<div class="btn-row"><button class="btn btn--secondary" type="submit" name="nav" value="stay">Save draft</button><button class="btn btn--primary" type="submit" name="nav" value="next">' +
      esc(opts.nextLabel || "Save and continue") + " " + icon("arrow") + "</button></div></div>" : "";
    var card = '<div class="glass glass--strong wizard-card"><div class="row" style="gap:14px;margin-bottom:6px"><span class="icon-tile icon-tile--soft">' + icon(STEPS[n - 1][2]) +
      '</span><div><span class="tiny muted mono">STEP ' + n + "</span><h2>" + esc(STEPS[n - 1][1]) + '</h2></div></div><p class="lead">' + INTROS[n] + "</p><hr>" +
      '<form class="form" data-step="' + n + '" data-no-busy novalidate><div data-errors></div>' + inner + nav + "</form></div>";
    var preview = opts.preview ? '<div class="wizard-split">' + card + previewFrame() + "</div>" : card;
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 28px)"><div class="container">' +
      '<div class="page-head"><div><h1>Set up ' + esc(ev.name) + "</h1><p>Private draft, saved in this browser as you go. Nothing is shared until you publish.</p></div>" +
      '<div class="btn-row"><a class="btn btn--ghost btn--sm" href="#my-events">My events</a><a class="btn btn--secondary btn--sm" href="#preview-event">' + icon("eye") + " Full preview</a></div></div>" +
      '<div class="wizard-progress"><span>' + pct + '% complete</span><div class="progress"><span style="width:' + pct + '%"></span></div><span class="mono">Step ' + n + ' of 10</span></div>' +
      '<div class="wizard"><nav aria-label="Set-up steps"><ol class="stepper">' + stepper + "</ol></nav><div>" + preview + "</div></div></div></section>";
    refreshPreview(true);
  }
  function previewFrame(height) {
    return '<div class="preview-frame" data-jpreview data-device="desktop"><div class="preview-frame__bar"><span class="preview-frame__url">aurelia.events/' + esc(slugOf(cur())) + "</span>" +
      '<div class="seg" role="group" aria-label="Device"><button type="button" data-device="desktop" aria-pressed="true">Desktop</button><button type="button" data-device="mobile" aria-pressed="false">Mobile</button></div></div>' +
      '<div class="preview-frame__stage" style="height:' + (height || 680) + 'px"><iframe title="Live preview of your event website" data-live></iframe></div></div>';
  }
  function slugOf(ev) {
    var s = ((ev && (ev.hosts || ev.name)) || "your-event").toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return s.slice(0, 50) || "your-event";
  }
  function refreshPreview(now) {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      var f = document.querySelector("#journey-root iframe[data-live]");
      var ev = cur();
      if (f && ev) f.srcdoc = R.render(ev, "preview");
    }, now ? 0 : 350);
  }

  // --- step 1 ---------------------------------------------------------------------------------------
  var HOST = D.host_label;
  function step1(ev) {
    var g = groupOf(ev), hl = HOST[g] || ["Hosts", ""];
    var cats = D.categories.map(function (c) { return [c.slug, D.groups[c.group].name + ": " + c.name]; });
    return '<fieldset><legend>About you</legend><div class="form-row form-row--3">' + field("contact_name", "Your name", ev.contact.name, { required: true, attrs: { autocomplete: "name" } }) +
      field("contact_email", "Your email", ev.contact.email, { type: "email", required: true, attrs: { autocomplete: "email" }, hint: "Your booking confirmation and payment link go here." }) +
      field("contact_phone", "Your mobile (optional)", ev.contact.phone, { type: "tel", attrs: { autocomplete: "tel" } }) + "</div></fieldset>" +
      '<div class="form-row form-row--2">' + field("name", "Event name", ev.name, { required: true, hint: "For you and your emails." }) + select("category", "Type of event", cats, ev.category, { required: true }) + "</div>" +
      field("hosts", hl[0], ev.hosts, { required: true, attrs: { placeholder: hl[1] }, hint: "Shown large on your website and used for your link." }) +
      field("description", "A short welcome or description", ev.description, { type: "textarea", hint: "Optional. One or two sentences guests read first." }) +
      '<div class="form-row form-row--3">' + field("event_date", "Date", ev.event_date, { type: "date", required: true, attrs: { min: todayIso() } }) +
      field("start_time", "Starts", ev.start_time, { type: "time" }) + field("end_time", "Ends", ev.end_time, { type: "time" }) + "</div>" +
      check("ends_next_day", "Ends after midnight", !!ev.ends_next_day) + '<p class="tiny muted">Several ceremonies or days? Add each one in the Programme step.</p>';
  }
  function collect1(ev, fd) {
    ev.contact = { name: val(fd, "contact_name"), email: val(fd, "contact_email").toLowerCase(), phone: val(fd, "contact_phone") };
    ev.name = val(fd, "name"); ev.category = val(fd, "category") || ev.category; ev.hosts = val(fd, "hosts"); ev.description = val(fd, "description");
    ev.event_date = val(fd, "event_date"); ev.start_time = val(fd, "start_time"); ev.end_time = val(fd, "end_time"); ev.ends_next_day = !!fd.get("ends_next_day");
  }
  function validate1(ev) {
    var e = {};
    if (!ev.contact.name) e.contact_name = "Your name is required.";
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(ev.contact.email)) e.contact_email = "Enter a valid email address, like name@example.com.";
    if (ev.contact.phone && !/^\+?[0-9 ()-]{7,20}$/.test(ev.contact.phone)) e.contact_phone = "Enter a phone number using digits, spaces and an optional +.";
    if (!ev.name) e.name = "Event name is required.";
    if (!ev.hosts) e.hosts = (HOST[groupOf(ev)] || ["Hosts"])[0] + " is required.";
    if (!ev.event_date) e.event_date = "Date is required.";
    else if (ev.event_date < todayIso()) e.event_date = "Date can't be in the past.";
    if (ev.start_time && ev.end_time && ev.end_time <= ev.start_time && !ev.ends_next_day) e.end_time = "End time must be after the start time (tick “ends after midnight” if it does).";
    return e;
  }
  function val(fd, k) { return (fd.get(k) || "").toString().trim(); }

  // --- step 2 ---------------------------------------------------------------------------------------
  function step2(ev) {
    var v = ev.venue;
    return '<div class="form-row form-row--2">' + field("venue_name", "Venue name", v.name, { required: true }) + field("address", "Street address", v.address, { required: true, hint: "Guests get a Google Maps link built from this." }) + "</div>" +
      field("map_url", "Google Maps link (optional)", v.map_url, { type: "url", hint: "Paste a share link from Google Maps for an exact pin, e.g. a farm gate." }) +
      field("parking", "Parking", v.parking, { type: "textarea", attrs: { rows: 3 }, hint: "Where to park, security, valet, drop-off." }) +
      field("directions", "Directions", v.directions, { type: "textarea", attrs: { rows: 3 }, hint: "Landmarks, gate codes, the last turn GPS gets wrong." }) +
      field("accommodation", "Accommodation nearby", v.accommodation, { type: "textarea", attrs: { rows: 3 }, hint: "Optional. Add specific places with links in the Extras step." });
  }
  function collect2(ev, fd) {
    var url = val(fd, "map_url");
    if (url && !/^https?:\/\//i.test(url)) url = "https://" + url;
    ev.venue = { name: val(fd, "venue_name"), address: val(fd, "address"), map_url: url, parking: val(fd, "parking"), directions: val(fd, "directions"), accommodation: val(fd, "accommodation") };
  }
  function validate2(ev) {
    var e = {};
    if (!ev.venue.name) e.venue_name = "Venue name is required.";
    if (!ev.venue.address) e.address = "Address is required.";
    if (ev.venue.map_url && !/^https?:\/\/[^\s<>"]+\.[^\s<>"]+/i.test(ev.venue.map_url)) e.map_url = "Map link must be a web address.";
    return e;
  }

  // --- step 3 ---------------------------------------------------------------------------------------
  function step3(ev) {
    var g = groupOf(ev), t = tpl(ev.template) || D.templates[0], dsg = D.themes.designs[t.design], res = R.resolve(t.design, ev.design);
    var tplOpts = D.templates.slice().sort(function (a, b) { return (a.groups.indexOf(g) > -1 ? 0 : 1) - (b.groups.indexOf(g) > -1 ? 0 : 1); }).map(function (x) {
      var p = D.themes.designs[x.design].palettes[0][2];
      return '<label class="choice"><input type="radio" name="template" value="' + x.slug + '"' + (x.slug === ev.template ? " checked" : "") + '><span><span class="row row--between"><b>' + esc(x.name) +
        '</b><span class="palette-swatches">' + ["bg", "text", "accent", "accent2"].map(function (k) { return '<i style="background:' + p[k] + '"></i>'; }).join("") + "</span></span><small>" + esc(x.direction) + "</small></span></label>";
    }).join("");
    var pal = dsg.palettes.map(function (pp) {
      return '<label class="choice"><input type="radio" name="palette" value="' + pp[0] + '"' + (pp[0] === res.palette ? " checked" : "") + '><span><span class="palette-swatches">' +
        ["bg", "text", "accent", "accent2"].map(function (k) { return '<i style="background:' + pp[2][k] + '"></i>'; }).join("") + "</span>" + esc(pp[1]) + "</span></label>"; }).join("");
    var fonts = dsg.fonts.concat(Object.keys(D.themes.font_pairs).filter(function (k) { return dsg.fonts.indexOf(k) < 0; }))
      .map(function (k) { var f = D.themes.font_pairs[k]; return [k, f[0] + " (" + f[1] + " + " + f[2] + ")"]; });
    var bgs = dsg.backgrounds.map(function (k) { return [k, D.themes.backgrounds[k]]; });
    var adv = feature(ev, "advanced_design"), custom = !!(ev.design.colors);
    var w = ev.design.wording || {};
    function upl(kind, label, hint) {
      var cur = ev.images[kind];
      return '<div class="field"><span class="label">' + esc(label) + "</span>" + (cur ? '<div class="row" style="gap:10px"><img src="' + cur + '" alt="" style="width:72px;height:54px;object-fit:cover;border-radius:8px">' +
        '<button class="btn btn--sm btn--ghost" type="button" data-remove-image="' + kind + '">' + icon("trash") + " Remove</button></div>" : "") +
        '<label class="file-drop" style="position:relative">' + icon("upload") + "<span>" + (cur ? "Replace" : "Upload") + " " + esc(label.toLowerCase()) + '</span><span class="hint">' + esc(hint) + "</span>" +
        '<input type="file" data-image="' + kind + '" accept="image/jpeg,image/png,image/webp,image/gif"></label></div>';
    }
    return "<fieldset><legend>Template</legend>" + '<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">' + tplOpts + "</div>" +
      '<p class="hint" style="margin-top:8px">Switching template resets colours and fonts to that template\'s defaults. Your content stays.</p></fieldset>' +
      '<fieldset><legend>Colour palette</legend><div class="choice-grid">' + pal + "</div></fieldset>" +
      '<div class="box" style="padding:16px">' + check("custom_colors", "Use my own colours" + (adv ? "" : " <span class='pill pill--gold pill--plain'>Premium</span>"), custom, { attrs: { disabled: !adv, "data-reveals": "#custom-colors" } }) +
      '<div id="custom-colors" class="form-row form-row--4" style="margin-top:12px"' + (custom ? "" : " hidden") + ">" +
      [["bg", "Background"], ["text", "Text"], ["accent", "Accent"], ["accent2", "Second accent"]].map(function (c) { return color("color_" + c[0], c[1], res.colors[c[0]]); }).join("") + "</div></div>" +
      '<div class="form-row form-row--2">' + select("font_pair", "Typography", fonts, res.font_pair) + select("background", "Background", bgs, res.background) + "</div>" +
      '<div class="form-row form-row--3">' + upl("hero", "Main photo", "Landscape works best.") + upl("background", "Background image", "Used when Background is set to your photo.") + upl("logo", "Logo or crest", "PNG with transparency works best.") + "</div>" +
      field("monogram", "Monogram or initials", ev.design.monogram || "", { attrs: { maxlength: 12, placeholder: "L & S" }, hint: "Shown where the template uses a monogram, if you don't upload a logo." }) +
      '<fieldset><legend>Your wording</legend><div class="form-row">' + field("w_welcome", "Welcome line", w.welcome || "", { attrs: { placeholder: "Together with their families" } }) +
      field("w_invitation", "Invitation wording", w.invitation || "", { type: "textarea", attrs: { rows: 4, placeholder: "Request the pleasure of your company as they celebrate their marriage." } }) +
      '<div class="form-row form-row--2">' + field("w_rsvp_note", "RSVP note", w.rsvp_note || "", { attrs: { placeholder: "Kindly reply by 1 February." } }) +
      field("w_closing", "Closing line", w.closing || "", { attrs: { placeholder: "We can't wait to celebrate with you." } }) + "</div></div></fieldset>";
  }
  function collect3(ev, fd) {
    var t = val(fd, "template") || ev.template, d = Object.assign({}, ev.design);
    if (t !== ev.template) { delete d.palette; delete d.font_pair; delete d.background; delete d.colors; ev.template = t; d._reset = true; }
    else {
      d.palette = val(fd, "palette") || d.palette; d.font_pair = val(fd, "font_pair") || d.font_pair; d.background = val(fd, "background") || d.background;
      if (fd.get("custom_colors") && feature(ev, "advanced_design")) {
        d.colors = {};
        ["bg", "text", "accent", "accent2"].forEach(function (k) { var v = val(fd, "color_" + k); if (/^#[0-9A-Fa-f]{6}$/.test(v)) d.colors[k] = v.toUpperCase(); });
      } else delete d.colors;
    }
    d.monogram = val(fd, "monogram");
    d.wording = { welcome: val(fd, "w_welcome"), invitation: val(fd, "w_invitation"), rsvp_note: val(fd, "w_rsvp_note"), closing: val(fd, "w_closing") };
    ev.design = d;
  }

  // --- step 4 ---------------------------------------------------------------------------------------
  function step4(ev) {
    var gs = ev.guest_settings, preset = ["Family", "Friends", "Colleagues", "VIP", "Church", "Neighbours", "Partners", "Clients"], chosen = gs.categories || [];
    var sides = (gs.sides || ["", ""]).concat(["", ""]).slice(0, 2);
    var pol = [["none", "No plus-ones", "Invitations are for the named guest only."], ["per_guest", "Set per guest", "You decide for each guest in your list."], ["open", "Everyone may bring", "Guests on the general link can add plus-ones."]];
    return '<div class="form-row form-row--2">' + field("estimated", "Estimated number of guests", gs.estimated, { type: "number", attrs: { min: 0, max: 5000 } }) +
      field("rsvp_deadline", "RSVP deadline", gs.rsvp_deadline, { type: "date", hint: "Replies close at the end of this day." }) + "</div>" +
      "<fieldset><legend>Guest categories</legend>" + featureNote(ev, "guest_categories", "Using several guest categories") + '<div class="choice-grid">' +
      preset.map(function (c) { return '<label class="choice"><input type="checkbox" name="categories" value="' + c + '"' + (chosen.indexOf(c) > -1 ? " checked" : "") + "><span>" + c + "</span></label>"; }).join("") + "</div>" +
      field("categories_other", "Other categories", chosen.filter(function (c) { return preset.indexOf(c) < 0; }).join(", "), { hint: "Comma-separated, e.g. Book club, Soccer team" }) + "</fieldset>" +
      '<fieldset><legend>Families</legend><div class="form-row form-row--2">' + field("side_a", "First family or side", sides[0], { attrs: { placeholder: "Bride's family" } }) +
      field("side_b", "Second family or side", sides[1], { attrs: { placeholder: "Groom's family" } }) + "</div>" +
      field("family_groups", "Family groups", (gs.family_groups || []).join("\n"), { type: "textarea", attrs: { rows: 4, placeholder: "Mokoena family\nDlamini family" }, hint: "One per line. Use them to group guests and seat families together." }) + "</fieldset>" +
      field("vip_note", "VIP guests", gs.vip_note || "", { type: "textarea", attrs: { rows: 2 }, hint: "Who needs special attention, e.g. grandparents, dignitaries." }) +
      '<fieldset><legend>Plus-ones</legend><div class="choice-grid">' + pol.map(function (x) { return '<label class="choice"><input type="radio" name="plus_one_policy" value="' + x[0] + '"' +
        ((gs.plus_one_policy || "per_guest") === x[0] ? " checked" : "") + "><span>" + x[1] + "<small>" + x[2] + "</small></span></label>"; }).join("") + "</div>" +
      field("plus_ones_default", "Plus-ones allowed by default", gs.plus_ones_default || 0, { type: "number", attrs: { min: 0, max: 10 } }) + "</fieldset>" +
      "<fieldset><legend>Children</legend>" + check("children_allowed", "Children are welcome", !!gs.children_allowed, { attrs: { "data-reveals": "#kids" } }) +
      '<div id="kids"' + (gs.children_allowed ? "" : " hidden") + ">" + field("max_children", "Children per invitation (maximum)", gs.max_children || 0, { type: "number", attrs: { min: 0, max: 10 } }) + "</div></fieldset>" +
      '<div class="notice">' + icon("info") + "<span>After publishing, you add your actual guest list (or import a spreadsheet). Each guest gets a personal RSVP link.</span></div>";
  }
  function collect4(ev, fd) {
    var gs = ev.guest_settings, cats = fd.getAll("categories").concat(val(fd, "categories_other").split(",").map(function (s) { return s.trim(); }).filter(Boolean));
    gs.estimated = val(fd, "estimated"); gs.rsvp_deadline = val(fd, "rsvp_deadline");
    gs.categories = cats.filter(function (c, i) { return cats.indexOf(c) === i; }).slice(0, 20);
    var sides = [val(fd, "side_a"), val(fd, "side_b")].filter(Boolean);
    if (sides.length) gs.sides = sides; else delete gs.sides;
    gs.family_groups = val(fd, "family_groups").split("\n").map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 100);
    gs.vip_note = val(fd, "vip_note"); gs.children_allowed = !!fd.get("children_allowed"); gs.max_children = parseInt(val(fd, "max_children") || 0, 10) || 0;
    gs.plus_one_policy = val(fd, "plus_one_policy") || "per_guest"; gs.plus_ones_default = parseInt(val(fd, "plus_ones_default") || 0, 10) || 0;
  }
  function validate4(ev) {
    var gs = ev.guest_settings, e = {};
    if (gs.estimated && !(+gs.estimated >= 0 && +gs.estimated <= 5000)) e.estimated = "Estimated guests must be between 0 and 5000.";
    if (gs.rsvp_deadline && ev.event_date && gs.rsvp_deadline > ev.event_date) e.rsvp_deadline = "The RSVP deadline should be on or before the event date.";
    if (gs.plus_ones_default < 0 || gs.plus_ones_default > 10) e.plus_ones_default = "Plus-ones must be between 0 and 10.";
    return e;
  }

  // --- step 5 ---------------------------------------------------------------------------------------
  function maxFunctions(ev) { return feature(ev, "multi_functions") ? (limit(ev, "functions") || 1) : 1; }
  function fnOptions(ev) { return [["", "Whole event"]].concat(ev.functions.filter(function (f) { return f.name; }).map(function (f) { return [f.id, f.name]; })); }
  function fnRow(i, f) {
    f = f || {};
    return '<div class="repeat__row" style="--cols:repeat(4,minmax(0,1fr))"><input type="hidden" name="fn-' + i + '-id" value="' + esc(f.id || uid("f")) + '">' +
      mini("fn-" + i + "-name", f.name, "text", "Ceremony", "Name") + mini("fn-" + i + "-date", f.func_date, "date", "", "Date") + mini("fn-" + i + "-start", f.start_time, "time", "", "Starts") +
      mini("fn-" + i + "-end", f.end_time, "time", "", "Ends") + mini("fn-" + i + "-venue", f.venue_name, "text", "Venue (if different)", "Venue") + mini("fn-" + i + "-address", f.address, "text", "Address", "Address") +
      mini("fn-" + i + "-map", f.map_url, "url", "Map link", "Map link") + "<span></span>" + rm() + "</div>";
  }
  var KINDS = D.kinds;
  function siRow(i, s, ev) {
    s = s || {};
    return '<div class="repeat__row" style="--cols:110px minmax(0,1.3fr) minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr)">' + mini("si-" + i + "-time", s.item_time, "time", "", "Time") +
      mini("si-" + i + "-title", s.title, "text", "Arrival and welcome drinks", "Title") + mini("si-" + i + "-description", s.description, "text", "Optional detail", "Detail") +
      miniSel("si-" + i + "-kind", KINDS, s.kind || "other", "Type") + miniSel("si-" + i + "-function", fnOptions(ev), s.function_id || "", "Part of") + rm() + "</div>";
  }
  function step5(ev) {
    var mf = maxFunctions(ev), multi = ((cat(ev.category) || {}).features || []).indexOf("multi_function") > -1;
    var fr = ev.functions.length ? ev.functions.map(function (f, i) { return fnRow(i, f); }) : [fnRow(0)];
    var sr = ev.schedule.length ? ev.schedule.map(function (s, i) { return siRow(i, s, ev); }) : [siRow(0, null, ev), siRow(1, null, ev)];
    return featureNote(ev, "programme", "The programme") + '<fieldset><legend>Event functions</legend><p class="hint" style="margin-bottom:12px">' +
      (multi ? "Traditional and multi-day events often have several parts, each with its own venue. " : "") + "Add each ceremony or reception. Leave venue blank to use the main venue. Your package allows " + mf + ".</p>" +
      repeat("fn", fr, null, "Add a function", mf) + "</fieldset>" +
      '<fieldset><legend>Programme</legend><p class="hint" style="margin-bottom:12px">The running order guests see: arrival, ceremony, speeches, first dance, entertainment.</p>' + repeat("si", sr, null, "Add an item") + "</fieldset>";
  }
  function collect5(ev, fd) {
    ev.functions = readRows(fd, "fn", ["id", "name", "date", "start", "end", "venue", "address", "map"]).map(function (r) {
      return { id: r.id || uid("f"), name: r.name, func_date: r.date, start_time: r.start, end_time: r.end, venue_name: r.venue, address: r.address, map_url: r.map }; });
    var ids = ev.functions.map(function (f) { return f.id; });
    ev.schedule = readRows(fd, "si", ["time", "title", "description", "kind", "function"]).map(function (r) {
      return { item_time: r.time, title: r.title, description: r.description, kind: r.kind || "other", function_id: ids.indexOf(r.function) > -1 ? r.function : "" }; });
  }
  function validate5(ev) {
    var e = {}, mf = maxFunctions(ev);
    if (ev.functions.length > mf) e.functions = "Your package includes " + mf + " event function" + (mf === 1 ? "" : "s") + ". Upgrade in step 10 for more.";
    if (ev.functions.some(function (f) { return !f.name; })) e.functions = "Each function needs a name, e.g. Ceremony or Reception.";
    if (ev.schedule.some(function (s) { return !s.title; })) e.schedule = "Each programme item needs a title.";
    return e;
  }

  // --- step 6 ---------------------------------------------------------------------------------------
  function miRow(i, it) {
    it = it || {};
    return '<div class="repeat__row" style="--cols:140px minmax(0,1.2fr) minmax(0,1.6fr) minmax(0,1fr) 130px">' + miniSel("mi-" + i + "-course", D.courses.map(function (c) { return [c, c]; }), it.course || "Main", "Course") +
      mini("mi-" + i + "-name", it.name, "text", "Slow-roasted lamb", "Dish") + mini("mi-" + i + "-description", it.description, "text", "Rosemary jus, crushed potatoes", "Description") +
      mini("mi-" + i + "-tags", (it.tags || []).join(", "), "text", "Halal, Gluten-free", "Tags") +
      '<label class="check" style="padding-top:22px"><input type="checkbox" name="mi-' + i + '-selectable" value="1"' + (it.selectable ? " checked" : "") + '><span class="small">Guests choose</span></label>' + rm() + "</div>";
  }
  function step6(ev) {
    var items = ev.menu.items, info = ev.info, diet = info.dietary_options || [];
    return featureNote(ev, "menu", "The digital menu") + field("menu_name", "Menu name", ev.menu.name || "Reception menu") +
      '<fieldset><legend>Menu</legend><p class="hint" style="margin-bottom:12px">Tick “Guests choose” on main-course options to ask for a meal choice in the RSVP.</p>' +
      repeat("mi", items.length ? items.map(function (it, i) { return miRow(i, it); }) : [miRow(0), miRow(1)], null, "Add a dish") + "</fieldset>" +
      "<fieldset><legend>Dietary requirements guests can tell you about</legend>" + featureNote(ev, "dietary", "Collecting dietary requirements") + '<div class="choice-grid">' +
      D.dietary.map(function (d) { return '<label class="choice"><input type="checkbox" name="dietary_options" value="' + esc(d) + '"' + (diet.indexOf(d) > -1 ? " checked" : "") + "><span>" + esc(d) + "</span></label>"; }).join("") +
      '</div><p class="hint" style="margin-top:8px">Guests can always add allergies in their own words.</p></fieldset>' +
      '<div class="form-row form-row--2">' + field("drinks", "Drinks", info.drinks || "", { type: "textarea", attrs: { rows: 3, placeholder: "Welcome bubbles, open bar until 23:00, mocktails for kids" } }) +
      field("catering_notes", "Notes for guests about food", info.catering_notes || "", { type: "textarea", attrs: { rows: 3 } }) + "</div>";
  }
  function collect6(ev, fd) {
    ev.menu = { name: val(fd, "menu_name") || "Menu", items: readRows(fd, "mi", ["course", "name", "description", "tags", "selectable"]).map(function (r) {
      return { course: D.courses.indexOf(r.course) > -1 ? r.course : "Main", name: r.name, description: r.description,
        tags: r.tags.split(",").map(function (t) { return t.trim(); }).filter(Boolean).slice(0, 6), selectable: !!r.selectable }; }) };
    ev.info.dietary_options = fd.getAll("dietary_options"); ev.info.drinks = val(fd, "drinks"); ev.info.catering_notes = val(fd, "catering_notes");
  }
  function validate6(ev) { return ev.menu.items.some(function (i) { return !i.name; }) ? { menu: "Each menu item needs a name." } : {}; }

  // --- step 7 ---------------------------------------------------------------------------------------
  function step7(ev) {
    var t = ev.tables, est = +ev.guest_settings.estimated || 0, sug = est ? Math.max(1, Math.ceil(est / 10)) : 10;
    return featureNote(ev, "seating", "The seating chart") + '<div class="form-row form-row--3">' +
      field("table_count", "Number of tables", t.count === "" ? sug : t.count, { type: "number", attrs: { min: 0, max: 200 }, hint: est ? "About " + sug + " for " + est + " guests at 10 a table." : "" }) +
      field("capacity", "Seats per table", t.capacity || 10, { type: "number", attrs: { min: 1, max: 40 } }) + select("shape", "Table shape", [["round", "Round"], ["long", "Long / banquet"]], t.shape || "round") + "</div>" +
      field("table_names", "Table names (optional)", (t.names || []).join("\n"), { type: "textarea", attrs: { rows: 5, placeholder: "Head table\nProtea\nBaobab" }, hint: "One per line, in order. Leave blank for Table 1, Table 2 and so on." }) +
      field("seating_notes", "Special seating requirements", ev.info.seating_notes || "", { type: "textarea", attrs: { rows: 3, placeholder: "Grandparents near the front and away from the speakers; wheelchair access at Table 3." } }) +
      '<div class="notice">' + icon("seat") + "<span>Once guests reply, you'll drag them onto tables in the seating editor in your dashboard.</span></div>";
  }
  function collect7(ev, fd) {
    ev.tables = { count: val(fd, "table_count"), capacity: parseInt(val(fd, "capacity") || 10, 10) || 10, shape: val(fd, "shape") || "round",
      names: val(fd, "table_names").split("\n").map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 200) };
    ev.info.seating_notes = val(fd, "seating_notes");
  }
  function validate7(ev) {
    var e = {}, c = +ev.tables.count;
    if (ev.tables.count !== "" && !(c >= 0 && c <= 200)) e.table_count = "Number of tables must be between 0 and 200.";
    if (!(ev.tables.capacity >= 1 && ev.tables.capacity <= 40)) e.capacity = "Seats per table must be between 1 and 40.";
    return e;
  }

  // --- step 8 ---------------------------------------------------------------------------------------
  function row3(prefix, i, it, fields) {
    it = it || {};
    return '<div class="repeat__row" style="--cols:repeat(3,minmax(0,1fr))">' + fields.map(function (f) {
      return mini(prefix + "-" + i + "-" + f[0], it[f[0]], f[0] === "url" ? "url" : "text", f[2], f[1]); }).join("") + rm() + "</div>";
  }
  function ctRow(i, c) {
    c = c || {};
    return '<div class="repeat__row" style="--cols:repeat(4,minmax(0,1fr))">' + mini("ct-" + i + "-name", c.name, "text", "Zanele", "Name") + mini("ct-" + i + "-role", c.role, "text", "Maid of honour", "Role") +
      mini("ct-" + i + "-phone", c.phone, "tel", "+27 82 000 0000", "Phone") + mini("ct-" + i + "-email", c.email, "email", "", "Email") + rm() + "</div>";
  }
  var RG = [["name", "Registry", "Yuppiechef"], ["url", "Link", "https://"], ["note", "Note", "Optional"]];
  var AC = [["name", "Place", "Guest farm"], ["url", "Link", "https://"], ["note", "Note", "Use code SIPHO10"]];
  function step8(ev) {
    var info = ev.info, gal = ev.images.gallery || [], glimit = limit(ev, "gallery_photos");
    var reg = info.registry || [], acc = info.accommodation || [], cts = info.contacts || [];
    var thumbs = gal.map(function (g, k) { return '<div style="position:relative"><img src="' + g.url + '" alt="" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:10px">' +
      '<button class="btn btn--sm btn--glass" style="position:absolute;right:6px;bottom:6px" type="button" data-remove-gallery="' + k + '" aria-label="Remove photo">' + icon("trash") + "</button></div>"; }).join("");
    return '<div class="form-row form-row--2">' + select("dress_code", "Dress code", D.dress_codes.map(function (d) { return [d, d || "No dress code"]; }), info.dress_code || "") +
      field("dress_code_notes", "Dress code notes", info.dress_code_notes || "", { attrs: { placeholder: "Shades of emerald and gold; comfortable shoes for the lawn" } }) + "</div>" +
      "<fieldset><legend>Gift registry</legend>" + repeat("rg", (reg.length ? reg : [{}]).map(function (r, i) { return row3("rg", i, r, RG); }), null, "Add a registry", 10) +
      field("gift_note", "Gift preferences", info.gift_note || "", { type: "textarea", attrs: { rows: 2, placeholder: "Your presence is our present." } }) + "</fieldset>" +
      "<fieldset><legend>Contacts for guests</legend>" + repeat("ct", (cts.length ? cts : [{}]).map(function (c, i) { return ctRow(i, c); }), null, "Add a contact", 8) + "</fieldset>" +
      "<fieldset><legend>Accommodation</legend>" + repeat("ac", (acc.length ? acc : [{}]).map(function (a, i) { return row3("ac", i, a, AC); }), null, "Add a place to stay", 10) + "</fieldset>" +
      field("instructions", "Special instructions", info.instructions || "", { type: "textarea", attrs: { rows: 3, placeholder: "Unplugged ceremony: please keep phones away until the reception." } }) +
      "<fieldset><legend>Photo gallery</legend>" + featureNote(ev, "gallery", "The photo gallery") +
      '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px;margin-bottom:12px">' + thumbs + "</div>" +
      (glimit ? '<label class="file-drop" style="position:relative">' + icon("image") + "<span>Add photos (" + gal.length + " of " + glimit + ')</span><span class="hint">JPG, PNG or WebP.</span>' +
        '<input type="file" data-gallery multiple accept="image/jpeg,image/png,image/webp,image/gif"></label>' : '<p class="hint">The Essential package has no gallery. Premium includes 40 photos.</p>') + "</fieldset>";
  }
  function collect8(ev, fd) {
    var info = ev.info;
    info.dress_code = val(fd, "dress_code"); info.dress_code_notes = val(fd, "dress_code_notes"); info.gift_note = val(fd, "gift_note"); info.instructions = val(fd, "instructions");
    var fix = function (r) { if (r.url && !/^https?:\/\//i.test(r.url)) r.url = "https://" + r.url; return r; };
    info.registry = readRows(fd, "rg", ["name", "url", "note"]).map(fix).slice(0, 10);
    info.accommodation = readRows(fd, "ac", ["name", "url", "note"]).map(fix).slice(0, 10);
    info.contacts = readRows(fd, "ct", ["name", "role", "phone", "email"]).slice(0, 8);
  }
  function validate8(ev) {
    var e = {}, info = ev.info;
    if (info.registry.concat(info.accommodation).some(function (r) { return !r.name; })) e.registry = "Each registry or accommodation entry needs a name.";
    info.contacts.forEach(function (c) { if (c.email && !/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(c.email)) e.contacts = "Check the email for " + (c.name || "a contact") + "."; });
    return e;
  }

  // --- step 9: review --------------------------------------------------------------------------------
  function step9(ev) {
    var v = ev.venue, gs = ev.guest_settings, info = ev.info, t = tpl(ev.template) || {};
    var checks = [[!!ev.event_date, "Event date", 1], [!!(v.name && v.address), "Venue and address", 2], [!!gs.rsvp_deadline, "RSVP deadline", 4],
      [!!ev.schedule.length || !feature(ev, "programme"), "Programme", 5], [!!(ev.contact.name && ev.contact.email), "Your contact details", 1]];
    var missing = checks.filter(function (c) { return !c[0]; });
    function sec(n, title, rows) {
      return '<div class="review-section"><div class="review-section__head"><h3>' + esc(title) + '</h3><a class="btn btn--sm btn--ghost" href="#setup-' + n + '">' + icon("edit") + ' Edit</a></div><dl class="dl">' +
        rows.map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + (r[1] ? esc(r[1]) : '<span class="muted">Not added</span>') + "</dd>"; }).join("") + "</dl></div>";
    }
    var tc = +ev.tables.count || 0;
    return (missing.length ? '<div class="notice notice--warn">' + icon("alert") + '<div><b>Worth adding before you book:</b><ul style="margin:6px 0 0;padding-left:18px">' +
        missing.map(function (m) { return '<li><a class="text-link" href="#setup-' + m[2] + '">' + esc(m[1]) + "</a></li>"; }).join("") + "</ul></div></div>" : "") +
      '<div class="notice">' + icon("link") + "<span>Your website address will be <b class=\"mono\">aurelia.events/" + esc(slugOf(ev)) + "</b> once published.</span></div>" +
      '<div style="margin:18px 0">' + previewFrame(620) + "</div>" +
      sec(1, "Event details", [["You", ev.contact.name + (ev.contact.email ? " · " + ev.contact.email : "")], ["Event", ev.name], ["Type", (cat(ev.category) || {}).name], ["Hosts", ev.hosts],
        ["Date", ev.event_date ? R.fmtDate(ev.event_date) : ""], ["Time", [ev.start_time, ev.end_time].filter(Boolean).join(" – ")]]) +
      sec(2, "Venue", [["Venue", v.name], ["Address", v.address], ["Parking", v.parking], ["Directions", v.directions]]) +
      sec(3, "Design", [["Template", t.name], ["Photos", String(["hero", "logo", "background"].filter(function (k) { return ev.images[k]; }).length + (ev.images.gallery || []).length) + " added"], ["Welcome", (ev.design.wording || {}).welcome]]) +
      sec(4, "Guests", [["Estimated", gs.estimated], ["RSVP deadline", gs.rsvp_deadline ? R.fmtDate(gs.rsvp_deadline) : ""],
        ["Plus-ones", { none: "Not allowed", per_guest: "Set per guest", open: "Allowed" }[gs.plus_one_policy]], ["Children", gs.children_allowed ? "Welcome" : "Adults only"]]) +
      sec(5, "Programme", [["Functions", ev.functions.map(function (f) { return f.name; }).join(", ")], ["Programme items", ev.schedule.length ? String(ev.schedule.length) : ""]]) +
      sec(6, "Food and drinks", [["Menu items", ev.menu.items.length ? String(ev.menu.items.length) : ""], ["Dietary options", (info.dietary_options || []).join(", ")]]) +
      sec(7, "Seating", [["Tables", tc ? tc + " tables, " + tc * ev.tables.capacity + " seats" : ""]]) +
      sec(8, "Extras", [["Dress code", info.dress_code], ["Registry", (info.registry || []).length ? String(info.registry.length) : ""], ["Contacts", (info.contacts || []).length ? String(info.contacts.length) : ""]]);
  }

  // --- step 10: package and booking ----------------------------------------------------------------------
  function step10(ev) {
    var cards = D.packages.map(function (p) {
      var sel = (ev.selected_package || "premium") === p.code;
      return '<label class="price' + (sel ? " price--highlight" : "") + '" style="cursor:pointer">' + (p.highlight ? '<span class="price__badge">Most chosen</span>' : "") +
        '<div class="row row--between"><h3>' + esc(p.name) + '</h3><input type="radio" name="package" value="' + p.code + '"' + (sel ? " checked" : "") + ' aria-label="Choose ' + esc(p.name) + '" style="width:22px;height:22px;accent-color:var(--color-accent-dark)"></div>' +
        '<p class="muted small">' + esc(p.tagline) + '</p><div class="price__amount">' + money(p.price_cents) + "<small>once-off, VAT incl.</small></div><ul>" +
        p.bullets.map(function (b) { return "<li>" + icon("check") + "<span>" + esc(b) + "</span></li>"; }).join("") + '</ul><div class="price__limits">' +
        Object.keys(D.limit_labels).map(function (k) { return "<div><span>" + esc(D.limit_labels[k]) + "</span><b>" + (p.limits[k] || "—") + "</b></div>"; }).join("") + "</div></label>";
    }).join("");
    return '<div class="price-grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">' + cards + "</div>" +
      '<div data-field="accept">' + check("accept", 'I accept the <a class="text-link" href="#terms">terms of service</a> and <a class="text-link" href="#refunds">refund policy</a>. My website is published once payment is confirmed.', false) + "</div>" +
      '<div class="wizard-actions"><a class="btn btn--ghost" href="#setup-9">' + icon("arrow-left") + ' Back</a><div class="btn-row"><button class="btn btn--primary btn--lg" type="submit" name="nav" value="book">Request my booking ' + icon("arrow") + "</button></div></div>";
  }

  // --- booking confirmation ---------------------------------------------------------------------------
  function summaryText(ev) {
    var p = pkg(ev.selected_package) || {}, v = ev.venue, gs = ev.guest_settings, info = ev.info, lines = [];
    var add = function (k, x) { if (x !== undefined && x !== null && String(x).trim() !== "") lines.push(k + ": " + x); };
    lines.push("AURELIA BOOKING REQUEST " + (ev.booking ? ev.booking.ref : ""), "");
    add("Package", (p.name || "") + " (" + money(p.price_cents || 0) + ", VAT incl.)");
    add("Name", ev.contact.name); add("Email", ev.contact.email); add("Mobile", ev.contact.phone); lines.push("");
    add("Event", ev.name); add("Type", (cat(ev.category) || {}).name); add("Hosts", ev.hosts); add("Template", (tpl(ev.template) || {}).name);
    add("Date", ev.event_date ? R.fmtDate(ev.event_date) : ""); add("Time", [ev.start_time, ev.end_time].filter(Boolean).join(" - ")); add("Description", ev.description); lines.push("");
    add("Venue", v.name); add("Address", v.address); add("Map", v.map_url); add("Parking", v.parking); add("Directions", v.directions); add("Accommodation", v.accommodation); lines.push("");
    var d = ev.design, w = d.wording || {};
    add("Palette", d.palette); add("Typography", d.font_pair); add("Background", d.background); add("Own colours", d.colors ? JSON.stringify(d.colors) : ""); add("Monogram", d.monogram);
    add("Welcome line", w.welcome); add("Invitation wording", w.invitation); add("RSVP note", w.rsvp_note); add("Closing line", w.closing);
    add("Photos chosen", ["hero", "logo", "background"].filter(function (k) { return ev.images[k]; }).join(", ") + ((ev.images.gallery || []).length ? " + " + ev.images.gallery.length + " gallery" : "") + " (please email them with this request)");
    lines.push("");
    add("Estimated guests", gs.estimated); add("RSVP deadline", gs.rsvp_deadline); add("Guest categories", (gs.categories || []).join(", ")); add("Families / sides", (gs.sides || []).join(", "));
    add("Family groups", (gs.family_groups || []).join(", ")); add("VIP note", gs.vip_note); add("Plus-one policy", gs.plus_one_policy + " (default " + (gs.plus_ones_default || 0) + ")");
    add("Children", gs.children_allowed ? "welcome, up to " + (gs.max_children || 0) + " per invitation" : "adults only"); lines.push("");
    if (ev.functions.length) { lines.push("FUNCTIONS"); ev.functions.forEach(function (f) { lines.push("- " + [f.name, f.func_date, [f.start_time, f.end_time].filter(Boolean).join("-"), f.venue_name, f.address, f.map_url].filter(Boolean).join(" | ")); }); lines.push(""); }
    if (ev.schedule.length) { lines.push("PROGRAMME"); ev.schedule.forEach(function (s) { lines.push("- " + [s.item_time, s.title, s.description, s.kind].filter(Boolean).join(" | ")); }); lines.push(""); }
    if (ev.menu.items.length) { lines.push("MENU: " + ev.menu.name); ev.menu.items.forEach(function (i) { lines.push("- " + [i.course, i.name, i.description, (i.tags || []).join(", "), i.selectable ? "guests choose" : ""].filter(Boolean).join(" | ")); }); }
    add("Dietary options", (info.dietary_options || []).join(", ")); add("Drinks", info.drinks); add("Catering notes", info.catering_notes); lines.push("");
    add("Tables", ev.tables.count ? ev.tables.count + " x " + ev.tables.capacity + " seats, " + ev.tables.shape : ""); add("Table names", (ev.tables.names || []).join(", ")); add("Seating notes", info.seating_notes); lines.push("");
    add("Dress code", [info.dress_code, info.dress_code_notes].filter(Boolean).join(" - "));
    (info.registry || []).forEach(function (r) { add("Registry", [r.name, r.url, r.note].filter(Boolean).join(" | ")); });
    add("Gift note", info.gift_note);
    (info.contacts || []).forEach(function (c) { add("Contact", [c.name, c.role, c.phone, c.email].filter(Boolean).join(" | ")); });
    (info.accommodation || []).forEach(function (a) { add("Stay", [a.name, a.url, a.note].filter(Boolean).join(" | ")); });
    add("Special instructions", info.instructions);
    return lines.join("\n").replace(/\n{3,}/g, "\n\n");
  }
  function viewBooked() {
    var ev = cur();
    if (!ev || !ev.booking) { location.hash = "#my-events"; return; }
    var p = pkg(ev.selected_package) || {}, link = (D.payment_links || {})[p.code] || "", text = summaryText(ev), email = D.email;
    var pay = link
      ? '<a class="btn btn--primary btn--lg" href="' + esc(link) + '" target="_blank" rel="noopener">' + icon("card") + " Pay " + money(p.price_cents) + " securely</a>"
      : '<div class="notice">' + icon("clock") + "<span><b>Online payment opens soon.</b> We'll email you a secure payment link for " + money(p.price_cents) + ". Your website goes live as soon as payment is confirmed.</span></div>";
    var subject = "Booking " + ev.booking.ref + ": " + ev.name;
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 32px)"><div class="container container--narrow" style="display:grid;gap:var(--gap)">' +
      '<div class="glass glass--strong panel" style="display:grid;gap:14px;text-align:left"><span class="icon-tile icon-tile--soft">' + icon("check") + "</span>" +
      '<h1 style="font-size:clamp(1.8rem,1.3rem + 2vw,2.6rem)">Booking request ready</h1><p class="lead" style="font-size:1.0625rem">Reference <b class="mono">' + esc(ev.booking.ref) + "</b> · " + esc(p.name || "") + " · " + money(p.price_cents || 0) + " (VAT incl.)</p>" + pay + "</div>" +
      '<div class="box" style="display:grid;gap:14px"><h2 style="font-size:1.25rem">Send your booking to us</h2>' +
      '<p class="muted small">Copy your booking details and email them to us, with any photos you chose. We confirm within one working day.</p>' +
      '<div class="notice">' + icon("mail") + '<div><span class="mono" style="user-select:all">' + esc(email) + "</span><br>" +
      '<span class="tiny muted">Subject: <span style="user-select:all">' + esc(subject) + "</span></span></div></div>" +
      '<div class="btn-row"><button class="btn btn--primary" type="button" data-copy-booking>' + icon("copy") + ' Copy booking details</button>' +
      '<button class="btn btn--secondary" type="button" data-copy="' + esc(email) + '" data-copied="Email address copied">Copy email address</button>' +
      '<a class="btn btn--ghost" href="mailto:' + esc(email) + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent("Hello Aurelia,\n\nPlease find my booking request " + ev.booking.ref + " below.\n\n") + '">Open my email app</a></div>' +
      '<details><summary class="small" style="cursor:pointer;min-height:44px;display:flex;align-items:center">Show the booking details</summary><textarea class="textarea mono" readonly rows="14" style="font-size:.8125rem" data-booking-text>' + esc(text) + "</textarea></details></div>" +
      '<div class="btn-row"><a class="btn btn--secondary" href="#preview-event">' + icon("eye") + ' Preview your website</a><a class="btn btn--ghost" href="#setup-1">Edit details</a><a class="btn btn--ghost" href="#my-events">My events</a></div></div></section>';
  }

  // --- full preview ------------------------------------------------------------------------------------
  function viewPreview() {
    var ev = cur();
    if (!ev) { location.hash = "#my-events"; return; }
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 24px)"><div class="container"><div class="page-head"><div><h1>' + esc(ev.name) +
      "</h1><p>Your event website with the details you've entered. Guests see it once it's published.</p></div>" +
      '<div class="btn-row"><a class="btn btn--primary btn--sm" href="#setup-' + (ev.booking ? 10 : Math.min(10, Math.max.apply(null, [0].concat(ev.wizard_done)) + 1)) + '">Continue set-up</a><a class="btn btn--ghost btn--sm" href="#my-events">My events</a></div></div>' +
      previewFrame(Math.max(560, window.innerHeight - 220)) + "</div></section>";
    refreshPreview(true);
  }

  // --- step dispatch ------------------------------------------------------------------------------------
  var STEP = { 1: [step1, collect1, validate1], 2: [step2, collect2, validate2], 3: [step3, collect3], 4: [step4, collect4, validate4], 5: [step5, collect5, validate5],
    6: [step6, collect6, validate6], 7: [step7, collect7, validate7], 8: [step8, collect8, validate8], 9: [step9], 10: [step10] };
  function viewStep(n) {
    var ev = cur();
    if (!ev) { location.hash = state.order.length ? "#my-events" : "#create"; return; }
    frame(ev, n, STEP[n][0](ev), { preview: n === 3, nextLabel: n === 9 ? "Looks good, choose a package" : "" });
  }
  function collectStep(form) {
    var n = +form.getAttribute("data-step"), ev = cur();
    if (!ev || !STEP[n][1]) return ev;
    STEP[n][1](ev, new FormData(form));
    ev.updated = new Date().toISOString();
    return ev;
  }
  function submitStep(form, nav) {
    var n = +form.getAttribute("data-step"), ev = collectStep(form);
    if (n === 10) {
      ev.selected_package = (new FormData(form)).get("package") || ev.selected_package;
      var errs = {};
      if (!form.querySelector("input[name=accept]").checked) errs.accept = "Please accept the terms and refund policy to continue.";
      var need = [validate1(ev), validate2(ev)].reduce(function (a, b) { return Object.assign(a, b); }, {});
      if (Object.keys(need).length) errs.details = "Some required details are missing in steps 1 and 2 (" + Object.keys(need).length + "). Go back and complete them.";
      if (showErrors(form, errs)) { save(); return; }
      ev.booking = ev.booking || { ref: "AUR-" + Math.random().toString(36).slice(2, 7).toUpperCase(), at: new Date().toISOString() };
      ev.booking.package = ev.selected_package;
      if (ev.wizard_done.indexOf(10) < 0) ev.wizard_done.push(10);
      save(); location.hash = "#booked"; return;
    }
    var e = STEP[n][2] ? STEP[n][2](ev) : {};
    if (showErrors(form, e)) { save(); return; }
    if (ev.wizard_done.indexOf(n) < 0) ev.wizard_done.push(n);
    if (ev.design._reset) { delete ev.design._reset; }
    save();
    if (nav === "next") location.hash = "#setup-" + (n + 1);
    else { toast("Saved."); viewStep(n); }
  }

  // --- images ---------------------------------------------------------------------------------------------
  function shrink(file, max, keepPng) {
    return new Promise(function (resolve, reject) {
      if (!/^image\/(jpeg|png|webp|gif)$/.test(file.type)) { reject(new Error("Upload a JPG, PNG, WebP or GIF image.")); return; }
      var fr = new FileReader();
      fr.onload = function () {
        var img = new Image();
        img.onload = function () {
          var s = Math.min(1, max / Math.max(img.width, img.height)), c = document.createElement("canvas");
          c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
          resolve(keepPng ? c.toDataURL("image/png") : c.toDataURL("image/jpeg", 0.82));
        };
        img.onerror = function () { reject(new Error("That file isn't a readable image.")); };
        img.src = fr.result;
      };
      fr.onerror = function () { reject(new Error("Couldn't read that file.")); };
      fr.readAsDataURL(file);
    });
  }

  // --- events ------------------------------------------------------------------------------------------
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("#journey-root form[data-step]");
    if (!form) return;
    e.preventDefault();
    var nav = (e.submitter && e.submitter.value) || "next";
    submitStep(form, nav);
  });
  document.addEventListener("change", function (e) {
    var form = e.target.closest("#journey-root form[data-step]");
    if (!form) return;
    var t = e.target;
    if (t.type === "color" && t.hasAttribute("data-sync")) { var txt = form.querySelector('input[name="' + t.getAttribute("data-sync") + '"]'); if (txt) txt.value = t.value.toUpperCase(); }
    if (t.hasAttribute("data-reveals")) { var tg = document.querySelector(t.getAttribute("data-reveals")); if (tg) tg.hidden = !t.checked; }
    if (t.hasAttribute("data-image")) {
      var kind = t.getAttribute("data-image"), f = t.files[0];
      if (!f) return;
      collectStep(form);
      shrink(f, kind === "logo" ? 600 : 1600, kind === "logo").then(function (url) { cur().images[kind] = url; save(); toast("Photo added."); viewStep(+form.getAttribute("data-step")); })
        .catch(function (err) { toast(err.message, "error"); });
      return;
    }
    if (t.hasAttribute("data-gallery")) {
      var ev = cur(), lim = limit(ev, "gallery_photos"), files = Array.prototype.slice.call(t.files);
      collectStep(form);
      var room = lim - (ev.images.gallery || []).length;
      if (files.length > room) toast("Your package includes " + lim + " gallery photos.", "error");
      Promise.all(files.slice(0, Math.max(0, room)).map(function (fl) { return shrink(fl, 1200).catch(function () { return null; }); })).then(function (urls) {
        ev.images.gallery = (ev.images.gallery || []).concat(urls.filter(Boolean).map(function (u) { return { url: u, caption: "" }; }));
        save(); viewStep(8);
      });
      return;
    }
    var n = +form.getAttribute("data-step");
    if (n === 3 && t.name === "template") { collectStep(form); save(); viewStep(3); return; }
    collectStep(form); save(); refreshPreview();
    if (n === 5 && /^fn-\d+-name$/.test(t.name)) {
      var opts = fnOptions(cur());
      form.querySelectorAll('select[name$="-function"]').forEach(function (s) {
        var v = s.value;
        s.innerHTML = opts.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (o[0] === v ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("");
      });
    }
  });
  document.addEventListener("input", function (e) {
    var form = e.target.closest("#journey-root form[data-step]");
    if (!form || e.target.type === "file") return;
    if (e.target.name && e.target.name.indexOf("color_") === 0) { var c = form.querySelector('input[type=color][data-sync="' + e.target.name + '"]'); if (c && /^#[0-9a-f]{6}$/i.test(e.target.value)) c.value = e.target.value; }
    clearTimeout(form._t);
    form._t = setTimeout(function () { collectStep(form); save(); refreshPreview(); }, 400);
  });
  document.addEventListener("click", function (e) {
    var t = e.target.closest("#journey-root [data-add-row], #journey-root [data-remove-row], #journey-root [data-device], #journey-root [data-open], #journey-root [data-delete], #journey-root [data-remove-image], #journey-root [data-remove-gallery], #journey-root [data-copy-booking]");
    if (!t) return;
    var form = t.closest("form[data-step]");
    if (t.hasAttribute("data-add-row")) {
      var wrap = t.closest("[data-repeat]"), list = wrap.querySelector("[data-rows]"), prefix = wrap.getAttribute("data-repeat"), max = +wrap.getAttribute("data-max");
      if (list.children.length >= max) { toast("Your package allows " + max + " here.", "error"); return; }
      var next = 0;
      list.querySelectorAll("input,select").forEach(function (i) { var m = new RegExp("^" + prefix + "-(\\d+)-").exec(i.name || ""); if (m) next = Math.max(next, +m[1] + 1); });
      var ev = cur(), html = prefix === "fn" ? fnRow(next) : prefix === "si" ? siRow(next, null, ev) : prefix === "mi" ? miRow(next) : prefix === "ct" ? ctRow(next) : row3(prefix, next, null, prefix === "rg" ? RG : AC);
      list.insertAdjacentHTML("beforeend", html);
      var first = list.lastElementChild.querySelector("input:not([type=hidden]),select"); if (first) first.focus();
      return;
    }
    if (t.hasAttribute("data-remove-row")) { t.closest(".repeat__row").remove(); if (form) { collectStep(form); save(); refreshPreview(); } return; }
    if (t.hasAttribute("data-device") && t.tagName === "BUTTON") {
      var box = t.closest("[data-jpreview]"); box.setAttribute("data-device", t.getAttribute("data-device"));
      box.querySelectorAll("button[data-device]").forEach(function (b) { b.setAttribute("aria-pressed", b === t ? "true" : "false"); });
      return;
    }
    if (t.hasAttribute("data-open")) { state.current = t.getAttribute("data-open"); save(); location.hash = "#" + t.getAttribute("data-to"); if (currentHash === t.getAttribute("data-to")) route(currentHash); return; }
    if (t.hasAttribute("data-delete")) {
      if (t.getAttribute("data-armed") !== "1") { t.setAttribute("data-armed", "1"); t.innerHTML = "Tap again to delete"; setTimeout(function () { if (t.isConnected) { t.removeAttribute("data-armed"); t.innerHTML = icon("trash") + " Delete"; } }, 4000); return; }
      var id = t.getAttribute("data-delete");
      delete state.events[id]; state.order = state.order.filter(function (x) { return x !== id; }); if (state.current === id) state.current = null;
      try { localStorage.removeItem(KEY + "-img-" + id); } catch (er) { /* ignore */ }
      save(); toast("Event deleted."); viewMyEvents(); return;
    }
    if (t.hasAttribute("data-remove-image")) { if (form) collectStep(form); delete cur().images[t.getAttribute("data-remove-image")]; save(); viewStep(3); return; }
    if (t.hasAttribute("data-remove-gallery")) { if (form) collectStep(form); cur().images.gallery.splice(+t.getAttribute("data-remove-gallery"), 1); save(); viewStep(8); return; }
    if (t.hasAttribute("data-copy-booking")) {
      var ta = document.querySelector("[data-booking-text]"), text = ta ? ta.value : "";
      var done = function () { toast("Booking details copied. Paste them into an email to " + D.email + "."); };
      var fallback = function () { if (ta) { ta.closest("details").open = true; ta.focus(); ta.select(); } try { document.execCommand("copy"); done(); } catch (er) { toast("Select the text below and copy it.", "error"); } };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback); else fallback();
    }
  });

  // --- routing ---------------------------------------------------------------------------------------------
  function route(id) {
    currentHash = id;
    if (id.indexOf("create") === 0) return viewCreate(id);
    if (id === "my-events") return viewMyEvents();
    if (id === "preview-event") return viewPreview();
    if (id === "booked") return viewBooked();
    var m = /^setup-(\d+)$/.exec(id);
    if (m && +m[1] >= 1 && +m[1] <= 10) return viewStep(+m[1]);
    return viewMyEvents();
  }
  function handles(id) { return /^(create(-.+)?|my-events|preview-event|booked|setup-\d+)$/.test(id); }
  window.AureliaJourney = { route: route, handles: handles };
})();
