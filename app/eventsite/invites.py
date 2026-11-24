"""The invitation collection: event websites that open like a real invitation.

Each design starts with an invitation people recognise from 2026 stationery and digital invites: a
Nguni cowhide envelope sealed in gold wax, a woven chevron envelope, a card tied with a hand-drawn bow,
chrome party balloons, a Christmas card in the snow, a champagne toast. Below it the page carries on
as the full event website (RSVP, programme, menu, seating...), built with the shared section builders
in designs.py.

Motion lives in static/css/invites.css. The finished invitation is the base style: animations only add
an entrance or a gentle loop, and they are off for visitors who ask for reduced motion, so nothing has
to animate (or run JavaScript) to be read.
"""
from __future__ import annotations

import functools
import math
import re

from ..web import esc
from . import designs as D


# --- small helpers for drawing ------------------------------------------------------------------
def _rng(seed: int):
    """Deterministic pseudo-random numbers, so a drawing is identical on every page load."""
    state = [seed * 7919 + 17]

    def rnd() -> float:
        state[0] = (state[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return state[0] / 0x7FFFFFFF
    return rnd


def _smooth(pts, closed: bool = True, tension: float = 1 / 6) -> str:
    """Points → a smooth SVG path (Catmull-Rom curves through every point)."""
    n = len(pts)
    out = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    last = n if closed else n - 1
    for i in range(last):
        p0 = pts[i - 1] if (closed or i > 0) else pts[i]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension, p1[1] + (p2[1] - p0[1]) * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension, p2[1] - (p3[1] - p1[1]) * tension)
        out += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return out + ("Z" if closed else "")


def blob(cx: float, cy: float, r: float, seed: int, n: int = 11, jitter: float = .3, squash: float = .8) -> str:
    rnd = _rng(seed)
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n + (rnd() - .5) * (math.pi / n)
        rr = r * (1 - jitter + 2 * jitter * rnd())
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * squash))
    return _smooth(pts)


# --- Nguni cowhide ------------------------------------------------------------------------------
# Patches of a Nguni hide as a seamless tile (patches crossing an edge are repeated on the far side).
# Colours come from CSS: --hide-base, --hide-a (main patches), --hide-b (darker patches and speckles).
_HIDE_W, _HIDE_H = 560, 470
_HIDE_SPOTS = [
    # x, y, radius, seed, tone ("a" main patches, "b" darker ones); small ones are the dappled speckles
    (92, 96, 92, 11, "a"), (318, 58, 62, 23, "b"), (476, 176, 84, 37, "a"), (232, 246, 98, 29, "a"),
    (52, 340, 66, 41, "b"), (396, 388, 76, 53, "a"), (152, 446, 48, 61, "b"), (524, 456, 40, 67, "b"),
    (330, 214, 30, 139, "b"), (140, 330, 26, 149, "a"),
    (300, 118, 11, 71, "b"), (322, 140, 7, 73, "b"), (282, 152, 6, 79, "a"), (400, 250, 12, 83, "b"),
    (424, 272, 8, 89, "b"), (126, 222, 10, 97, "a"), (110, 246, 6, 101, "a"), (500, 300, 7, 103, "b"),
    (182, 30, 8, 107, "b"), (262, 360, 9, 109, "b"), (248, 384, 5, 113, "a"), (36, 190, 6, 127, "b"),
    (540, 80, 9, 131, "a"), (330, 452, 7, 137, "b"),
]


def _hide_tile() -> str:
    out = []
    for cx, cy, r, seed, cls in _HIDE_SPOTS:
        for dx in (-_HIDE_W, 0, _HIDE_W):
            for dy in (-_HIDE_H, 0, _HIDE_H):
                x, y = cx + dx, cy + dy
                if x + r * 1.4 < 0 or x - r * 1.4 > _HIDE_W or y + r * 1.4 < 0 or y - r * 1.4 > _HIDE_H:
                    continue
                out.append(f'<path class="hd-{cls}" d="{blob(x, y, r, seed, n=10 if r > 20 else 7, jitter=.24 if r > 20 else .3, squash=.72 + (seed % 5) * .07)}"/>')
    return "".join(out)


HIDE_TILE = _hide_tile()

# One hidden <svg> per page holds the shared patterns and filters (referenced by id).
def defs_hide(pid: str = "nv-hide") -> str:
    return (f'<svg class="iv-defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>'
            f'<pattern id="{pid}" width="{_HIDE_W}" height="{_HIDE_H}" patternUnits="userSpaceOnUse">'
            f'<rect class="hd-base" width="{_HIDE_W}" height="{_HIDE_H}"/>{HIDE_TILE}</pattern>'
            f'<pattern id="{pid}-sm" href="#{pid}" patternTransform="scale(.28)"/>'
            f'<filter id="{pid}-fur" x="-2%" y="-2%" width="104%" height="104%"><feTurbulence type="fractalNoise" baseFrequency=".045" numOctaves="2" seed="7"/>'
            f'<feDisplacementMap in="SourceGraphic" scale="7" xChannelSelector="R" yChannelSelector="G"/></filter>'
            f'<filter id="{pid}-grain"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>'
            f'<feColorMatrix values="0 0 0 0 .16  0 0 0 0 .11  0 0 0 0 .07  0 0 0 .55 0"/></filter>'
            f'</defs></svg>')


def hide_fill(pid: str = "nv-hide", small: bool = False) -> str:
    """A rectangle of cowhide that fills its box (patterns keep their size, so nothing stretches)."""
    fill = f"{pid}-sm" if small else pid
    return (f'<svg class="hide-fill" width="100%" height="100%" aria-hidden="true" focusable="false">'
            f'<rect x="-3%" y="-3%" width="106%" height="106%" fill="url(#{fill})" filter="url(#{pid}-fur)"/>'
            f'<rect width="100%" height="100%" filter="url(#{pid}-grain)" opacity=".32"/></svg>')


# --- wax seal -------------------------------------------------------------------------------------
def seal(mono: str, sid: str, cls: str = "") -> str:
    letters = [c for c in (mono or "") if c.strip()][:3]
    text = " | ".join(esc(c) for c in letters) if len(letters) == 2 else esc("".join(letters))
    size = 30 if len(letters) <= 2 else 26
    edge = blob(60, 60, 55, 5, n=19, jitter=.045, squash=1)
    return (f'<svg class="seal {cls}" viewBox="0 0 120 120" aria-hidden="true" focusable="false"><defs>'
            f'<radialGradient id="{sid}-g" cx="38%" cy="30%" r="80%"><stop offset="0" class="sl-1"/><stop offset=".45" class="sl-2"/>'
            f'<stop offset=".85" class="sl-3"/><stop offset="1" class="sl-4"/></radialGradient>'
            f'<clipPath id="{sid}-c"><path d="{edge}"/></clipPath>'
            f'<linearGradient id="{sid}-glint" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>'
            f'<path class="seal__edge" d="{edge}" fill="url(#{sid}-g)"/>'
            f'<circle class="seal__ring" cx="60" cy="60" r="41"/><circle class="seal__ring2" cx="60" cy="60" r="36.5"/>'
            f'<text class="seal__shadow" x="61" y="{70.5 if size == 30 else 69.5}" text-anchor="middle" font-size="{size}">{text}</text>'
            f'<text class="seal__mono" x="60" y="{69.5 if size == 30 else 68.5}" text-anchor="middle" font-size="{size}">{text}</text>'
            f'<g clip-path="url(#{sid}-c)"><rect class="seal__glint" x="-50" y="-20" width="40" height="160" fill="url(#{sid}-glint)"/></g>'
            f'</svg>')


# --- dried pampas and bunny tails -------------------------------------------------------------------
def _quad(p0, p1, p2, t):
    return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])


def _dquad(p0, p1, p2, t):
    return (2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]),
            2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1]))


