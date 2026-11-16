/* Event website behaviour: live countdown, show/hide attending details, focus the thank-you. */
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  // Countdown
  document.querySelectorAll("[data-countdown]").forEach(function (box) {
    var target = Date.parse(box.getAttribute("data-countdown"));
    if (isNaN(target)) return;
    var cells = {};
    box.querySelectorAll("[data-u]").forEach(function (b) { cells[b.getAttribute("data-u")] = b; });
    var done = box.parentElement.querySelector(".ev-count__done");
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    function tick() {
      var ms = target - Date.now();
      if (ms <= 0) {
        box.hidden = true;
        if (done) done.hidden = false;
        return false;
      }
      var s = Math.floor(ms / 1000);
      cells.d.textContent = Math.floor(s / 86400);
      cells.h.textContent = pad(Math.floor(s % 86400 / 3600));
      cells.m.textContent = pad(Math.floor(s % 3600 / 60));
      cells.s.textContent = pad(s % 60);
      return true;
    }
    if (tick()) { var t = setInterval(function () { if (!tick()) clearInterval(t); }, 1000); }
  });

  // RSVP: hide attending-only fields when declining
  document.querySelectorAll(".ev-rsvp").forEach(function (form) {
    var block = form.querySelector("[data-attending]");
    if (!block) return;
    function sync() {
      var picked = form.querySelector('input[name="status"]:checked');
      block.hidden = !!picked && picked.value === "declined";
    }
    form.addEventListener("change", function (e) { if (e.target.name === "status") sync(); });
    sync();
  });

  var thanks = document.querySelector("[data-focus-me]");
  if (thanks) { thanks.focus({ preventScroll: false }); }
  var err = document.querySelector(".ev-errors");
  if (err) { err.setAttribute("tabindex", "-1"); err.focus(); }
})();
