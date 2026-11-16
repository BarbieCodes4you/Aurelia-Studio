/* Table-type drawings and a floor-plan sketch for the seating step (app wizard and static site).
   AureliaFloor.icon(kind) returns an SVG for one table type; AureliaFloor.plan(opts) returns a room sketch:
   opts = { top: "sweetheart" | "head" | "none", guest: "round" | "long" | "mixed", count: n, cap: seats,
            topLabel: "Couple", dance: true }. Colours use currentColor so light and dark themes both work. */
(function () {
  "use strict";
  function chairsRound(cx, cy, r, n, rc) {
    var out = "";
    for (var k = 0; k < n; k++) {
      var a = (Math.PI * 2 * k) / n - Math.PI / 2;
      out += '<circle cx="' + (cx + Math.cos(a) * r).toFixed(1) + '" cy="' + (cy + Math.sin(a) * r).toFixed(1) + '" r="' + rc + '" class="fp-chair"/>';
    }
    return out;
  }
  function chairsLine(x1, x2, y, n, rc) {
    var out = "", step = (x2 - x1) / (n - 1 || 1);
    for (var k = 0; k < n; k++) out += '<circle cx="' + (x1 + step * k).toFixed(1) + '" cy="' + y + '" r="' + rc + '" class="fp-chair"/>';
    return out;
  }
  function roundTable(cx, cy, r, seats) { return chairsRound(cx, cy, r + r * 0.42, seats, r * 0.26) + '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" class="fp-table"/>'; }
  function longTable(cx, cy, w, h, perSide, oneSide) {
    var x = cx - w / 2, y = cy - h / 2, rc = h * 0.32;
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="' + (h * 0.18) + '" class="fp-table"/>' +
      (oneSide ? "" : chairsLine(x + w * 0.1, x + w * 0.9, y - rc * 1.6, perSide, rc)) + chairsLine(x + w * 0.1, x + w * 0.9, y + h + rc * 1.6, perSide, rc);
  }
  var ICONS = {
    sweetheart: function () { return '<rect x="34" y="30" width="52" height="18" rx="4" class="fp-table"/><circle cx="50" cy="60" r="6" class="fp-chair fp-chair--couple"/><circle cx="70" cy="60" r="6" class="fp-chair fp-chair--couple"/>'; },
    head: function () { return '<rect x="8" y="26" width="104" height="18" rx="4" class="fp-table"/>' + chairsLine(16, 42, 56, 3, 5) + chairsLine(78, 104, 56, 3, 5) +
      '<circle cx="54" cy="56" r="5" class="fp-chair fp-chair--couple"/><circle cx="66" cy="56" r="5" class="fp-chair fp-chair--couple"/>'; },
    none: function () { return roundTable(60, 40, 16, 8) + '<circle cx="60" cy="17.5" r="4.2" class="fp-chair fp-chair--couple"/><circle cx="76" cy="24" r="4.2" class="fp-chair fp-chair--couple"/>'; },
    round: function () { return roundTable(60, 40, 17, 10); },
    long: function () { return longTable(60, 40, 96, 16, 6, false); },
    mixed: function () { return roundTable(32, 40, 13, 8) + longTable(86, 40, 50, 12, 3, false); }
  };
  function icon(kind) {
    return '<svg class="fp" viewBox="0 0 120 80" aria-hidden="true" focusable="false">' + (ICONS[kind] || ICONS.round)() + "</svg>";
  }
  function plan(o) {
    var count = Math.max(1, Math.min(60, +o.count || 10)), cap = Math.max(2, Math.min(20, +o.cap || 10)), W = 320, svg = "", y = 22;
    var cols = o.guest === "long" ? 2 : 4, rows = Math.ceil(count / cols), rowH = o.guest === "long" ? 46 : 54;
    var H = y + (o.top === "none" ? 0 : 54) + (o.dance ? 52 : 6) + rows * rowH + 10;
    svg += '<text x="' + W / 2 + '" y="12" class="fp-label" text-anchor="middle">' + (o.stage || "Front of the room") + "</text>";
    if (o.top === "sweetheart") { svg += '<rect x="' + (W / 2 - 26) + '" y="' + y + '" width="52" height="14" rx="3" class="fp-table fp-table--top"/>' + chairsLine(W / 2 - 9, W / 2 + 9, y + 24, 2, 5).replace(/fp-chair/g, "fp-chair fp-chair--couple"); y += 54; }
    else if (o.top === "head") { svg += '<rect x="' + (W / 2 - 90) + '" y="' + y + '" width="180" height="14" rx="3" class="fp-table fp-table--top"/>' + chairsLine(W / 2 - 80, W / 2 - 22, y + 24, 4, 4.6) + chairsLine(W / 2 + 22, W / 2 + 80, y + 24, 4, 4.6) +
      chairsLine(W / 2 - 7, W / 2 + 7, y + 24, 2, 4.8).replace(/fp-chair/g, "fp-chair fp-chair--couple"); y += 54; }
    if (o.dance) { svg += '<rect x="' + (W / 2 - 60) + '" y="' + (y - 2) + '" width="120" height="38" rx="6" class="fp-dance"/><text x="' + W / 2 + '" y="' + (y + 21) + '" class="fp-label" text-anchor="middle">Dance floor</text>'; y += 52; }
    for (var k = 0; k < count; k++) {
      var c = k % cols, r = Math.floor(k / cols), cx = (W / cols) * (c + 0.5), cy = y + r * rowH + rowH / 2 - 4;
      var isLong = o.guest === "long" || (o.guest === "mixed" && (k % 3 === 2));
      svg += isLong ? longTable(cx, cy, o.guest === "long" ? 120 : 52, 12, Math.min(8, Math.ceil(cap / 2)), false) : roundTable(cx, cy, 13, Math.min(cap, 12));
    }
    return '<svg class="fp fp--plan" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Sketch of your room layout">' + svg + "</svg>";
  }
  window.AureliaFloor = { icon: icon, plan: plan };
})();
