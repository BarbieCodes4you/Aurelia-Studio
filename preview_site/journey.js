/* Aurelia customer journey for the shareable site: choose occasion and template, the 10-step set-up,
   live preview, package choice and booking request. Runs entirely in the visitor's browser; drafts are
   kept in localStorage. Mirrors the fields and rules of app/views/wizard.py.
   Exposes window.AureliaJourney.route(hashId). */
(function () {
  "use strict";
  var D = window.AURELIA_DATA, R = window.AureliaRender, esc = R.esc;
  var KEY = "aurelia-journey-v1";
  var HOST = D.host_label;
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
        var e = s.events[id];
        if (e && !e.v) {           // drafts from the 10-step version: map step numbers onto the 8 steps
          var map = { 1: 1, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 8 };
          e.wizard_done = (e.wizard_done || []).map(function (n) { return map[n] || n; }).filter(function (n, k, a) { return a.indexOf(n) === k; });
          e.guest_list = e.guest_list || []; e.v = 2;
        }
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
  function plural(n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); }
  function joinOr(parts) { return parts.length === 1 ? parts[0] : parts.slice(0, -1).join(", ") + " or " + parts[parts.length - 1]; }

  // --- ready-made content and parsers (mirror app/suggestions.py) ---------------------------------
  var SUG = D.suggest || { wording: {}, programmes: {}, programme_for: {}, default_start: {} };
  function autoName(category, hosts) {
    var h = (hosts || "").trim(), noun = (SUG.name_noun || {})[category];
    if (!h || !noun) return h;
    return h + (/s$/.test(h) && !/'s$/.test(h) ? "' " : "'s ") + noun;
  }
  function wordingOptions(ev) { return SUG.wording[ev.category] || SUG.wording["private-celebration"] || []; }
  function fillWording(text, hosts, deadline) {
    text = text.split("{hosts}").join(hosts || "the hosts");
    return deadline ? text.split("{deadline}").join(deadline) : text.replace(/\s*by \{deadline\}/g, "").split("{deadline}").join("");
  }
  var KIND_WORDS = [["meal", ["dinner", "lunch", "breakfast", "brunch", "meal", "food", "starter", "main course", "dessert", "cake", "canap", "braai", "buffet", "tea", "supper", "snack"]],
    ["ceremony", ["ceremony", "vows", "wedding", "negotiation", "lobola", "blessing", "prayer", "unveiling", "graduation", "church", "service", "ritual", "exchange of gifts", "umembeso", "umabo"]],
    ["speech", ["speech", "toast", "welcome", "remarks", "introduction", "thanks", "keynote", "panel", "announcement"]],
    ["entertainment", ["dance", "music", "dj", "band", "entertainment", "party", "reveal", "performance", "choir", "show"]],
    ["reception", ["reception", "seated", "drinks", "cocktail", "arrival of the couple", "entrance"]], ["activity", ["photo", "games", "gift", "workshop", "registration", "tour"]]];
  function guessKind(title) {
    var t = (title || "").toLowerCase();
    for (var i = 0; i < KIND_WORDS.length; i++) if (KIND_WORDS[i][1].some(function (w) { return t.indexOf(w) > -1; })) return KIND_WORDS[i][0];
    return "other";
  }
  function sampleProgramme(ev) {
    var key = SUG.programme_for[ev.category] || ev.category;
    if (!SUG.programmes[key]) key = "private-celebration";
    var start = /^\d{2}:\d{2}$/.test(ev.start_time || "") ? ev.start_time : (SUG.default_start[groupOf(ev)] || "12:00");
    var base = +start.slice(0, 2) * 60 + +start.slice(3);
    return (SUG.programmes[key] || []).map(function (x) {
      var t = ((base + x[0]) % 1440 + 1440) % 1440;
      return { item_time: ("0" + Math.floor(t / 60)).slice(-2) + ":" + ("0" + t % 60).slice(-2), title: x[1], kind: x[2], description: x[3], function_id: "" };
    });
  }
  var HEADER_WORDS = ["name", "names", "full name", "guest", "guests", "guest name", "first name", "surname", "last name", "phone", "mobile", "cell",
    "cellphone", "phone number", "whatsapp", "email", "e-mail", "email address"];
  function saPhone(p) {
    var d = String(p || "").replace(/\D/g, "");
    return d.length === 9 && "678".indexOf(d[0]) > -1 && String(p).trim().charAt(0) !== "+" ? "0" + d : String(p || "").trim();
  }
  function parseGuests(text) {
    var out = [], seen = {}, group = "";
    (text || "").split(/\r?\n/).forEach(function (raw) {
      var line = raw.trim().replace(/^[,;\t]+|[,;\t]+$/g, "");
      if (!line) return;
      if (/:$/.test(line) && !/@/.test(line) && !/\d{6,}/.test(line.replace(/\D/g, ""))) { group = line.slice(0, -1).trim().slice(0, 60); return; }
      var cells = line.split(/[,;\t|]+/).map(function (c) { return c.trim().toLowerCase(); }).filter(Boolean);
      if (cells.length && cells.every(function (c) { return HEADER_WORDS.indexOf(c) > -1; })) return;
      var em = /[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}/.exec(line), rest = em ? line.replace(em[0], " ") : line;
      var ph = /\+?\d[\d ()-]{6,}\d/.exec(rest);
      if (ph) rest = rest.replace(ph[0], " ");
      var name = rest.replace(/[,;\t|]+/g, " ").replace(/\s+/g, " ").replace(/^[ -]+|[ -]+$/g, "");
      if (!name) return;
      var key = name.toLowerCase() + "|" + (em ? em[0].toLowerCase() : "");
      if (seen[key]) return;
      seen[key] = 1;
      out.push({ name: name.slice(0, 120), phone: ph ? saPhone(ph[0]) : "", email: em ? em[0].toLowerCase() : "", group: group });
    });
    return out.slice(0, 2000);
  }
  var COLS = { name: ["name", "full name", "guest", "guest name", "names", "guest names"], first: ["first name", "first", "firstname", "given name"],
    last: ["surname", "last name", "last", "lastname", "family name"], phone: ["phone", "mobile", "cell", "cellphone", "whatsapp", "number", "phone number", "mobile number", "contact", "tel"],
    email: ["email", "e-mail", "email address", "mail"], group: ["family", "family group", "group", "side", "household"] };
  function parseSheet(rows) {
    rows = rows.map(function (r) { return r.map(function (c) { return String(c == null ? "" : c).trim(); }); }).filter(function (r) { return r.some(Boolean); });
    if (!rows.length) return [];
    var head = rows[0].map(function (c) { return c.toLowerCase(); }), col = {};
    Object.keys(COLS).forEach(function (k) { var at = head.findIndex(function (h) { return COLS[k].indexOf(h) > -1; }); col[k] = at < 0 ? null : at; });
    if (col.name === null && col.first === null) return parseGuests(rows.map(function (r) { return r.filter(Boolean).join(", "); }).join("\n"));
    var get = function (r, k) { return col[k] !== null && col[k] < r.length ? r[col[k]] : ""; }, out = [], seen = {};
    rows.slice(1).forEach(function (r) {
      var name = get(r, "name") || get(r, "first"), last = get(r, "last");
      if (last && name.toLowerCase().indexOf(last.toLowerCase()) < 0) name = name + " " + last;
      name = name.replace(/\s+/g, " ").trim();
      if (!name) return;
      var em = /[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}/.exec(get(r, "email")), key = name.toLowerCase() + "|" + (em ? em[0].toLowerCase() : "");
      if (seen[key]) return;
      seen[key] = 1;
      out.push({ name: name.slice(0, 120), phone: saPhone(get(r, "phone")), email: em ? em[0].toLowerCase() : "", group: get(r, "group").slice(0, 60) });
    });
    return out.slice(0, 2000);
  }
  // Spreadsheets: .csv, or .xlsx (Excel and Google Sheets downloads) read with a small zip reader.
  function parseCsv(text) {
    var first = text.split(/\r?\n/)[0] || "", delim = [",", ";", "\t"].sort(function (a, b) { return first.split(b).length - first.split(a).length; })[0];
    var rows = [], row = [], cell = "", q = false;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (q) { if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += ch; }
      else if (ch === '"') q = true;
      else if (ch === delim) { row.push(cell); cell = ""; }
      else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
      else cell += ch;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    return rows;
  }
  function readXlsx(buf) {
    var u8 = new Uint8Array(buf), dv = new DataView(buf), i, files = {};
    for (i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) break;
    if (i < 0) return Promise.reject(new Error("bad zip"));
    var count = dv.getUint16(i + 10, true), p = dv.getUint32(i + 16, true), td = new TextDecoder();
    for (var k = 0; k < count && dv.getUint32(p, true) === 0x02014b50; k++) {
      var nlen = dv.getUint16(p + 28, true), name = td.decode(u8.subarray(p + 46, p + 46 + nlen));
      files[name] = { method: dv.getUint16(p + 10, true), size: dv.getUint32(p + 20, true), at: dv.getUint32(p + 42, true) };
      p += 46 + nlen + dv.getUint16(p + 30, true) + dv.getUint16(p + 32, true);
    }
    function read(name) {
      var f = files[name];
      if (!f) return Promise.resolve("");
      var start = f.at + 30 + dv.getUint16(f.at + 26, true) + dv.getUint16(f.at + 28, true), data = u8.subarray(start, start + f.size);
      return (f.method === 0 ? Promise.resolve(data) : through(data, new DecompressionStream("deflate-raw"))).then(function (b) { return td.decode(b); });
    }
    var sheet = files["xl/worksheets/sheet1.xml"] ? "xl/worksheets/sheet1.xml" : Object.keys(files).filter(function (n) { return /^xl\/worksheets\/sheet\d+\.xml$/.test(n); }).sort()[0];
    if (!sheet) return Promise.reject(new Error("no sheet"));
    return Promise.all([read("xl/sharedStrings.xml"), read(sheet)]).then(function (x) {
      var dp = new DOMParser(), shared = [];
      if (x[0]) Array.prototype.forEach.call(dp.parseFromString(x[0], "application/xml").getElementsByTagName("si"), function (si) {
        shared.push(Array.prototype.map.call(si.getElementsByTagName("t"), function (t) { return t.textContent; }).join("")); });
      return Array.prototype.map.call(dp.parseFromString(x[1], "application/xml").getElementsByTagName("row"), function (row) {
        var out = [];
        Array.prototype.forEach.call(row.getElementsByTagName("c"), function (c) {
          var ref = /^([A-Z]+)/.exec(c.getAttribute("r") || "A")[1], n = 0;
          for (var j = 0; j < ref.length; j++) n = n * 26 + ref.charCodeAt(j) - 64;
          var t = c.getAttribute("t"), v = c.getElementsByTagName("v")[0], value;
          if (t === "s") value = shared[+(v ? v.textContent : -1)] || "";
          else if (t === "inlineStr") value = Array.prototype.map.call(c.getElementsByTagName("t"), function (e) { return e.textContent; }).join("");
          else value = v ? v.textContent.replace(/\.0$/, "") : "";
          out[n - 1] = value;
        });
        return Array.from(out, function (c) { return c || ""; });
      });
    });
  }
  function readSheetFile(file) {
    return file.arrayBuffer().then(function (buf) {
      var head = new Uint8Array(buf.slice(0, 2));
      if (head[0] === 0x50 && head[1] === 0x4b) {
        if (!window.DecompressionStream) throw new Error("old browser");
        return readXlsx(buf);
      }
      return parseCsv(new TextDecoder().decode(buf).replace(/^\ufeff/, ""));
    });
  }
  var COURSE_WORDS = {
    "Canapés": ["canapé", "canape", "canapés", "canapes", "snacks", "hors d'oeuvres", "on arrival"],
    "Starter": ["starter", "starters", "entrée", "entree", "entrées", "appetiser", "appetisers", "appetizer", "appetizers", "first course"],
    "Main": ["main", "mains", "main course", "main courses", "buffet", "main meal"],
    "Dessert": ["dessert", "desserts", "pudding", "sweet", "sweets"],
    "Late-night": ["late-night", "late night", "late night snack", "midnight snack"],
    "Drinks": ["drinks", "beverages", "bar"]
  };
  function courseOf(word) {
    var w = word.trim().replace(/^:+|:+$/g, "").trim().toLowerCase();
    return Object.keys(COURSE_WORDS).filter(function (c) { return COURSE_WORDS[c].indexOf(w) > -1; })[0] || "";
  }
  function parseMenu(text) {
    var items = [], course = "Main";
    (text || "").split(/\r?\n/).forEach(function (raw) {
      var line = raw.trim().replace(/^[•*\-·– ]+/, "").trim();
      if (!line || items.length >= 60) return;
      var c = courseOf(line);
      if (c) { course = c; return; }
      var m = /^([^:]{2,30}):\s*(.+)$/.exec(line), here = course;
      if (m && courseOf(m[1])) { here = course = courseOf(m[1]); line = m[2].trim(); }
      var name = line, desc = "", seps = [" - ", " – ", " — ", " | "], k;
      for (k = 0; k < seps.length; k++) {
        var at = line.indexOf(seps[k]);
        if (at > -1) { name = line.slice(0, at).trim(); desc = line.slice(at + seps[k].length).trim(); break; }
      }
      if (k === seps.length) { var b = /^(.+?)\s*\((.+)\)$/.exec(line); if (b) { name = b[1].trim(); desc = b[2].trim(); } }
      if (name) items.push({ course: here, name: name.slice(0, 120), description: desc.slice(0, 240), tags: [], selectable: false });
    });
    return items;
  }

  // --- what a package would leave out (mirror events.package_gaps) ----------------------------------
  function gaps(ev, code) {
    var p = pkg(code) || {}, feats = p.features || [], lim = p.limits || {}, out = [], n, allowed;
    var has = function (k) { return feats.indexOf(k) > -1; };
    n = ev.schedule.length; if (n && !has("programme")) out.push("your programme (" + plural(n, "item") + ")");
    n = ev.menu.items.length; if (n && !has("menu")) out.push("your menu (" + plural(n, "dish", "dishes") + ")");
    if (ev.tables.chosen && !has("seating")) out.push("your seating layout");
    n = (ev.images.gallery || []).length; allowed = has("gallery") ? (lim.gallery_photos || 0) : 0;
    if (n > allowed) out.push(allowed ? (n - allowed) + " of your " + n + " gallery photos" : "your photo gallery (" + plural(n, "photo") + ")");
    n = ev.functions.length; allowed = has("multi_functions") ? (lim.functions || 1) : 1;
    if (n > allowed) out.push((n - allowed) + " of your " + n + " event functions");
    if (ev.design.colors && !has("advanced_design")) out.push("your own colours");
    n = (ev.guest_list || []).length; if (n && !has("guest_management")) out.push("your guest list (" + plural(n, "guest") + ")");
    return out;
  }

  // --- links that carry a draft: continue on another device, or show someone ----------------------------
  function b64url(bytes) { var s = ""; for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function unb64url(str) {
    str = str.replace(/-/g, "+").replace(/_/g, "/");
    while (str.length % 4) str += "=";
    var s = atob(str), b = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    return b;
  }
  function through(bytes, stream) { return new Response(new Blob([bytes]).stream().pipeThrough(stream)).arrayBuffer().then(function (b) { return new Uint8Array(b); }); }
  function pack(ev, forSharing) {
    var copy = Object.assign({}, ev, { images: undefined });
    if (forSharing) { copy.contact = { name: "", email: "", phone: "" }; copy.guest_list = []; copy.booking = null; }
    var bytes = new TextEncoder().encode(JSON.stringify(copy));
    if (window.CompressionStream) return through(bytes, new CompressionStream("deflate-raw")).then(function (z) { return "z" + b64url(z); });
    return Promise.resolve("j" + b64url(bytes));
  }
  function safeUrl(u) { return /^https?:\/\/[^\s<>"]+$/i.test(u || "") ? u : ""; }
  function clean(raw) {
    if (!raw || typeof raw !== "object" || !cat(raw.category) || !tpl(raw.template)) throw new Error("Not an event draft");
    var ev = newEvent(raw.category, raw.template, String(raw.name || ""));
    ["id", "created", "updated", "hosts", "description", "event_date", "start_time", "end_time", "ends_next_day", "selected_package", "booking"].forEach(function (k) { if (raw[k] !== undefined) ev[k] = raw[k]; });
    ["contact", "venue", "design", "guest_settings", "menu", "info", "tables"].forEach(function (k) { if (raw[k] && typeof raw[k] === "object") ev[k] = Object.assign(ev[k], raw[k]); });
    ["functions", "schedule", "wizard_done", "guest_list"].forEach(function (k) { if (Array.isArray(raw[k])) ev[k] = raw[k]; });
    if (!/^e[a-z0-9]{4,12}$/.test(String(ev.id))) ev.id = uid("e");
    if (!pkg(ev.selected_package)) ev.selected_package = "premium";
    ev.images = { gallery: [] };
    ev.venue.map_url = safeUrl(ev.venue.map_url);
    ev.functions.forEach(function (f) { f.map_url = safeUrl(f.map_url); });
    ["registry", "accommodation"].forEach(function (k) { (ev.info[k] || []).forEach(function (r) { r.url = safeUrl(r.url); }); });
    return ev;
  }
  function unpack(code) {
    return new Promise(function (resolve) { resolve(unb64url(code.slice(1))); }).then(function (bytes) {
      if (code.charAt(0) === "z") {
        if (!window.DecompressionStream) throw new Error("This browser is too old to open the link. Try Chrome, Safari or Edge.");
        return through(bytes, new DecompressionStream("deflate-raw"));
      }
      return bytes;
    }).then(function (b) { return clean(JSON.parse(new TextDecoder().decode(b))); });
  }
  function pageUrl() { return location.href.split("#")[0]; }
  function shareOrCopy(url, title, done) {
    if (navigator.share && /Android|iPhone|iPad/i.test(navigator.userAgent)) { navigator.share({ title: title, url: url }).catch(function () {}); return; }
    var fallback = function () { window.prompt("Copy this link:", url); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { toast(done); }, fallback); else fallback();
  }

  // --- sending to Aurelia (Netlify Forms on the hosted static site) ---------------------------------------
  function dataUrlBlob(u) {
    var m = /^data:([^;,]+)(;base64)?,(.*)$/.exec(u || "");
    if (!m) return null;
    var s = m[2] ? atob(m[3]) : decodeURIComponent(m[3]), b = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    return new Blob([b], { type: m[1] });
  }
  function postForm(name, fields, files) {
    if (!D.forms) return Promise.reject(new Error("Forms are off on this copy of the site"));
    var fd = new FormData();
    fd.append("form-name", name);
    Object.keys(fields).forEach(function (k) { fd.append(k, fields[k] == null ? "" : String(fields[k])); });
    (files || []).forEach(function (f) { if (f[1]) fd.append(f[0], f[1], f[2]); });
    return fetch("/", { method: "POST", body: fd }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); });
  }

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
    }).filter(function (r) { return Object.keys(r).some(function (k) { return ["id", "kind", "function", "course"].indexOf(k) < 0 && r[k]; }); });
  }
  function featureNote(ev, key, what) {
    if (feature(ev, key)) return "";
    var need = D.packages.filter(function (p) { return p.features.indexOf(key) > -1; })[0];
    return '<div class="notice notice--warn">' + icon("lock") + "<span>" + esc(what) + " shows on your website with the " + esc(need ? need.name : "a higher package") +
      ". You can fill it in now and choose your package at the last step.</span></div>";
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
      info: { dietary_options: ["Vegetarian", "Vegan", "Halal", "Gluten-free", "Nut allergy"] }, tables: { count: "", capacity: 10, shape: "round", names: [], plan_now: false },
      guest_list: [], selected_package: "premium", wizard_done: [], booking: null, v: 2 };
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
      '<h1>Let\'s create your <span class="serif grad">event</span></h1><p class="lead">Three quick questions, then we build your website as you go. Everything is saved in this browser, and nothing is charged until you\'re ready.</p>' +
      '<p class="small" style="margin-top:14px">' + (state.order.length ? '<a class="text-link" href="#my-events">Continue an event you started</a> · ' : "") + 'Rather have us do it? <a class="text-link" href="#help-me-set-up">We can set it up for you</a>.</p></div></section>' +
      '<section class="section"><div class="container"><form class="form" data-create data-no-busy novalidate><div data-errors></div>' +
      '<div class="box" data-field="category"><h2 style="font-size:1.25rem;margin-bottom:16px">1. What are you celebrating?</h2>' + groups + "</div>" +
      '<div class="box" data-field="template"><h2 style="font-size:1.25rem;margin-bottom:6px">2. Choose a starting template</h2><p class="muted small" style="margin-bottom:16px">These templates suit your occasion. You can switch any time in the design step. <a class="text-link" href="#templates">Preview the templates</a></p>' +
      '<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(230px,1fr))" data-tpl-grid>' + tpls + "</div>" +
      '<button class="btn btn--ghost btn--sm" type="button" data-show-all hidden style="margin-top:12px">Show all templates</button></div>' +
      '<div class="box"><h2 style="font-size:1.25rem;margin-bottom:16px">3. Whose celebration is it?</h2>' + field("hosts", (HOST[pre.group || "weddings"] || ["Names"])[0], "", { required: true,
        attrs: { placeholder: (HOST[pre.group || "weddings"] || ["", "e.g. Lerato & Sipho"])[1] }, hint: "Shown large on your website and used for your link. You can change it later." }) + "</div>" +
      '<div class="btn-row"><button class="btn btn--primary btn--lg" type="submit">Start setting up ' + icon("arrow") + "</button></div></form></div></section>";
    var form = root().querySelector("[data-create]"), grid = form.querySelector("[data-tpl-grid]"), more = form.querySelector("[data-show-all]"), all = false;
    function sync(auto) {
      var c = form.querySelector("input[name=category]:checked"), g = c ? c.getAttribute("data-group") : pre.group, first = null;
      grid.querySelectorAll(".choice").forEach(function (l) {
        var ok = !g || l.getAttribute("data-groups").split(" ").indexOf(g) > -1;
        l.hidden = !(ok || all);
        if (ok && !first) first = l;
      });
      more.hidden = !g || all;
      more.textContent = "Show all " + D.templates.length + " templates";
      var picked = grid.querySelector("input[name=template]:checked");
      if (auto && first && (!picked || picked.closest(".choice").hidden)) first.querySelector("input").checked = true;
    }
    form.addEventListener("change", function (e) {
      if (e.target.name !== "category") return;
      sync(true);
      var L = HOST[e.target.getAttribute("data-group")], h = form.querySelector("[name=hosts]");
      if (L && h) { form.querySelector("label[for=f-hosts]").firstChild.textContent = L[0]; h.placeholder = L[1]; }
    });
    more.addEventListener("click", function () { all = true; sync(false); });
    sync(false);
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData(form), errs = {};
      if (!fd.get("category")) errs.category = "Choose the type of event.";
      if (!fd.get("template")) errs.template = "Choose a template. You can change it later.";
      if (!val(fd, "hosts")) errs.hosts = "Add the names to show on your website, e.g. Lerato & Sipho.";
      if (showErrors(form, errs)) return;
      var ev = newEvent(fd.get("category"), fd.get("template"), autoName(fd.get("category"), val(fd, "hosts")) || cat(fd.get("category")).name);
      ev.hosts = val(fd, "hosts");
      if (pkg(pre.pkg)) ev.selected_package = pre.pkg;
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
      var pct = Math.round(100 * ev.wizard_done.filter(function (n) { return n < LAST; }).length / (LAST - 1));
      var c = cat(ev.category), status = !ev.booking ? '<span class="pill pill--draft">Draft</span>'
        : (ev.booking.status === "sent" || !D.forms ? '<span class="pill pill--ok">' + (D.forms ? "Booking sent" : "Booking ready") + "</span>" : '<span class="pill pill--draft">Booking not sent yet</span>');
      return '<article class="box event-card"><div class="event-card__top"><div><h2 style="font-size:1.25rem">' + esc(ev.name) + '</h2><div class="event-card__meta"><span>' + esc(c ? c.name : "") + "</span>" +
        (ev.event_date ? "<span>" + esc(R.fmtDate(ev.event_date, false)) + "</span>" : "") + "<span>" + esc((tpl(ev.template) || {}).name || "") + " template</span></div></div>" + status + "</div>" +
        '<div class="progress"><span style="width:' + pct + '%"></span></div><div class="btn-row">' +
        '<button class="btn btn--primary btn--sm" type="button" data-open="' + id + '" data-to="' + (ev.booking ? "booked" : "setup-" + Math.min(LAST, (Math.max.apply(null, [0].concat(ev.wizard_done)) + 1))) + '">' + (ev.booking ? "View booking" : "Continue set-up") + "</button>" +
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
  var STEPS = [[1, "Details", "calendar"], [2, "Design", "palette"], [3, "Guests", "users"], [4, "Programme", "list"], [5, "Food and drinks", "dish"],
    [6, "Seating", "seat"], [7, "Extras", "gift"], [8, "Review and pay", "card"]];
  var LAST = 8;
  var INTROS = { 1: "Who, when and where. The essentials guests see first.", 2: "Make the template yours. The preview updates as you go.",
    3: "Who's coming. Add them however suits you, or skip and let guests reply through your link.", 4: "The running order of your day, or of each day.",
    5: "Menus, meal choices and dietary needs.", 6: "Choose your table layout. You seat guests once replies are in.", 7: "Dress code, gifts, places to stay and photos.",
    8: "Check what's left, choose your package and pay." };
  var OPTIONAL = [3, 4, 5, 6, 7], STEP_FEATURE = { 4: "programme", 5: "menu", 6: "seating" };

  function frame(ev, n, inner, opts) {
    opts = opts || {};
    var done = ev.wizard_done;
    var stepper = STEPS.map(function (s) {
      var tag = STEP_FEATURE[s[0]] && !feature(ev, STEP_FEATURE[s[0]]) ? '<span class="stepper__tag" title="Not in your planned package">' + icon("lock") + "</span>"
        : (OPTIONAL.indexOf(s[0]) > -1 ? '<span class="stepper__tag">optional</span>' : "");
      return '<li><a href="#setup-' + s[0] + '" class="' + (done.indexOf(s[0]) > -1 ? "is-done" : "") + '"' + (s[0] === n ? ' aria-current="step"' : "") + '><span class="n">' +
        (done.indexOf(s[0]) > -1 && s[0] !== n ? "✓" : s[0]) + "</span>" + esc(s[1]) + tag + "</a></li>"; }).join("");
    var pct = Math.round(100 * done.filter(function (x) { return x <= LAST; }).length / LAST);
    var nav = n < LAST ? '<div class="wizard-actions">' + (n > 1 ? '<a class="btn btn--ghost" href="#setup-' + (n - 1) + '">' + icon("arrow-left") + " Back</a>" : "<span></span>") +
      '<div class="btn-row">' + (n >= 2 && n <= 6 ? '<button class="btn btn--ghost" type="submit" name="nav" value="review">Skip to review and pay</button>' : "") +
      (OPTIONAL.indexOf(n) > -1 ? '<a class="btn btn--ghost" href="#setup-' + (n + 1) + '">Skip this step</a>' : "") +
      '<button class="btn btn--primary" type="submit" name="nav" value="next">' + esc(opts.nextLabel || "Continue") + " " + icon("arrow") + "</button></div></div>" : "";
    var optional = OPTIONAL.indexOf(n) > -1 ? '<p class="small muted" style="margin-top:6px">Optional. Skip it now and add it any time, before or after you pay.</p>' : "";
    var card = '<div class="glass glass--strong wizard-card"><div class="row" style="gap:14px;margin-bottom:6px"><span class="icon-tile icon-tile--soft">' + icon(STEPS[n - 1][2]) +
      '</span><div><span class="tiny muted mono">STEP ' + n + "</span><h2>" + esc(STEPS[n - 1][1]) + '</h2></div></div><p class="lead">' + INTROS[n] + "</p>" + optional + "<hr>" +
      '<form class="form" data-step="' + n + '" data-no-busy novalidate><div data-errors></div>' + inner + nav + "</form></div>";
    var preview = opts.preview ? '<div class="wizard-split">' + card + previewFrame() + "</div>" : card;
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 28px)"><div class="container">' +
      '<div class="page-head"><div><h1>Set up ' + esc(ev.name) + "</h1><p>Private draft. Everything saves as you type; nothing is shared until you pay.</p></div>" +
      '<div class="btn-row"><button class="btn btn--ghost btn--sm" type="button" data-continue-link>' + icon("link") + ' Continue on another device</button>' +
      '<a class="btn btn--secondary btn--sm" href="#preview-event">' + icon("eye") + " Full preview</a></div></div>" +
      '<div class="wizard-progress"><span>' + pct + '% complete</span><div class="progress"><span style="width:' + pct + '%"></span></div><span class="mono">Step ' + n + " of " + LAST + '</span></div>' +
      '<div class="wizard"><nav aria-label="Set-up steps"><ol class="stepper">' + stepper + "</ol></nav><div>" + preview + "</div></div></div></section>";
    refreshPreview(true);
  }
  function previewFrame(height) {
    return '<div class="preview-frame" data-jpreview data-device="desktop"><div class="preview-frame__bar"><span class="preview-frame__url">aureliastudio.co.za/events/' + esc(slugOf(cur())) + "</span>" +
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

  // --- step 1: details (names, date, venue) ---------------------------------------------------------
  function stepDetails(ev) {
    var g = groupOf(ev), hl = HOST[g] || ["Hosts", ""], v = ev.venue;
    var cats = D.categories.map(function (c) { return [c.slug, D.groups[c.group].name + ": " + c.name]; });
    var more = !!(v.map_url || v.parking || v.directions || ev.description);
    return field("hosts", hl[0], ev.hosts, { required: true, attrs: { placeholder: hl[1] }, hint: "Shown large on your website and used for your link." }) +
      '<div class="form-row form-row--3">' + field("event_date", "Date", ev.event_date, { type: "date", required: true, attrs: { min: todayIso() } }) +
      field("start_time", "Starts", ev.start_time, { type: "time" }) + field("end_time", "Ends", ev.end_time, { type: "time" }) + "</div>" +
      check("ends_next_day", "Ends after midnight", !!ev.ends_next_day) +
      '<div class="form-row form-row--2">' + field("venue_name", "Venue", v.name, { required: true, attrs: { placeholder: "Oakhaven Wine Estate" } }) +
      field("address", "Address", v.address, { required: true, hint: "Guests get directions and a map from this." }) + "</div>" +
      '<p class="tiny muted">More than one day, or a second venue? Add each day in the Programme step.</p>' +
      '<details class="box" style="padding:14px 16px"' + (more ? " open" : "") + '><summary style="cursor:pointer;font-weight:500">More details (optional): map pin, parking, directions, a short welcome</summary><div style="display:grid;gap:16px;margin-top:16px">' +
      field("map_url", "Google Maps link", v.map_url, { type: "url", hint: "For an exact pin, e.g. a farm gate. Paste the share link from Google Maps." }) +
      field("parking", "Parking", v.parking, { type: "textarea", attrs: { rows: 2 }, hint: "Where to park, security, drop-off." }) +
      field("directions", "Directions", v.directions, { type: "textarea", attrs: { rows: 2 }, hint: "Landmarks, gate codes, the last turn GPS gets wrong." }) +
      field("description", "A short welcome", ev.description, { type: "textarea", attrs: { rows: 2 }, hint: "One or two sentences guests read first." }) +
      '<div class="form-row form-row--2">' + field("name", "Event name", ev.name, { attrs: { "data-autoname": (!ev.name || ev.name === ev.hosts || ev.name === (cat(ev.category) || {}).name || ev.name === autoName(ev.category, ev.hosts)) ? "1" : "0" },
        hint: "Used in invitation messages. Filled in from your names." }) + select("category", "Occasion", cats, ev.category) + "</div></div></details>";
  }
  function collectDetails(ev, fd) {
    ev.category = val(fd, "category") || ev.category; ev.hosts = val(fd, "hosts"); ev.description = val(fd, "description");
    ev.name = val(fd, "name") || autoName(ev.category, ev.hosts) || (cat(ev.category) || {}).name || "My event";
    ev.event_date = val(fd, "event_date"); ev.start_time = val(fd, "start_time"); ev.end_time = val(fd, "end_time"); ev.ends_next_day = !!fd.get("ends_next_day");
    var url = val(fd, "map_url");
    if (url && !/^https?:\/\//i.test(url)) url = "https://" + url;
    ev.venue = Object.assign(ev.venue || {}, { name: val(fd, "venue_name"), address: val(fd, "address"), map_url: url, parking: val(fd, "parking"), directions: val(fd, "directions") });
  }
  function validateDetails(ev) {
    var e = {};
    if (!ev.hosts) e.hosts = (HOST[groupOf(ev)] || ["Names"])[0] + " is needed.";
    if (!ev.event_date) e.event_date = "Date is needed.";
    else if (ev.event_date < todayIso()) e.event_date = "Date can't be in the past.";
    if (ev.start_time && ev.end_time && ev.end_time <= ev.start_time && !ev.ends_next_day) e.end_time = "End time must be after the start time (tick “ends after midnight” if it does).";
    if (!ev.venue.name) e.venue_name = "Venue is needed.";
    if (!ev.venue.address) e.address = "Address is needed.";
    if (ev.venue.map_url && !/^https?:\/\/[^\s<>"]+\.[^\s<>"]+/i.test(ev.venue.map_url)) e.map_url = "Map link must be a web address.";
    return e;
  }
  function validateContact(ev) {
    var e = {};
    if (!ev.contact.name) e.contact_name = "Your name is needed.";
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(ev.contact.email)) e.contact_email = "Enter a valid email address, like name@example.com.";
    if (ev.contact.phone && !/^\+?[0-9 ()-]{7,20}$/.test(ev.contact.phone)) e.contact_phone = "Enter a phone number using digits, spaces and an optional +.";
    return e;
  }
  function val(fd, k) { return (fd.get(k) || "").toString().trim(); }

  // --- step 2: design ---------------------------------------------------------------------------------------
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
    var deadline = ev.guest_settings.rsvp_deadline ? R.fmtDate(ev.guest_settings.rsvp_deadline, false) : "";
    var cards = wordingOptions(ev).map(function (o) {
      var f = {}; ["welcome", "invitation", "rsvp_note", "closing"].forEach(function (k) { f["w_" + k] = fillWording(o[k], ev.hosts, deadline); });
      return '<div class="suggest-card"><b>' + esc(o.label) + "</b><p>" + esc(f.w_welcome) + "</p><p>" + esc(f.w_invitation) + "</p>" +
        '<button class="btn btn--secondary btn--sm" type="button" data-fill="' + esc(JSON.stringify(f)) + '">Use this wording</button></div>';
    }).join("");
    function upl(kind, label, hint) {
      var cur = ev.images[kind];
      return '<div class="field"><span class="label">' + esc(label) + "</span>" + (cur ? '<div class="row" style="gap:10px"><img src="' + cur + '" alt="" style="width:72px;height:54px;object-fit:cover;border-radius:8px">' +
        '<button class="btn btn--sm btn--ghost" type="button" data-remove-image="' + kind + '">' + icon("trash") + " Remove</button></div>" : "") +
        '<label class="file-drop" style="position:relative">' + icon("upload") + "<span>" + (cur ? "Replace" : "Upload") + " " + esc(label.toLowerCase()) + '</span><span class="hint">' + esc(hint) + "</span>" +
        '<input type="file" data-image="' + kind + '" accept="image/jpeg,image/png,image/webp,image/gif"></label></div>';
    }
    return "<fieldset><legend>Template</legend>" + '<div class="choice-grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">' + tplOpts + "</div>" +
      '<p class="hint" style="margin-top:8px">Switching template resets colours and fonts to that template\'s defaults. Your content stays.</p></fieldset>' +
      '<fieldset><legend>Colour palette</legend><div class="choice-grid">' + pal + "</div>" +
      '<button class="btn btn--ghost btn--sm" type="button" data-surprise style="margin-top:10px">' + icon("sparkle") + " Try another look</button></fieldset>" +
      '<div class="box" style="padding:16px">' + check("custom_colors", "Use my own colours" + (adv ? "" : " <span class='pill pill--gold pill--plain'>Premium</span>"), custom, { attrs: { disabled: !adv, "data-reveals": "#custom-colors" } }) +
      '<div id="custom-colors" class="form-row form-row--4" style="margin-top:12px"' + (custom ? "" : " hidden") + ">" +
      [["bg", "Background"], ["text", "Text"], ["accent", "Accent"], ["accent2", "Second accent"]].map(function (c) { return color("color_" + c[0], c[1], res.colors[c[0]]); }).join("") + "</div></div>" +
      '<div class="form-row form-row--2">' + select("font_pair", "Typography", fonts, res.font_pair) + select("background", "Background", bgs, res.background) + "</div>" +
      '<div class="form-row form-row--3">' + upl("hero", "Main photo", "Landscape works best.") + upl("background", "Background image", "Used when Background is set to your photo.") + upl("logo", "Logo or crest", "PNG with transparency works best.") + "</div>" +
      field("monogram", "Monogram or initials", ev.design.monogram || "", { attrs: { maxlength: 12, placeholder: "L & S" }, hint: "Shown where the template uses a monogram, if you don't upload a logo." }) +
      '<fieldset><legend>Your wording</legend><p class="hint" style="margin-bottom:12px">Pick ready-made wording for your occasion, then change anything you like. Leave a box empty to use the template\'s own wording.</p>' +
      '<div class="suggest-grid">' + cards + '</div><div class="form-row">' + field("w_welcome", "Welcome line", w.welcome || "", { attrs: { placeholder: "Together with their families" } }) +
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

  // --- step 3: guests --------------------------------------------------------------------------------------
  function guestListHtml(ev) {
    var list = ev.guest_list || [];
    if (!list.length) return '<p class="small muted">No guests yet.</p>';
    var groups = [];
    list.forEach(function (g, k) { var name = g.group || ""; var grp = groups.filter(function (x) { return x[0] === name; })[0]; if (!grp) groups.push(grp = [name, []]); grp[1].push([g, k]); });
    return '<p class="small"><b>' + plural(list.length, "guest") + '</b> on your list. <button class="btn btn--ghost btn--sm" type="button" data-clear-guests>Clear the list</button></p>' +
      groups.map(function (grp) {
        return (grp[0] ? '<p class="tiny muted mono" style="margin:10px 0 4px">' + esc(grp[0].toUpperCase()) + "</p>" : "") + '<ul class="guest-chips">' + grp[1].map(function (x) {
          return '<li><span>' + esc(x[0].name) + (x[0].phone ? ' <span class="muted">' + esc(x[0].phone) + "</span>" : "") + '</span><button type="button" data-remove-guest="' + x[1] + '" aria-label="Remove ' + esc(x[0].name) + '">' + icon("close") + "</button></li>";
        }).join("") + "</ul>";
      }).join("");
  }
  function addGuests(people) {
    var ev = cur(), have = {}, added = 0;
    ev.guest_list = ev.guest_list || [];
    ev.guest_list.forEach(function (g) { have[g.name.toLowerCase()] = 1; if (g.email) have[g.email] = 1; if (g.phone) have[g.phone.replace(/\D/g, "")] = 1; });
    people.forEach(function (g) {
      var d = (g.phone || "").replace(/\D/g, "");
      if (have[g.name.toLowerCase()] || (g.email && have[g.email]) || (d && have[d])) return;
      ev.guest_list.push({ name: g.name, phone: g.phone || "", email: g.email || "", group: g.group || "" });
      have[g.name.toLowerCase()] = 1; added++;
    });
    ev.updated = new Date().toISOString(); save();
    var box = document.querySelector("#journey-root [data-guest-list]");
    if (box) box.innerHTML = guestListHtml(ev);
    return added;
  }
  function step4(ev) {
    var gs = ev.guest_settings, preset = ["Family", "Friends", "Colleagues", "VIP", "Church", "Neighbours", "Partners", "Clients"], chosen = gs.categories || [];
    var sides = (gs.sides || ["", ""]).concat(["", ""]).slice(0, 2), paste;
    var pol = [["none", "No plus-ones", "Invitations are for the named guest only."], ["per_guest", "Set per guest", "You decide for each guest in your list."], ["open", "Everyone may bring", "Guests on the general link can add plus-ones."]];
    if (feature(ev, "guest_management")) {
      var canPick = "contacts" in navigator && "ContactsManager" in window;
      paste = '<fieldset><legend>Your guest list</legend>' +
        '<div class="quick-add"><input class="input" data-qa-name placeholder="Guest\'s name" aria-label="Guest\'s name" autocomplete="off">' +
        '<input class="input" data-qa-phone type="tel" placeholder="Mobile (optional)" aria-label="Guest\'s mobile" autocomplete="off">' +
        '<button class="btn btn--secondary" type="button" data-qa-add>' + icon("plus") + " Add</button></div>" +
        '<p class="tiny muted" style="margin:6px 0 10px">Type a name, press Enter, type the next one. Couples can go on one line, e.g. “Thabo & Lindi Mokoena”.</p>' +
        '<div class="btn-row">' + (canPick ? '<button class="btn btn--ghost btn--sm" type="button" data-pick-contacts>' + icon("phone") + " Choose from my phone contacts</button>" : "") +
        '<label class="btn btn--ghost btn--sm" style="position:relative">' + icon("upload") + ' Upload Excel or CSV<input type="file" data-guest-file accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" style="position:absolute;inset:0;opacity:0;cursor:pointer"></label></div>' +
        '<details style="margin-top:10px"><summary class="small" style="cursor:pointer;font-weight:500">Paste a list</summary>' +
        field("guest_paste", "Names to add", "", { type: "textarea", attrs: { rows: 6, placeholder: "Mokoena family:\nThandi Mokoena, 082 123 4567\nGogo Nomsa\nFriends:\nSipho Dlamini, sipho@example.com" },
          hint: "One guest per line, with a mobile or email if you have it. A line ending in a colon, like “Mokoena family:”, groups the names below it. Copying a column from Excel, Google Sheets or your phone's notes works too." }) +
        '<button class="btn btn--secondary btn--sm" type="button" data-paste-add>' + icon("plus") + " Add these names</button></details>" +
        '<div data-guest-list style="margin-top:14px">' + guestListHtml(ev) + "</div>" +
        '<p class="small muted" style="margin-top:10px">No list yet? That\'s fine. Skip this step: when guests reply through your link, they\'re added to your list for you.</p></fieldset>';
    } else {
      paste = '<div class="notice">' + icon("users") + "<span>With Essential, guests reply through your one link and appear in your dashboard as they do. Keeping your own guest list, with a personal link for each guest, is part of Premium.</span></div>";
    }
    return paste + '<div class="form-row form-row--2">' + field("estimated", "Roughly how many guests?", gs.estimated, { type: "number", attrs: { min: 0, max: 5000 } }) +
      field("rsvp_deadline", "RSVP deadline", gs.rsvp_deadline, { type: "date", hint: "Replies close at the end of this day." }) + "</div>" +
      '<details class="box" style="padding:14px 16px"><summary style="cursor:pointer;font-weight:500">More options: plus-ones, children, families and guest groups</summary><div style="display:grid;gap:18px;margin-top:16px">' +
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
      '<div id="kids"' + (gs.children_allowed ? "" : " hidden") + ">" + field("max_children", "Children per invitation (maximum)", gs.max_children || 0, { type: "number", attrs: { min: 0, max: 10 } }) + "</div></fieldset></div></details>";
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

  // --- step 4: programme, one block per day -----------------------------------------------------------------
  function maxFunctions(ev) { return feature(ev, "multi_functions") ? (limit(ev, "functions") || 1) : 1; }
  function progRow(k, d, it) {
    it = it || {};
    return '<div class="prog-row"><input type="hidden" name="si-' + k + '-day" value="' + d + '">' + mini("si-" + k + "-time", it.item_time, "time", "", "Time") +
      mini("si-" + k + "-title", it.title, "text", "Ceremony", "What happens") + mini("si-" + k + "-description", it.description, "text", "Optional detail", "Detail") +
      '<button class="btn btn--ghost btn--icon" type="button" data-remove-item aria-label="Remove item">' + icon("trash") + "</button></div>";
  }
  function dayBlock(d, fn, rowsHtml) {
    fn = fn || {};
    var place = !!(fn.venue_name || fn.address || fn.map_url);
    return '<section class="day-block" data-day="' + d + '"><input type="hidden" name="fn-' + d + '-id" value="' + esc(fn.id || "") + '">' +
      '<div class="day-head"><div class="row row--between"><h3 data-day-title>Day</h3><button class="btn btn--ghost btn--sm" type="button" data-remove-day>' + icon("trash") + " Remove day</button></div>" +
      '<div class="form-row form-row--4">' + mini("fn-" + d + "-name", fn.name, "text", "e.g. Negotiations, or Ceremony", "What's on this day") + mini("fn-" + d + "-date", fn.func_date, "date", "", "Date") +
      mini("fn-" + d + "-start", fn.start_time, "time", "", "Starts") + mini("fn-" + d + "-end", fn.end_time, "time", "", "Ends") + "</div>" +
      "<details" + (place ? " open" : "") + '><summary class="small" style="cursor:pointer">Different venue for this day?</summary><div class="form-row form-row--3" style="margin-top:10px">' +
      mini("fn-" + d + "-venue", fn.venue_name, "text", "Leave empty for the main venue", "Venue") + mini("fn-" + d + "-address", fn.address, "text", "Address", "Address") +
      mini("fn-" + d + "-map", fn.map_url, "url", "Google Maps link", "Map link") + "</div></details></div>" +
      '<div data-items>' + rowsHtml + '</div><div><button class="btn btn--sm btn--secondary" type="button" data-add-item>' + icon("plus") + " Add to this day</button></div></section>";
  }
  function step5(ev) {
    var mf = maxFunctions(ev), k = 0, blocks;
    var multi = ((cat(ev.category) || {}).features || []).indexOf("multi_function") > -1 || ev.category === "lobola";
    if (ev.functions.length) {
      var ids = ev.functions.map(function (f) { return f.id; });
      blocks = ev.functions.map(function (fn, d) {
        var mine = ev.schedule.filter(function (x) { return x.function_id === fn.id || (d === 0 && ids.indexOf(x.function_id) < 0); });
        var rows = mine.map(function (it) { return progRow(k++, d, it); }).join("") || progRow(k++, d);
        return dayBlock(d, fn, rows);
      }).join("");
    } else {
      var rows = ev.schedule.map(function (it) { return progRow(k++, 0, it); }).join("");
      if (!rows) { rows = progRow(0, 0) + progRow(1, 0); k = 2; }
      blocks = dayBlock(0, null, rows);
    }
    return featureNote(ev, "programme", "The programme") +
      '<div class="notice" style="margin-bottom:6px">' + icon("wand") + "<div><span>Start from a typical " + esc(((cat(ev.category) || {}).name || "event").toLowerCase()) + " programme" +
      (ev.start_time ? " timed from " + esc(ev.start_time) : "") + ', then change the times and titles.</span><div style="margin-top:10px"><button class="btn btn--secondary btn--sm" type="button" data-sample>Use a sample programme</button></div></div></div>' +
      '<div class="days" data-days data-max-days="' + mf + '">' + blocks + "</div>" +
      '<div class="row" style="gap:12px;flex-wrap:wrap"><button class="btn btn--secondary btn--sm" type="button" data-add-day>' + icon("calendar") + " Add another day</button>" +
      '<p class="small muted" style="margin:0">' + (multi ? "Lobola, traditional and multi-day weddings often run over more than one day. Add each day and plan what happens on it. " : "") +
      (mf > 1 ? "Your package includes up to " + mf + " days." : "") + "</p>" +
      '<p class="small muted" data-day-limit hidden style="margin:0">' + (mf > 1 ? "You've reached the number of days your package includes." : "Events over more than one day are part of Premium and Signature. Choose one at the last step.") + "</p></div>";
  }
  function readIndexed(fd, prefix, fields) {
    var idx = {}, re = new RegExp("^" + prefix + "-(\\d+)-");
    fd.forEach(function (v, key) { var m = re.exec(key); if (m) idx[m[1]] = 1; });
    return Object.keys(idx).map(Number).sort(function (a, b) { return a - b; }).map(function (n) {
      var row = { _i: n }; fields.forEach(function (f) { row[f] = (fd.get(prefix + "-" + n + "-" + f) || "").toString().trim(); }); return row; });
  }
  function collect5(ev, fd) {
    var days = readIndexed(fd, "fn", ["id", "name", "date", "start", "end", "venue", "address", "map"]);
    var items = readIndexed(fd, "si", ["time", "title", "description", "day"]).filter(function (r) { return r.time || r.title || r.description; });
    var single = days.length <= 1 && !(days[0] && (days[0].name || days[0].date || days[0].venue || days[0].address || days[0].map));
    var idFor = {};
    ev.functions = single ? [] : days.map(function (r, n) {
      var date = r.date;
      if (!date && ev.event_date) { var dt = new Date(ev.event_date + "T12:00:00"); dt.setDate(dt.getDate() + n); date = dt.toISOString().slice(0, 10); }
      var id = r.id || uid("f"); idFor[r._i] = id;
      return { id: id, name: r.name || "Day " + (n + 1), func_date: date, start_time: r.start, end_time: r.end, venue_name: r.venue, address: r.address, map_url: r.map };
    });
    var first = ev.functions.length ? ev.functions[0].id : "";
    ev.schedule = items.map(function (r) { return { item_time: r.time, title: r.title, description: r.description, kind: guessKind(r.title), function_id: idFor[r.day] || first }; });
  }
  function validate5(ev) {
    var e = {}, mf = maxFunctions(ev);
    if (ev.functions.length > mf) e.functions = "Your package includes " + plural(mf, "day") + ". Choose a bigger package at the last step for more.";
    if (ev.schedule.some(function (s) { return !s.title; })) e.schedule = "Each programme item needs a short description of what happens, e.g. Ceremony or Dinner.";
    return e;
  }
  function syncDays() {
    var box = document.querySelector("#journey-root [data-days]");
    if (!box) return;
    var days = box.querySelectorAll(".day-block"), max = +box.getAttribute("data-max-days");
    box.classList.toggle("is-single", days.length === 1);
    days.forEach(function (d, n) { var t = d.querySelector("[data-day-title]"); if (t) t.textContent = "Day " + (n + 1); });
    var add = document.querySelector("#journey-root [data-add-day]"), lock = document.querySelector("#journey-root [data-day-limit]");
    if (add) add.hidden = days.length >= max;
    if (lock) lock.hidden = days.length < max;
  }
  function nextIndex(form, prefix) {
    var n = -1, re = new RegExp("^" + prefix + "-(\\d+)-");
    form.querySelectorAll("input,select,textarea").forEach(function (i) { var m = re.exec(i.name || ""); if (m) n = Math.max(n, +m[1]); });
    return n + 1;
  }

  // --- step 5: food and drinks ---------------------------------------------------------------------------------------
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
      repeat("mi", items.length ? items.map(function (it, i) { return miRow(i, it); }) : [miRow(0), miRow(1)], null, "Add a dish") +
      '<details style="margin-top:14px"' + (items.length ? "" : " open") + '><summary class="small" style="cursor:pointer;font-weight:500">Have the menu from your caterer? Paste it here</summary>' +
      field("menu_paste", "Paste the menu", "", { type: "textarea", attrs: { rows: 7, placeholder: "Starters\nButternut soup with toasted seeds\nMain: Lamb shank - rosemary jus\nDessert: Malva pudding" },
        hint: "One dish per line. A line with only a course name (Starters, Mains, Dessert) applies to the dishes below it. Text after a dash becomes the description." }) +
      '<button class="btn btn--secondary btn--sm" type="button" data-menu-paste>' + icon("plus") + " Add these dishes</button></details></fieldset>" +
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

  // --- step 6: seating layout ------------------------------------------------------------------------------
  var TOP_CHOICES = { weddings: ["Where will the couple sit?", [["sweetheart", "Sweetheart table", "Just the two of you, facing your guests."],
      ["head", "Head table", "The couple with the bridal party, along one side, facing guests."], ["none", "With your guests", "No top table. You sit at a table among family and friends."]]],
    other: ["A top table for the hosts?", [["sweetheart", "Small top table", "For the hosts only, facing guests."], ["head", "Top table", "Hosts and special guests, along one side, facing the room."],
      ["none", "No top table", "Hosts sit among their guests."]]] };
  var GUEST_CHOICES = [["round", "Round tables", "Easy conversation. 8 to 10 per table."], ["long", "Long tables", "Family style, in rows. Seats more in the same space."],
    ["mixed", "A mix", "Round tables with a few long ones for big families."]];
  function layoutOf(ev) {
    var t = ev.tables || {};
    return { top: t.top || (groupOf(ev) === "weddings" ? "head" : "none"), guest: t.guest || "round", capacity: +t.capacity || 10, count: t.count };
  }
  function layoutChoices(name, options, value) {
    return '<div class="choice-grid layout-choice" style="grid-template-columns:repeat(auto-fill,minmax(180px,1fr))">' + options.map(function (o) {
      return '<label class="choice"><input type="radio" name="' + name + '" value="' + o[0] + '"' + (o[0] === value ? " checked" : "") + "><span>" +
        (window.AureliaFloor ? AureliaFloor.icon(o[0]) : "") + "<b>" + esc(o[1]) + "</b><small>" + esc(o[2]) + "</small></span></label>"; }).join("") + "</div>";
  }
  function suggestedTables(ev, cap) { var est = +ev.guest_settings.estimated || (ev.guest_list || []).length || 0; return est ? Math.max(1, Math.ceil(est / (cap || 10))) : 10; }
  function step7(ev) {
    var lay = layoutOf(ev), top = TOP_CHOICES[groupOf(ev) === "weddings" ? "weddings" : "other"], est = +ev.guest_settings.estimated || (ev.guest_list || []).length || 0;
    var count = lay.count === undefined || lay.count === "" ? suggestedTables(ev, lay.capacity) : lay.count;
    return featureNote(ev, "seating", "The seating chart") +
      '<div class="notice">' + icon("seat") + "<span>Most hosts plan seating once replies are in. Then the seating editor in your dashboard can seat everyone automatically, keeping families and groups together, and you drag people to fine-tune.</span></div>" +
      "<fieldset><legend>" + esc(top[0]) + "</legend>" + layoutChoices("top_table", top[1], lay.top) + "</fieldset>" +
      "<fieldset><legend>Guest tables</legend>" + layoutChoices("guest_tables", GUEST_CHOICES, lay.guest) + "</fieldset>" +
      '<div class="form-row form-row--2">' + field("capacity", "Seats per table", lay.capacity, { type: "number", attrs: { min: 2, max: 40 } }) +
      field("table_count", "Number of guest tables", count, { type: "number", attrs: { min: 0, max: 120 }, hint: est ? "About " + suggestedTables(ev, lay.capacity) + " for " + est + " guests." : "We'll adjust this once you know your numbers." }) + "</div>" +
      '<div class="fp-plan-box"><p class="tiny muted mono" style="margin-bottom:8px">YOUR ROOM, ROUGHLY</p><div data-plan-preview>' + planSvg(ev) + "</div></div>" +
      field("seating_notes", "Special seating requirements", ev.info.seating_notes || "", { type: "textarea", attrs: { rows: 3, placeholder: "Grandparents near the front and away from the speakers; wheelchair access at Table 3." } });
  }
  function planSvg(ev) {
    var lay = layoutOf(ev);
    return window.AureliaFloor ? AureliaFloor.plan({ top: lay.top, guest: lay.guest, count: lay.count === undefined || lay.count === "" ? suggestedTables(ev, lay.capacity) : lay.count,
      cap: lay.capacity, dance: ["weddings", "parties"].indexOf(groupOf(ev)) > -1 }) : "";
  }
  function collect7(ev, fd) {
    ev.tables = { top: val(fd, "top_table") || "none", guest: val(fd, "guest_tables") || "round", capacity: parseInt(val(fd, "capacity") || 10, 10) || 10,
      count: val(fd, "table_count"), chosen: true };
    ev.info.seating_notes = val(fd, "seating_notes");
    var box = document.querySelector("#journey-root [data-plan-preview]");
    if (box) box.innerHTML = planSvg(ev);
  }
  function validate7(ev) {
    var e = {}, c = +ev.tables.count;
    if (ev.tables.count !== "" && !(c >= 0 && c <= 120)) e.table_count = "Number of tables must be between 0 and 120.";
    if (!(ev.tables.capacity >= 2 && ev.tables.capacity <= 40)) e.capacity = "Seats per table must be between 2 and 40.";
    return e;
  }

  // --- step 7: extras ---------------------------------------------------------------------------------------
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
      '<details class="box" style="padding:14px 16px"' + (cts.length ? " open" : "") + '><summary style="cursor:pointer;font-weight:500">Someone guests can call on the day (optional)</summary>' +
      '<p class="hint" style="margin:10px 0 12px">For guests who are lost, running late or need help on the day, e.g. your planner, MC or a cousin. It shows on your website, so you\'re not the one answering calls. Leave it empty if you don\'t need it.</p>' +
      repeat("ct", (cts.length ? cts : [{}]).map(function (c, i) { return ctRow(i, c); }), null, "Add a person", 8) + "</details>" +
      "<fieldset><legend>Accommodation</legend>" + repeat("ac", (acc.length ? acc : [{}]).map(function (a, i) { return row3("ac", i, a, AC); }), null, "Add a place to stay", 10) + "</fieldset>" +
      field("instructions", "Special instructions", info.instructions || "", { type: "textarea", attrs: { rows: 3, placeholder: "Unplugged ceremony: please keep phones away until the reception." } }) +
      "<fieldset><legend>Photo gallery</legend>" + featureNote(ev, "gallery", "The photo gallery") +
      '<p class="hint" style="margin-bottom:12px">Add a few photos now, like your engagement shoot, or come back after the event and add photos from the day. Guests see them on the same link they already have.</p>' +
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

  // --- step 8: review and pay ---------------------------------------------------------------------------------
  function payOption(code) { return (D.payment_links || {})[code] || ""; }
  function step9(ev) {
    var v = ev.venue, gs = ev.guest_settings, info = ev.info, t = tpl(ev.template) || {}, w = ev.design.wording || {};
    var needed = [[!!(ev.hosts && ev.event_date), "Names and date", 1], [!!(v.name && v.address), "Venue and address", 1]];
    var nice = [[!!ev.images.hero, "A main photo", 2], [!!(w.welcome || w.invitation || w.rsvp_note || w.closing), "Your own wording (or keep the template's)", 2], [!!gs.rsvp_deadline, "An RSVP deadline", 3]];
    if (feature(ev, "programme")) nice.push([!!ev.schedule.length, "The programme", 4]);
    if (feature(ev, "menu")) nice.push([!!ev.menu.items.length, "The menu", 5]);
    var missing = needed.filter(function (c) { return !c[0]; });
    function li(c, must) {
      return '<li class="' + (c[0] ? "is-done" : "") + '">' + icon(c[0] ? "check" : (must ? "alert" : "plus")) + "<span>" + (c[0] ? esc(c[1]) : '<a class="text-link" href="#setup-' + c[2] + '">' + esc(c[1]) + "</a>" + (must ? " <b>(needed)</b>" : "")) + "</span></li>";
    }
    var checklist = '<details class="box"' + (missing.length ? " open" : "") + ' style="padding:14px 16px"><summary style="cursor:pointer;font-weight:500">' +
      (missing.length ? (missing.length === 2 ? "Two things are needed before you pay" : "One thing is needed before you pay") : "Ready to go. Optional extras you can still add") +
      '</summary><ul class="checklist" style="margin-top:12px">' + needed.map(function (c) { return li(c, true); }).join("") + nice.map(function (c) { return li(c, false); }).join("") + "</ul></details>";
    var c = ev.contact;
    var contact = '<fieldset><legend>Your details</legend><div class="form-row form-row--3">' + field("contact_name", "Your name", c.name, { required: true, attrs: { autocomplete: "name" } }) +
      field("contact_email", "Your email", c.email, { type: "email", required: true, attrs: { autocomplete: "email" }, hint: "Your receipt and website link go here." }) +
      field("contact_phone", "Your mobile", c.phone, { type: "tel", attrs: { autocomplete: "tel" }, hint: "Optional. For quick questions." }) + "</div></fieldset>";
    var cards = D.packages.map(function (p) {
      var pg = gaps(ev, p.code);
      return '<article class="price' + (p.highlight ? " price--highlight" : "") + '">' + (p.highlight ? '<span class="price__badge">Most chosen</span>' : "") +
        "<div><h3>" + esc(p.name) + '</h3><p class="muted small" style="margin-top:6px">' + esc(p.tagline) + '</p></div><div class="price__amount">' + money(p.price_cents) + "<small>once-off, VAT incl.</small></div>" +
        '<button class="btn ' + (p.highlight ? "btn--primary" : "btn--secondary") + ' btn--block" type="submit" name="nav" value="pay:' + p.code + '">' + icon("card") + " Pay " + money(p.price_cents) + "</button>" +
        "<ul>" + p.bullets.map(function (b) { return "<li>" + icon("check") + "<span>" + esc(b) + "</span></li>"; }).join("") + "</ul>" +
        '<details><summary class="small" style="cursor:pointer">Limits</summary><div class="price__limits" style="margin-top:8px">' +
        Object.keys(D.limit_labels).map(function (k) { return "<div><span>" + esc(D.limit_labels[k]) + "</span><b>" + (p.limits[k] || "—") + "</b></div>"; }).join("") + "</div></details>" +
        (pg.length ? '<p class="small price__gap">' + icon("lock") + "<span>Won't show " + esc(joinOr(pg)) + ".</span></p>" : "") + "</article>";
    }).join("");
    var share = '<div class="box" style="display:grid;gap:10px"><h3 style="font-size:1.0625rem">Show someone before you pay</h3>' +
      '<p class="small muted">Send a link to your partner or family. They see your website as it is now, without your contact details or guest list. Photos stay on this device.</p>' +
      '<div class="btn-row"><button class="btn btn--secondary btn--sm" type="button" data-share-preview>' + icon("link") + ' Copy a preview link</button>' +
      '<button class="btn btn--ghost btn--sm" type="button" data-share-preview="whatsapp">' + icon("chat") + " Send on WhatsApp</button></div></div>";
    function sec(n, title, rows) {
      return '<div class="review-section"><div class="review-section__head"><h3>' + esc(title) + '</h3><a class="btn btn--sm btn--ghost" href="#setup-' + n + '">' + icon("edit") + ' Edit</a></div><dl class="dl">' +
        rows.map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + (r[1] ? esc(r[1]) : '<span class="muted">Not added</span>') + "</dd>"; }).join("") + "</dl></div>";
    }
    var lay = layoutOf(ev);
    var review = sec(1, "Details", [["Names", ev.hosts], ["Occasion", (cat(ev.category) || {}).name], ["Date", ev.event_date ? R.fmtDate(ev.event_date) : ""],
        ["Time", [ev.start_time, ev.end_time].filter(Boolean).join(" – ")], ["Venue", v.name], ["Address", v.address]]) +
      sec(2, "Design", [["Template", t.name], ["Photos", String(["hero", "logo", "background"].filter(function (k) { return ev.images[k]; }).length + (ev.images.gallery || []).length) + " added"], ["Welcome", w.welcome]]) +
      sec(3, "Guests", [["Guest list", (ev.guest_list || []).length ? plural(ev.guest_list.length, "guest") : ""], ["RSVP deadline", gs.rsvp_deadline ? R.fmtDate(gs.rsvp_deadline) : ""], ["Children", gs.children_allowed ? "Welcome" : "Adults only"]]) +
      sec(4, "Programme", [["Days", ev.functions.length ? ev.functions.map(function (f) { return f.name; }).join(", ") : "One day"], ["Programme items", ev.schedule.length ? String(ev.schedule.length) : ""]]) +
      sec(5, "Food and drinks", [["Menu items", ev.menu.items.length ? String(ev.menu.items.length) : ""], ["Dietary options", (info.dietary_options || []).join(", ")]]) +
      sec(6, "Seating", [["Layout", ev.tables.chosen ? ({ sweetheart: "Sweetheart table", head: "Head table", none: "No top table" })[lay.top] + ", " + ({ round: "round", long: "long", mixed: "mixed" })[lay.guest] + " tables" : ""]]) +
      sec(7, "Extras", [["Dress code", info.dress_code], ["Registry", (info.registry || []).length ? String(info.registry.length) : ""], ["Gallery", (ev.images.gallery || []).length ? plural(ev.images.gallery.length, "photo") : ""]]);
    var connected = D.packages.some(function (p) { return payOption(p.code); });
    return checklist + contact + '<div data-field="details"></div><div class="price-grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">' + cards + "</div>" +
      '<p class="small muted">' + (connected ? "Secure payment with PayFast: card, instant EFT and more. " : "") + "Prices include 15% VAT. By paying, you accept the " +
      '<a class="text-link" href="#terms">terms of service</a> and <a class="text-link" href="#refunds">refund policy</a>.</p>' + share +
      '<details class="box" style="padding:14px 16px"><summary style="cursor:pointer;font-weight:500">See everything you\'ve entered</summary><div style="display:grid;gap:16px;margin-top:16px">' +
      '<div class="notice">' + icon("link") + "<span>Your website address will be <b class=\"mono\">aureliastudio.co.za/events/" + esc(slugOf(ev)) + "</b> once published.</span></div>" +
      previewFrame(560) + review + "</div></details>" +
      '<div class="wizard-actions"><a class="btn btn--ghost" href="#setup-7">' + icon("arrow-left") + ' Back</a><span></span></div>' +
      '<p class="small muted" style="margin-top:14px">Questions first, or rather have us finish the set-up? <a class="text-link" href="#help-me-set-up">Ask us to help</a>.</p>';
  }
  function collect9(ev, fd) {
    ev.contact = { name: val(fd, "contact_name"), email: val(fd, "contact_email").toLowerCase(), phone: val(fd, "contact_phone") };
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
    var photos = ["hero", "logo", "background"].filter(function (k) { return ev.images[k]; }).join(", ") + ((ev.images.gallery || []).length ? " + " + ev.images.gallery.length + " gallery" : "");
    add("Photos chosen", photos ? photos + (D.forms ? "" : " (please email them with this request)") : "");
    lines.push("");
    add("Estimated guests", gs.estimated); add("RSVP deadline", gs.rsvp_deadline); add("Guest categories", (gs.categories || []).join(", ")); add("Families / sides", (gs.sides || []).join(", "));
    add("Family groups", (gs.family_groups || []).join(", ")); add("VIP note", gs.vip_note); add("Plus-one policy", gs.plus_one_policy + " (default " + (gs.plus_ones_default || 0) + ")");
    add("Children", gs.children_allowed ? "welcome, up to " + (gs.max_children || 0) + " per invitation" : "adults only");
    add("Guest list", (ev.guest_list || []).length ? plural(ev.guest_list.length, "guest") + (D.forms ? " (attached)" : "") : ""); lines.push("");
    if (!D.forms && (ev.guest_list || []).length) { lines.push("GUEST LIST"); ev.guest_list.forEach(function (x) { lines.push("- " + [x.name, x.phone, x.email, x.group].filter(Boolean).join(" | ")); }); lines.push(""); }
    if (ev.functions.length) { lines.push("DAYS"); ev.functions.forEach(function (f) { lines.push("- " + [f.name, f.func_date, [f.start_time, f.end_time].filter(Boolean).join("-"), f.venue_name, f.address, f.map_url].filter(Boolean).join(" | ")); }); lines.push(""); }
    var dayName = {}; ev.functions.forEach(function (f) { dayName[f.id] = f.name; });
    if (ev.schedule.length) { lines.push("PROGRAMME"); ev.schedule.forEach(function (s) { lines.push("- " + [dayName[s.function_id], s.item_time, s.title, s.description].filter(Boolean).join(" | ")); }); lines.push(""); }
    if (ev.menu.items.length) { lines.push("MENU: " + ev.menu.name); ev.menu.items.forEach(function (i) { lines.push("- " + [i.course, i.name, i.description, (i.tags || []).join(", "), i.selectable ? "guests choose" : ""].filter(Boolean).join(" | ")); }); }
    add("Dietary options", (info.dietary_options || []).join(", ")); add("Drinks", info.drinks); add("Catering notes", info.catering_notes); lines.push("");
    var lay = layoutOf(ev);
    add("Seating layout", ev.tables.chosen ? lay.top + " top table, " + lay.guest + " guest tables, " + (lay.count || suggestedTables(ev, lay.capacity)) + " x " + lay.capacity + " seats" : "not chosen yet");
    add("Seating notes", info.seating_notes); lines.push("");
    add("Dress code", [info.dress_code, info.dress_code_notes].filter(Boolean).join(" - "));
    (info.registry || []).forEach(function (r) { add("Registry", [r.name, r.url, r.note].filter(Boolean).join(" | ")); });
    add("Gift note", info.gift_note);
    (info.contacts || []).forEach(function (c) { add("Day-of contact", [c.name, c.role, c.phone, c.email].filter(Boolean).join(" | ")); });
    (info.accommodation || []).forEach(function (a) { add("Stay", [a.name, a.url, a.note].filter(Boolean).join(" | ")); });
    add("Special instructions", info.instructions);
    return lines.join("\n").replace(/\n{3,}/g, "\n\n");
  }
  function guestCsv(ev) {
    return ["Name,Mobile,Email"].concat((ev.guest_list || []).map(function (g) {
      return [g.name, g.phone, g.email].map(function (x) { return '"' + String(x || "").replace(/"/g, '""') + '"'; }).join(","); })).join("\n");
  }
  function sendBooking(ev, kind) {
    var p = pkg(ev.selected_package) || {};
    var fields = { website: "", kind: kind, ref: ev.booking.ref, package: p.name || "", amount: money(p.price_cents || 0), name: ev.contact.name, email: ev.contact.email,
      phone: ev.contact.phone, event: ev.hosts || ev.name, occasion: (cat(ev.category) || {}).name || "", date: ev.event_date,
      guests: String((ev.guest_list || []).length || ev.guest_settings.estimated || ""), details: summaryText(ev),
      guest_list: (ev.guest_list || []).length ? guestCsv(ev) : "", draft: JSON.stringify(Object.assign({}, ev, { images: undefined })) };
    var files = ["hero", "logo", "background"].map(function (k) { var b = dataUrlBlob(ev.images[k]); return [k, b, k + (b && b.type === "image/png" ? ".png" : ".jpg")]; });
    fields.guest_list = (ev.guest_list || []).length ? ["Name,Mobile,Email,Group"].concat(ev.guest_list.map(function (g) {
      return [g.name, g.phone, g.email, g.group].map(function (x) { return '"' + String(x || "").replace(/"/g, '""') + '"'; }).join(","); })).join("\n") : "";
    var gal = (ev.images.gallery || []).slice(0, 40), batches = [];
    for (var i = 0; i < gal.length; i += 8) batches.push(gal.slice(i, i + 8));
    return postForm("booking", fields, files).then(function () {
      return batches.reduce(function (chain, batch, n) {
        return chain.then(function () {
          return postForm("booking-photos", { website: "", ref: ev.booking.ref, email: ev.contact.email, batch: (n + 1) + " of " + batches.length },
            batch.map(function (g, j) { return ["photo" + (j + 1), dataUrlBlob(g.url), "gallery-" + (n * 8 + j + 1) + ".jpg"]; }));
        });
      }, Promise.resolve());
    });
  }
  function startSend(ev, kind) {
    ev.booking.status = "sending"; save();
    return sendBooking(ev, kind).then(function () {
      ev.booking.status = "sent"; ev.booking.sent_at = new Date().toISOString(); ev.booking.sent_version = ev.updated; save();
    }, function () { ev.booking.status = "failed"; save(); });
  }
  function goPay(ev) {
    var opt = payOption(ev.selected_package);
    if (!opt) { location.hash = "#booked"; if (currentHash === "booked") viewBooked(); return; }
    ev.booking.paying_at = new Date().toISOString(); save();
    if (typeof opt === "object" && opt.action) {
      var f = document.createElement("form");
      f.method = "post"; f.action = opt.action;
      Object.keys(opt.fields).forEach(function (k) { var i = document.createElement("input"); i.type = "hidden"; i.name = k; i.value = opt.fields[k]; f.appendChild(i); });
      document.body.appendChild(f); f.submit();
    } else location.href = opt;
  }
  function viewBooked() {
    var ev = cur();
    if (!ev || !ev.booking) { location.hash = "#my-events"; return; }
    var p = pkg(ev.selected_package) || {}, opt = payOption(p.code), b = ev.booking, email = D.email, text = summaryText(ev);
    var first = (ev.contact.name || "").split(" ")[0];
    var changed = b.status === "sent" && b.sent_version && ev.updated > b.sent_version;
    var lead = opt
      ? (b.paying_at ? "If your payment went through, PayFast emails you a receipt. We publish your website and send your link to " + esc(ev.contact.email) + " within one working day."
        : "Pay with PayFast to confirm your booking.")
      : "Your booking is in. We'll contact you on " + esc(ev.contact.phone || ev.contact.email) + " within one working day to take payment and publish your website.";
    var pay = opt ? '<div><button class="btn ' + (b.paying_at ? "btn--secondary" : "btn--primary btn--lg") + '" type="button" data-pay-again>' + icon("card") + " " +
      (b.paying_at ? "Didn't finish paying? Pay " : "Pay ") + money(p.price_cents) + "</button></div>" : "";
    var problem = "";
    if (!D.forms || b.status === "failed") {
      var subject = "Booking " + b.ref + ": " + ev.name;
      problem = '<div class="box" style="display:grid;gap:12px"><h2 style="font-size:1.125rem">' + (D.forms ? "One more thing" : "This preview can't send bookings") + "</h2>" +
        '<p class="small muted">' + (D.forms ? "Your details didn't reach us automatically. Tap below to send them again, or email them, so we can build your website."
          : "On your live website this happens by itself. Here, copy the details and email them to " + esc(email) + ".") + "</p>" +
        '<div class="btn-row">' + (D.forms ? '<button class="btn btn--primary btn--sm" type="button" data-resend>Try sending again</button>' : "") +
        '<a class="btn btn--secondary btn--sm" href="mailto:' + esc(email) + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(text.slice(0, 1800)) + '">' + icon("mail") + " Email the details</a>" +
        '<button class="btn btn--ghost btn--sm" type="button" data-copy-booking>' + icon("copy") + ' Copy details</button></div><textarea data-booking-text hidden>' + esc(text) + "</textarea></div>";
    }
    var next = '<div class="box" style="display:grid;gap:12px"><h2 style="font-size:1.25rem">What happens next</h2><ol class="how-list" style="list-style:none;margin:0;padding:0;display:grid;gap:14px">' +
      [["01", "We build your website", "From everything you entered, within one working day. If anything's missing, we ask."],
        ["02", "You get your link", "By email, ready to share on WhatsApp, by email or as a QR code."],
        ["03", "Replies come in", "Guests RSVP on your website. You can keep adding guests, photos and details."]].map(function (x) {
        return '<li><span class="mono">' + x[0] + "</span><div><b>" + esc(x[1]) + '</b><p class="small muted" style="margin-top:4px">' + esc(x[2]) + "</p></div></li>"; }).join("") + "</ol></div>";
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 32px)"><div class="container container--narrow" style="display:grid;gap:var(--gap)">' +
      '<div class="glass glass--strong panel" style="display:grid;gap:14px;text-align:left"><span class="icon-tile icon-tile--soft">' + icon("check") + "</span>" +
      '<h1 style="font-size:clamp(1.8rem,1.3rem + 2vw,2.6rem)">Thank you' + (first ? ", " + esc(first) : "") + '</h1><p class="small muted">Reference <b class="mono">' + esc(b.ref) + "</b> · " + esc(p.name || "") + " · " + money(p.price_cents || 0) + " (VAT incl.)</p>" +
      '<p class="lead" style="font-size:1.0625rem">' + lead + "</p>" + pay +
      (changed ? '<div class="notice">' + icon("edit") + '<div>You\'ve changed your event since you booked.<div style="margin-top:10px"><button class="btn btn--secondary btn--sm" type="button" data-resend="update">Send my changes</button></div></div></div>' : "") +
      "</div>" + problem + next +
      '<div class="btn-row"><a class="btn btn--secondary" href="#preview-event">' + icon("eye") + ' Preview your website</a><a class="btn btn--ghost" href="#setup-1">Edit details</a><a class="btn btn--ghost" href="#my-events">My events</a></div></div></section>';
    window.scrollTo(0, 0);
  }

  // --- a draft opened from a link ---------------------------------------------------------------------
  function linkError(err) {
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 48px)"><div class="container container--narrow"><div class="empty"><span class="icon-tile">' + icon("alert") +
      '</span><h1 style="font-size:1.5rem">This link didn\'t open</h1><p>' + esc(err && err.message && /browser/.test(err.message) ? err.message : "It may have been cut short when it was copied. Ask for the link again, and copy all of it.") +
      '</p><a class="btn btn--primary" href="#create">Create your own event</a></div></div></section>';
  }
  function importResume(code) {
    unpack(code).then(function (ev) {
      var mine = state.events[ev.id];
      if (mine && mine.updated > ev.updated) { toast("This device already has a newer copy of that event.", "error"); ev = mine; }
      else {
        if (mine) ev.images = mine.images;
        state.events[ev.id] = ev;
        if (state.order.indexOf(ev.id) < 0) state.order.unshift(ev.id);
        toast("Your draft is open on this device." + (ev.images.hero ? "" : " Photos stay on the device you added them on, so add them again in Design."));
      }
      state.current = ev.id; save();
      history.replaceState(null, "", "#setup-" + Math.min(LAST, Math.max.apply(null, [0].concat(ev.wizard_done)) + 1));
      route(location.hash.slice(1));
    }, linkError);
  }
  function viewShared(code) {
    unpack(code).then(function (ev) {
      root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 24px)"><div class="container"><div class="page-head"><div><h1>' + esc(ev.hosts || ev.name) +
        '</h1><p>A draft of this event website, shared with you before it goes live. RSVPs open once it\'s published.</p></div>' +
        '<div class="btn-row"><a class="btn btn--primary btn--sm" href="#create">Create your own event</a></div></div>' +
        '<div class="preview-frame" data-jpreview data-device="desktop"><div class="preview-frame__bar"><span class="preview-frame__url">aureliastudio.co.za/events/' + esc(slugOf(ev)) + "</span>" +
        '<div class="seg" role="group" aria-label="Device"><button type="button" data-device="desktop" aria-pressed="true">Desktop</button><button type="button" data-device="mobile" aria-pressed="false">Mobile</button></div></div>' +
        '<div class="preview-frame__stage" style="height:' + Math.max(560, window.innerHeight - 220) + 'px"><iframe title="Shared draft of an event website" data-shared></iframe></div></div></div></section>';
      document.querySelector("iframe[data-shared]").srcdoc = R.render(ev, "preview");
    }, linkError);
  }

  // --- forms on the static site: contact and set-up help ------------------------------------------------------
  var REQUIRED = { contact: { name: "Your name", email: "Email", message: "Your message" }, "setup-help": { name: "Your name", email: "Email", occasion: "What you're celebrating" } };
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form[data-static-form]");
    if (!form) return;
    e.preventDefault();
    var name = form.getAttribute("data-static-form"), fd = new FormData(form), fields = {}, errs = [];
    fd.forEach(function (v, k) { if (k !== "_csrf") fields[k] = String(v).trim(); });
    Object.keys(REQUIRED[name] || {}).forEach(function (k) { if (!fields[k]) errs.push(REQUIRED[name][k] + " is needed."); });
    if (fields.email && !/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(fields.email)) errs.push("Enter a valid email address, like name@example.com.");
    if (name === "setup-help" && /whatsapp|phone/.test(fields.reach || "") && !fields.phone) errs.push("Add a mobile number so we can reach you on " + (fields.reach === "phone" ? "the phone." : "WhatsApp."));
    var box = form.querySelector("[data-static-errors]");
    if (!box) { form.insertAdjacentHTML("afterbegin", '<div data-static-errors></div>'); box = form.querySelector("[data-static-errors]"); }
    if (errs.length) {
      box.innerHTML = '<div class="form-errors" role="alert" tabindex="-1"><b>Please fix ' + (errs.length === 1 ? "this item" : "these " + errs.length + " items") + ":</b><ul>" + errs.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul></div>";
      box.firstChild.focus(); return;
    }
    box.innerHTML = "";
    var ref = (name === "contact" ? "C-" : "H-") + Math.random().toString(36).slice(2, 7).toUpperCase(), btn = form.querySelector("[type=submit]");
    fields.message = (fields.message || "") + "\n\nReference: " + ref;
    if (btn) { btn.disabled = true; btn.setAttribute("aria-busy", "true"); }
    postForm(name, fields).then(function () {
      form.outerHTML = '<div class="notice notice--success" role="status">' + icon("check") + "<div><b>Thank you. Your reference is " + ref + '.</b><p class="small" style="margin-top:4px">' +
        (name === "setup-help" ? "We'll contact you within one working day to go through the details and send you a quote." : "We usually reply within one working day.") + "</p></div></div>";
    }, function () {
      if (btn) { btn.disabled = false; btn.removeAttribute("aria-busy"); }
      var body = Object.keys(fields).filter(function (k) { return k !== "website" && fields[k]; }).map(function (k) { return k + ": " + fields[k]; }).join("\n");
      box.innerHTML = '<div class="notice notice--warn" role="alert">' + icon("alert") + '<div><b>We couldn\'t send this from here.</b> <a class="text-link" href="mailto:' + esc(D.email) + "?subject=" +
        encodeURIComponent((name === "setup-help" ? "Set-up help " : "Message ") + ref) + "&body=" + encodeURIComponent(body) + '">Email it to us instead</a>.</div></div>';
    });
  });

  // --- full preview ------------------------------------------------------------------------------------
  function viewPreview() {
    var ev = cur();
    if (!ev) { location.hash = "#my-events"; return; }
    root().innerHTML = '<section class="section" style="padding-top:calc(var(--header-h) + 24px)"><div class="container"><div class="page-head"><div><h1>' + esc(ev.name) +
      "</h1><p>Your event website with the details you've entered. Guests see it once it's published.</p></div>" +
      '<div class="btn-row"><a class="btn btn--primary btn--sm" href="#setup-' + (ev.booking ? LAST : Math.min(LAST, Math.max.apply(null, [0].concat(ev.wizard_done)) + 1)) + '">Continue set-up</a><a class="btn btn--ghost btn--sm" href="#my-events">My events</a></div></div>' +
      previewFrame(Math.max(560, window.innerHeight - 220)) + "</div></section>";
    refreshPreview(true);
  }

  // --- step dispatch ------------------------------------------------------------------------------------
  var STEP = { 1: [stepDetails, collectDetails, validateDetails], 2: [step3, collect3], 3: [step4, collect4, validate4], 4: [step5, collect5, validate5],
    5: [step6, collect6, validate6], 6: [step7, collect7, validate7], 7: [step8, collect8, validate8], 8: [step9, collect9] };
  function viewStep(n) {
    var ev = cur();
    if (!ev) { location.hash = state.order.length ? "#my-events" : "#create"; return; }
    frame(ev, n, STEP[n][0](ev), { preview: n === 2 });
    if (n === 4) syncDays();
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
    if (n === LAST) {
      var code = String(nav || "").replace(/^pay:/, "");
      if (pkg(code)) ev.selected_package = code;
      var errs = Object.assign({}, validateContact(ev)), need = validateDetails(ev);
      if (Object.keys(need).length) errs.details = "Your names, date and venue are needed first. Go back to Details (step 1) and add them.";
      if (showErrors(form, errs)) { save(); return; }
      ev.booking = ev.booking || { ref: "AUR-" + Math.random().toString(36).slice(2, 7).toUpperCase(), at: new Date().toISOString() };
      ev.booking.package = ev.selected_package;
      if (ev.wizard_done.indexOf(LAST) < 0) ev.wizard_done.push(LAST);
      save();
      var buttons = form.querySelectorAll("button[type=submit]");
      buttons.forEach(function (b) { b.disabled = true; });
      var sending = ev.booking.status === "sent" ? Promise.resolve() : startSend(ev, "new");
      // give the details a few seconds to reach us, then go to payment either way
      Promise.race([sending, new Promise(function (r) { setTimeout(r, 4000); })]).then(function () { goPay(ev); });
      return;
    }
    var e = STEP[n][2] ? STEP[n][2](ev) : {}, added = -1;
    if (n === 3) {
      var people = parseGuests((new FormData(form)).get("guest_paste"));
      if (people.length) {
        var have = {}; (ev.guest_list || []).forEach(function (g) { have[g.name.toLowerCase()] = 1; if (g.email) have[g.email] = 1; if (g.phone) have[g.phone.replace(/\D/g, "")] = 1; });
        ev.guest_list = ev.guest_list || []; added = 0;
        people.forEach(function (g) { var d = g.phone.replace(/\D/g, ""); if (have[g.name.toLowerCase()] || (g.email && have[g.email]) || (d && have[d])) return; ev.guest_list.push(g); have[g.name.toLowerCase()] = 1; added++; });
      }
    }
    if (showErrors(form, e)) { save(); return; }
    if (ev.wizard_done.indexOf(n) < 0) ev.wizard_done.push(n);
    if (ev.design._reset) { delete ev.design._reset; }
    save();
    if (added > -1) toast("Added " + plural(added, "guest") + " to your list.");
    if (nav === "next") location.hash = "#setup-" + (n + 1);
    else if (nav === "review") location.hash = "#setup-" + LAST;
    else { if (added < 0) toast("Saved."); viewStep(n); }
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

  // --- quick add guests --------------------------------------------------------------------------------------
  function quickAdd() {
    var nm = document.querySelector("#journey-root [data-qa-name]"), ph = document.querySelector("#journey-root [data-qa-phone]");
    if (!nm || !nm.value.trim()) { if (nm) nm.focus(); return; }
    var name = nm.value.trim(), n = addGuests([{ name: name, phone: saPhone(ph.value.trim()), email: "" }]);
    if (!n) toast(name + " is already on your list.", "error");
    nm.value = ""; ph.value = ""; nm.focus();
  }
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" || !e.target.matches("#journey-root [data-qa-name], #journey-root [data-qa-phone]")) return;
    e.preventDefault();
    var ph = document.querySelector("#journey-root [data-qa-phone]");
    if (e.target.hasAttribute("data-qa-name") && e.target.value.trim() && !ph.value.trim()) { quickAdd(); return; }
    if (e.target.hasAttribute("data-qa-name")) { ph.focus(); return; }
    quickAdd();
  });
  document.addEventListener("change", function (e) {
    if (!e.target.matches("#journey-root [data-guest-file]")) return;
    var file = e.target.files[0];
    if (!file) return;
    readSheetFile(file).then(function (rows) {
      var people = parseSheet(rows);
      if (!people.length) { toast("We couldn't find any names in that file. Check it has a Name column, or paste the names instead.", "error"); return; }
      var n = addGuests(people);
      toast("Added " + plural(n, "guest") + " from " + file.name + (n < people.length ? ". " + (people.length - n) + " were already on your list." : "."));
    }).catch(function () { toast("We couldn't read that file. Save it as Excel (.xlsx) or CSV and try again, or paste the names instead.", "error"); });
    e.target.value = "";
  });

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
    if (t.name === "guest_paste" || t.name === "menu_paste" || t.hasAttribute("data-guest-file") || t.hasAttribute("data-qa-name") || t.hasAttribute("data-qa-phone")) return;
    if (t.hasAttribute("data-gallery")) {
      var ev = cur(), lim = limit(ev, "gallery_photos"), files = Array.prototype.slice.call(t.files);
      collectStep(form);
      var room = lim - (ev.images.gallery || []).length;
      if (files.length > room) toast("Your package includes " + lim + " gallery photos.", "error");
      Promise.all(files.slice(0, Math.max(0, room)).map(function (fl) { return shrink(fl, 1200).catch(function () { return null; }); })).then(function (urls) {
        ev.images.gallery = (ev.images.gallery || []).concat(urls.filter(Boolean).map(function (u) { return { url: u, caption: "" }; }));
        save(); viewStep(7);
      });
      return;
    }
    var n = +form.getAttribute("data-step");
    if (n === 2 && t.name === "template") { collectStep(form); save(); viewStep(2); return; }
    collectStep(form); save(); refreshPreview();
  });
  document.addEventListener("input", function (e) {
    var form = e.target.closest("#journey-root form[data-step]");
    if (!form || e.target.type === "file") return;
    if (e.target.name && e.target.name.indexOf("color_") === 0) { var c = form.querySelector('input[type=color][data-sync="' + e.target.name + '"]'); if (c && /^#[0-9a-f]{6}$/i.test(e.target.value)) c.value = e.target.value; }
    if (e.target.name === "name") e.target.setAttribute("data-autoname", "0");
    if (e.target.name === "hosts") { var nm = form.querySelector('[data-autoname="1"]'), cs = form.querySelector("[name=category]"); if (nm) nm.value = autoName(cs ? cs.value : cur().category, e.target.value); }
    if (e.target.name === "guest_paste" || e.target.name === "menu_paste") return;
    clearTimeout(form._t);
    form._t = setTimeout(function () { collectStep(form); save(); refreshPreview(); }, 400);
  });
  document.addEventListener("click", function (e) {
    var t = e.target.closest("#journey-root [data-add-row], #journey-root [data-remove-row], #journey-root [data-device], #journey-root [data-open], #journey-root [data-delete], #journey-root [data-remove-image], #journey-root [data-remove-gallery], #journey-root [data-copy-booking], " +
      "#journey-root [data-fill], #journey-root [data-surprise], #journey-root [data-sample], #journey-root [data-menu-paste], #journey-root [data-clear-guests], #journey-root [data-continue-link], #journey-root [data-share-preview], #journey-root [data-resend], " +
      "#journey-root [data-qa-add], #journey-root [data-pick-contacts], #journey-root [data-paste-add], #journey-root [data-remove-guest], #journey-root [data-add-day], #journey-root [data-add-item], " +
      "#journey-root [data-remove-day], #journey-root [data-remove-item], #journey-root [data-pay-again]");
    if (!t) return;
    var form = t.closest("form[data-step]");
    if (t.hasAttribute("data-qa-add")) { quickAdd(); return; }
    if (t.hasAttribute("data-pick-contacts")) {
      navigator.contacts.select(["name", "tel", "email"], { multiple: true }).then(function (list) {
        var people = list.map(function (c) { return { name: (c.name && c.name[0]) || "", phone: saPhone((c.tel && c.tel[0]) || ""), email: ((c.email && c.email[0]) || "").toLowerCase() }; }).filter(function (x) { return x.name; });
        if (people.length) toast("Added " + plural(addGuests(people), "guest") + " from your contacts.");
      }).catch(function () {});
      return;
    }
    if (t.hasAttribute("data-paste-add")) {
      var pt = form.querySelector("[name=guest_paste]"), ppl = parseGuests(pt.value);
      if (!ppl.length) { toast("Paste the names first, one per line.", "error"); return; }
      var n1 = addGuests(ppl); pt.value = "";
      toast("Added " + plural(n1, "guest") + (n1 < ppl.length ? ". " + (ppl.length - n1) + " were already on your list." : "."));
      return;
    }
    if (t.hasAttribute("data-remove-guest")) {
      var gl = cur().guest_list; gl.splice(+t.getAttribute("data-remove-guest"), 1); cur().updated = new Date().toISOString(); save();
      document.querySelector("#journey-root [data-guest-list]").innerHTML = guestListHtml(cur()); return;
    }
    if (t.hasAttribute("data-add-day")) {
      var box = form.querySelector("[data-days]"), d = nextIndex(form, "fn"), dk = nextIndex(form, "si");
      if (d === 0 && box.querySelectorAll(".day-block").length) d = 1;
      box.insertAdjacentHTML("beforeend", dayBlock(d, null, progRow(dk, d)));
      syncDays(); var nm = box.lastElementChild.querySelector('input[name$="-name"]'); if (nm) nm.focus();
      collectStep(form); save(); refreshPreview(); return;
    }
    if (t.hasAttribute("data-add-item")) {
      var day = t.closest(".day-block"), list2 = day.querySelector("[data-items]");
      list2.insertAdjacentHTML("beforeend", progRow(nextIndex(form, "si"), day.getAttribute("data-day")));
      list2.lastElementChild.querySelector("input").focus(); return;
    }
    if (t.hasAttribute("data-remove-day")) {
      if (!window.confirm("Remove this day and everything planned for it?")) return;
      t.closest(".day-block").remove(); syncDays(); collectStep(form); save(); refreshPreview(); return;
    }
    if (t.hasAttribute("data-remove-item")) { t.closest(".prog-row").remove(); collectStep(form); save(); refreshPreview(); return; }
    if (t.hasAttribute("data-pay-again")) { goPay(cur()); return; }
    if (t.hasAttribute("data-fill")) {
      var vals = JSON.parse(t.getAttribute("data-fill"));
      Object.keys(vals).forEach(function (k) { var el = form.querySelector('[name="' + k + '"]'); if (el) el.value = vals[k]; });
      collectStep(form); save(); refreshPreview(true); toast("Wording added. Edit it as you like."); return;
    }
    if (t.hasAttribute("data-surprise")) {
      var pals = form.querySelectorAll("input[name=palette]");
      if (pals.length) pals[Math.floor(Math.random() * pals.length)].checked = true;
      ["font_pair", "background"].forEach(function (k) { var sl = form.querySelector("select[name=" + k + "]"); if (sl && sl.options.length) sl.selectedIndex = Math.floor(Math.random() * Math.min(sl.options.length, k === "font_pair" ? 4 : sl.options.length)); });
      collectStep(form); save(); refreshPreview(true); return;
    }
    if (t.hasAttribute("data-sample")) {
      collectStep(form);
      var sev = cur(), firstId = sev.functions.length ? sev.functions[0].id : "";
      var mineFirst = sev.schedule.filter(function (x) { return (x.function_id || "") === firstId; });
      if (mineFirst.length && !window.confirm("This replaces the items for the first day with a sample. Continue?")) return;
      var sample = sampleProgramme(sev).map(function (x) { x.function_id = firstId; return x; });
      sev.schedule = sample.concat(sev.schedule.filter(function (x) { return (x.function_id || "") !== firstId; }));
      save(); viewStep(4); toast("Sample programme added. Change the times and titles to match your day."); return;
    }
    if (t.hasAttribute("data-menu-paste")) {
      var txt = form.querySelector("[name=menu_paste]"), dishes = parseMenu(txt ? txt.value : "");
      if (!dishes.length) { toast("Paste the menu first, one dish per line.", "error"); return; }
      collectStep(form);
      var mev = cur(); mev.menu.items = mev.menu.items.filter(function (it) { return it.name; }).concat(dishes); save(); viewStep(5);
      toast("Added " + plural(dishes.length, "dish", "dishes") + ". Check the courses."); return;
    }
    if (t.hasAttribute("data-clear-guests")) {
      if (!window.confirm("Remove everyone from your guest list?")) return;
      collectStep(form); cur().guest_list = []; save(); viewStep(3); return;
    }
    if (t.hasAttribute("data-continue-link")) {
      var f0 = document.querySelector("#journey-root form[data-step]"); if (f0) { collectStep(f0); save(); }
      pack(cur(), false).then(function (code) { shareOrCopy(pageUrl() + "#resume=" + code, "Continue my " + D.brand + " event", "Link copied. Open it on your other device to carry on. Photos stay on this device."); });
      return;
    }
    if (t.hasAttribute("data-share-preview")) {
      var how = t.getAttribute("data-share-preview");
      pack(cur(), true).then(function (code) {
        var url = pageUrl() + "#see=" + code;
        if (how === "whatsapp") window.open("https://wa.me/?text=" + encodeURIComponent("Have a look at our event website draft: " + url), "_blank", "noopener");
        else shareOrCopy(url, "Our event website draft", "Preview link copied. Anyone with it can see the draft, without your contact details.");
      });
      return;
    }
    if (t.hasAttribute("data-resend")) { var rev = cur(); startSend(rev, t.getAttribute("data-resend") || "new").then(function () { viewBooked(); toast(rev.booking.status === "sent" ? "Sent." : "Still couldn't send. Please email the details.", rev.booking.status === "sent" ? "" : "error"); }); return; }
    if (t.hasAttribute("data-add-row")) {
      var wrap = t.closest("[data-repeat]"), list = wrap.querySelector("[data-rows]"), prefix = wrap.getAttribute("data-repeat"), max = +wrap.getAttribute("data-max");
      if (list.children.length >= max) { toast("Your package allows " + max + " here.", "error"); return; }
      var next = 0;
      list.querySelectorAll("input,select").forEach(function (i) { var m = new RegExp("^" + prefix + "-(\\d+)-").exec(i.name || ""); if (m) next = Math.max(next, +m[1] + 1); });
      var html = prefix === "mi" ? miRow(next) : prefix === "ct" ? ctRow(next) : row3(prefix, next, null, prefix === "rg" ? RG : AC);
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
    if (t.hasAttribute("data-remove-image")) { if (form) collectStep(form); delete cur().images[t.getAttribute("data-remove-image")]; save(); viewStep(2); return; }
    if (t.hasAttribute("data-remove-gallery")) { if (form) collectStep(form); cur().images.gallery.splice(+t.getAttribute("data-remove-gallery"), 1); save(); viewStep(7); return; }
    if (t.hasAttribute("data-copy-booking")) {
      var ta = document.querySelector("[data-booking-text]"), text = ta ? ta.value : "";
      var done = function () { toast("Booking details copied. Paste them into an email to " + D.email + "."); };
      var fallback = function () { if (ta) { ta.hidden = false; var dt = ta.closest("details"); if (dt) dt.open = true; ta.focus(); ta.select(); } try { document.execCommand("copy"); done(); } catch (er) { toast("Select the text below and copy it.", "error"); } };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback); else fallback();
    }
  });

  // --- routing ---------------------------------------------------------------------------------------------
  function route(id) {
    currentHash = id;
    if (id.indexOf("resume=") === 0) return importResume(id.slice(7));
    if (id.indexOf("see=") === 0) return viewShared(id.slice(4));
    if (id.indexOf("create") === 0) return viewCreate(id);
    if (id === "my-events") return viewMyEvents();
    if (id === "preview-event") return viewPreview();
    if (id === "booked") return viewBooked();
    var m = /^setup-(\d+)$/.exec(id);
    if (m && +m[1] >= 1 && +m[1] <= 10) return viewStep(+m[1]);
    return viewMyEvents();
  }
  function handles(id) { return /^(create(-.+)?|my-events|preview-event|booked|setup-\d+|resume=.+|see=.+)$/.test(id); }
  window.AureliaJourney = { route: route, handles: handles };
})();
