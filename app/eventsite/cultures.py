"""Heritage: one traditional wedding invitation, in an edition for each culture.

Each edition opens like a gatefold: two doors covered in that culture's own pattern swing open on a
beaded medallion, and inside is a card with the same pattern as its border, an emblem drawn from
the culture's wedding dress, and (where a source confirmed it) the culture's own word for the
wedding.

What each edition draws on (researched November 2026; colours are motifs, not a fixed code, since
meanings vary by region and family):
- Ndebele: painted geometric walls, bold colour outlined in black; the nguba blanket's broad
  stripes; isigolwani beaded hoops.
- Zulu: beadwork in triangles and diamonds; the isicholo, the wide hat married women wear; umabo,
  the traditional wedding.
- Xhosa: umbhaco cloth, cream or ochre, edged in black braid; beaded collars; umtshato, marriage.
- Pedi: turquoise, bright pink and yellow, with blue and white; ribbon-trimmed cloths; lenyalo.
- Venda: minwenda cloth, stripes of red, yellow, green and blue between bold black lines; the
  ngoma drum; mbingano.
- Tsonga: the xibelani, a gathered skirt in pink, yellow, purple, blue and green that shakes when
  the wearer dances; vukati, marriage.
- Swati: emahiya, red cloth printed in white; the shield and spears; umtsimba, the wedding.
"""
from __future__ import annotations

import functools
import math

from ..web import esc
from . import designs as D
from . import themes

# word for the wedding (only where a source confirmed it) and the line under it
WORDS = {
    "ndebele": ("", "An Ndebele traditional wedding"),
    "zulu": ("Umabo", "A Zulu traditional wedding"),
    "xhosa": ("Umtshato", "A Xhosa traditional wedding"),
    "pedi": ("Lenyalo", "A Pedi traditional wedding"),
    "venda": ("Mbingano", "A Venda traditional wedding"),
    "tsonga": ("Vukati", "A Tsonga traditional wedding"),
    "swati": ("Umtsimba", "A Swati traditional wedding"),
    "classic": ("", "A traditional wedding"),
}


def _r(cls, x, y, w, h, extra=""):
    return f'<rect class="{cls}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"{extra}/>'


def _bead(cls, x, y, s=4.0):
    return f'<rect class="{cls}" x="{x * s + .35:g}" y="{y * s + .35:g}" width="{s - .7:g}" height="{s - .7:g}" rx="1"/>'


# --- patterns: a band (borders, 56 high) and a panel (the gatefold doors) for each culture ----------
def _ndebele():
    band = ['<rect class="m6" width="120" height="56"/>', _r("m5", 0, 0, 120, 5), _r("m5", 0, 51, 120, 5)]
    ln = ' stroke-width="2.6" stroke-linejoin="round"'
    band.append(f'<rect class="m1 st" x="3" y="8" width="34" height="40"{ln}/>')
    band.append(f'<path class="m6 st" d="M7 44V38H11V32H15V26H19V20H21V26H25V32H29V38H33V44Z"{ln}/>')
    band.append(f'<path class="m2 st" d="M43 8H77V48H43Z"{ln}/><path class="m3 st" d="M43 8H77L43 48Z"{ln}/>')
    band.append(f'<rect class="m6 st" x="54" y="22" width="12" height="12"{ln}/>')
    band.append(f'<rect class="m4 st" x="83" y="8" width="34" height="40"{ln}/><path class="m6 st" d="M100 12 112 28 100 44 88 28Z"{ln}/>')
    band.append(f'<path class="m1 st" d="M100 20 106 28 100 36 94 28Z"{ln}/>')
    panel = ['<rect class="m6" width="120" height="120"/>']
    cols = ("m1", "m3", "m2", "m4")
    for q, (qx, qy) in enumerate(((0, 0), (60, 0), (0, 60), (60, 60))):
        a, b = cols[q], cols[(q + 2) % 4]
        panel.append(f'<rect class="{a} st" x="{qx + 4}" y="{qy + 4}" width="52" height="52" stroke-width="3"/>')
        panel.append(f'<path class="m6 st" d="M{qx + 12} {qy + 48}V{qy + 40}H{qx + 18}V{qy + 32}H{qx + 24}V{qy + 24}H{qx + 36}V{qy + 32}H{qx + 42}V{qy + 40}H{qx + 48}V{qy + 48}Z" stroke-width="2.6"/>')
        panel.append(f'<rect class="{b} st" x="{qx + 26}" y="{qy + 34}" width="8" height="14" stroke-width="2"/>')
    return "".join(band), "".join(panel), (120, 56), (120, 120)