@functools.lru_cache(maxsize=8)
def pampas(cls: str, seed: int = 3, stems: int = 5, tails: int = 3) -> str:
    """A spray of dried pampas plumes and bunny-tail grass growing from the bottom centre of a 220×320 box."""
    rnd = _rng(seed)
    groups = []
    for s in range(stems):
        base = (110 + (rnd() - .5) * 24, 318)
        tip = (22 + s * (176 / max(1, stems - 1)) + (rnd() - .5) * 24, 16 + rnd() * 64)
        ctrl = ((base[0] + tip[0]) / 2 + (rnd() - .5) * 50, (base[1] + tip[1]) / 2 + 20)
        stem = f"M{base[0]:.1f} {base[1]:.1f}Q{ctrl[0]:.1f} {ctrl[1]:.1f} {tip[0]:.1f} {tip[1]:.1f}"
        body = [_quad(base, ctrl, tip, .44 + .56 * k / 8) for k in range(9)]
        fibres = []
        for _ in range(96):
            t = .44 + .56 * rnd() ** .8
            x, y = _quad(base, ctrl, tip, t)
            dx, dy = _dquad(base, ctrl, tip, t)
            ln = math.hypot(dx, dy) or 1
            ux, uy = dx / ln, dy / ln
            side = 1 if rnd() > .5 else -1
            # plumes are fullest a third of the way up and taper to a soft point
            fullness = math.sin(math.pi * min(1, (t - .44) / .56 * 1.1)) ** .7
            reach = (5 + 22 * fullness) * (.55 + .45 * rnd())
            ang = (.35 + .5 * rnd()) * side
            ex = x + (ux * math.cos(ang) - uy * math.sin(ang)) * reach
            ey = y + (uy * math.cos(ang) + ux * math.sin(ang)) * reach
            mx = (x + ex) / 2 + (rnd() - .5) * 4
            my = (y + ey) / 2 + (rnd() - .5) * 4
            fibres.append(f"M{x:.0f} {y:.0f}q{mx - x:.0f} {my - y:.0f} {ex - x:.0f} {ey - y:.0f}")
        plume = _smooth(body, closed=False)
        groups.append(f'<g class="pm-stem" style="--i:{s}"><path class="pm-s" d="{stem}"/><path class="pm-glow" d="{plume}"/>'
                      f'<path class="pm-glow pm-glow--in" d="{plume}"/><path class="pm-f" d="{"".join(fibres)}"/></g>')
    for s in range(tails):
        base = (100 + rnd() * 20, 318)
        tip = (50 + rnd() * 120, 110 + rnd() * 100)
        ctrl = ((base[0] + tip[0]) / 2 + (rnd() - .5) * 30, (base[1] + tip[1]) / 2)
        lean = (tip[0] - base[0]) / 4
        groups.append(f'<g class="pm-tail" style="--i:{s + stems}"><path class="pm-s pm-s--thin" d="M{base[0]:.1f} {base[1]:.1f}Q{ctrl[0]:.1f} {ctrl[1]:.1f} {tip[0]:.1f} {tip[1]:.1f}"/>'
                      f'<ellipse class="pm-bun" cx="{tip[0]:.1f}" cy="{tip[1] - 9:.1f}" rx="6" ry="11" transform="rotate({lean:.0f} {tip[0]:.1f} {tip[1]:.1f})"/></g>')
    return f'<svg class="pampas {cls}" viewBox="0 0 220 320" aria-hidden="true" focusable="false">{"".join(groups)}</svg>'


# --- woven baskets (wall-basket cluster) -------------------------------------------------------
def _basket(cx, cy, r, tone, band, seed):
    rnd = _rng(seed)
    rings = "".join(f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" class="bk-ring"/>' for rr in [r * f for f in (.92, .8, .68, .32, .2)])
    n = 12 if r > 40 else 9
    tris = []
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + .5) / n
        a2 = 2 * math.pi * (k + 1) / n
        ri, ro = r * .4, r * .62
        pts = [(cx + ri * math.cos(a0), cy + ri * math.sin(a0)), (cx + ro * math.cos(a1), cy + ro * math.sin(a1)),
               (cx + ri * math.cos(a2), cy + ri * math.sin(a2))]
        tris.append(f'<path class="bk-{band[k % len(band)]}" d="M{pts[0][0]:.1f} {pts[0][1]:.1f}L{pts[1][0]:.1f} {pts[1][1]:.1f}L{pts[2][0]:.1f} {pts[2][1]:.1f}Z"/>')
    spokes = '<path class="bk-spoke" d="' + "".join(
        f"M{cx + r * .2 * math.cos(a):.0f} {cy + r * .2 * math.sin(a):.0f}L{cx + r * .97 * math.cos(a):.0f} {cy + r * .97 * math.sin(a):.0f}"
        for a in [2 * math.pi * k / 30 + rnd() * .02 for k in range(30)]) + '"/>'
    return (f'<g class="bk" style="--r:{r}"><ellipse class="bk-shadow" cx="{cx + 4}" cy="{cy + r * .12 + 4}" rx="{r}" ry="{r * .98:.1f}"/>'
            f'<circle class="bk-{tone}" cx="{cx}" cy="{cy}" r="{r}"/>{spokes}{rings}{"".join(tris)}'
            f'<circle class="bk-c" cx="{cx}" cy="{cy}" r="{r * .14:.1f}"/></g>')


BASKETS = ('<svg class="baskets" viewBox="0 0 240 190" aria-hidden="true" focusable="false">'
           + _basket(84, 104, 66, "straw", ("ink", "clay"), 2) + _basket(186, 62, 44, "straw2", ("clay", "ink", "straw"), 4)
           + _basket(178, 152, 28, "dark", ("straw", "straw2"), 6) + "</svg>")


# --- a Nguni cow, head on, with lyre horns ------------------------------------------------------------
COW = """<svg class="cow" viewBox="0 0 120 100" aria-hidden="true" focusable="false"><defs>
<linearGradient id="cow-horn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3B2A1F"/><stop offset=".32" stop-color="#C9B48F"/><stop offset="1" stop-color="#F3EADA"/></linearGradient>
<clipPath id="cow-face"><path d="M60 25C70 25 77 30 77 40 77 52 73 64 71 74 70 80 72 86 70 90 67 95 53 95 50 90 48 86 50 80 49 74 47 64 43 52 43 40 43 30 50 25 60 25Z"/></clipPath></defs>
<g class="cow__horns" fill="url(#cow-horn)" stroke="#3B2A1E" stroke-width=".8"><path d="M47 33C36 34 24 32 18 24 13 18 11 11 13 4 16 11 20 18 27 22 33 25 41 26 49 26Z"/>
<path d="M73 33C84 34 96 32 102 24 107 18 109 11 107 4 104 11 100 18 93 22 87 25 79 26 71 26Z"/></g>
<g class="cow__ears" stroke="#3B2A1E" stroke-width=".8"><path class="cow-a" d="M46 38C38 34 28 35 21 41 28 47 39 47 46 43Z"/><path class="cow-a" d="M74 38C82 34 92 35 99 41 92 47 81 47 74 43Z"/>
<path class="cow-in" d="M43 40C37 38.4 31 39 26.5 41.3 31.5 44 38 44 43 42.4Z"/><path class="cow-in" d="M77 40C83 38.4 89 39 93.5 41.3 88.5 44 82 44 77 42.4Z"/></g>
<path class="cow-base" d="M60 25C70 25 77 30 77 40 77 52 73 64 71 74 70 80 72 86 70 90 67 95 53 95 50 90 48 86 50 80 49 74 47 64 43 52 43 40 43 30 50 25 60 25Z"/>
<g clip-path="url(#cow-face)"><path class="cow-a" d="M40 30C49 27 57 34 57 45 57 54 52 62 45 66L38 60Z"/><path class="cow-b" d="M63 24C72 23 79 30 78 38 72 40 66 36 63 24Z"/>
<circle class="cow-a" cx="60" cy="53" r="1.6"/><circle class="cow-a" cx="56.5" cy="59" r="1.2"/><circle class="cow-b" cx="66" cy="62" r="1.1"/><circle class="cow-a" cx="61.5" cy="47" r=".9"/></g>
<path d="M60 25C70 25 77 30 77 40 77 52 73 64 71 74 70 80 72 86 70 90 67 95 53 95 50 90 48 86 50 80 49 74 47 64 43 52 43 40 43 30 50 25 60 25Z" fill="none" stroke="#3B2A1E" stroke-width=".9"/>
<path d="M53 27.5c2-3.5 5.5-4 7-1.4 1.6-2.6 5-2.1 6.8 1.4" fill="none" stroke="#B9A27C" stroke-width="1.1" stroke-linecap="round"/>
<ellipse class="cow-eye" cx="51" cy="47.5" rx="2.3" ry="2.7"/><ellipse class="cow-eye" cx="69" cy="47.5" rx="2.3" ry="2.7"/><circle cx="51.8" cy="46.6" r=".7" fill="#fff"/><circle cx="69.8" cy="46.6" r=".7" fill="#fff"/>
<ellipse class="cow-muzzle" cx="60" cy="87.5" rx="11.5" ry="7.6"/><ellipse cx="55.6" cy="88.6" rx="1.9" ry="1.25" fill="#3A2A22"/><ellipse cx="64.4" cy="88.6" rx="1.9" ry="1.25" fill="#3A2A22"/>
<path d="M56 93.2c2.6 1.1 5.4 1.1 8 0" fill="none" stroke="#7A5246" stroke-width=".8" stroke-linecap="round"/></svg>"""

SHIELD = """<svg class="shield" viewBox="0 0 64 56" aria-hidden="true" focusable="false"><g class="sh-spear" fill="none" stroke-linecap="round"><path pathLength="1" d="M8 52 56 4"/><path pathLength="1" d="M56 52 8 4"/></g>
<ellipse class="sh-tip" cx="56.5" cy="3.5" rx="5" ry="1.9" transform="rotate(-45 56.5 3.5)"/><ellipse class="sh-tip" cx="7.5" cy="3.5" rx="5" ry="1.9" transform="rotate(45 7.5 3.5)"/>
<ellipse class="sh-body" pathLength="1" cx="32" cy="29" rx="12" ry="21"/>
<path class="sh-spots" d="M27 16c3-2 7-1 8 2-1 3-6 4-8 2-1-1-1-3 0-4Zm7 14c3 0 5 3 4 6-3 2-7 1-8-2 0-2 2-4 4-4Zm-10 7c2-1 4 1 4 3-1 2-4 2-5 1-1-1 0-3 1-4Z"/>
<path class="sh-stick" pathLength="1" d="M32 6v46"/></svg>"""

