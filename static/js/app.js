/* Aurelia site + app script: theme, header, drawer, reveal, toasts, copy, repeatable rows,
   colour sync, preview frames, tilt, confirm, autosave. No dependencies. */
(function () {
  "use strict";
  var doc = document, root = doc.documentElement;
  var csrf = (doc.querySelector('meta[name="csrf"]') || {}).content || "";
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  window.Aurelia = {
    csrf: csrf,
    post: function (url, data) {
      return fetch(url, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Accept": "application/json", "X-Requested-With": "fetch" },
        body: JSON.stringify(data || {})
      }).then(function (r) { return r.json().then(function (j) { if (!r.ok) { throw new Error(j.error || "Request failed"); } return j; }); });
    },
    toast: function (msg, kind) {
      var box = doc.querySelector(".toasts");
      if (!box) { box = doc.createElement("div"); box.className = "toasts"; doc.body.appendChild(box); }
      var t = doc.createElement("div");
      t.className = "toast toast--" + (kind || "success") + " glass glass--strong";
      t.setAttribute("role", "status");
      t.innerHTML = '<i class="i i--' + (kind === "error" ? "alert" : "check") + '" aria-hidden="true"></i><span></span><button type="button" aria-label="Dismiss" data-dismiss>×</button>';
      t.querySelector("span").textContent = msg;
      box.appendChild(t);
      setTimeout(function () { t.remove(); }, 5200);
    }
  };

  // Theme
  doc.addEventListener("click", function (e) {
    var b = e.target.closest("[data-theme-toggle]");
    if (!b) return;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("aurelia-theme-v1", next); } catch (err) {}
  });

  // Header glass after 40px
  var header = doc.querySelector("[data-header]");
  if (header) {
    var onScroll = function () { header.classList.toggle("is-scrolled", window.scrollY > 40); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // Drawer
  var drawer = doc.getElementById("drawer"), opener = null;
  doc.addEventListener("click", function (e) {
    if (e.target.closest("[data-drawer-open]") && drawer) { opener = e.target.closest("[data-drawer-open]"); drawer.showModal(); }
    if (e.target.closest("[data-drawer-close]") && drawer) { drawer.close(); }
    if (drawer && e.target === drawer) { drawer.close(); }
  });
  if (drawer) drawer.addEventListener("close", function () { if (opener) opener.focus(); });

  // Toasts
  doc.addEventListener("click", function (e) {
    var d = e.target.closest("[data-dismiss]");
    if (d) d.closest(".toast").remove();
  });
  doc.querySelectorAll(".toast").forEach(function (t) { setTimeout(function () { t.remove(); }, 6500); });

  // Focus the first error summary
  var errs = doc.querySelector("[data-focus]");
  if (errs) errs.focus();

  // Reveal on scroll
  var reveals = doc.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, parent = el.parentElement;
        if (parent && parent.hasAttribute("data-stagger")) {
          var idx = Array.prototype.indexOf.call(parent.children, el);
          el.style.transitionDelay = Math.min(idx, 4) * 60 + "ms";
        }
        el.classList.add("is-visible");
        io.unobserve(el);
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -10% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  // Copy buttons: data-copy="text" or data-copy-target="#id"
  doc.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy], [data-copy-target]");
    if (!b) return;
    var text = b.getAttribute("data-copy");
    if (!text) { var t = doc.querySelector(b.getAttribute("data-copy-target")); text = t ? (t.value || t.textContent) : ""; }
    var done = function () { Aurelia.toast(b.getAttribute("data-copied") || "Copied to clipboard"); };
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); }); }
    else { fallback(text); done(); }
  });
  function fallback(text) {
    var ta = doc.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    doc.body.appendChild(ta); ta.select(); try { doc.execCommand("copy"); } catch (err) {} ta.remove();
  }

  // Confirm before destructive submits
  doc.addEventListener("submit", function (e) {
    var f = e.target, msg = f.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) { e.preventDefault(); return; }
    var btn = f.querySelector('button[type="submit"]:not([formnovalidate])');
    if (btn && !f.hasAttribute("data-no-busy")) { setTimeout(function () { btn.setAttribute("aria-disabled", "true"); }, 0); }
  });
  doc.addEventListener("click", function (e) {
    var a = e.target.closest("[data-confirm-click]");
    if (a && !window.confirm(a.getAttribute("data-confirm-click"))) e.preventDefault();
  });

  // Colour inputs mirror their hex text field
  doc.querySelectorAll("input[type=color][data-sync]").forEach(function (c) {
    var t = c.parentElement.querySelector('input[name="' + c.getAttribute("data-sync") + '"]');
    c.addEventListener("input", function () { t.value = c.value.toUpperCase(); t.dispatchEvent(new Event("change", { bubbles: true })); });
    t.addEventListener("input", function () { if (/^#[0-9a-f]{6}$/i.test(t.value)) c.value = t.value; });
  });

  // Repeatable rows: <div data-repeat="prefix"> with <template> and [data-add-row]
  doc.querySelectorAll("[data-repeat]").forEach(function (wrap) {
    var tpl = wrap.querySelector("template"), list = wrap.querySelector("[data-rows]");
    var add = wrap.querySelector("[data-add-row]");
    var max = parseInt(wrap.getAttribute("data-max") || "200", 10);
    function next() { var n = parseInt(wrap.getAttribute("data-next") || list.children.length, 10); wrap.setAttribute("data-next", n + 1); return n; }
    if (add) add.addEventListener("click", function () {
      if (list.children.length >= max) { Aurelia.toast("Your package allows " + max + " here.", "error"); return; }
      var html = tpl.innerHTML.replace(/__i__/g, next());
      list.insertAdjacentHTML("beforeend", html);
      var first = list.lastElementChild.querySelector("input, select, textarea"); if (first) first.focus();
    });
    wrap.addEventListener("click", function (e) {
      var rm = e.target.closest("[data-remove-row]");
      if (rm) rm.closest(".repeat__row").remove();
    });
  });

  // Preview frame device toggle + refresh
  doc.querySelectorAll("[data-preview]").forEach(function (box) {
    var frame = box.querySelector("iframe");
    box.addEventListener("click", function (e) {
      var b = e.target.closest("[data-device]");
      if (b && b.tagName === "BUTTON") {
        box.setAttribute("data-device", b.getAttribute("data-device"));
        box.querySelectorAll("button[data-device]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      }
      if (e.target.closest("[data-refresh]")) { frame.src = frame.src; }
    });
  });

  // Scale fixed-size iframes (template thumbnails, showcase devices) to their box
  function fit() {
    doc.querySelectorAll("[data-fit]").forEach(function (box) {
      var f = box.querySelector("iframe"); if (!f) return;
      var w = parseInt(f.getAttribute("width"), 10) || 1280;
      var s = box.clientWidth / w;
      f.style.width = w + "px";
      f.style.height = Math.ceil(box.clientHeight / s) + "px";
      f.style.transform = "scale(" + s + ")";
    });
  }
  fit();
  window.addEventListener("resize", fit);

  // File drop zones show chosen file names
  doc.querySelectorAll(".file-drop").forEach(function (z) {
    var input = z.querySelector("input[type=file]"), label = z.querySelector("[data-files]");
    if (!input) return;
    ["dragenter", "dragover"].forEach(function (ev) { z.addEventListener(ev, function (e) { e.preventDefault(); z.classList.add("is-over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { z.addEventListener(ev, function () { z.classList.remove("is-over"); }); });
    z.addEventListener("drop", function (e) { e.preventDefault(); input.files = e.dataTransfer.files; input.dispatchEvent(new Event("change")); });
    input.addEventListener("change", function () {
      if (label) label.textContent = Array.prototype.map.call(input.files, function (f) { return f.name; }).join(", ") || "";
    });
  });

  // Auto-submit selects (filters)
  doc.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit(); });
  });

  // Template gallery filter (client side)
  var filterBar = doc.querySelector("[data-filter-bar]");
  if (filterBar) {
    filterBar.addEventListener("click", function (e) {
      var b = e.target.closest("[data-filter]"); if (!b) return;
      var val = b.getAttribute("data-filter");
      filterBar.querySelectorAll("[data-filter]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      doc.querySelectorAll("[data-groups]").forEach(function (card) {
        card.hidden = !(val === "all" || card.getAttribute("data-groups").split(" ").indexOf(val) > -1);
      });
      fit();
      if (history.replaceState) history.replaceState(null, "", val === "all" ? location.pathname : "?category=" + val);
    });
  }

  // Hero orbit tilt (fine pointers only)
  var orbit = doc.querySelector("[data-tilt]");
  if (orbit && finePointer && !reduce) {
    var phone = orbit.querySelector(".phone"), tiles = orbit.querySelectorAll(".float-tile"), raf = 0, px = 0, py = 0;
    orbit.addEventListener("pointermove", function (e) {
      var r = orbit.getBoundingClientRect();
      px = (e.clientX - r.left) / r.width - .5; py = (e.clientY - r.top) / r.height - .5;
      if (!raf) raf = requestAnimationFrame(apply);
    });
    orbit.addEventListener("pointerleave", function () { px = py = 0; if (!raf) raf = requestAnimationFrame(apply); });
    function apply() {
      raf = 0;
      phone.style.transform = "rotateY(" + (px * 10) + "deg) rotateX(" + (-py * 8) + "deg)";
      tiles.forEach(function (t, k) { var d = (k + 1) * 6; t.style.transform = "translate(" + (px * d) + "px," + (py * d) + "px)"; });
    }
  }

  // Count-up numbers
  var counters = doc.querySelectorAll("[data-count]");
  if (counters.length && "IntersectionObserver" in window && !reduce) {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, end = parseFloat(el.getAttribute("data-count")), t0 = performance.now();
        (function step(t) {
          var p = Math.min(1, (t - t0) / 1200), v = Math.round(end * (1 - Math.pow(1 - p, 3)));
          el.textContent = v.toLocaleString("en-ZA");
          if (p < 1) requestAnimationFrame(step);
        })(t0);
        co.unobserve(el);
      });
    }, { threshold: .5 });
    counters.forEach(function (c) { co.observe(c); });
  }

  // Simple show/hide toggles: data-toggle="#id"
  doc.addEventListener("change", function (e) {
    var el = e.target;
    if (el.hasAttribute && el.hasAttribute("data-reveals")) {
      var target = doc.querySelector(el.getAttribute("data-reveals"));
      if (target) target.hidden = el.type === "checkbox" ? !el.checked : !el.value;
    }
  });
})();