def _zulu():
    band = []
    for r in range(14):
        for c in range(12):
            if r in (0, 13):
                cls = "m5"
            elif r in (1, 12):
                cls = "m6"
            else:
                half, cc = c // 6, c % 6
                d = abs(cc - 2.5) + abs(r - 6.5)
                cls = "m2" if d <= 1.5 else ("m1", "m3")[half] if d <= 3.5 else ("m4" if (r in (2, 11) and cc in (0, 5)) else "m6")
            band.append(_bead(cls, c, r))
    panel = []
    for r in range(12):
        for c in range(12):
            d = abs(c - 5.5) + abs(r - 5.5)
            panel.append(_bead(("m1", "m6", "m3", "m2", "m5", "m6")[int(d) % 6], c, r))
    return '<rect class="m6" width="48" height="56"/>' + "".join(band), "".join(panel), (48, 56), (48, 48)


def _xhosa():
    band = ['<rect class="m2" width="40" height="56"/>', _r("m5", 0, 4, 40, 3), _r("m5", 0, 10, 40, 7), _r("m5", 0, 20, 40, 2)]
    for k, cls in enumerate(("m6", "m3", "m6", "m1", "m6", "m3", "m6", "m1")):
        band.append(f'<rect class="{cls}" x="{k * 5 + .5}" y="25.5" width="4" height="5" rx="1"/>')
    band += [_r("m5", 0, 34, 40, 2), _r("m5", 0, 39, 40, 7), _r("m5", 0, 49, 40, 3)]
    panel = ['<rect class="m1" width="40" height="120"/>', '<rect class="m2" y="58" width="40" height="62"/>',
             _r("m5", 0, 46, 40, 3), _r("m5", 0, 52, 40, 6), _r("m5", 0, 60, 40, 2)]
    for k, cls in enumerate(("m6", "m3", "m6", "m5", "m6", "m3", "m6", "m5")):
        panel.append(f'<rect class="{cls}" x="{k * 5 + .5}" y="64.5" width="4" height="5" rx="1"/>')
    panel += [_r("m5", 0, 72, 40, 2), _r("m5", 0, 76, 40, 6), _r("m5", 0, 84, 40, 3)]
    panel.append('<path d="M0 20h40M0 100h40" stroke="rgb(0 0 0 / .08)" stroke-width="1"/>')
    return "".join(band), "".join(panel), (40, 56), (40, 120)


def _pedi():
    band = ['<rect class="m6" width="36" height="56"/>', _r("m3", 0, 0, 36, 6), _r("m1", 0, 8, 36, 8), _r("m2", 0, 18, 36, 5)]
    for k in range(6):
        band.append(f'<path class="{("m4", "m1")[k % 2]}" d="M{k * 6} 33l3-7 3 7Z"/>')
    band += [_r("m2", 0, 35, 36, 5), _r("m1", 0, 42, 36, 8), _r("m3", 0, 52, 36, 4)]
    panel = ['<rect class="m6" width="40" height="80"/>']
    for k, cls in enumerate(("m1", "m3", "m2", "m4", "m1")):
        panel.append(_r(cls, k * 8 + 1, 0, 6, 80))
    for k in range(5):
        panel.append(f'<path class="m6" d="M{k * 8} 46l4-6 4 6Z"/><path class="m5o" d="M{k * 8} 40h8"/>')
    return "".join(band), "".join(panel), (36, 56), (40, 80)