_SHIELD_SM = ('<ellipse class="sh-body" pathLength="1" cx="0" cy="0" rx="12" ry="22"/>'
              '<path class="sh-spots" d="M-5-13c3-2 7-1 8 2-1 3-6 4-8 2-1-1-1-3 0-4Zm7 14c3 0 5 3 4 6-3 2-7 1-8-2 0-2 2-4 4-4Zm-10 7c2-1 4 1 4 3-1 2-4 2-5 1-1-1 0-3 1-4Z"/>'
              '<path class="sh-stick" pathLength="1" d="M0-24v48"/>')
# The lobola crest: a Nguni cow (lobola is counted in cattle) between two shields, over crossed spears.
# The homepage phone shows the same crest with its colours written in.
CREST = ('<svg class="crest" viewBox="0 -8 150 92" aria-hidden="true" focusable="false">'
         '<g class="sh-spear" fill="none" stroke-linecap="round"><path pathLength="1" d="M22 80 128 6"/><path pathLength="1" d="M128 80 22 6"/></g>'
         '<ellipse class="sh-tip" cx="128.5" cy="5.5" rx="6" ry="2.2" transform="rotate(-35 128.5 5.5)"/>'
         '<ellipse class="sh-tip" cx="21.5" cy="5.5" rx="6" ry="2.2" transform="rotate(35 21.5 5.5)"/>'
         f'<g transform="translate(27 50) rotate(-12)"><g class="crest__shield">{_SHIELD_SM}</g></g>'
         f'<g transform="translate(123 50) rotate(12)"><g class="crest__shield">{_SHIELD_SM}</g></g>'
         '<g class="crest__cow"><svg x="22" y="-10" width="106" height="88" viewBox="0 0 120 100">'
         + COW[COW.index(">") + 1:-len("</svg>")] + '</svg></g></svg>')

POT = """<svg class="pot" viewBox="0 0 60 60" aria-hidden="true" focusable="false"><path class="pot__body" d="M14 18h32c-1 3-2 4-4 5 8 4 12 11 12 19 0 11-10 17-24 17S6 53 6 42c0-8 4-15 12-19-2-1-3-2-4-5Z"/>
<path d="M9 36h42" stroke="#F3DDB8" stroke-width="1.4"/><path d="M10 40l4-4 4 4 4-4 4 4 4-4 4 4 4-4 4 4 4-4 4 4" fill="none" stroke="#2A1A10" stroke-width="1.2"/><path d="M16 18h28" stroke="#6E3520" stroke-width="2"/></svg>"""

BASKET_BOWL = """<svg class="bowl" viewBox="0 0 70 50" aria-hidden="true" focusable="false"><path d="M4 14h62c0 18-12 32-31 32S4 32 4 14Z" fill="#C9A26B"/><ellipse cx="35" cy="14" rx="31" ry="6" fill="#DDBB85"/>
<path d="M8 24l6 6 6-6 6 6 6-6 6 6 6-6 6 6 6-6 6 6" fill="none" stroke="#3B2A1E" stroke-width="1.6"/><path d="M13 34l5 4 5-4 5 4 5-4 5 4 5-4 5 4 5-4" fill="none" stroke="#8E3B22" stroke-width="1.4"/></svg>"""

ORNAMENT = """<svg class="tc-orn" viewBox="0 0 120 10" aria-hidden="true" focusable="false"><path d="M2 5h40M78 5h40" fill="none" stroke-width=".8"/><path class="tc-orn__d" d="M50 5 53 2l3 3-3 3ZM64 5l3-3 3 3-3 3Z"/>
<path class="tc-orn__h" d="M60 8.5c-3-2.2-5-3.8-5-5.6 0-1.3 1-2.2 2.2-2.2.9 0 1.8.5 2.8 1.6 1-1.1 1.9-1.6 2.8-1.6 1.2 0 2.2.9 2.2 2.2 0 1.8-2 3.4-5 5.6Z"/></svg>"""

ICONS = {
    "date": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>',
    "time": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg>',
    "venue": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.4-6 10-6 10Z"/><circle cx="12" cy="11" r="2.2"/></svg>',
}


# --- ribbon and bow ----------------------------------------------------------------------------------
BOW = """<svg class="bow" viewBox="0 0 240 172" aria-hidden="true" focusable="false">
<g class="bow__tail bow__tail--l"><path class="bw-a" d="M113 78C103 100 88 128 70 158l22-6 6 16c14-30 22-60 26-86Z"/><path class="bw-line" d="M108 92c-8 18-18 38-30 58"/></g>
<g class="bow__tail bow__tail--r"><path class="bw-a" d="M127 78c10 22 23 50 41 76l-22-4-2 18c-12-30-20-60-24-86Z"/><path class="bw-line" d="M132 92c8 18 16 36 28 54"/></g>
<g class="bow__loop bow__loop--l"><path class="bw-a" d="M120 70C104 52 84 30 60 26 36 22 20 36 24 56c4 20 32 30 62 26 14-2 26-6 34-10Z"/>
<path class="bw-b" d="M120 70C102 66 84 60 68 46c14 4 32 12 52 22Z"/><path class="bw-hi" d="M40 40c8-8 22-8 34-2"/></g>
<g class="bow__loop bow__loop--r"><path class="bw-a" d="M120 70c16-18 36-40 60-44 24-4 40 10 36 30-4 20-32 30-62 26-14-2-26-6-34-10Z"/>
<path class="bw-b" d="M120 70c18-4 36-10 52-24-14 4-32 12-52 22Z"/><path class="bw-hi" d="M200 40c-8-8-22-8-34-2"/></g>
<path class="bw-k" d="M108 60c4-4 20-4 24 0 4 8 2 20-2 24-6 4-14 4-20 0-4-6-6-16-2-24Z"/><path class="bw-line" d="M112 64c4 6 12 6 16 0M112 80c4-3 12-3 16 0"/></svg>"""


BOW_RB = BOW.replace('class="bow"', 'class="bow rb-bow"', 1)
BOW_MT = BOW.replace('class="bow"', 'class="bow mt-bow"', 1)
BOW_FS = BOW.replace('class="bow"', 'class="bow fs-bow"', 1)
BOW_DIV = BOW.replace('class="bow"', 'class="bow bow--div"', 1)


_EDGE_H = "M0 6C18 4.6 32 7.4 50 6S82 4.6 100 6"          # left to right, 12 high
_EDGE_V = "M6 0C4.6 18 7.4 32 6 50S4.6 82 6 100"          # top to bottom, 12 wide
_LOOP = "M0 12C10 12 19 11.4 24.5 8.6 30 5.8 30.6 -.4 26.2 -1.6 21.6-2.8 18.6 2.6 20 8.4 21.4 14.6 24 22 24 36"


def _rf_piece(cls: str, d: str, box: str, stretch: bool) -> str:
    keep = ' preserveAspectRatio="none"' if stretch else ""
    paths = "".join(f'<path class="{c}" pathLength="1" d="{d}"/>' for c in ("rf-under", "rf-ribbon", "rf-sheen"))
    return f'<svg class="rf {cls}" viewBox="{box}"{keep} focusable="false">{paths}</svg>'


def ribbon_frame(cls: str = "") -> str:
    """A hand-drawn ribbon round the card that draws itself from under the bow, loops at each corner
    and comes back to the bow (pieces are animated one after another in invites.css)."""
    rev_h = "M100 6C82 7.4 68 4.6 50 6S18 7.4 0 6"
    rev_v = "M6 100C7.4 82 4.6 68 6 50S7.4 18 6 0"
    pieces = [("rf-t2", _EDGE_H, "0 0 100 12", True), ("rf-c rf-c1", _LOOP, "0 0 36 36", False),
              ("rf-r", _EDGE_V, "0 0 12 100", True), ("rf-c rf-c2", _LOOP, "0 0 36 36", False),
              ("rf-b", rev_h, "0 0 100 12", True), ("rf-c rf-c3", _LOOP, "0 0 36 36", False),
              ("rf-l", rev_v, "0 0 12 100", True), ("rf-c rf-c4", _LOOP, "0 0 36 36", False),
              ("rf-t1", _EDGE_H, "0 0 100 12", True)]
    return (f'<div class="ribbon-frame {cls}" aria-hidden="true">'
            + "".join(_rf_piece(c, d, b, st) for c, d, b, st in pieces) + "</div>")


MINI_BOW = ('<svg viewBox="0 0 40 28" aria-hidden="true"><path d="M20 12C15 6 8 2 4 5S3 15 9 15c4 0 8-1 11-3Z"/>'
            '<path d="M20 12c5-6 12-10 16-7s1 10-5 10c-4 0-8-1-11-3Z"/><path d="M18.5 13 14 26l3-1 2 2 1.5-13M21.5 13 26 26l-3-1-2 2-1.5-13Z"/>'
            '<circle cx="20" cy="12.5" r="2.6"/></svg>')


