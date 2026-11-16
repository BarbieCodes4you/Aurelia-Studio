/* Seating chart editor: drag tables around the floor, drag guest parties onto tables,
   tap-to-assign on touch screens. Talks to /dashboard/events/<uid>/seating/api/* (JSON, CSRF header). */
(function () {
  "use strict";
  var root = document.querySelector("[data-seating]");
  if (!root) return;
  var api = root.getAttribute("data-api");
  var dataEl = document.getElementById("seating-data");
  var state = JSON.parse(dataEl.textContent);
  var floor = root.querySelector("[data-floor]");
  var pool = root.querySelector("[data-pool]");
  var editor = root.querySelector("[data-table-editor]");
  var includePending = root.querySelector("[data-include-pending]");
  var selectedGuest = null, selectedTable = null;

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function call(action, body) {
    return Aurelia.post(api + "/" + action, body).then(function (res) {
      state = res.state;
      render();
      if (res.warning) Aurelia.toast(res.warning, "error");
      return res;
    }).catch(function (err) { Aurelia.toast(err.message || "Something went wrong", "error"); });
  }

  function guestsAt(tableId) { return state.guests.filter(function (g) { return g.table === tableId; }); }

  function render() {
    // pool
    var loose = state.guests.filter(function (g) {
      return !g.table && (g.status === "attending" || (includePending && includePending.checked && g.status === "pending"));
    });
    pool.innerHTML = loose.length ? loose.map(function (g) {
      return '<div class="seat-chip' + (selectedGuest === g.id ? " is-selected" : "") + '" draggable="true" tabindex="0" role="button" data-guest="' + g.id + '" aria-label="' + esc(g.name) + ", party of " + g.party + '">' +
        '<span>' + esc(g.name) + (g.vip ? ' <span class="tag">VIP</span>' : "") + (g.status === "pending" ? ' <span class="tag">Pending</span>' : "") +
        (g.group ? '<br><span class="tiny muted">' + esc(g.group) + "</span>" : "") + '</span><span class="party">' + g.party + "</span></div>";
    }).join("") : '<p class="small muted">Everyone in this view has a seat.</p>';

    // floor
    floor.querySelectorAll(".s-table").forEach(function (n) { n.remove(); });
    var maxY = 0;
    state.tables.forEach(function (t) {
      var people = guestsAt(t.id);
      var fill = Math.min(100, Math.round(100 * t.seated / t.capacity));
      var el = document.createElement("div");
      el.className = "s-table glass glass--strong" + (t.shape === "long" ? " s-table--long" : "") +
        (t.seated === t.capacity ? " is-full" : "") + (t.seated > t.capacity ? " is-over-cap" : "") + (selectedTable === t.id ? " is-over" : "");
      el.style.left = t.x + "%";
      el.style.top = t.y + "%";
      el.setAttribute("data-table", t.id);
      el.setAttribute("tabindex", "0");
      el.setAttribute("aria-label", t.name + ", " + t.seated + " of " + t.capacity + " seats");
      el.innerHTML = '<div class="s-table__ring" style="--fill:' + fill + '"><span>' + t.seated + "/" + t.capacity + "</span></div>" +
        '<div class="s-table__name">' + esc(t.name) + '</div><div class="s-table__occ">' +
        (t.seated > t.capacity ? "Over by " + (t.seated - t.capacity) : (t.capacity - t.seated) + " free") + "</div>" +
        (people.length ? "<ul>" + people.map(function (g) {
          return '<li draggable="true" data-guest="' + g.id + '"><span>' + esc(g.name) + (g.party > 1 ? " +" + (g.party - 1) : "") +
            '</span><button type="button" data-unassign="' + g.id + '" aria-label="Remove ' + esc(g.name) + ' from table">×</button></li>';
        }).join("") + "</ul>" : "");
      floor.appendChild(el);
      maxY = Math.max(maxY, t.y);
    });
    floor.style.minHeight = Math.max(640, (maxY / 100) * 640 + 260) + "px";
    if (!state.tables.length) {
      if (!floor.querySelector("[data-empty]")) floor.insertAdjacentHTML("beforeend", '<p data-empty class="small muted" style="position:absolute;inset:auto 0 45% 0;text-align:center">Add tables on the left to start your floor plan.</p>');
    } else {
      var e = floor.querySelector("[data-empty]"); if (e) e.remove();
    }
    renderEditor();
  }

  function renderEditor() {
    var t = state.tables.filter(function (x) { return x.id === selectedTable; })[0];
    if (!t) { editor.hidden = true; editor.innerHTML = ""; return; }
    editor.hidden = false;
    editor.innerHTML = '<form class="stack" style="--stack:10px" data-edit-table><h2 style="font-size:1rem">Edit ' + esc(t.name) + "</h2>" +
      '<div class="form-row form-row--2"><input class="input input--sm" name="name" value="' + esc(t.name) + '" maxlength="40" aria-label="Table name">' +
      '<input class="input input--sm" name="capacity" type="number" min="1" max="40" value="' + t.capacity + '" aria-label="Capacity"></div>' +
      (state.advanced ? '<select class="select select--sm" name="shape" aria-label="Shape"><option value="round"' + (t.shape === "round" ? " selected" : "") + '>Round</option><option value="long"' + (t.shape === "long" ? " selected" : "") + ">Long</option></select>" +
        '<input class="input input--sm" name="notes" value="' + esc(t.notes) + '" maxlength="200" placeholder="Note, e.g. near the stage" aria-label="Table note">' : "") +
      '<div class="row"><button class="btn btn--primary btn--sm" type="submit">Save</button><button class="btn btn--danger btn--sm" type="button" data-delete-table>Delete</button>' +
      '<button class="btn btn--ghost btn--sm" type="button" data-close-editor>Done</button></div></form>';
  }

  // --- automatic seating ------------------------------------------------------------------------
  root.addEventListener("click", function (e) {
    var b = e.target.closest("[data-autoseat]");
    if (!b) return;
    b.disabled = true;
    call("autoseat", { include_pending: !!(includePending && includePending.checked) }).then(function (res) {
      b.disabled = false;
      if (res && res.message) Aurelia.toast(res.message);
    });
  });

  // --- forms -------------------------------------------------------------------------------
  root.addEventListener("submit", function (e) {
    var f = e.target;
    if (f.hasAttribute("data-new-table")) {
      e.preventDefault();
      call("create", { name: f.elements["name"].value, capacity: f.elements["capacity"].value, shape: f.elements["shape"] ? f.elements["shape"].value : "round" }).then(function () { f.elements["name"].value = ""; });
    } else if (f.hasAttribute("data-auto-tables")) {
      e.preventDefault();
      call("autocreate", { count: f.elements["count"].value, capacity: f.elements["capacity"].value });
    } else if (f.hasAttribute("data-edit-table")) {
      e.preventDefault();
      var body = { id: selectedTable, name: f.elements["name"].value, capacity: f.elements["capacity"].value };
      if (f.elements["shape"]) body.shape = f.elements["shape"].value;
      if (f.elements["notes"]) body.notes = f.elements["notes"].value;
      call("update", body).then(function () { Aurelia.toast("Table saved"); });
    }
  }, true);

  root.addEventListener("click", function (e) {
    var un = e.target.closest("[data-unassign]");
    if (un) { e.stopPropagation(); call("assign", { guest_id: +un.getAttribute("data-unassign"), table_id: null }); return; }
    if (e.target.closest("[data-delete-table]")) {
      var t = state.tables.filter(function (x) { return x.id === selectedTable; })[0];
      if (t && window.confirm("Delete " + t.name + "? Guests at it go back to the not-seated list.")) { selectedTable = null; call("delete", { id: t.id }); }
      return;
    }
    if (e.target.closest("[data-close-editor]")) { selectedTable = null; render(); return; }
    var chip = e.target.closest(".seat-chip");
    if (chip) { var id = +chip.getAttribute("data-guest"); selectedGuest = selectedGuest === id ? null : id; render(); }
  });

  pool.addEventListener("keydown", function (e) {
    var chip = e.target.closest(".seat-chip");
    if (chip && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); chip.click(); }
  });

  if (includePending) includePending.addEventListener("change", render);

  // --- drag guests (HTML5 DnD) ---------------------------------------------------------------
  root.addEventListener("dragstart", function (e) {
    var g = e.target.closest("[data-guest]");
    if (!g) return;
    e.dataTransfer.setData("text/plain", g.getAttribute("data-guest"));
    e.dataTransfer.effectAllowed = "move";
    g.classList.add("is-dragging");
  });
  root.addEventListener("dragend", function (e) { var g = e.target.closest("[data-guest]"); if (g) g.classList.remove("is-dragging"); });
  floor.addEventListener("dragover", function (e) {
    var t = e.target.closest(".s-table"); if (!t) return;
    e.preventDefault(); t.classList.add("is-over");
  });
  floor.addEventListener("dragleave", function (e) { var t = e.target.closest(".s-table"); if (t && !t.contains(e.relatedTarget)) t.classList.remove("is-over"); });
  floor.addEventListener("drop", function (e) {
    var t = e.target.closest(".s-table"); if (!t) return;
    e.preventDefault();
    var gid = +e.dataTransfer.getData("text/plain");
    if (gid) call("assign", { guest_id: gid, table_id: +t.getAttribute("data-table") });
  });
  pool.addEventListener("dragover", function (e) { e.preventDefault(); });
  pool.addEventListener("drop", function (e) {
    e.preventDefault();
    var gid = +e.dataTransfer.getData("text/plain");
    var g = state.guests.filter(function (x) { return x.id === gid; })[0];
    if (g && g.table) call("assign", { guest_id: gid, table_id: null });
  });

  // --- move tables (pointer events), click to select / assign -----------------------------------
  var drag = null;
  floor.addEventListener("pointerdown", function (e) {
    var el = e.target.closest(".s-table");
    if (!el || e.target.closest("li, button")) return;
    var rect = floor.getBoundingClientRect();
    drag = { el: el, id: +el.getAttribute("data-table"), sx: e.clientX, sy: e.clientY, rect: rect, moved: false };
    el.setPointerCapture(e.pointerId);
  });
  floor.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
    drag.moved = true;
    var x = Math.max(4, Math.min(96, ((e.clientX - drag.rect.left) / drag.rect.width) * 100));
    var y = Math.max(6, Math.min(96, ((e.clientY - drag.rect.top) / drag.rect.height) * 100));
    drag.el.style.left = x + "%"; drag.el.style.top = y + "%";
    drag.x = x; drag.y = y;
  });
  floor.addEventListener("pointerup", function () {
    if (!drag) return;
    var d = drag; drag = null;
    if (d.moved) {
      call("update", { id: d.id, x: Math.round(d.x * 10) / 10, y: Math.round(d.y * 10) / 10 });
    } else if (selectedGuest) {
      var gid = selectedGuest; selectedGuest = null;
      call("assign", { guest_id: gid, table_id: d.id });
    } else {
      selectedTable = selectedTable === d.id ? null : d.id;
      render();
    }
  });
  floor.addEventListener("keydown", function (e) {
    var el = e.target.closest(".s-table");
    if (!el || (e.key !== "Enter" && e.key !== " ")) return;
    e.preventDefault();
    var id = +el.getAttribute("data-table");
    if (selectedGuest) { var gid = selectedGuest; selectedGuest = null; call("assign", { guest_id: gid, table_id: id }); }
    else { selectedTable = id; render(); }
  });

  render();
})();