def _venda():
    band = ['<rect class="m5" width="48" height="56"/>', _r("m1", 0, 4, 48, 4), _r("m2", 0, 10, 48, 3), _r("m4", 0, 15, 48, 3)]
    for k in range(4):
        x = k * 12
        band.append(f'<path class="{("m6", "m2")[k % 2]}" d="M{x} 34 {x + 6} 22l6 12Z"/>')
        band.append(f'<path class="{("m3", "m1")[k % 2]}" d="M{x + 6} 22h12l-6 12Z"/>')
    band += [_r("m4", 0, 38, 48, 3), _r("m2", 0, 43, 48, 3), _r("m1", 0, 48, 48, 4)]
    panel = ['<rect class="m5" width="48" height="96"/>']
    for y0 in (0, 48):
        panel += [_r("m1", 0, y0 + 4, 48, 5), _r("m2", 0, y0 + 12, 48, 3), _r("m4", 0, y0 + 18, 48, 3), _r("m3", 0, y0 + 24, 48, 2)]
        for k in range(4):
            x = k * 12
            panel.append(f'<path class="{("m6", "m2")[k % 2]}" d="M{x} {y0 + 40} {x + 6} {y0 + 30}l6 10Z"/>')
    return "".join(band), "".join(panel), (48, 56), (48, 96)


def _tsonga():
    def ruffles(colours, y0=0, h=11, w=30):
        out = []
        for k, cls in enumerate(colours):
            y = y0 + k * h
            out.append(_r(cls, 0, y, w, h))
            out.append('<path class="pleat" d="' + "".join(f"M{x} {y}v{h}" for x in range(2, w, 3)) + '"/>')
            out.append("".join(f'<circle class="{cls}" cx="{x + 1.5}" cy="{y + h}" r="1.9"/>' for x in range(0, w, 3)))
        return "".join(out)
    band = ['<rect class="m6" width="30" height="60"/>', ruffles(("m1", "m2", "m3", "m4"))]
    fringe = "".join(f'<path class="m5s" d="M{x + 1.5} 46v9"/><circle class="{("m1", "m2", "m3", "m4", "m5")[k % 5]}" cx="{x + 1.5}" cy="56" r="1.8"/>'
                     for k, x in enumerate(range(0, 30, 3)))
    band.append(f'<g class="ts-fringe">{fringe}</g>')
    panel = ['<rect class="m6" width="30" height="55"/>', ruffles(("m1", "m2", "m5", "m3", "m4"))]
    return "".join(band), "".join(panel), (30, 60), (30, 55)


def _swati():
    def shield(cx, cy, s=1.0):
        return (f'<ellipse class="m6" cx="{cx}" cy="{cy}" rx="{5 * s:g}" ry="{9 * s:g}"/><path class="m1s" d="M{cx} {cy - 9 * s:g}v{18 * s:g}"/>'
                f'<circle class="m1" cx="{cx - 2 * s:g}" cy="{cy - 3 * s:g}" r="{1 * s:g}"/><circle class="m1" cx="{cx + 2 * s:g}" cy="{cy + 3 * s:g}" r="{1 * s:g}"/>')
    band = ['<rect class="m1" width="48" height="56"/>', _r("m5", 0, 0, 48, 4), _r("m6", 0, 4, 48, 2), _r("m3", 0, 7, 48, 2),
            shield(12, 28), '<path class="m6" d="M36 20l6 8-6 8-6-8Z"/><circle class="m1" cx="36" cy="28" r="1.6"/>',
            _r("m2", 0, 47, 48, 2), _r("m6", 0, 50, 48, 2), _r("m5", 0, 52, 48, 4)]
    panel = ['<rect class="m1" width="60" height="60"/>', shield(15, 15, .9), shield(45, 45, .9),
             '<path class="m6" d="M45 9l4 6-4 6-4-6ZM15 39l4 6-4 6-4-6Z"/>',
             "".join(f'<circle class="m6" cx="{x}" cy="{y}" r=".9"/>' for x, y in ((30, 5), (5, 30), (30, 55), (55, 30), (30, 30)))]
    return "".join(band), "".join(panel), (48, 56), (60, 60)


def _classic():
    band = ['<rect class="m6" width="48" height="56"/>', _r("m5", 0, 0, 48, 4), _r("m5", 0, 52, 48, 4)]
    for k in range(4):
        x = k * 12
        band.append(f'<path class="{("m1", "m2")[k % 2]}" d="M{x} 44 {x + 6} 12l6 32Z"/><path class="m3" d="M{x + 6} 22l3 6-3 6-3-6Z"/>')
    panel = ['<rect class="m2" width="40" height="40"/>', '<path class="m1" d="M0 20 20 0l20 20-20 20Z"/>',
             '<path class="m6" d="M10 20 20 10l10 10-10 10Z"/>', '<path class="m3" d="M16 20l4-4 4 4-4 4Z"/>']
    return "".join(band), "".join(panel), (48, 56), (40, 40)