def scatter(cls: str, count: int, seed: int, art: str) -> str:
    """Small ornaments (sparkles, bows) scattered down both sides of a hero, clear of the text."""
    rnd = _rng(seed)
    out = []
    for k in range(count):
        x = rnd() * 24 + (74 if k % 2 else 0)
        out.append(f'<i style="--x:{x:.1f}%;--y:{rnd() * 100:.1f}%;--s:{10 + rnd() * 16:.0f}px;'
                   f'--d:{2.6 + rnd() * 2.6:.2f}s;--dl:{-rnd() * 4:.2f}s;--r:{(rnd() - .5) * 50:.0f}deg">{art}</i>')
    return f'<div class="iv-scatter {cls}" aria-hidden="true">{"".join(out)}</div>'


# --- woven chevron cloth ---------------------------------------------------------------------------
def defs_weave(pid: str = "wv-cloth") -> str:
    """Stacked chevrons in four colours with a fine basket-weave texture over them (a seamless 48×96 tile)."""
    band = 12
    colours = ("wc-1", "wc-2", "wc-3", "wc-4", "wc-2", "wc-1", "wc-4", "wc-3")

    def chevron(y, cls):
        return f'<path class="{cls}" d="M0 {y + 24}L24 {y}L48 {y + 24}V{y + 24 + band}L24 {y + band}L0 {y + 24 + band}Z"/>'
    rows = [chevron(k * band - 24, c) for k, c in enumerate(colours)]
    rows += [chevron(k * band - 24 + 96, c) for k, c in enumerate(colours[:2])]   # what spills over the top, repeated below
    weave = "".join(f'<rect class="wc-ta" x="{i * 4}" y="{j * 4 + 1.3}" width="4" height="1.4"/>' if (i + j) % 2 else
                    f'<rect class="wc-tb" x="{i * 4 + 1.3}" y="{j * 4}" width="1.4" height="4"/>'
                    for i in range(12) for j in range(24))
    return (f'<svg class="iv-defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>'
            f'<pattern id="{pid}" width="48" height="96" patternUnits="userSpaceOnUse"><rect class="wc-4" width="48" height="96"/>{"".join(rows)}</pattern>'
            f'<pattern id="{pid}-tex" width="48" height="96" patternUnits="userSpaceOnUse">{weave}</pattern>'
            f'<filter id="{pid}-grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/>'
            f'<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .3 0"/></filter></defs></svg>')


def cloth_fill(pid: str = "wv-cloth") -> str:
    return (f'<svg class="cloth-fill" width="100%" height="100%" aria-hidden="true" focusable="false">'
            f'<rect width="100%" height="100%" fill="url(#{pid})"/><rect width="100%" height="100%" fill="url(#{pid}-tex)"/>'
            f'<rect width="100%" height="100%" filter="url(#{pid}-grain)"/></svg>')


# --- glitter: disco ball, sparkles -----------------------------------------------------------------
def _disco() -> str:
    rnd = _rng(21)
    tiles = []
    for row in range(13):
        shades = [rnd() for _ in range(13)]
        for col in range(26):                       # 13 columns, twice, so the turning loop is seamless
            shade = shades[col % 13]
            cls = "db-h" if shade > .9 else "db-l" if shade > .55 else "db-m" if shade > .2 else "db-d"
            tiles.append(f'<rect class="{cls}" x="{col * 8.4:.1f}" y="{10 + row * 8.4:.1f}" width="7.6" height="7.6" rx=".8"/>')
    return ("<svg class=\"disco\" viewBox=\"0 0 120 132\" aria-hidden=\"true\" focusable=\"false\"><defs>"
            "<clipPath id=\"db-c\"><circle cx=\"60\" cy=\"72\" r=\"52\"/></clipPath>"
            "<radialGradient id=\"db-shade\" cx=\"36%\" cy=\"34%\" r=\"75%\"><stop offset=\"0\" stop-color=\"#fff\" stop-opacity=\".55\"/>"
            "<stop offset=\".45\" stop-color=\"#fff\" stop-opacity=\"0\"/><stop offset=\"1\" stop-color=\"#000\" stop-opacity=\".62\"/></radialGradient></defs>"
            "<path class=\"db-wire\" d=\"M60 0v20\"/><rect class=\"db-cap\" x=\"54\" y=\"16\" width=\"12\" height=\"6\" rx=\"1.5\"/>"
            "<g clip-path=\"url(#db-c)\"><circle cx=\"60\" cy=\"72\" r=\"52\" class=\"db-d\"/>"
            f"<g class=\"db-tiles\">{''.join(tiles)}</g><circle cx=\"60\" cy=\"72\" r=\"52\" fill=\"url(#db-shade)\"/></g>"
            "<path class=\"db-star\" d=\"M38 44l2.2 6 6 2.2-6 2.2-2.2 6-2.2-6-6-2.2 6-2.2Z\"/></svg>")


DISCO = _disco()

SPARK = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 0c.9 5.4 4.6 9.1 10 10-5.4.9-9.1 4.6-10 10-.9-5.4-4.6-9.1-10-10C5.4 9.1 9.1 5.4 10 0Z"/></svg>'


def balloon_text(ctx) -> str:
    """What the chrome balloons spell: an age from the title (\"Thabo turns 40\" → 40), else a word."""
    m = re.search(r"(?<!\d)(\d{1,3})(?:st|nd|rd|th)?(?!\d)", f'{ctx["title"]} {ctx["hosts"]}')
    if m:
        return m.group(1)
    if ctx["group"] == "baby":
        return "oh baby"
    if ctx["group"] == "weddings":
        return "I do"
    d = ctx["date"]
    return str(d.year) if (ctx["group"] == "other" and d) else "party"


def balloons(text: str) -> str:
    cells = "".join(f'<span class="gl-b" style="--i:{k}">{esc(ch)}</span>' if ch != " " else '<span class="gl-sp"></span>'
                    for k, ch in enumerate(text))
    return f'<p class="gl-balloons" aria-hidden="true" style="--n:{max(2, len(text))}">{cells}</p>'


# --- matcha: awning, glass, pilates ball -------------------------------------------------------------
MATCHA = """<svg class="matcha" viewBox="0 0 90 150" aria-hidden="true" focusable="false"><defs>
<clipPath id="mt-glass"><path d="M14 30h62l-6 108a8 8 0 0 1-8 8H28a8 8 0 0 1-8-8Z"/></clipPath>
<linearGradient id="mt-green" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#A9C46F"/><stop offset="1" stop-color="#6F8F3A"/></linearGradient></defs>
<path class="mt-straw" d="M58 4 50 120"/><g clip-path="url(#mt-glass)"><rect x="0" y="30" width="90" height="120" fill="#FFFDF8"/>
<g class="mt-milk"><path d="M-100 70c10-6 20-6 30 0s20 6 30 0 20-6 30 0 20 6 30 0 20-6 30 0 20 6 30 0 20-6 30 0 20 6 30 0 20-6 30 0V150H-100Z" fill="#F4EEDF"/></g>
<g class="mt-tea"><path d="M-100 96c10-5 20-5 30 0s20 5 30 0 20-5 30 0 20 5 30 0 20-5 30 0 20 5 30 0 20-5 30 0 20 5 30 0 20-5 30 0V150H-100Z" fill="url(#mt-green)"/></g>
<rect class="mt-ice" x="24" y="52" width="20" height="18" rx="4" transform="rotate(-12 34 61)"/><rect class="mt-ice" x="46" y="60" width="18" height="16" rx="4" transform="rotate(14 55 68)"/>
<rect x="18" y="30" width="7" height="120" fill="#fff" opacity=".45"/></g>
<path class="mt-glassline" d="M14 30h62l-6 108a8 8 0 0 1-8 8H28a8 8 0 0 1-8-8Z"/></svg>"""

BALL = """<svg class="pball" viewBox="0 0 100 100" aria-hidden="true" focusable="false"><defs><radialGradient id="pb-g" cx="35%" cy="30%" r="75%">
<stop offset="0" stop-color="#fff" stop-opacity=".7"/><stop offset=".35" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".22"/></radialGradient></defs>
<ellipse class="pb-shadow" cx="50" cy="96" rx="30" ry="4"/><g class="pb-ball"><circle class="pb-fill" cx="50" cy="50" r="42"/><path class="pb-seam" d="M12 40c20 8 56 8 76 0"/><circle cx="50" cy="50" r="42" fill="url(#pb-g)"/></g></svg>"""


