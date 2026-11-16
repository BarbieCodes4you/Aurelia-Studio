/* Aurelia event-website renderer for the browser.
   A line-for-line port of app/eventsite/render.py + designs.py, so the shareable preview site can
   draw a customer's event website live, with the same markup and static/css/eventsite.css.
   Exposes window.AureliaRender.render(ev, mode) -> full HTML document string. */
(function () {
  "use strict";
  var D = window.AURELIA_DATA;
  var DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function esc(v) {
    if (v === null || v === undefined) return "";
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
  }
  function parseDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return null;
    var d = new Date(+m[1], +m[2] - 1, +m[3]);
    return isNaN(d) ? null : d;
  }
  function fmtDate(iso, long) {
    var d = parseDate(iso);
    if (!d) return iso || "";
    if (long === false) return d.getDate() + " " + MONTHS[d.getMonth()].slice(0, 3) + " " + d.getFullYear();
    return DAYS[d.getDay()] + ", " + d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
  }
  function fmtTime(t) { return /^\d{2}:\d{2}$/.test(t || "") ? t : (t || ""); }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function quotePlus(s) { return encodeURIComponent(s).replace(/%20/g, "+"); }

  // --- themes (mirror of eventsite/themes.py) -------------------------------------------------
  function design(key) { return D.themes.designs[key] || D.themes.designs.atelier; }
  function resolve(dkey, choices) {
    var d = design(dkey);
    choices = choices || {};
    var palKey = choices.palette || d.palettes[0][0];
    var base = (d.palettes.filter(function (p) { return p[0] === palKey; })[0] || d.palettes[0])[2];
    var colors = Object.assign({}, base);
    var custom = choices.colors || {};
    Object.keys(custom).forEach(function (k) { if (k in colors && /^#[0-9A-Fa-f]{6}$/.test(custom[k])) colors[k] = custom[k]; });
    var fp = D.themes.font_pairs[choices.font_pair] ? choices.font_pair : d.font_pair;
    var bg = D.themes.backgrounds[choices.background] ? choices.background : d.background;
    var pair = D.themes.font_pairs[fp];
    return { palette: palKey, colors: colors, font_pair: fp, display: pair[1], body: pair[2], background: bg };
  }
  function fontsUrl(a, b) {
    var fams = a === b ? [a] : [a, b];
    return "https://fonts.googleapis.com/css2?" + fams.map(function (f) {
      var spec = D.themes.fonts[f] || "";
      return "family=" + quotePlus(f) + (spec ? ":" + spec : "");
    }).join("&") + "&display=swap";
  }
  function cssVars(r) {
    var c = r.colors;
    return "--ev-bg:" + c.bg + ";--ev-surface:" + c.surface + ";--ev-text:" + c.text + ";--ev-muted:" + c.muted + ";" +
      "--ev-accent:" + c.accent + ";--ev-accent2:" + c.accent2 + ";" +
      "--ev-display:'" + r.display + "',Georgia,serif;--ev-body:'" + r.body + "',system-ui,sans-serif;";
  }

  // --- colour contrast (render.py) ------------------------------------------------------------
  function rgb(h) { h = h.replace("#", ""); return [0, 2, 4].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }
  function hex(c) { return "#" + c.map(function (x) { var v = Math.max(0, Math.min(255, Math.round(x))); return (v < 16 ? "0" : "") + v.toString(16).toUpperCase(); }).join(""); }
  function lum(h) {
    var c = rgb(h).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contrast(a, b) { var la = lum(a), lb = lum(b); var hi = Math.max(la, lb), lo = Math.min(la, lb); return (hi + 0.05) / (lo + 0.05); }
  function mix(a, b, t) { var ra = rgb(a), rb = rgb(b); return hex([0, 1, 2].map(function (i) { return ra[i] + (rb[i] - ra[i]) * t; })); }
  function ink(color, against, target) {
    target = target || 4.5;
    var toward = lum(against) > 0.25 ? "#000000" : "#FFFFFF", t = 0, out = color;
    while (contrast(out, against) < target && t < 1) { t += 0.05; out = mix(color, toward, t); }
    return out;
  }
  function contrastVars(c) {
    try {
      var dark = lum(c.bg) < 0.2, btn, btnText;
      if (dark) { btn = c.accent; btnText = contrast(btn, c.bg) >= 4.5 ? c.bg : "#111111"; }
      else { btn = ink(c.accent, "#FFFFFF"); btnText = "#FFFFFF"; }
      return "--ev-btn:" + btn + ";--ev-btn-text:" + btnText + ";--ev-ink:" + ink(c.accent, c.bg) + ";--ev-ink-s:" +
        ink(c.accent, c.surface) + ";--ev-muted:" + ink(c.muted, c.bg) + ";";
    } catch (e) { return ""; }
  }

  // --- context (render.build_context) ---------------------------------------------------------
  function groupOf(ev) {
    var c = D.categories.filter(function (x) { return x.slug === ev.category; })[0];
    return c ? c.group : "other";
  }
  function designKey(ev) {
    var t = D.templates.filter(function (x) { return x.slug === ev.template; })[0];
    var k = t ? t.design : "atelier";
    return D.themes.designs[k] ? k : "atelier";
  }
  function splitNames(text) {
    text = text || "";
    var seps = [" & ", " and ", " + "];
    for (var i = 0; i < seps.length; i++) {
      var at = text.indexOf(seps[i]);
      if (at > -1) return [text.slice(0, at).trim(), text.slice(at + seps[i].length).trim()];
    }
    return [text.trim()];
  }
  function mapsLink(name, address, url) {
    if (url) return url;
    var q = [name, address].filter(Boolean).join(", ");
    return q ? "https://www.google.com/maps/search/?api=1&query=" + quotePlus(q) : "";
  }
  function packageFeatures(code) {
    var p = D.packages.filter(function (x) { return x.code === code; })[0];
    return p ? p.features : [];
  }
  function hasFeature(ev, key) { return packageFeatures(ev.selected_package || "premium").indexOf(key) > -1; }

  function buildContext(ev, mode) {
    var group = groupOf(ev), dkey = designKey(ev), dsg = ev.design || {};
    var theme = resolve(dkey, dsg);
    var show = {};
    D.sections.forEach(function (s) { show[s[0]] = mode === "demo" || !s[2] || hasFeature(ev, s[2]); });
    var feat = function (key) { return mode === "demo" || hasFeature(ev, key); };
    var gs = ev.guest_settings || {}, venue = ev.venue || {}, info = ev.info || {};
    var hosts = ev.hosts || ev.name || "Your names";
    var deadline = gs.rsvp_deadline ? fmtDate(gs.rsvp_deadline) : "the date on your invitation";
    var defaults = D.group_wording[group] || D.group_wording.other;
    var raw = dsg.wording || {}, wording = {};
    Object.keys(defaults).forEach(function (k) {
      var text = (raw[k] || "").trim() || defaults[k];
      wording[k] = text.split("{hosts}").join(hosts).split("{deadline}").join(deadline);
    });
    if (raw.families) wording.families = raw.families;
    var d = parseDate(ev.event_date);
    var start = ev.start_time || "12:00";
    var funcs = (ev.functions || []).filter(function (f) { return f.name; });
    var fnames = {};
    funcs.forEach(function (f) { fnames[f.id] = f.name; });
    var schedule = (ev.schedule || []).filter(function (s) { return s.title; }).map(function (s) {
      return Object.assign({}, s, { function_name: s.function_id ? (fnames[s.function_id] || "") : "" });
    });
    var menus = [];
    var items = ((ev.menu || {}).items || []).filter(function (it) { return it.name; });
    if (items.length) menus.push({ name: (ev.menu || {}).name || "Menu", description: "", items: items });
    var meals = feat("menu") ? items.filter(function (it) { return it.selectable; }) : [];
    var imgs = ev.images || {};
    var names = splitNames(hosts);
    return {
      ev: ev, mode: mode, guest: null, form: {}, design: dkey, theme: theme, group: group, show: show, feat: feat,
      hosts: hosts, names: names, title: ev.name || hosts, description: ev.description || "",
      date: d, date_text: d ? fmtDate(ev.event_date) : "Date to be announced",
      time_text: [fmtTime(ev.start_time), fmtTime(ev.end_time)].filter(Boolean).join(" – "),
      countdown_iso: d ? ev.event_date + "T" + start + ":00+02:00" : "",
      venue: venue, info: info, gs: gs,
      map_url: mapsLink(venue.name || "", venue.address || "", venue.map_url || ""),
      functions: funcs, schedule: schedule, menus: menus, meals: meals,
      hero: imgs.hero || "", logo: imgs.logo || "", background: imgs.background || "", gallery: imgs.gallery || [],
      monogram: (dsg.monogram || "").trim() || names.map(function (n) { return n.charAt(0); }).join("").slice(0, 3).toUpperCase(),
      wording: wording, deadline_text: deadline, table: mode === "demo" ? "Table 4 · Jacaranda" : "",
      closed: "", allow: allowances(ev), guest_functions: {}, thanks: false, path: "#"
    };
  }
  function allowances(ev) {
    var gs = ev.guest_settings || {}, policy = gs.plus_one_policy || "per_guest";
    var def = parseInt(gs.plus_ones_default || 0, 10) || 0, plus;
    if (policy === "none") plus = 0; else plus = policy === "open" ? Math.max(def, 1) : def;
    var kids = gs.children_allowed ? (parseInt(gs.max_children || 0, 10) || 0) : 0;
    return { plus_ones: Math.max(0, Math.min(plus, 10)), children: Math.max(0, Math.min(kids, 10)) };
  }

  // --- designs.py -------------------------------------------------------------------------------
  var ORDER = ["invitation", "countdown", "venue", "programme", "menu", "dress_code", "rsvp", "seating", "accommodation", "registry", "gallery", "contact"];
  var TITLES = { invitation: "The invitation", countdown: "Counting down", venue: "Where and when", programme: "Programme", menu: "Menu",
    dress_code: "Dress code", rsvp: "RSVP", seating: "Your table", accommodation: "Where to stay", registry: "Gifts", gallery: "Gallery", contact: "Questions" };
  var NAV = { invitation: "Invitation", countdown: "Countdown", venue: "Venue", programme: "Programme", menu: "Menu", dress_code: "Dress code",
    rsvp: "RSVP", seating: "Seating", accommodation: "Stay", registry: "Gifts", gallery: "Gallery", contact: "Contact" };

  function p(text, cls) {
    if (!text) return "";
    var c = cls ? ' class="' + cls + '"' : "";
    return String(text).replace(/\r/g, "").split("\n\n").map(function (x) { return x.trim(); }).filter(Boolean)
      .map(function (x) { return "<p" + c + ">" + esc(x).replace(/\n/g, "<br>") + "</p>"; }).join("");
  }
  function namesHtml(ctx, amp) {
    var n = ctx.names;
    if (n.length === 2) return '<span class="ev-name">' + esc(n[0]) + '</span><span class="ev-amp" aria-hidden="true">' + amp +
      '</span><span class="sr-only"> and </span><span class="ev-name">' + esc(n[1]) + "</span>";
    return '<span class="ev-name">' + esc(n[0]) + "</span>";
  }
  function dateParts(ctx) {
    var d = ctx.date;
    if (!d) return { day: "", dd: "", month: "", mon: "", year: "", weekday: "" };
    return { day: String(d.getDate()), dd: pad2(d.getDate()), month: MONTHS[d.getMonth()], mon: MONTHS[d.getMonth()].slice(0, 3),
      year: String(d.getFullYear()), weekday: DAYS[d.getDay()] };
  }
  function btn(href, label, cls, external) {
    return '<a class="ev-btn ' + (cls || "") + '" href="' + esc(href) + '"' + (external ? ' target="_blank" rel="noopener"' : "") + ">" + esc(label) + "</a>";
  }
  function heroImage(ctx, cls, art) {
    cls = cls || "ev-photo";
    if (ctx.hero) return '<div class="' + cls + '"><img src="' + esc(ctx.hero) + '" alt="" loading="eager"></div>';
    return '<div class="' + cls + ' ev-photo--art" aria-hidden="true">' + (art || "") + "</div>";
  }

  function sInvitation(ctx) { return '<p class="ev-lead">' + esc(ctx.wording.invitation) + "</p>" + (ctx.description ? p(ctx.description, "ev-text") : ""); }
  function sCountdown(ctx) {
    if (!ctx.countdown_iso) return "";
    var cells = [["d", "Days"], ["h", "Hours"], ["m", "Minutes"], ["s", "Seconds"]].map(function (u) {
      return '<div class="ev-count__cell"><b data-u="' + u[0] + '">00</b><span>' + u[1] + "</span></div>"; }).join("");
    return '<div class="ev-count" data-countdown="' + esc(ctx.countdown_iso) + '" role="timer" aria-live="off">' + cells +
      '</div><p class="ev-count__done" hidden>The celebration has begun.</p>';
  }
  function sVenue(ctx) {
    var v = ctx.venue, out = "";
    if (v.name || v.address) {
      out += '<div class="ev-venue">';
      if (v.name) out += '<h3 class="ev-venue__name">' + esc(v.name) + "</h3>";
      if (v.address) out += '<p class="ev-venue__addr">' + esc(v.address) + "</p>";
      out += '<p class="ev-venue__time">' + esc(ctx.date_text) + (ctx.time_text ? " · " + esc(ctx.time_text) : "") + "</p>";
      if (ctx.map_url) out += '<div class="ev-actions">' + btn(ctx.map_url, "Open in Google Maps", "", true) + "</div>";
      out += "</div>";
    }
    var extras = [];
    if (v.parking) extras.push(["Parking", v.parking]);
    if (v.directions) extras.push(["Directions", v.directions]);
    if (extras.length) out += '<div class="ev-notes">' + extras.map(function (x) { return '<div class="ev-note"><h4>' + x[0] + "</h4>" + p(x[1]) + "</div>"; }).join("") + "</div>";
    if (ctx.functions.length > 1) {
      out += '<ol class="ev-funcs">';
      ctx.functions.forEach(function (f) {
        var when = [f.func_date ? fmtDate(f.func_date, false) : "", [fmtTime(f.start_time), fmtTime(f.end_time)].filter(Boolean).join(" – ")].filter(Boolean).join(" · ");
        var murl = f.map_url || ((f.venue_name || f.address) ? "https://www.google.com/maps/search/?api=1&query=" + quotePlus([f.venue_name, f.address].filter(Boolean).join(", ")) : "");
        out += '<li class="ev-func"><h3>' + esc(f.name) + "</h3>" + (when ? "<p class=ev-func__when>" + esc(when) + "</p>" : "") +
          ((f.venue_name || f.address) ? "<p class=ev-func__venue>" + esc(f.venue_name || "") + (f.address ? "<br>" + esc(f.address) : "") + "</p>" : "") +
          (murl ? btn(murl, "Map", "ev-btn--ghost ev-btn--sm", true) : "") + "</li>";
      });
      out += "</ol>";
    }
    return out;
  }
  function sProgramme(ctx) {
    var items = ctx.schedule;
    if (!items.length) return "";
    var groups = [];
    items.forEach(function (it) {
      var name = it.function_name || "";
      if (!groups.length || groups[groups.length - 1][0] !== name) groups.push([name, []]);
      groups[groups.length - 1][1].push(it);
    });
    return groups.map(function (g) {
      return (g[0] && groups.length > 1 ? '<h3 class="ev-prog__group">' + esc(g[0]) + "</h3>" : "") + '<ol class="ev-prog">' + g[1].map(function (it) {
        return '<li class="ev-prog__item ev-kind-' + esc(it.kind || "other") + '"><time>' + esc(fmtTime(it.item_time)) + "</time><div><h4>" + esc(it.title) +
          "</h4>" + p(it.description || "", "ev-small") + "</div></li>"; }).join("") + "</ol>";
    }).join("");
  }
  function sMenu(ctx) {
    var info = ctx.info;
    if (!ctx.menus.length && !info.drinks) return "";
    var out = "";
    ctx.menus.forEach(function (m) {
      out += '<div class="ev-menu"><h3 class="ev-menu__name">' + esc(m.name) + "</h3>";
      var course = null;
      m.items.forEach(function (it) {
        if (it.course !== course) {
          if (course !== null) out += "</ul>";
          course = it.course;
          out += '<h4 class="ev-menu__course">' + esc(course || "") + '</h4><ul class="ev-menu__items">';
        }
        var tags = (it.tags || []).map(function (t) { return '<span class="ev-tag">' + esc(t) + "</span>"; }).join("");
        var choice = it.selectable ? '<span class="ev-tag ev-tag--choice">Choose on RSVP</span>' : "";
        out += '<li><span class="ev-menu__dish">' + esc(it.name) + "</span>" + p(it.description || "", "ev-small") +
          (tags || choice ? "<span class=ev-tags>" + tags + choice + "</span>" : "") + "</li>";
      });
      if (course !== null) out += "</ul>";
      out += "</div>";
    });
    if (info.drinks) out += '<div class="ev-note"><h4>Drinks</h4>' + p(info.drinks) + "</div>";
    if (info.catering_notes) out += '<div class="ev-note"><h4>Catering notes</h4>' + p(info.catering_notes) + "</div>";
    return out;
  }
  function sDress(ctx) {
    var i = ctx.info;
    return i.dress_code ? '<p class="ev-dress">' + esc(i.dress_code) + "</p>" + p(i.dress_code_notes || "", "ev-text") : "";
  }
  function sSeating(ctx) {
    if (!ctx.table) return "";
    return '<div class="ev-table"><span class="ev-table__label">Your guest, you are seated at</span><strong class="ev-table__name">' + esc(ctx.table) +
      '</strong><span class="ev-small ev-muted">Your seat is shown only on your personal invitation link.</span></div>';
  }
  function sAccommodation(ctx) {
    var v = ctx.venue, items = (ctx.info.accommodation || []).filter(function (a) { return a.name || a.url; });
    if (!v.accommodation && !items.length) return "";
    var out = p(v.accommodation || "", "ev-text");
    if (items.length) out += '<ul class="ev-list">' + items.map(function (a) {
      return "<li><h4>" + (a.url ? '<a href="' + esc(a.url) + '" target=_blank rel=noopener>' + esc(a.name || "Link") + "</a>" : esc(a.name || "")) + "</h4>" + p(a.note || "", "ev-small") + "</li>"; }).join("") + "</ul>";
    return out;
  }
  function sRegistry(ctx) {
    var info = ctx.info, items = (info.registry || []).filter(function (r) { return r.name || r.url; });
    if (!items.length && !info.gift_note) return "";
    var out = p(info.gift_note || "", "ev-text");
    if (items.length) out += '<ul class="ev-list ev-list--reg">' + items.map(function (r) {
      return "<li><h4>" + esc(r.name || "Registry") + "</h4>" + p(r.note || "", "ev-small") + (r.url ? btn(r.url, "View registry", "ev-btn--ghost ev-btn--sm", true) : "") + "</li>"; }).join("") + "</ul>";
    return out;
  }
  function sGallery(ctx) {
    if (!ctx.gallery.length) return "";
    return '<div class="ev-gal">' + ctx.gallery.slice(0, 60).map(function (g, k) {
      if (g.url) return '<figure class="ev-gal__item"><img src="' + esc(g.url) + '" alt="' + esc(g.caption || "Event photo") + '" loading="lazy">' +
        (g.caption ? "<figcaption>" + esc(g.caption) + "</figcaption>" : "") + "</figure>";
      return '<figure class="ev-gal__item ev-gal__art ev-art-' + (k % 6) + '" aria-hidden="true"></figure>';
    }).join("") + "</div>";
  }
  function sContact(ctx) {
    var info = ctx.info, contacts = (info.contacts || []).filter(function (c) { return c.name || c.phone || c.email; });
    if (!contacts.length && !info.instructions) return "";
    var out = "";
    if (info.instructions) out += '<div class="ev-note"><h4>Good to know</h4>' + p(info.instructions) + "</div>";
    if (contacts.length) {
      out += '<ul class="ev-contacts">';
      contacts.forEach(function (c) {
        var links = "";
        if (c.phone) {
          var tel = c.phone.replace(/[^\d+]/g, ""), wa = tel.replace(/^\+/, "");
          if (wa.charAt(0) === "0") wa = "27" + wa.slice(1);
          links += '<a class="ev-btn ev-btn--ghost ev-btn--sm" href="tel:' + esc(tel) + '">Call ' + esc(c.phone) + "</a>" +
            '<a class="ev-btn ev-btn--ghost ev-btn--sm" href="https://wa.me/' + esc(wa) + '" target="_blank" rel="noopener">WhatsApp</a>';
        }
        if (c.email) links += '<a class="ev-btn ev-btn--ghost ev-btn--sm" href="mailto:' + esc(c.email) + '">Email</a>';
        out += "<li><h4>" + esc(c.name || "") + "</h4>" + (c.role ? "<p class=ev-small>" + esc(c.role) + "</p>" : "") + '<div class="ev-actions">' + links + "</div></li>";
      });
      out += "</ul>";
    }
    return out;
  }
  function field(name, label, type, required, hint) {
    return '<div class="ev-field"><label for="r-' + name + '">' + esc(label) + (required ? " <span aria-hidden=true>*</span>" : "") + "</label>" +
      '<input class="ev-input" id="r-' + name + '" name="' + name + '" type="' + (type || "text") + '" value=""' + (required ? " required" : "") + ">" +
      (hint ? "<span class=ev-hint>" + esc(hint) + "</span>" : "") + "</div>";
  }
  function numberSelect(name, label, max) {
    var o = "";
    for (var n = 0; n <= max; n++) o += '<option value="' + n + '">' + n + "</option>";
    return '<div class="ev-field"><label for="r-' + name + '">' + esc(label) + '</label><select class="ev-input" id="r-' + name + '" name="' + name + '">' + o + "</select></div>";
  }
  function rsvpForm(ctx) {
    var allow = ctx.allow;
    var parts = ['<p class="ev-rsvp__note">' + esc(ctx.wording.rsvp_note) + "</p>",
      '<div class="ev-grid2">' + field("first_name", "First name", "text", true) + field("last_name", "Surname", "text", true) + "</div>" +
      '<div class="ev-grid2">' + field("email", "Email", "email", true, "We'll send your confirmation here.") + field("phone", "Mobile (optional)", "tel") + "</div>",
      '<fieldset class="ev-choice"><legend>Will you attend?</legend><label class="ev-radio"><input type="radio" name="status" value="attending" required><span>Joyfully accepts</span></label>' +
      '<label class="ev-radio"><input type="radio" name="status" value="declined"><span>Regretfully declines</span></label></fieldset>'];
    var att = [];
    if (allow.plus_ones) att.push('<div class="ev-grid2">' + numberSelect("plus_ones", "Guests joining you (up to " + allow.plus_ones + ")", allow.plus_ones) + field("plus_one_names", "Their names") + "</div>");
    if (allow.children) att.push(numberSelect("children", "Children attending (up to " + allow.children + ")", allow.children));
    if (ctx.functions.length > 1 && ctx.feat("multi_functions")) {
      att.push('<fieldset class="ev-choice"><legend>Which parts will you attend?</legend>' + ctx.functions.map(function (f, k) {
        return '<label class="ev-check"><input type="checkbox" name="functions" value="' + k + '" checked><span>' + esc(f.name) + (f.func_date ? " · " + esc(fmtDate(f.func_date, false)) : "") + "</span></label>"; }).join("") + "</fieldset>");
    }
    if (ctx.meals.length) att.push('<div class="ev-field"><label for="r-meal">Meal choice</label><select class="ev-input" id="r-meal" name="meal_item_id"><option value="">Choose a meal</option>' +
      ctx.meals.map(function (m, k) { return '<option value="' + k + '">' + esc(m.name) + "</option>"; }).join("") + "</select></div>");
    if (ctx.feat("dietary")) {
      var offered = (ctx.info.dietary_options && ctx.info.dietary_options.length) ? ctx.info.dietary_options : D.dietary;
      att.push('<fieldset class="ev-choice ev-choice--wrap"><legend>Dietary requirements</legend>' + offered.map(function (o) {
        return '<label class="ev-check"><input type="checkbox" name="dietary" value="' + esc(o) + '"><span>' + esc(o) + "</span></label>"; }).join("") + "</fieldset>" +
        field("allergies", "Allergies we should know about"));
    }
    if (att.length) parts.push('<div class="ev-attending" data-attending>' + att.join("") + "</div>");
    parts.push('<div class="ev-field"><label for="r-req">Message or special requests</label><textarea class="ev-input" id="r-req" name="special_requests" rows="3"></textarea></div>');
    var note = ctx.mode === "demo" ? "This is a sample. RSVPs work on your own published event." : "Preview only: guests can reply once your website is published.";
    return '<form class="ev-rsvp" onsubmit="return false"><fieldset disabled>' + parts.join("") +
      '<button class="ev-btn ev-btn--wide" type="button">Send my reply</button></fieldset><p class="ev-small ev-muted">Your reply is shared only with the hosts. It is never shown to other guests.</p>' +
      '<p class="ev-small ev-muted">' + note + "</p></form>";
  }
  var BUILDERS = { invitation: sInvitation, countdown: sCountdown, venue: sVenue, programme: sProgramme, menu: sMenu, dress_code: sDress,
    rsvp: rsvpForm, seating: sSeating, accommodation: sAccommodation, registry: sRegistry, gallery: sGallery, contact: sContact };

  function collect(ctx) {
    var out = [];
    ORDER.forEach(function (k) { if (ctx.show[k]) { var h = BUILDERS[k](ctx); if (h) out.push([k, h]); } });
    return out;
  }
  function head(key, title, kicker) { return '<header class="ev-h">' + (kicker ? '<p class="ev-kicker">' + esc(kicker) + "</p>" : "") + '<h2 id="' + key + '-h">' + esc(title) + "</h2></header>"; }
  function section(key, inner, o) {
    o = o || {};
    return '<section class="ev-sec ev-sec--' + key + " " + (o.cls || "") + '" id="' + key + '" aria-labelledby="' + key + '-h"><div class="ev-sec__in">' +
      head(key, o.title || TITLES[key], o.kicker) + '<div class="ev-sec__body">' + inner + "</div></div></section>";
  }
  function nav(ctx, secs, cls, numbered) {
    if (secs.length < 3) return "";
    var items = "";
    secs.forEach(function (s, i) {
      if (s[0] === "countdown") return;
      items += '<li><a href="#' + s[0] + '">' + (numbered ? "<span class=ev-nav__n>" + pad2(i + 1) + "</span>" : "") + esc(NAV[s[0]]) + "</a></li>";
    });
    return '<nav class="' + (cls || "ev-nav") + '" aria-label="Event sections"><ul>' + items + "</ul></nav>";
  }
  function rsvpCta(ctx, label) { return ctx.show.rsvp ? '<a class="ev-btn" href="#rsvp">' + esc(label || "RSVP") + "</a>" : ""; }
  function kicker(ctx) { return '<p class="ev-kicker">' + esc(ctx.wording.welcome) + "</p>"; }

  var SPRIG = D.ornaments.sprig, FAN = D.ornaments.fan, DECO = D.ornaments.deco, CREST = D.ornaments.crest, MOON = D.ornaments.moon, STAR = D.ornaments.star;
  var CONFETTI = "";
  for (var ci = 0; ci < 14; ci++) CONFETTI += '<i class="cf cf-' + ci + '" aria-hidden="true"></i>';
  function beads(cls) {
    var tri = "";
    for (var k = 0; k < 4; k++) tri += '<path class="' + (k % 3 === 0 ? "bd-a" : k % 3 === 1 ? "bd-b" : "bd-c") + '" d="M' + (k * 24) + ' 22l12-18 12 18Z"/><path class="bd-d" d="M' + (k * 24 + 12) + ' 4l6 9-6 9-6-9Z"/>';
    var id = "bd" + (cls || "x");
    return '<div class="orn-beads ' + (cls || "") + '" aria-hidden="true"><svg width="100%" height="26"><defs><pattern id="' + id + '" width="96" height="26" patternUnits="userSpaceOnUse">' + tri +
      '<rect class="bd-c" y="23" width="96" height="3"/></pattern></defs><rect width="100%" height="26" fill="url(#' + id + ')"/></svg></div>';
  }
  function monogramRing(ctx, cls) {
    cls = cls || "ev-mono";
    if (ctx.logo) return '<div class="' + cls + " " + cls + '--logo"><img src="' + esc(ctx.logo) + '" alt="' + esc(ctx.hosts) + ' logo"></div>';
    return '<div class="' + cls + '" aria-hidden="true"><span>' + esc(ctx.monogram) + "</span></div>";
  }

  var LAYOUTS = {
    atelier: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var hero = '<header class="at-hero" id="welcome">' + monogramRing(ctx) + kicker(ctx) + '<h1 class="at-names">' + namesHtml(ctx, "&amp;") + '</h1><div class="at-rule" aria-hidden="true"></div>' +
        '<p class="at-date">' + esc(dp.weekday) + (dp.weekday ? ", " : "") + esc(dp.day) + " " + esc(dp.month) + " " + esc(dp.year) + '</p><p class="at-place">' + esc(ctx.venue.name || "") + "</p>" + rsvpCta(ctx, "Reply") + "</header>";
      var body = secs.map(function (s) { return section(s[0], s[1], { cls: "at-sec" }); }).join("");
      return hero + nav(ctx, secs, "ev-nav at-nav") + (ctx.hero ? '<div class="at-photo">' + heroImage(ctx) + "</div>" : "") + '<div class="at-col">' + body + "</div>";
    },
    folio: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var issue = { weddings: "The Wedding Issue", baby: "The Baby Issue", parties: "The Party Issue" }[ctx.group] || "The Occasion Issue";
      var art = '<span class="fo-art__mark">' + esc(ctx.monogram) + "</span>";
      var hero = '<header class="fo-hero" id="welcome"><div class="fo-mast"><span>' + esc(issue) + '</span><span class="mono">' + esc(dp.dd) + "." + esc(dp.mon).toUpperCase() + "." + esc(dp.year) + "</span></div>" +
        '<div class="fo-hero__grid"><div class="fo-hero__text">' + kicker(ctx) + '<h1 class="fo-title">' + namesHtml(ctx, "&amp;") + '</h1><p class="fo-deck">' + esc(ctx.wording.invitation) + "</p>" +
        '<div class="ev-actions">' + rsvpCta(ctx, "Reply to the invitation") + '</div></div><figure class="fo-hero__fig">' + heroImage(ctx, "ev-photo fo-photo", art) +
        "<figcaption>" + esc(ctx.venue.name || ctx.title) + " · " + esc(ctx.date_text) + "</figcaption></figure></div></header>";
      var body = secs.map(function (s, i) { return section(s[0], s[1], { kicker: pad2(i + 1), cls: "fo-sec" }); }).join("");
      return hero + '<div class="fo-body">' + nav(ctx, secs, "ev-nav fo-index", true) + '<div class="fo-main">' + body + "</div></div>";
    },
    bloom: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var hero = '<header class="bl-hero" id="welcome">' + SPRIG.replace("orn-sprig", "orn-sprig bl-tl") + SPRIG.replace("orn-sprig", "orn-sprig bl-br") + '<div class="bl-hero__in">' + kicker(ctx) +
        '<div class="bl-arch">' + heroImage(ctx, "ev-photo bl-arch__img", SPRIG) + '</div><h1 class="bl-names">' + namesHtml(ctx, "&amp;") + "</h1>" +
        '<p class="bl-date"><span>' + esc(dp.weekday) + "</span><b>" + esc(dp.day) + "</b><span>" + esc(dp.month) + " " + esc(dp.year) + "</span></p>" + rsvpCta(ctx, "Kindly reply") + "</div></header>";
      var body = secs.map(function (s, i) { return section(s[0], s[1], { cls: "bl-sec" }) + (i < secs.length - 1 ? '<div class="bl-div" aria-hidden="true">❀</div>' : ""); }).join("");
      return hero + nav(ctx, secs, "ev-nav bl-nav") + '<div class="bl-body">' + body + "</div>";
    },
    heritage: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx), sides = ctx.gs.sides || [], fam = "";
      if (sides.length && (ctx.group === "weddings" || ctx.group === "other")) {
        fam = '<section class="ev-sec hr-fam" aria-labelledby="fam-h"><div class="ev-sec__in">' + head("fam", "Two families, one celebration", "Umndeni") +
          '<p class="ev-text">' + esc(ctx.wording.families || "With the blessing of our elders and the joy of both families, we welcome you.") + '</p><ul class="hr-fam__list">' +
          sides.slice(0, 4).map(function (s) { return '<li><span class="hr-fam__mark" aria-hidden="true">◆</span><h3>' + esc(s) + "</h3></li>"; }).join("") + "</ul></div></section>";
      }
      var hero = beads("hr-top") + '<header class="hr-hero" id="welcome"><div class="hr-hero__text">' + kicker(ctx) + '<h1 class="hr-names">' + namesHtml(ctx, "&amp;") + "</h1>" +
        '<p class="hr-date">' + esc(dp.day) + " · " + esc(dp.month) + " · " + esc(dp.year) + '</p><p class="ev-text">' + esc(ctx.venue.name || "") + '</p><div class="ev-actions">' + rsvpCta(ctx, "Respond") + "</div></div>" +
        '<div class="hr-hero__mark"><div class="hr-diamond">' + heroImage(ctx, "ev-photo hr-photo", "<span>" + esc(ctx.monogram) + "</span>") + "</div></div></header>" + beads("hr-mid");
      var body = "";
      secs.forEach(function (s, n) {
        var title = s[0] === "venue" && ctx.functions.length > 1 ? "The ceremonies" : TITLES[s[0]];
        body += section(s[0], s[1], { title: title, cls: "hr-sec" + (n % 2 ? " hr-sec--alt" : "") });
        if (s[0] === "invitation" && fam) { body += fam; fam = ""; }
      });
      return hero + nav(ctx, secs, "ev-nav hr-nav") + fam + body + beads("hr-bottom");
    },
    champagne: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var hero = '<header class="ch-hero" id="welcome">' + FAN + '<div class="ch-hero__in">' + kicker(ctx) + '<h1 class="ch-names foil">' + namesHtml(ctx, "&amp;") + "</h1>" + DECO +
        '<p class="ch-date"><span>' + esc(dp.weekday) + '</span><b class="foil">' + esc(dp.dd) + "</b><span>" + esc(dp.month) + " " + esc(dp.year) + "</span></p>" +
        '<p class="ch-place">' + esc(ctx.venue.name || "") + "</p>" + rsvpCta(ctx, "RSVP") + "</div></header>";
      var body = secs.map(function (s) { return section(s[0], s[1], { cls: "ch-sec ch-glass" }); }).join("");
      return hero + nav(ctx, secs, "ev-nav ch-nav") + (ctx.hero ? '<div class="ch-photo">' + heroImage(ctx) + "</div>" : "") + '<div class="ch-body">' + body + "</div>";
    },
    linea: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx), v = ctx.venue;
      var meta = '<dl class="li-meta"><div><dt>Date</dt><dd>' + esc(dp.day) + " " + esc(dp.month) + " " + esc(dp.year) + "</dd></div><div><dt>Time</dt><dd>" + esc(ctx.time_text || "To be confirmed") +
        "</dd></div><div><dt>Place</dt><dd>" + esc(v.name || "To be confirmed") + "</dd></div></dl>";
      var hero = '<header class="li-hero" id="welcome"><div class="li-hero__top"><span class="li-mono">' + esc(ctx.monogram) + "</span>" + nav(ctx, secs, "ev-nav li-nav") + "</div>" + kicker(ctx) +
        '<h1 class="li-names">' + namesHtml(ctx, "+") + "</h1>" + meta + (ctx.hero ? "<div class=li-photo>" + heroImage(ctx) + "</div>" : "") + "</header>";
      var rows = secs.map(function (s, i) {
        return '<section class="ev-sec li-row ev-sec--' + s[0] + '" id="' + s[0] + '" aria-labelledby="' + s[0] + '-h"><div class="li-row__label"><span class="li-row__n">' + pad2(i + 1) +
          '</span><h2 id="' + s[0] + '-h">' + esc(TITLES[s[0]]) + '</h2></div><div class="li-row__body ev-sec__body">' + s[1] + "</div></section>"; }).join("");
      return hero + '<div class="li-body">' + rows + "</div>";
    },
    confetti: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var hero = '<header class="cf-hero" id="welcome"><div class="cf-sky">' + CONFETTI + '</div><div class="cf-card">' + kicker(ctx) + '<h1 class="cf-names">' + namesHtml(ctx, "&amp;") + "</h1>" +
        '<div class="cf-sticker"><b>' + esc(dp.day) + "</b><span>" + esc(dp.mon) + '</span></div><p class="cf-when">' + esc(ctx.date_text) + (ctx.time_text ? " · " + esc(ctx.time_text) : "") + "</p>" + rsvpCta(ctx, "Count me in") + "</div></header>";
      var cards = secs.map(function (s, i) { return section(s[0], s[1], { cls: "cf-sec cf-tone-" + (i % 4) }); }).join("");
      return hero + nav(ctx, secs, "ev-nav cf-nav") + (ctx.hero ? '<div class="cf-photo">' + heroImage(ctx) + "</div>" : "") + '<div class="cf-board">' + cards + "</div>";
    },
    pulse: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var tick = [ctx.hosts, ctx.date_text, ctx.venue.name || "", "RSVP by " + ctx.deadline_text].filter(Boolean).map(esc).join(" ✦ ");
      var hero = '<header class="pu-hero" id="welcome">' + kicker(ctx) + '<h1 class="pu-names">' + namesHtml(ctx, "+") + '</h1><div class="pu-date"><b>' + esc(dp.dd) + "</b><span>" + esc(dp.month) + "<br>" + esc(dp.year) +
        '</span><div class="ev-actions">' + rsvpCta(ctx, "I am in") + '</div></div></header><div class="pu-ticker" aria-hidden="true"><div class="pu-ticker__track"><span>' + tick + " ✦ </span><span>" + tick + " ✦ </span><span>" + tick + " ✦ </span></div></div>";
      var blocks = secs.map(function (s, i) { return section(s[0], s[1], { title: TITLES[s[0]], kicker: pad2(i + 1) + "/" + pad2(secs.length), cls: "pu-sec pu-tone-" + ((i + 1) % 3) }); }).join("");
      return hero + (ctx.hero ? '<div class="pu-photo">' + heroImage(ctx) + "</div>" : "") + nav(ctx, secs, "ev-nav pu-nav") + blocks;
    },
    aurora: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var chips = [(dp.weekday + " " + dp.day + " " + dp.month + " " + dp.year).trim(), ctx.time_text, ctx.venue.name || ""].filter(Boolean)
        .map(function (x) { return '<span class="au-chip">' + esc(x) + "</span>"; }).join("");
      var hero = '<header class="au-hero" id="welcome"><div class="au-glass au-hero__card">' + kicker(ctx) + '<h1 class="au-names">' + namesHtml(ctx, "&amp;") + '</h1><div class="au-chips">' + chips +
        '</div><div class="ev-actions">' + rsvpCta(ctx, "RSVP") + "</div></div></header>";
      var wide = { invitation: 1, rsvp: 1, programme: 1, gallery: 1, menu: 1, venue: 1 };
      var cards = secs.map(function (s) { return section(s[0], s[1], { cls: "au-glass au-card" + (wide[s[0]] ? " au-card--wide" : "") }); }).join("");
      return '<div class="au-field" aria-hidden="true"><i></i><i></i><i></i><i></i></div>' + hero + nav(ctx, secs, "ev-nav au-nav au-glass") + '<div class="au-bento">' +
        (ctx.hero ? '<div class="au-glass au-photo">' + heroImage(ctx) + "</div>" : "") + cards + "</div>";
    },
    laureate: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var crest = ctx.logo ? monogramRing(ctx, "la-logo") : '<div class="la-crest">' + CREST + '<span class="la-crest__mono">' + esc(ctx.monogram) + "</span></div>";
      var hero = '<header class="la-hero" id="welcome"><div class="la-frame">' + crest + kicker(ctx) + '<h1 class="la-names">' + namesHtml(ctx, "&amp;") + '</h1><p class="la-formal">' + esc(ctx.wording.invitation) +
        '</p><p class="la-date">' + esc(dp.weekday) + " the " + esc(dp.day) + " of " + esc(dp.month) + ", " + esc(dp.year) + "</p>" + rsvpCta(ctx, "Respond") + "</div></header>";
      var mainKeys = { invitation: 1, programme: 1, menu: 1, rsvp: 1, gallery: 1, countdown: 1 };
      var main = secs.filter(function (s) { return mainKeys[s[0]] && s[0] !== "invitation"; }).map(function (s) { return section(s[0], s[1], { cls: "la-sec" }); }).join("");
      var inv = (secs.filter(function (s) { return s[0] === "invitation"; })[0] || [0, ""])[1];
      var side = secs.filter(function (s) { return !mainKeys[s[0]]; }).map(function (s) { return section(s[0], s[1], { cls: "la-sec la-side" }); }).join("");
      return hero + nav(ctx, secs, "ev-nav la-nav") + (ctx.hero ? '<div class="la-photo">' + heroImage(ctx) + "</div>" : "") +
        (inv ? section("invitation", inv, { title: "With pleasure", cls: "la-sec la-inv" }) : "") +
        '<div class="la-cols"><div class="la-main">' + main + '</div><aside class="la-aside" aria-label="Details">' + side + "</aside></div>";
    },
    cradle: function (ctx) {
      var dp = dateParts(ctx), secs = collect(ctx);
      var hero = '<header class="cr-hero cr-page" id="welcome">' + MOON + kicker(ctx) + '<h1 class="cr-names">' + namesHtml(ctx, "&amp;") + '</h1><p class="cr-date">' + esc(dp.weekday) + ", " + esc(dp.day) + " " + esc(dp.month) + " " + esc(dp.year) + "</p>" +
        (ctx.hero ? "<div class=cr-photo>" + heroImage(ctx) + "</div>" : "") + rsvpCta(ctx, "Reply") + '<span class="cr-pageno">i</span></header>';
      var pages = secs.map(function (s, i) {
        return section(s[0], s[1], { kicker: "Chapter " + (i + 1), cls: "cr-page cr-sec" }).replace("</div></section>", '</div><span class="cr-pageno">' + (i + 1) + "</span>" + STAR + "</section>"); }).join("");
      return hero + nav(ctx, secs, "ev-nav cr-nav") + '<div class="cr-book">' + pages + "</div>";
    }
  };

  function render(ev, mode) {
    mode = mode || "preview";
    var ctx = buildContext(ev, mode);
    var body = (LAYOUTS[ctx.design] || LAYOUTS.atelier)(ctx);
    var t = ctx.theme;
    var title = ctx.date ? ctx.title + " · " + ctx.date_text : ctx.title;
    var bgImg = ctx.background || (t.background === "image" ? ctx.hero : "");
    var style = cssVars(t) + contrastVars(t.colors) + (bgImg ? "--ev-bg-image:url('" + bgImg + "');" : "");
    var classes = "ev d-" + ctx.design + " bg-" + t.background + " grp-" + ctx.group + (ctx.hero ? " has-hero" : "");
    var banner = mode === "preview" ? '<div class="ev-banner" role="note">Preview · not visible to guests until you publish</div>' : "";
    return '<!doctype html><html lang="en-ZA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + esc(title) + "</title>" +
      '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
      '<link rel="stylesheet" href="' + esc(fontsUrl(t.display, t.body)) + '"><link rel="stylesheet" href="static/css/eventsite.css">' +
      '<script>document.addEventListener("click",function(e){var a=e.target.closest("a[href^=\'#\']");if(a){e.preventDefault();var el=document.getElementById(a.getAttribute("href").slice(1));if(el)el.scrollIntoView({behavior:"smooth"});}});<\/script>' +
      '</head><body class="' + classes + '" style="' + esc(style) + '"><a class="ev-skip" href="#ev-main">Skip to content</a>' + banner + '<main id="ev-main">' + body + "</main>" +
      '<footer class="ev-foot"><p>' + esc(ctx.wording.closing) + '</p><p class="ev-made"><a href="#welcome">Made with ' + esc(D.brand) + "</a></p></footer>" +
      '<script src="static/js/eventsite.js"><\/script></body></html>';
  }

  window.AureliaRender = { render: render, fmtDate: fmtDate, resolve: resolve, esc: esc, groupOf: groupOf, hasFeature: hasFeature, packageFeatures: packageFeatures };
})();