MAKERS = {"ndebele": _ndebele, "zulu": _zulu, "xhosa": _xhosa, "pedi": _pedi, "venda": _venda,
          "tsonga": _tsonga, "swati": _swati, "classic": _classic}


PANEL_SCALE = {"zulu": 1.7, "ndebele": 1.3, "pedi": 1.8, "tsonga": 1.7, "venda": 1.25, "xhosa": 1.15, "swati": 1.1, "classic": 1.4}


@functools.lru_cache(maxsize=16)
def defs(key: str) -> str:
    band, panel, (bw, bh), (pw, ph) = MAKERS.get(key, _classic)()
    scale = PANEL_SCALE.get(key, 1)
    return (f'<svg class="iv-defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>'
            f'<pattern id="cu-band" width="{bw}" height="{bh}" patternUnits="userSpaceOnUse">{band}</pattern>'
            f'<pattern id="cu-band-sm" href="#cu-band" patternTransform="scale(.6)"/>'
            f'<pattern id="cu-panel" width="{pw}" height="{ph}" patternUnits="userSpaceOnUse" patternTransform="scale({scale})">{panel}</pattern>'
            f'</defs></svg>')


def band(cls: str = "", small: bool = False) -> str:
    h, pid = (34, "cu-band-sm") if small else (56, "cu-band")
    return (f'<div class="cu-band {cls}" aria-hidden="true"><svg width="100%" height="{h}" focusable="false">'
            f'<rect width="100%" height="{h}" fill="url(#{pid})"/></svg></div>')


def panel_fill() -> str:
    return ('<svg class="cu-fill" width="100%" height="100%" aria-hidden="true" focusable="false">'
            '<rect width="100%" height="100%" fill="url(#cu-panel)"/></svg>')