# --- festive: tree with bows, snow -------------------------------------------------------------------
def _tree() -> str:
    tiers = [(30, 70, 32), (54, 104, 46), (84, 140, 60), (118, 178, 74)]
    shapes = []
    for k, (top, bottom, half) in enumerate(tiers):
        scallops = "".join(f"q{half / 4:.1f} 9 {half / 2:.1f} 0" for _ in range(4))   # left to right along the hem
        shapes.append(f'<path class="ft-g{k % 2}" d="M80 {top - 24}L{80 - half} {bottom}{scallops}Z"/>')
    lights = []
    rnd = _rng(33)
    for k in range(18):
        t = rnd()
        tier = tiers[k % 4]
        y = tier[0] + (tier[1] - tier[0]) * (.45 + .45 * t)
        span = tier[2] * (.25 + .7 * (y - tier[0] + 24) / (tier[1] - tier[0] + 24))
        x = 80 + (rnd() - .5) * 2 * span * .9
        lights.append(f'<circle class="ft-light" cx="{x:.1f}" cy="{y:.1f}" r="2.3" style="--d:{-rnd() * 3:.2f}s"/>')
    bows = []
    for k, (x, y) in enumerate([(70, 60), (96, 92), (62, 120), (102, 128), (80, 158), (52, 166), (110, 168)]):
        bows.append(f'<g class="ft-bow" transform="translate({x} {y}) scale(.11)" style="--d:{k * -.6:.1f}s"><use href="#ft-bowshape"/></g>')
    bowshape = ('<g id="ft-bowshape"><path class="ft-bow__a" d="M0 0C-16-18-36-40-60-44-84-48-100-34-96-14-92 6-64 16-34 12-20 10-8 6 0 2Z"/>'
                '<path class="ft-bow__a" d="M0 0C16-18 36-40 60-44 84-48 100-34 96-14 92 6 64 16 34 12 20 10 8 6 0 2Z"/>'
                '<path class="ft-bow__a" d="M-6 8C-16 30-30 58-48 88l22-6 6 16C-6 68 2 38 4 10Z"/><path class="ft-bow__a" d="M6 8c10 22 22 50 40 76l-22-4-2 18C10 68 2 38-2 10Z"/>'
                '<circle class="ft-bow__k" r="14"/></g>')
    return (f'<svg class="tree" viewBox="0 0 160 230" aria-hidden="true" focusable="false"><defs>{bowshape}</defs>'
            f'<rect class="ft-trunk" x="72" y="184" width="16" height="22" rx="2"/>'
            f'<g class="ft-gift"><rect class="ft-box1" x="26" y="192" width="34" height="28" rx="2"/><path class="ft-rib" d="M43 192v28M26 204h34"/>'
            f'<rect class="ft-box2" x="98" y="198" width="38" height="22" rx="2"/><path class="ft-rib2" d="M117 198v22M98 208h38"/></g>'
            f'{"".join(shapes)}<g class="ft-lights">{"".join(lights)}</g>{"".join(bows)}'
            f'<path class="ft-star" d="M80 0l4.4 10.6 11.4.8-8.8 7.4 2.8 11.2L80 24l-9.8 6 2.8-11.2-8.8-7.4 11.4-.8Z"/></svg>')


TREE = _tree()


def snow(count: int = 34, seed: int = 41) -> str:
    rnd = _rng(seed)
    flakes = "".join(f'<i style="--x:{rnd() * 100:.1f}%;--s:{3 + rnd() * 5:.1f}px;--d:{7 + rnd() * 9:.1f}s;--dl:{-rnd() * 14:.1f}s;--dx:{(rnd() - .5) * 80:.0f}px"></i>'
                     for _ in range(count))
    return f'<div class="snow" aria-hidden="true">{flakes}</div>'


# --- cheers: a champagne bottle that pops, falling confetti ------------------------------------------
BOTTLE = """<svg class="bottle" viewBox="0 0 120 300" aria-hidden="true" focusable="false"><defs>
<linearGradient id="bt-glass" x1="0" x2="1"><stop offset="0" stop-color="#0B2A1D"/><stop offset=".35" stop-color="#1D4A35"/><stop offset=".6" stop-color="#123426"/><stop offset="1" stop-color="#06160F"/></linearGradient>
<linearGradient id="bt-foil" x1="0" x2="1"><stop offset="0" stop-color="#9C7A32"/><stop offset=".4" stop-color="#F3DDA0"/><stop offset=".7" stop-color="#C99B45"/><stop offset="1" stop-color="#7E5F22"/></linearGradient></defs>
<g class="bt-cork"><path d="M51 4h18v18H51Z" fill="#D9B98A"/><path d="M47 0h26a4 4 0 0 1 4 4v3H43V4a4 4 0 0 1 4-4Z" fill="#C49C64"/></g>
<path d="M50 22h20v70c0 18 22 30 22 56v132c0 6-4 10-10 10H38c-6 0-10-4-10-10V148c0-26 22-38 22-56Z" fill="url(#bt-glass)"/>
<path d="M48 20h24v78c0 10 8 16 13 22H35c5-6 13-12 13-22Z" fill="url(#bt-foil)"/><path d="M48 60h24" stroke="#7E5F22" stroke-width="1.5"/>
<rect x="34" y="176" width="52" height="64" rx="5" fill="#F7EFDD"/><rect x="38" y="180" width="44" height="56" rx="3" fill="none" stroke="#C99B45" stroke-width="1.2"/>
<path d="M60 194l3 7 7 3-7 3-3 7-3-7-7-3 7-3Z" fill="#C99B45"/><path d="M44 222h32M48 228h24" stroke="#6E5420" stroke-width="1.6" stroke-linecap="round"/>
<path d="M36 150c0-14 8-24 16-30" stroke="#fff" stroke-opacity=".22" stroke-width="5" stroke-linecap="round" fill="none"/>
<rect x="33" y="150" width="7" height="125" rx="3.5" fill="#fff" opacity=".13"/></svg>"""


def fizz(count: int = 14, seed: int = 61) -> str:
    """Bubbles streaming out of the bottle neck (they burst out once, then keep fizzing)."""
    rnd = _rng(seed)
    return '<span class="cs-fizz" aria-hidden="true">' + "".join(
        f'<i style="--s:{3 + rnd() * 6:.1f}px;--dx:{(rnd() - .5) * 70:.0f}px;--dy:{-90 - rnd() * 170:.0f}px;'
        f'--d:{1.6 + rnd() * 1.8:.2f}s;--dl:{rnd() * 2.4:.2f}s"></i>' for _ in range(count)) + "</span>"


def confetti(count: int = 34, seed: int = 71, cls: str = "cs-confetti") -> str:
    """Pieces of confetti falling and turning (gold, champagne, white and the accent)."""
    rnd = _rng(seed)
    out = []
    for k in range(count):
        shape = ("rect", "rect", "dot", "curl")[k % 4]
        out.append(f'<i class="cf-{shape} cf-c{k % 4}" style="--x:{rnd() * 100:.1f}%;--d:{6 + rnd() * 7:.1f}s;--dl:{-rnd() * 12:.1f}s;'
                   f'--dx:{(rnd() - .5) * 120:.0f}px;--r:{360 + rnd() * 720:.0f}deg;--s:{.7 + rnd() * .7:.2f}"></i>')
    return f'<div class="{cls}" aria-hidden="true">{"".join(out)}</div>'


# --- teddy: a bear peeking over the card with a bunch of balloons --------------------------------
def _balloon(cx, cy, r, cls):
    return (f'<g class="tb-b {cls}"><ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r * 1.16:.1f}"/>'
            f'<path d="M{cx - 4} {cy + r * 1.16 + 5:.1f}l4-6 4 6Z"/>'
            f'<ellipse class="tb-hi" cx="{cx - r * .38:.1f}" cy="{cy - r * .42:.1f}" rx="{r * .22:.1f}" ry="{r * .34:.1f}" transform="rotate(-24 {cx - r * .38:.1f} {cy - r * .42:.1f})"/></g>')


_TB = [(72, 70, 30, "tb-1"), (126, 50, 34, "tb-2"), (184, 78, 28, "tb-3"), (104, 122, 24, "tb-4")]
TEDDY = ('<svg class="teddy" viewBox="0 0 260 290" aria-hidden="true" focusable="false"><g class="tb-bunch">'
         + "".join(f'<path class="tb-str" d="M{cx} {cy + r * 1.16 + 5:.1f}C{cx + 6} {cy + 90:.0f} {150 + (cx - 120) * .2:.0f} 226 178 266"/>' for cx, cy, r, _ in _TB)
         + "".join(_balloon(*b) for b in _TB) + '</g>'
         '<g class="tb-bear">'
         '<circle class="tb-fur" cx="93" cy="179" r="17"/><circle class="tb-fur" cx="167" cy="179" r="17"/>'
         '<circle class="tb-in" cx="93" cy="179" r="9"/><circle class="tb-in" cx="167" cy="179" r="9"/>'
         '<circle class="tb-fur" cx="130" cy="214" r="45"/>'
         '<ellipse class="tb-muzzle" cx="130" cy="234" rx="21" ry="15.5"/><ellipse class="tb-nose" cx="130" cy="225" rx="8" ry="5.6"/>'
         '<path class="tb-line" d="M130 231v6M122 240q8 6 16 0"/>'
         '<g class="tb-eyes"><circle class="tb-eye" cx="112" cy="206" r="4.6"/><circle class="tb-eye" cx="148" cy="206" r="4.6"/>'
         '<circle cx="113.6" cy="204.4" r="1.4" fill="#fff"/><circle cx="149.6" cy="204.4" r="1.4" fill="#fff"/></g>'
         '<circle class="tb-cheek" cx="104" cy="226" r="7"/><circle class="tb-cheek" cx="156" cy="226" r="7"/>'
         '<ellipse class="tb-fur tb-paw" cx="86" cy="270" rx="19" ry="12"/><ellipse class="tb-fur tb-paw" cx="178" cy="268" rx="19" ry="12"/>'
         '<path class="tb-line" d="M78 267v5M86 266v6M94 267v5M170 265v5M178 264v6M186 265v5"/></g></svg>')

