"""Palettes, font pairings and background options for each event-website design.

Shared by the wizard (design step) and the renderer. A customer's choices are stored in
events.design as {palette, font_pair, background, colors{...}}; `resolve()` merges them with
the design defaults into CSS variables.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote_plus

FONTS = {
    # family: google axis spec
    "Cormorant Garamond": "ital,wght@0,300..700;1,300..700",
    "Jost": "wght@300..600",
    "Bodoni Moda": "ital,opsz,wght@0,6..96,400..800;1,6..96,400..800",
    "Inter": "wght@300..700",
    "Pinyon Script": "",
    "Cinzel": "wght@400..800",
    "Marcellus": "",
    "Italiana": "",
    "Montserrat": "wght@300..700",
    "Outfit": "wght@200..700",
    "Fredoka": "wght@400..700",
    "Nunito": "wght@400..800",
    "Syne": "wght@500..800",
    "Space Grotesk": "wght@400..700",
    "EB Garamond": "ital,wght@0,400..700;1,400..700",
    "Libre Franklin": "wght@300..700",
    "Fraunces": "ital,opsz,wght@0,9..144,300..800;1,9..144,300..800",
    "DM Sans": "wght@300..700",
    "Playfair Display": "ital,wght@0,400..800;1,400..800",
    "Lato": "wght@300;400;700",
    "Great Vibes": "",
    "Lora": "ital,wght@0,400..700;1,400..700",
    "Instrument Serif": "ital@0;1",
    "Geist": "wght@300..700",
}

FONT_PAIRS = {
    "cormorant-jost": ("Classic serif", "Cormorant Garamond", "Jost"),
    "bodoni-inter": ("High-contrast editorial", "Bodoni Moda", "Inter"),
    "pinyon-cormorant": ("Flowing script", "Pinyon Script", "Cormorant Garamond"),
    "greatvibes-lora": ("Romantic script", "Great Vibes", "Lora"),
    "cinzel-marcellus": ("Carved capitals", "Cinzel", "Marcellus"),
    "italiana-montserrat": ("Deco elegance", "Italiana", "Montserrat"),
    "outfit": ("Clean geometric", "Outfit", "Outfit"),
    "fredoka-nunito": ("Soft and rounded", "Fredoka", "Nunito"),
    "syne-space": ("Bold display", "Syne", "Space Grotesk"),
    "space-inter": ("Modern tech", "Space Grotesk", "Inter"),
    "garamond-franklin": ("Academic classic", "EB Garamond", "Libre Franklin"),
    "fraunces-dm": ("Warm storybook", "Fraunces", "DM Sans"),
    "playfair-lato": ("Timeless", "Playfair Display", "Lato"),
    "instrument-geist": ("Contemporary serif", "Instrument Serif", "Geist"),
}

# palette keys: bg, surface, text, muted, accent, accent2
DESIGNS = {
    "atelier": {
        "font_pair": "cormorant-jost", "fonts": ["cormorant-jost", "playfair-lato", "instrument-geist", "bodoni-inter"],
        "backgrounds": ["plain", "paper", "image"], "background": "paper",
        "palettes": [
            ("ivory", "Ivory and ink", {"bg": "#FBF8F3", "surface": "#FFFFFF", "text": "#1E1C1A", "muted": "#6E675F", "accent": "#A88B5C", "accent2": "#E9E1D3"}),
            ("stone", "Stone and sage", {"bg": "#F3F2EE", "surface": "#FBFAF7", "text": "#26302A", "muted": "#66706A", "accent": "#7D8F7A", "accent2": "#DCE2D8"}),
            ("noir", "Noir", {"bg": "#161514", "surface": "#1F1D1C", "text": "#F2EEE8", "muted": "#A9A29A", "accent": "#C8A96E", "accent2": "#2A2724"}),
        ]},
    "folio": {
        "font_pair": "bodoni-inter", "fonts": ["bodoni-inter", "playfair-lato", "instrument-geist", "space-inter"],
        "backgrounds": ["plain", "image"], "background": "image",
        "palettes": [
            ("newsprint", "Newsprint and red", {"bg": "#F4F1EA", "surface": "#FFFFFF", "text": "#111111", "muted": "#5D5A55", "accent": "#C2382B", "accent2": "#E6E0D4"}),
            ("cobalt", "Paper and cobalt", {"bg": "#F6F5F2", "surface": "#FFFFFF", "text": "#0E1530", "muted": "#555B6E", "accent": "#2448C8", "accent2": "#E2E5EF"}),
            ("forest", "Ink and forest", {"bg": "#EEF0EA", "surface": "#FAFBF7", "text": "#132018", "muted": "#56635A", "accent": "#1F6B45", "accent2": "#D9E2D8"}),
        ]},
    "bloom": {
        "font_pair": "pinyon-cormorant", "fonts": ["pinyon-cormorant", "greatvibes-lora", "cormorant-jost", "playfair-lato"],
        "backgrounds": ["plain", "paper", "image"], "background": "paper",
        "palettes": [
            ("blush", "Blush and sage", {"bg": "#FBF3F0", "surface": "#FFFFFF", "text": "#4A3236", "muted": "#8A6F72", "accent": "#C7868B", "accent2": "#A7B59C"}),
            ("lavender", "Lavender field", {"bg": "#F6F3FA", "surface": "#FFFFFF", "text": "#3A3150", "muted": "#7A7190", "accent": "#9C84C4", "accent2": "#B9C8A4"}),
            ("peach", "Peach and olive", {"bg": "#FDF5EE", "surface": "#FFFFFF", "text": "#4B3424", "muted": "#8E7462", "accent": "#E29A72", "accent2": "#99A27A"}),
        ]},
    "heritage": {
        "font_pair": "cinzel-marcellus", "fonts": ["cinzel-marcellus", "playfair-lato", "cormorant-jost"],
        "backgrounds": ["pattern", "plain", "image"], "background": "pattern",
        "palettes": [
            ("ochre", "Ochre and indigo", {"bg": "#F7EFE3", "surface": "#FFFAF2", "text": "#1E2140", "muted": "#5F5A6E", "accent": "#C0702E", "accent2": "#1F3A73"}),
            ("emerald", "Emerald and gold", {"bg": "#F2F1E8", "surface": "#FFFDF6", "text": "#0F2A22", "muted": "#4F5E57", "accent": "#B8892F", "accent2": "#0E5A43"}),
            ("royal", "Royal plum", {"bg": "#F6EFEA", "surface": "#FFFAF6", "text": "#2C1430", "muted": "#6C5868", "accent": "#C4572F", "accent2": "#5B1F63"}),
        ]},
    "champagne": {
        "font_pair": "italiana-montserrat", "fonts": ["italiana-montserrat", "cinzel-marcellus", "cormorant-jost"],
        "backgrounds": ["plain", "image"], "background": "plain",
        "palettes": [
            ("midnight", "Midnight and gold", {"bg": "#0D0C10", "surface": "#17151C", "text": "#F3EBDD", "muted": "#B3A88F", "accent": "#D4AF6A", "accent2": "#2A2433"}),
            ("emerald-night", "Emerald night", {"bg": "#07120F", "surface": "#0F1D19", "text": "#EFE8D8", "muted": "#A6A08C", "accent": "#CFAE6B", "accent2": "#173029"}),
            ("ivory-gold", "Ivory and gold", {"bg": "#F8F3E9", "surface": "#FFFDF8", "text": "#2A2218", "muted": "#7B6E5C", "accent": "#B08D45", "accent2": "#EADFC9"}),
        ]},
    "linea": {
        "font_pair": "outfit", "fonts": ["outfit", "space-inter", "instrument-geist"],
        "backgrounds": ["plain", "image"], "background": "plain",
        "palettes": [
            ("sage", "Sage and white", {"bg": "#F7F8F5", "surface": "#FFFFFF", "text": "#1C211D", "muted": "#68716A", "accent": "#5E7A63", "accent2": "#E3E9E2"}),
            ("sand", "Sand and charcoal", {"bg": "#F6F2EC", "surface": "#FFFFFF", "text": "#232120", "muted": "#716B66", "accent": "#B4875B", "accent2": "#EAE3DA"}),
            ("slate", "Slate and sky", {"bg": "#F3F5F8", "surface": "#FFFFFF", "text": "#17202B", "muted": "#5F6A78", "accent": "#4A79A8", "accent2": "#E1E8F0"}),
        ]},
    "confetti": {
        "font_pair": "fredoka-nunito", "fonts": ["fredoka-nunito", "fraunces-dm", "outfit"],
        "backgrounds": ["plain", "pattern"], "background": "pattern",
        "palettes": [
            ("sorbet", "Sorbet", {"bg": "#FFF8F3", "surface": "#FFFFFF", "text": "#3B2F4A", "muted": "#7B6F88", "accent": "#F28FA6", "accent2": "#8CCFD9"}),
            ("mint", "Mint and lemon", {"bg": "#F5FBF7", "surface": "#FFFFFF", "text": "#23413A", "muted": "#647E77", "accent": "#5DBB9A", "accent2": "#F6D365"}),
            ("sky", "Baby blue", {"bg": "#F4F8FD", "surface": "#FFFFFF", "text": "#22334F", "muted": "#66758E", "accent": "#7AA6E8", "accent2": "#F5C6D0"}),
        ]},
    "pulse": {
        "font_pair": "syne-space", "fonts": ["syne-space", "space-inter", "outfit"],
        "backgrounds": ["plain", "image"], "background": "plain",
        "palettes": [
            ("electric", "Electric", {"bg": "#F1EFE9", "surface": "#FFFFFF", "text": "#0B0B0C", "muted": "#55524C", "accent": "#FF4F1F", "accent2": "#2B2BFF"}),
            ("lime", "Lime and black", {"bg": "#0E0E0E", "surface": "#191919", "text": "#F3F3EE", "muted": "#A3A39C", "accent": "#C6F432", "accent2": "#FF5DA2"}),
            ("candy", "Candy", {"bg": "#FFF0F6", "surface": "#FFFFFF", "text": "#1A0B1E", "muted": "#6E5672", "accent": "#E8247C", "accent2": "#FFB000"}),
        ]},
    "aurora": {
        "font_pair": "space-inter", "fonts": ["space-inter", "instrument-geist", "outfit", "italiana-montserrat"],
        "backgrounds": ["aurora", "image"], "background": "aurora",
        "palettes": [
            ("opal", "Opal", {"bg": "#EEF0F7", "surface": "#FFFFFF", "text": "#16182A", "muted": "#5D6178", "accent": "#7C6CF2", "accent2": "#F2A7C8"}),
            ("dusk", "Dusk", {"bg": "#0C0D18", "surface": "#161830", "text": "#EEF0FF", "muted": "#A3A7C6", "accent": "#9F8CFF", "accent2": "#FF9CC2"}),
            ("pearl-gold", "Pearl and gold", {"bg": "#F5F2EC", "surface": "#FFFFFF", "text": "#211D16", "muted": "#6E675B", "accent": "#C29B4F", "accent2": "#B8C7E6"}),
        ]},
    "laureate": {
        "font_pair": "garamond-franklin", "fonts": ["garamond-franklin", "playfair-lato", "cinzel-marcellus"],
        "backgrounds": ["plain", "paper", "image"], "background": "paper",
        "palettes": [
            ("navy", "Navy and gold", {"bg": "#F5F3EE", "surface": "#FFFFFF", "text": "#14213D", "muted": "#5A6377", "accent": "#B8913A", "accent2": "#14213D"}),
            ("burgundy", "Burgundy", {"bg": "#F7F2EE", "surface": "#FFFFFF", "text": "#3B0F1B", "muted": "#6D5459", "accent": "#A97C2F", "accent2": "#6A1B2E"}),
            ("green", "College green", {"bg": "#F2F3EE", "surface": "#FFFFFF", "text": "#10291F", "muted": "#53625B", "accent": "#B08D45", "accent2": "#18452F"}),
        ]},
    "cradle": {
        "font_pair": "fraunces-dm", "fonts": ["fraunces-dm", "fredoka-nunito", "cormorant-jost"],
        "backgrounds": ["paper", "plain"], "background": "paper",
        "palettes": [
            ("sage-cream", "Sage and cream", {"bg": "#F8F4EA", "surface": "#FFFDF7", "text": "#2F3A30", "muted": "#6F786D", "accent": "#8DA37F", "accent2": "#E8C9A0"}),
            ("dusty-blue", "Dusty blue", {"bg": "#F3F5F6", "surface": "#FFFFFF", "text": "#26364A", "muted": "#68778A", "accent": "#7F9CBA", "accent2": "#EAD7B4"}),
            ("rose", "Rosewood", {"bg": "#FAF3F1", "surface": "#FFFFFF", "text": "#4A2F33", "muted": "#8A6E71", "accent": "#C99396", "accent2": "#C9D3B8"}),
        ]},
}

# --- Cultural styles for Heritage ----------------------------------------------------------------
# Each is a palette for the page (text contrast checked to WCAG AA) plus six motif colours for the
# beadwork borders, which also take the culture's own pattern (designs.MOTIFS). They are chosen like
# any other palette, so saving, the live preview and custom colours work unchanged.
CULTURES = {
    "ndebele": ("Ndebele", "Bold painted geometry in primary colours, outlined in black",
                {"bg": "#FBFAF6", "surface": "#FFFFFF", "text": "#141414", "muted": "#555555", "accent": "#D62828", "accent2": "#1D3E8A"},
                ("#D62828", "#F2B705", "#1D5FB8", "#2E8B57", "#111111", "#FFFFFF")),
    "zulu": ("Zulu", "Beadwork triangles in red, blue, black and yellow",
             {"bg": "#F8F5EE", "surface": "#FFFFFF", "text": "#1A1A1A", "muted": "#5E5A55", "accent": "#C1272D", "accent2": "#1B3F8B"},
             ("#C1272D", "#F2C200", "#1B3F8B", "#2F8F46", "#151515", "#FFFFFF")),
    "xhosa": ("Xhosa", "Umbhaco cream and ochre with black braid bands",
              {"bg": "#F7F1E6", "surface": "#FFFDF8", "text": "#161616", "muted": "#5D564D", "accent": "#B8541E", "accent2": "#111111"},
              ("#C8642A", "#E9D8B6", "#1FA6A0", "#B23A2E", "#111111", "#FFFFFF")),
    "pedi": ("Pedi", "Bright stripes in pink, yellow, blue and purple",
             {"bg": "#FBF6F4", "surface": "#FFFFFF", "text": "#24132B", "muted": "#67586B", "accent": "#D6337A", "accent2": "#2A3F96"},
             ("#E0338A", "#F5B700", "#2D4FB0", "#2E9E5B", "#6B2FA0", "#FFFFFF")),
    "venda": ("Venda", "Minwenda stripes and zigzags on deep navy",
              {"bg": "#FAF7F0", "surface": "#FFFFFF", "text": "#121212", "muted": "#5A5650", "accent": "#C8102E", "accent2": "#12284C"},
              ("#D7262E", "#F4C20D", "#2457C5", "#229A4C", "#12284C", "#FFFFFF")),
    "tsonga": ("Tsonga", "Xibelani colour with a beaded fringe",
               {"bg": "#FFF8F0", "surface": "#FFFFFF", "text": "#2A1810", "muted": "#6E5A4E", "accent": "#E8590C", "accent2": "#1C5D99"},
               ("#F26B1D", "#F7C531", "#1C5D99", "#2FA36B", "#D7263D", "#F06EAA")),
    "swati": ("Swati", "Emahiya red with black and white shields",
              {"bg": "#FBF7F2", "surface": "#FFFFFF", "text": "#1B1414", "muted": "#625656", "accent": "#B5232A", "accent2": "#1E1E1E"},
              ("#C0262D", "#F2C200", "#2B3F8C", "#2E7D46", "#141414", "#FFFFFF")),
}
DESIGNS["heritage"]["palettes"] = DESIGNS["heritage"]["palettes"] + [(k, v[0], v[2]) for k, v in CULTURES.items()]
DESIGNS["heritage"]["cultures"] = list(CULTURES)


def culture(design_key: str, palette_key: str) -> str:
    """The cultural style in use ("zulu", ...), or "" for a classic palette or another template."""
    return palette_key if design_key == "heritage" and palette_key in CULTURES else ""


def culture_vars(key: str) -> str:
    return "".join(f"--m{n}:{c};" for n, c in enumerate(CULTURES[key][3], 1)) if key in CULTURES else ""


BACKGROUND_LABELS = {
    "plain": "Plain colour", "paper": "Soft paper texture", "pattern": "Signature pattern",
    "image": "Your photo behind the welcome", "aurora": "Aurora light field",
}


def design(key: str) -> dict:
    return DESIGNS.get(key) or DESIGNS["atelier"]


def palettes(key: str) -> list:
    return design(key)["palettes"]


def resolve(design_key: str, choices: Optional[dict]) -> dict:
    """Merge saved choices with design defaults → {colors, font_pair, display, body, background}."""
    d = design(design_key)
    choices = choices or {}
    pal_key = choices.get("palette") or d["palettes"][0][0]
    base = next((p[2] for p in d["palettes"] if p[0] == pal_key), d["palettes"][0][2])
    colors = dict(base)
    for k, v in (choices.get("colors") or {}).items():
        if k in colors and isinstance(v, str) and len(v) == 7 and v.startswith("#"):
            colors[k] = v
    fp = choices.get("font_pair") if choices.get("font_pair") in FONT_PAIRS else d["font_pair"]
    bg = choices.get("background") if choices.get("background") in BACKGROUND_LABELS else d["background"]
    _, display, body = FONT_PAIRS[fp]
    return {"palette": pal_key, "colors": colors, "font_pair": fp, "display": display, "body": body, "background": bg}


def fonts_url(*families: str) -> str:
    parts = []
    for fam in dict.fromkeys(families):
        spec = FONTS.get(fam, "")
        parts.append("family=" + quote_plus(fam) + (":" + spec if spec else ""))
    return "https://fonts.googleapis.com/css2?" + "&".join(parts) + "&display=swap"


def css_vars(resolved: dict) -> str:
    c = resolved["colors"]
    return (f"--ev-bg:{c['bg']};--ev-surface:{c['surface']};--ev-text:{c['text']};--ev-muted:{c['muted']};"
            f"--ev-accent:{c['accent']};--ev-accent2:{c['accent2']};"
            f"--ev-display:'{resolved['display']}',Georgia,serif;--ev-body:'{resolved['body']}',system-ui,sans-serif;")