# --- emblems: something from the culture's wedding dress or ceremony -------------------------------
EMBLEMS = {
    # the isicholo: the wide flared hat a married Zulu woman wears, with a beaded band
    "zulu": ('<path class="m1" d="M8 22 41 70q19 8 38 0l33-48Z"/><path d="M8 22 41 70q19 8 38 0l33-48" class="ln"/>'
             '<ellipse class="m1" cx="60" cy="22" rx="52" ry="12"/><ellipse cx="60" cy="22" rx="52" ry="12" class="ln hi"/>'
             '<ellipse cx="60" cy="21" rx="40" ry="7" class="shade"/>'
             '<path class="m6" d="M34 58h52l-5 9q-21 7-42 0Z"/>'
             + "".join(f'<rect class="{("m5", "m3", "m5", "m2")[k % 4]}" x="{36 + k * 4.2:.1f}" y="60" width="3" height="4.5" rx=".8"/>' for k in range(12))
             + '<path d="M18 30q42 18 84 0" class="ln soft"/><path d="M26 40q34 14 68 0" class="ln soft"/>'),
    # a beaded Xhosa collar: rows of white, turquoise and orange beads, with a fringe
    "xhosa": ("".join(f'<path class="arc {c}" d="M{60 - r} 8a{r} {r} 0 0 0 {2 * r} 0" stroke-width="7"/>'
                      for r, c in ((50, "m6s"), (43, "m3s"), (36, "m1s"), (29, "m6s"), (22, "m5s")))
              + "".join(f'<path class="m5s thin" d="M{60 + 52 * math.cos(a):.1f} {8 + 52 * math.sin(a):.1f}l{6 * math.cos(a):.1f} {6 * math.sin(a):.1f}"/>'
                        f'<circle class="{("m3", "m1", "m6")[k % 3]}" cx="{60 + 60 * math.cos(a):.1f}" cy="{8 + 60 * math.sin(a):.1f}" r="2.4"/>'
                        for k, a in enumerate(math.pi * (.12 + .76 * j / 12) for j in range(13)))),
    # isigolwani: Ndebele beaded hoops, worn stacked at the neck
    "ndebele": "".join(f'<ellipse cx="60" cy="{y}" rx="44" ry="11" class="m5s" stroke-width="13"/>'
                       f'<ellipse cx="60" cy="{y}" rx="44" ry="11" class="hoop" stroke-width="9"/>'
                       f'<ellipse cx="60" cy="{y}" rx="44" ry="11" class="hoop-b {c}" stroke-width="9" stroke-dasharray="5 3"/>'
                       for y, c in ((62, "m2s"), (44, "m3s"), (26, "m1s"))),
    # a rosette of ribbons in Pedi colours
    "pedi": ("".join(f'<path class="{("m1", "m3", "m2", "m4")[k % 4]}" d="M60 44 {60 + 34 * math.cos(a):.1f} {44 + 34 * math.sin(a):.1f}a10 10 0 0 1 {12 * math.cos(a + 1.6):.1f} {12 * math.sin(a + 1.6):.1f}Z"/>'
                     for k, a in enumerate(2 * math.pi * j / 16 for j in range(16)))
             + '<path class="m1" d="M52 56 40 88l8-3 5 6 5-32Z"/><path class="m3" d="M68 56l12 32-8-3-5 6-5-32Z"/>'
             '<circle class="m6" cx="60" cy="44" r="14"/><circle class="m2" cx="60" cy="44" r="9"/><circle class="m6" cx="60" cy="44" r="3"/>'),
    # the ngoma, the Venda drum, with a cowhide top and a carved zigzag band
    "venda": ('<path class="wood" d="M24 26h72l-8 40q-4 10-28 10T32 66Z"/>'
              '<path class="m5" d="M27 40h66l-2 10H29Z"/>'
              + "".join(f'<path class="{("m1", "m2")[k % 2]}" d="M{29 + k * 8} 50l4-10 4 10Z"/>' for k in range(8))
              + '<ellipse cx="60" cy="26" rx="36" ry="9" class="skin"/><path class="m5" d="M44 24c4-3 10-2 11 1-3 3-9 3-11-1Zm24 3c3-2 8-1 8 2-2 2-7 2-8-2Z"/>'
              + "".join(f'<rect class="m5" x="{30 + k * 10}" y="33" width="3" height="6" rx="1"/>' for k in range(7))
              + '<path d="M44 76h32l-4 8H48Z" class="wood"/>'),
    # the xibelani: a Tsonga gathered skirt in layered colours, with a beaded waistband
    "tsonga": ("".join(f'<path class="{c}" d="M{34 - k * 6} {20 + k * 15}h{52 + k * 12}l4 15H{30 - k * 6}Z"/>'
                       for k, c in enumerate(("m1", "m2", "m3", "m4")))
               + "".join(f'<path class="pleat" d="M{x} 20v60"/>' for x in range(16, 106, 4))
               + '<rect class="m5" x="32" y="13" width="56" height="8" rx="2"/>'
               + "".join(f'<rect class="{("m1", "m2", "m3", "m6")[k % 4]}" x="{34 + k * 4.4:.1f}" y="15" width="3" height="4" rx=".7"/>' for k in range(12))
               + '<path class="ts-fringe2 m5s" d="' + "".join(f"M{x} 80v6" for x in range(12, 110, 4)) + '"/>'),
    # the Swati shield and spears, with a staff carrying tassels
    "swati": ('<path class="ln" d="M12 70 108 18M12 18 108 70"/><path class="m2" d="M106 15l6-3-1 7Z"/><path class="m2" d="M14 15l-6-3 1 7Z"/>'
              '<path class="ln" d="M60 4v82"/><circle class="m3" cx="60" cy="8" r="3"/><circle class="m3" cx="60" cy="16" r="3"/><circle class="m2" cx="60" cy="24" r="3"/>'
              '<ellipse class="m6 st" cx="60" cy="46" rx="48" ry="21" stroke-width="2"/><path class="m5" d="M60 25a48 21 0 0 0 0 42Z"/>'
              '<path class="m6" d="M38 36c4-2 8-1 8 2-2 3-7 3-8-2Zm-6 14c3-1 6 0 6 2-2 2-5 2-6-2Z"/>'
              '<path class="m5" d="M76 36c4-2 8-1 8 2-2 3-7 3-8-2Zm6 14c3-1 6 0 6 2-2 2-5 2-6-2Z"/>'),
    "classic": ('<path class="m1" d="M60 6 104 46 60 86 16 46Z"/><path class="m6" d="M60 20 90 46 60 72 30 46Z"/>'
                '<path class="m2" d="M60 32 76 46 60 60 44 46Z"/><path class="m5" d="M60 40l6 6-6 6-6-6Z"/>'),
}