CLOUD = '<svg viewBox="0 0 120 60" aria-hidden="true"><path d="M22 52h76a20 20 0 0 0 0-40 26 26 0 0 0-48-6 18 18 0 0 0-28 20 13 13 0 0 0 0 26Z"/></svg>'


def clouds(count: int = 4, seed: int = 81) -> str:
    rnd = _rng(seed)
    return '<div class="tb-clouds" aria-hidden="true">' + "".join(
        f'<i style="--y:{8 + rnd() * 60:.0f}%;--w:{90 + rnd() * 90:.0f}px;--d:{38 + rnd() * 30:.0f}s;--dl:{-rnd() * 40:.0f}s">{CLOUD}</i>'
        for _ in range(count)) + "</div>"


# --- reveal: a question balloon that pops into pink and blue confetti ---------------------------------
QBALLOON = """<svg class="qballoon" viewBox="0 0 160 230" aria-hidden="true" focusable="false"><defs>
<radialGradient id="qb-g" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#5A5A66"/><stop offset=".45" stop-color="#1D1D24"/><stop offset="1" stop-color="#050507"/></radialGradient>
<linearGradient id="qb-gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FCE7A8"/><stop offset=".5" stop-color="#E0B54E"/><stop offset="1" stop-color="#A97C21"/></linearGradient></defs>
<path class="qb-str" d="M80 160c-6 18 8 30 0 48s6 18 2 22"/>
<ellipse cx="80" cy="82" rx="64" ry="74" fill="url(#qb-g)"/><path d="M74 160h12l-6-8Z" fill="#111"/>
<ellipse cx="54" cy="48" rx="12" ry="22" fill="#fff" opacity=".18" transform="rotate(-24 54 48)"/>
<text x="80" y="112" text-anchor="middle" class="qb-q" fill="url(#qb-gold)">?</text></svg>"""


def pastel_balloon(cls: str) -> str:
    return (f'<svg class="pb {cls}" viewBox="0 0 80 150" aria-hidden="true" focusable="false"><path class="pb-str" d="M40 86c-5 14 6 24 0 38s5 16 2 24"/>'
            f'<ellipse class="pb-body" cx="40" cy="42" rx="34" ry="40"/><path class="pb-body" d="M35 86l5-6 5 6Z"/>'
            f'<ellipse cx="28" cy="26" rx="7" ry="12" fill="#fff" opacity=".4" transform="rotate(-22 28 26)"/></svg>')


def burst(count: int = 30, seed: int = 91) -> str:
    """Confetti flying out from where the balloon popped, then drifting down."""
    rnd = _rng(seed)
    out = []
    for k in range(count):
        a = 2 * math.pi * k / count + rnd() * .3
        dist = 90 + rnd() * 160
        out.append(f'<i class="rv-c{k % 3}" style="--dx:{math.cos(a) * dist:.0f}px;--dy:{math.sin(a) * dist * .8 - 40:.0f}px;'
                   f'--r:{rnd() * 720:.0f}deg;--dl:{rnd() * .15:.2f}s"></i>')
    return f'<div class="rv-burst" aria-hidden="true">{"".join(out)}</div>'


# --- memorial: a candle and white lilies -------------------------------------------------------------
CANDLE = """<svg class="candle" viewBox="0 0 80 190" aria-hidden="true" focusable="false"><defs>
<radialGradient id="cd-glow" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#FFE6A8" stop-opacity=".85"/><stop offset=".4" stop-color="#FFD27A" stop-opacity=".28"/><stop offset="1" stop-color="#FFD27A" stop-opacity="0"/></radialGradient>
<linearGradient id="cd-flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFF6D6"/><stop offset=".45" stop-color="#FFC94D"/><stop offset="1" stop-color="#F08A24"/></linearGradient>
<linearGradient id="cd-wax" x1="0" x2="1"><stop offset="0" stop-color="#EDE6D8"/><stop offset=".45" stop-color="#FFFDF7"/><stop offset="1" stop-color="#DCD3C2"/></linearGradient></defs>
<circle class="cd-glow" cx="40" cy="44" r="40" fill="url(#cd-glow)"/>
<g class="cd-flame"><path d="M40 18c8 12 12 20 12 28a12 12 0 0 1-24 0c0-8 4-16 12-28Z" fill="url(#cd-flame)"/><path d="M40 40c3 4 4 7 4 10a4 4 0 0 1-8 0c0-3 1-6 4-10Z" fill="#7FB5FF" opacity=".55"/></g>
<path d="M40 56v10" stroke="#3A2C22" stroke-width="2" stroke-linecap="round"/>
<path d="M24 70c0-4 4-6 8-5 3 1 5 6 8 6s5-5 8-6c4-1 8 1 8 5v96H24Z" fill="url(#cd-wax)"/><path d="M48 66c2 6 1 14 3 18" stroke="#E2DACB" stroke-width="3" stroke-linecap="round" fill="none"/>
<path d="M12 168h56l-4 10H16Z" class="cd-holder"/><ellipse cx="40" cy="168" rx="28" ry="4" class="cd-holder"/></svg>"""


def _lily(cx, cy, s, rot):
    petals = "".join(f'<path class="ly-petal" d="M0 0C-7 -12 -6 -34 0 -46C6 -34 7 -12 0 0Z" transform="rotate({a})"/>' for a in range(0, 360, 60))
    stamens = "".join(f'<path class="ly-stamen" d="M0 0l{14 * math.cos(math.radians(a)):.1f} {14 * math.sin(math.radians(a)):.1f}"/>'
                      f'<ellipse class="ly-anther" cx="{15 * math.cos(math.radians(a)):.1f}" cy="{15 * math.sin(math.radians(a)):.1f}" rx="2.6" ry="1.4" transform="rotate({a} {15 * math.cos(math.radians(a)):.1f} {15 * math.sin(math.radians(a)):.1f})"/>'
                      for a in range(-150, 30, 36))
    return f'<g transform="translate({cx} {cy}) rotate({rot}) scale({s})">{petals}<circle class="ly-heart" r="5"/>{stamens}</g>'


LILIES = ('<svg class="lilies" viewBox="0 0 200 160" aria-hidden="true" focusable="false">'
          '<path class="ly-stem" d="M100 160C96 120 70 96 52 70M100 160c2-36 16-62 40-84M100 160c0-30-2-56-6-80"/>'
          '<path class="ly-leaf" d="M100 150c-20-6-40-22-46-44 18 6 36 22 46 44Z"/><path class="ly-leaf" d="M102 146c16-10 30-28 32-48-14 10-28 26-32 48Z"/>'
          + _lily(52, 66, .82, -30) + _lily(142, 74, .74, 34) + _lily(94, 52, .9, 4)
          + '<path class="ly-bud" d="M126 34c6-10 14-14 18-12-2 6-10 12-18 12Z"/></svg>')


LILIES_L = LILIES.replace('class="lilies"', 'class="lilies lilies--l"', 1)
LILIES_R = LILIES.replace('class="lilies"', 'class="lilies lilies--r"', 1)


def life_years(ctx) -> str:
    m = re.search(r"(1[89]\d\d|20\d\d)\s*[–—-]\s*(1[89]\d\d|20\d\d)", f'{ctx["title"]} {ctx["description"]}')
    return f"{m.group(1)} – {m.group(2)}" if m else ""


# --- shared invitation pieces -------------------------------------------------------------------------
def date_row(ctx, cls: str = "iv-daterow") -> str:
    dp = D.date_parts(ctx)
    if not dp["day"]:
        return f'<p class="{cls} {cls}--tba">{esc(ctx["date_text"])}</p>'
    return (f'<p class="{cls}"><span class="{cls}__side">{esc(dp["weekday"])}</span>'
            f'<span class="{cls}__mid"><b>{esc(dp["day"])}</b> <span>{esc(dp["month"])}</span></span>'
            f'<span class="{cls}__side">{esc(dp["year"])}</span></p>')


def families(ctx) -> str:
    sides = [s for s in (ctx["gs"].get("sides") or []) if s][:2]
    if len(sides) == 2 and ctx["group"] in ("weddings", "other"):
        return (f'<p class="iv-families"><span class="iv-families__f">{esc(sides[0])}</span> <span class="iv-families__and">and</span> '
                f'<span class="iv-families__f">{esc(sides[1])}</span></p>')
    return ""


def where(ctx, cls: str = "iv-where") -> str:
    v = ctx["venue"]
    out = ""
    if ctx["time_text"]:
        out += f'<span class="{cls}__time">{esc(ctx["time_text"])}</span>'
    if v.get("name"):
        out += f'<span class="{cls}__venue">{esc(v["name"])}</span>'
    if v.get("address"):
        out += f'<span class="{cls}__addr">{esc(v["address"])}</span>'
    return f'<p class="{cls}">{out}</p>' if out else ""


def reply_by(ctx) -> str:
    if ctx["show"].get("rsvp") and ctx["gs"].get("rsvp_deadline"):
        return f'<p class="iv-by">Kindly reply by {esc(ctx["deadline_text"])}</p>'
    return ""


def actions(ctx, label: str = "RSVP") -> str:
    btns = D.rsvp_cta(ctx, label)
    if ctx["show"].get("venue") and ctx["map_url"]:
        btns += f'<a class="ev-btn ev-btn--ghost" href="#venue">Directions</a>'
    return f'<div class="ev-actions iv-actions">{btns}</div>' if btns else ""


def body(ctx, secs, cls: str, divider: str = "") -> str:
    out = []
    for n, (k, html) in enumerate(secs):
        title = ""
        if k == "venue" and len(ctx["functions"]) > 1:
            title = "The ceremonies" if ctx["group"] in ("weddings", "other") else "Where and when"
        out.append(D.section(k, html, title=title, cls=f"iv-sec {cls} rv"))
        if divider and n < len(secs) - 1:
            out.append(divider)
    return "".join(out)


def photo(ctx, cls: str) -> str:
    return f'<div class="iv-photo {cls} rv">{D.hero_image(ctx)}</div>' if ctx["hero"] else ""


OCCASION = {
    "lobola": ("Lobola", "Celebration"), "traditional-wedding": ("Traditional", "Wedding"),
    "white-wedding": ("Wedding", "Celebration"), "engagement": ("Engagement", "Celebration"),
    "multi-day-wedding": ("Wedding", "Celebrations"), "family-celebration": ("Family", "Celebration"),
    "graduation": ("Graduation", "Celebration"), "anniversary": ("Anniversary", "Celebration"),
    "birthday": ("Birthday", "Celebration"), "baby-shower": ("Baby", "Shower"), "welcome-baby": ("Welcome", "Baby"),
}


def occasion(ctx) -> tuple:
    cat = ctx["ev"].get("category") or ""
    if cat in OCCASION:
        return OCCASION[cat]
    from .. import catalog
    words = catalog.category_name(cat).split() if cat else []
    return (words[0].capitalize(), " ".join(words[1:]).capitalize() or "Celebration") if words else ("You're", "Invited")


# --- layouts ---------------------------------------------------------------------------------------------
def nguni(ctx) -> str:
    """Nguni: a cowhide envelope sealed in gold wax opens, and the invitation card rises out of it."""
    secs = D.collect(ctx)
    fam = families(ctx)
    card = (f'<article class="nv-card env-card" id="welcome" aria-labelledby="nv-names">{seal(ctx["monogram"], "nv-seal-c", "nv-card__seal")}'
            f'{D.greeting(ctx)}{fam}<p class="nv-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="nv-names" id="nv-names">{D.names_html(ctx, "and")}</h1>'
            f'<div class="nv-rule" aria-hidden="true"><i></i></div>{date_row(ctx, "nv-date")}{where(ctx, "nv-where")}'
            f'{actions(ctx, "RSVP")}{reply_by(ctx)}</article>')
    env = (f'<div class="env-scene nv-scene">{pampas("nv-pampas nv-pampas--l", 3)}{pampas("nv-pampas nv-pampas--r", 8)}{BASKETS}'
           f'<div class="env-flapwrap" aria-hidden="true"><div class="env-flap"><div class="env-flap__out">{hide_fill()}</div>'
           f'<div class="env-flap__in"></div>{seal(ctx["monogram"], "nv-seal-f", "env-flap__seal")}</div></div>'
           f'{card}<div class="env-pocket" aria-hidden="true">{hide_fill()}<span class="env-pocket__seams"></span></div></div>')
    hero = (f'<header class="nv-hero">{defs_hide()}{env}'
            f'<a class="iv-scroll" href="#{secs[0][0] if secs else "welcome"}">Read the invitation</a></header>')
    strip = f'<div class="nv-strip" aria-hidden="true">{hide_fill(small=True)}</div>'
    return (hero + D.nav(ctx, secs, "ev-nav iv-nav nv-nav") + photo(ctx, "nv-photo")
            + f'<div class="nv-body">{body(ctx, secs, "nv-sec", strip)}</div>')


def terracotta(ctx) -> str:
    """Terracotta: cream paper, beadwork, a shield and spears, and a Nguni cow among the baskets and pots."""
    secs = D.collect(ctx)
    title, sub = occasion(ctx)
    count = D.s_countdown(ctx) if ctx["show"].get("countdown") else ""
    facts = []
    dp = D.date_parts(ctx)
    facts.append(("date", "Date", f'{dp["day"]} {dp["month"]} {dp["year"]}'.strip() or ctx["date_text"]))
    if ctx["time_text"]:
        facts.append(("time", "Time", ctx["time_text"].split(" – ")[0]))
    if ctx["venue"].get("name"):
        facts.append(("venue", "Venue", ctx["venue"]["name"]))
    fact_html = "".join(f'<div>{ICONS[k]}<b>{esc(lab)}</b><span>{esc(val)}</span></div>' for k, lab, val in facts)
    hero = (f'<header class="tc-hero" id="welcome"><span class="tc-beads" aria-hidden="true"></span><div class="tc-card">'
            f'{CREST}<p class="tc-title">{esc(title)}</p><p class="tc-sub">{esc(sub)}</p>{D.greeting(ctx)}'
            f'<p class="tc-intro">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="tc-names">{D.names_html(ctx, "&amp;")}</h1>{ORNAMENT}{families(ctx)}'
            f'<div class="tc-facts">{fact_html}</div>{count}{actions(ctx, "RSVP")}{reply_by(ctx)}</div>'
            f'<div class="tc-still" aria-hidden="true">{BASKET_BOWL}{POT}</div></header>')
    divider = f'<div class="tc-div" aria-hidden="true">{ORNAMENT}</div>'
    rest = [(k, h) for k, h in secs if k != "countdown"]
    return hero + D.nav(ctx, secs, "ev-nav iv-nav tc-nav") + photo(ctx, "tc-photo") + f'<div class="tc-body">{body(ctx, rest, "tc-sec", divider)}</div>'


def ribbon(ctx) -> str:
    """Ribbon: a card framed by a hand-drawn ribbon that draws itself, then ties into a bow."""
    secs = D.collect(ctx)
    hero = (f'<header class="rb-hero" id="welcome">{scatter("rb-bows", 9, 5, MINI_BOW)}<article class="rb-card" aria-labelledby="rb-names">'
            f'{ribbon_frame("rb-frame")}{BOW_RB}<div class="rb-in">'
            f'{D.greeting(ctx)}<p class="rb-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="rb-names" id="rb-names">{D.names_html(ctx, "&amp;")}</h1>{families(ctx)}'
            f'{date_row(ctx, "rb-date")}{where(ctx, "rb-where")}{actions(ctx, "Kindly reply")}{reply_by(ctx)}</div></article></header>')
    divider = f'<div class="rb-div" aria-hidden="true">{BOW_DIV}</div>'
    return hero + D.nav(ctx, secs, "ev-nav iv-nav rb-nav") + photo(ctx, "rb-photo") + f'<div class="rb-body">{body(ctx, secs, "rb-sec", divider)}</div>'


def weave(ctx) -> str:
    """Weave: a woven chevron envelope opens and a soft pink card rises out."""
    secs = D.collect(ctx)
    card = (f'<article class="wv-card env-card" id="welcome" aria-labelledby="wv-names"><p class="wv-mono" aria-hidden="true">{esc(ctx["monogram"])}</p>'
            f'{D.greeting(ctx)}<p class="wv-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="wv-names" id="wv-names">{D.names_html(ctx, "&amp;")}</h1>{families(ctx)}'
            f'{date_row(ctx, "wv-date")}{where(ctx, "wv-where")}{actions(ctx, "RSVP")}{reply_by(ctx)}</article>')
    env = (f'<div class="env-scene wv-scene">'
           f'<div class="env-flapwrap" aria-hidden="true"><div class="env-flap"><div class="env-flap__out">{cloth_fill()}</div>'
           f'<div class="env-flap__in"></div>{seal(ctx["monogram"], "wv-seal-f", "env-flap__seal")}</div></div>'
           f'{card}<div class="env-pocket" aria-hidden="true">{cloth_fill()}<span class="env-pocket__seams"></span></div></div>')
    hero = f'<header class="wv-hero">{defs_weave()}{env}</header>'
    strip = f'<div class="wv-strip" aria-hidden="true">{cloth_fill()}</div>'
    return hero + D.nav(ctx, secs, "ev-nav iv-nav wv-nav") + photo(ctx, "wv-photo") + f'<div class="wv-body">{body(ctx, secs, "wv-sec", strip)}</div>'


def glitter(ctx) -> str:
    """Glitter: chrome balloons, a turning disco ball and sequins that catch the light."""
    secs = D.collect(ctx)
    hero = (f'<header class="gl-hero" id="welcome"><div class="gl-sequins" aria-hidden="true"></div>{scatter("gl-sparks", 16, 7, SPARK)}'
            f'<div class="gl-disco" aria-hidden="true">{DISCO}</div>{balloons(balloon_text(ctx))}<div class="gl-in">'
            f'{D.greeting(ctx)}<p class="gl-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="gl-names">{D.names_html(ctx, "&amp;")}</h1>{date_row(ctx, "gl-date")}{where(ctx, "gl-where")}'
            f'{actions(ctx, "Count me in")}{reply_by(ctx)}</div></header>')
    return hero + D.nav(ctx, secs, "ev-nav iv-nav gl-nav") + photo(ctx, "gl-photo") + f'<div class="gl-body">{body(ctx, secs, "gl-sec")}</div>'