def emblem(key: str) -> str:
    return (f'<svg class="cu-emblem cu-emblem--{key}" viewBox="0 0 120 92" aria-hidden="true" focusable="false">'
            f'{EMBLEMS.get(key, EMBLEMS["classic"])}</svg>')


def medallion(mono: str) -> str:
    beads = "".join(f'<path class="{("m1", "m2", "m3", "m4")[k % 4]}s" d="M{50 + 44 * math.cos(a):.1f} {50 + 44 * math.sin(a):.1f}'
                    f'A44 44 0 0 1 {50 + 44 * math.cos(a + .2):.1f} {50 + 44 * math.sin(a + .2):.1f}" stroke-width="9"/>'
                    for k, a in enumerate(2 * math.pi * j / 24 for j in range(24)))
    return (f'<div class="cu-medal" aria-hidden="true"><svg viewBox="0 0 100 100" focusable="false">'
            f'<circle cx="50" cy="50" r="49" class="medal-rim"/>{beads}<circle cx="50" cy="50" r="37" class="medal-in"/>'
            f'<circle cx="50" cy="50" r="33" class="medal-line"/>'
            f'<text x="50" y="58" text-anchor="middle" class="medal-mono">{esc(mono[:3])}</text></svg></div>')


# --- the layout ---------------------------------------------------------------------------------
NAV = {"invitation": "Invitation", "venue": "Ceremonies", "registry": "Gifts", "rsvp": "RSVP"}


def heritage(ctx) -> str:
    from . import invites as I
    key = themes.culture("heritage", ctx["theme"]["palette"]) or "classic"
    word, line = WORDS[key]
    secs = D.collect(ctx)
    fam = I.families(ctx)
    card = (f'<article class="cu-card" aria-labelledby="cu-names">{band("cu-band--top")}<div class="cu-in">'
            f'{emblem(key)}{D.greeting(ctx)}'
            f'{f"<p class=cu-word>{esc(word)}</p>" if word else ""}<p class="cu-line">{esc(line)}</p>'
            f'<h1 class="cu-names" id="cu-names">{D.names_html(ctx, "&amp;")}</h1>'
            f'{fam}<p class="cu-welcome">{esc(ctx["wording"]["welcome"])}</p>'
            f'<div class="cu-rule" aria-hidden="true"><i></i></div>{I.date_row(ctx, "cu-date")}{I.where(ctx, "cu-where")}'
            f'{I.actions(ctx, "RSVP")}{I.reply_by(ctx)}</div>{band("cu-band--bottom")}</article>')
    doors = (f'<div class="cu-door cu-door--l" aria-hidden="true"><div class="cu-face cu-face--out">{panel_fill()}</div>'
             f'<div class="cu-face cu-face--in">{panel_fill()}</div></div>'
             f'<div class="cu-door cu-door--r" aria-hidden="true"><div class="cu-face cu-face--out">{panel_fill()}</div>'
             f'<div class="cu-face cu-face--in">{panel_fill()}</div></div>')
    hero = (f'<header class="cu-hero" id="welcome">{defs(key)}<div class="cu-gate">{doors}{card}{medallion(ctx["monogram"])}</div></header>')
    sections = []
    for k, html in secs:
        title = "The ceremonies" if (k == "venue" and len(ctx["functions"]) > 1) else ""
        sections.append(D.section(k, html, title=title, cls="iv-sec cu-sec rv").replace(
            '<div class="ev-sec__in">', f'<div class="ev-sec__in">{band("cu-band--sec", small=True)}', 1))
    return (hero + D.nav(ctx, secs, "ev-nav iv-nav cu-nav") + I.photo(ctx, "cu-photo")
            + f'<div class="cu-body">{"".join(sections)}</div>')