def matcha(ctx) -> str:
    """Matcha: pink cabana stripes, an olive bow, a matcha latte and a pilates ball."""
    secs = D.collect(ctx)
    hero = (f'<header class="mt-hero" id="welcome"><div class="mt-awning" aria-hidden="true"></div>'
            f'<div class="mt-card">{BOW_MT}'
            f'{D.greeting(ctx)}<p class="mt-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="mt-names">{D.names_html(ctx, "&amp;")}</h1>{date_row(ctx, "mt-date")}{where(ctx, "mt-where")}'
            f'{actions(ctx, "Save my spot")}{reply_by(ctx)}</div>'
            f'<div class="mt-still" aria-hidden="true">{MATCHA}{BALL}</div></header>')
    divider = '<div class="mt-div" aria-hidden="true"><i></i></div>'
    return hero + D.nav(ctx, secs, "ev-nav iv-nav mt-nav") + photo(ctx, "mt-photo") + f'<div class="mt-body">{body(ctx, secs, "mt-sec", divider)}</div>'


def festive(ctx) -> str:
    """Festive: candy stripes, an arched card tied with red ribbon, a tree with bows and falling snow."""
    secs = D.collect(ctx)
    hero = (f'<header class="fs-hero" id="welcome">{snow()}<div class="fs-arch">'
            f'{BOW_FS}<div class="fs-in">'
            f'{D.greeting(ctx)}<p class="fs-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="fs-names">{D.names_html(ctx, "&amp;")}</h1>{date_row(ctx, "fs-date")}{where(ctx, "fs-where")}'
            f'{actions(ctx, "RSVP")}{reply_by(ctx)}</div></div><div class="fs-tree" aria-hidden="true">{TREE}</div></header>')
    divider = '<div class="fs-div" aria-hidden="true"></div>'
    return hero + D.nav(ctx, secs, "ev-nav iv-nav fs-nav") + photo(ctx, "fs-photo") + f'<div class="fs-body">{body(ctx, secs, "fs-sec", divider)}</div>'


def cheers(ctx) -> str:
    """Cheers: a champagne bottle pops, bubbles fizz up and gold confetti falls around a golden ticket."""
    secs = D.collect(ctx)
    dp = D.date_parts(ctx)
    stub = (f'<div class="cs-stub" aria-hidden="true"><span class="cs-admit">Admit one</span>'
            f'<b>{esc(dp["day"] or "")}</b><span>{esc(dp["mon"])}</span><span>{esc(dp["year"])}</span></div>') if dp["day"] else ""
    hero = (f'<header class="cs-hero" id="welcome">{confetti()}<div class="cs-stage">'
            f'<div class="cs-bottlewrap" aria-hidden="true">{BOTTLE}{fizz()}</div>'
            f'<article class="cs-ticket" aria-labelledby="cs-names"><div class="cs-main">{D.greeting(ctx)}'
            f'<p class="cs-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="cs-names" id="cs-names">{D.names_html(ctx, "&amp;")}</h1>{date_row(ctx, "cs-date")}{where(ctx, "cs-where")}'
            f'{actions(ctx, "Count me in")}{reply_by(ctx)}</div>{stub}</article></div></header>')
    divider = '<div class="cs-div" aria-hidden="true"><i></i><i></i><i></i></div>'
    from .render import luminance
    light = " cs-light" if luminance(ctx["theme"]["colors"]["bg"]) > .4 else ""
    return hero + D.nav(ctx, secs, "ev-nav iv-nav cs-nav") + photo(ctx, "cs-photo") + f'<div class="cs-body{light}">{body(ctx, secs, "cs-sec", divider)}</div>'


def teddy(ctx) -> str:
    """Teddy: a teddy bear peeks over the card holding balloons, under drifting clouds."""
    secs = D.collect(ctx)
    tag = '<p class="tb-tag">We can bearly wait!</p>' if ctx["group"] == "baby" else ""
    hero = (f'<header class="tb-hero" id="welcome">{clouds()}<div class="tb-stage">'
            f'<article class="tb-card" aria-labelledby="tb-names">{TEDDY}{tag}{D.greeting(ctx)}'
            f'<p class="tb-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="tb-names" id="tb-names">{D.names_html(ctx, "&amp;")}</h1>{date_row(ctx, "tb-date")}{where(ctx, "tb-where")}'
            f'{actions(ctx, "RSVP")}{reply_by(ctx)}</article></div></header>')
    divider = '<div class="tb-div" aria-hidden="true"><i></i><i></i><i></i></div>'
    return hero + D.nav(ctx, secs, "ev-nav iv-nav tb-nav") + photo(ctx, "tb-photo") + f'<div class="tb-body">{body(ctx, secs, "tb-sec", divider)}</div>'


def reveal(ctx) -> str:
    """Reveal: a question balloon pops into pink and blue confetti; pink and blue balloons bob either side."""
    secs = D.collect(ctx)
    hero = (f'<header class="rv-hero" id="welcome"><div class="rv-pop" aria-hidden="true">{QBALLOON}{burst()}</div>'
            f'<div class="rv-stage">{pastel_balloon("pb--pink")}'
            f'<article class="rv-card" aria-labelledby="rv-names">{D.greeting(ctx)}<p class="rv-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="rv-names" id="rv-names">{D.names_html(ctx, "&amp;")}</h1>'
            f'<p class="rv-teams" aria-hidden="true"><span class="rv-team rv-team--pink">Team pink</span><span class="rv-or">or</span>'
            f'<span class="rv-team rv-team--blue">Team blue</span></p>'
            f'{date_row(ctx, "rv-date")}{where(ctx, "rv-where")}{actions(ctx, "RSVP")}{reply_by(ctx)}</article>'
            f'{pastel_balloon("pb--blue")}</div></header>')
    divider = '<div class="rv-div" aria-hidden="true"><i></i><i></i></div>'
    return hero + D.nav(ctx, secs, "ev-nav iv-nav rv-nav") + photo(ctx, "rv-photo") + f'<div class="rv-body">{body(ctx, secs, "rv-sec", divider)}</div>'


MEMORIAL_TITLES = {"invitation": "In loving memory", "venue": "The service", "programme": "Order of service",
                   "rsvp": "Let the family know", "registry": "In lieu of flowers", "gallery": "Memories",
                   "contact": "Family contacts", "dress_code": "Dress", "menu": "Refreshments", "seating": "Your seat"}
MEMORIAL_NAV = {"invitation": "Memory", "venue": "Service", "programme": "Order of service", "rsvp": "RSVP",
                "registry": "Donations", "gallery": "Memories", "contact": "Family", "menu": "Refreshments"}


def memorial(ctx) -> str:
    """Memorial: calm and respectful, with a candle that gently flickers and white lilies."""
    secs = [(k, h) for k, h in D.collect(ctx) if k != "countdown"]
    years = life_years(ctx)
    portrait = (f'<div class="mm-portrait">{D.hero_image(ctx, "ev-photo mm-photo")}</div>' if ctx["hero"]
                else f'<div class="mm-portrait mm-portrait--candle" aria-hidden="true">{CANDLE}</div>')
    name = ctx["hosts"]
    hero = (f'<header class="mm-hero" id="welcome"><div class="mm-stage">'
            f'<div class="mm-frame">{LILIES_L}{portrait}{LILIES_R}</div>'
            f'{D.greeting(ctx)}<p class="mm-kicker">{esc(ctx["wording"]["welcome"])}</p>'
            f'<h1 class="mm-name">{esc(name)}</h1>{f"<p class=mm-years>{esc(years)}</p>" if years else ""}'
            f'<div class="mm-rule" aria-hidden="true"><i></i></div>{date_row(ctx, "mm-date")}{where(ctx, "mm-where")}'
            f'{actions(ctx, "Let the family know")}{reply_by(ctx)}</div></header>')
    out = []
    for k, html in secs:
        out.append(D.section(k, html, title=MEMORIAL_TITLES.get(k, ""), cls="iv-sec mm-sec rv"))
    nav = D.nav(ctx, secs, "ev-nav iv-nav mm-nav")
    for k, label in MEMORIAL_NAV.items():
        nav = nav.replace(f'href="#{k}">{esc(D.NAV_LABELS[k])}<', f'href="#{k}">{esc(label)}<')
    return hero + nav + f'<div class="mm-body">{"".join(out)}</div>'


LAYOUTS = {"nguni": nguni, "terracotta": terracotta, "ribbon": ribbon, "weave": weave, "glitter": glitter,
           "matcha": matcha, "festive": festive, "cheers": cheers, "teddy": teddy, "reveal": reveal, "memorial": memorial}

# Heritage, the traditional wedding in an edition for each culture, lives in cultures.py.
from .cultures import heritage as _heritage  # noqa: E402

LAYOUTS["heritage"] = _heritage
