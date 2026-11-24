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
    "Gloock": "",
    "DM Serif Display": "ital@0;1",
    "Caveat": "wght@400..700",
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
    "gloock-dm": ("Retro serif", "Gloock", "DM Sans"),
    "dmserif-dm": ("Soft display serif", "DM Serif Display", "DM Sans"),
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

# --- The invitation collection (app/eventsite/invites.py) -----------------------------------------
# "extra" is a third font some designs use for a script or hand-written accent (--ev-extra).
DESIGNS.update({
    "nguni": {
        "font_pair": "cormorant-jost", "fonts": ["cormorant-jost", "cinzel-marcellus", "playfair-lato", "bodoni-inter"],
        "backgrounds": ["paper", "plain", "image"], "background": "paper", "extra": "Pinyon Script",
        "palettes": [
            ("brown-hide", "Brown hide and gold", {"bg": "#F2EBE0", "surface": "#FFFBF4", "text": "#2B1D14", "muted": "#6E5A4A", "accent": "#A97C2F", "accent2": "#6B3F22"}),
            ("black-hide", "Black hide and gold", {"bg": "#EFEDE8", "surface": "#FFFDF8", "text": "#1A1714", "muted": "#615A53", "accent": "#A88A4E", "accent2": "#2A2420"}),
            ("golden-hide", "Golden hide", {"bg": "#F5EDE1", "surface": "#FFFAF1", "text": "#3A2414", "muted": "#755F4C", "accent": "#B0782F", "accent2": "#A8692F"}),
        ]},
    "terracotta": {
        "font_pair": "greatvibes-lora", "fonts": ["greatvibes-lora", "pinyon-cormorant", "cinzel-marcellus", "playfair-lato"],
        "backgrounds": ["paper", "plain", "image"], "background": "paper", "extra": "Cinzel",
        "palettes": [
            ("terracotta", "Terracotta and cream", {"bg": "#F8EEDD", "surface": "#FFF8EC", "text": "#2E1F14", "muted": "#6B4A33", "accent": "#8E3B22", "accent2": "#D9A441"}),
            ("indigo", "Indigo and sand", {"bg": "#EEF1F6", "surface": "#FFFFFF", "text": "#13213F", "muted": "#4E5A72", "accent": "#1F3A73", "accent2": "#C9A26B"}),
            ("olive", "Olive and clay", {"bg": "#F3F0E2", "surface": "#FFFDF4", "text": "#2B2E1C", "muted": "#5E604A", "accent": "#5E6B42", "accent2": "#C0702E"}),
        ]},
    "ribbon": {
        "font_pair": "instrument-geist", "fonts": ["instrument-geist", "cormorant-jost", "playfair-lato", "pinyon-cormorant"],
        "backgrounds": ["paper", "plain", "image"], "background": "paper",
        "palettes": [
            ("olive", "Olive ribbon", {"bg": "#F5F1E6", "surface": "#FFFDF7", "text": "#2C3122", "muted": "#626850", "accent": "#66743A", "accent2": "#D8CBA4"}),
            ("burgundy", "Burgundy bow", {"bg": "#F7EEEC", "surface": "#FFFBFA", "text": "#3A1418", "muted": "#6E4E52", "accent": "#7A1F2B", "accent2": "#E8C5C3"}),
            ("blush", "Blush bow", {"bg": "#FCF2F3", "surface": "#FFFFFF", "text": "#4A2B33", "muted": "#7E5F66", "accent": "#D17C8F", "accent2": "#F3D3D9"}),
            ("powder", "Powder blue", {"bg": "#F1F5F9", "surface": "#FFFFFF", "text": "#1F2E44", "muted": "#58677C", "accent": "#6F95BE", "accent2": "#D8E4F1"}),
        ]},
    "weave": {
        "font_pair": "fraunces-dm", "fonts": ["fraunces-dm", "playfair-lato", "instrument-geist", "gloock-dm"],
        "backgrounds": ["plain", "paper", "image"], "background": "plain",
        "palettes": [
            ("sunset", "Sunset weave", {"bg": "#FFF4EF", "surface": "#FFE3E7", "text": "#540F1B", "muted": "#83434E", "accent": "#E4572E", "accent2": "#F49BB4"}),
            ("indigo", "Indigo weave", {"bg": "#F2F4FA", "surface": "#E4EAF7", "text": "#14213D", "muted": "#4F5B78", "accent": "#2B50AA", "accent2": "#9EC1E8"}),
            ("earth", "Earth weave", {"bg": "#F7F0E6", "surface": "#F3E5D0", "text": "#3B2314", "muted": "#6F5643", "accent": "#B5651D", "accent2": "#E3B47A"}),
        ]},
    "glitter": {
        "font_pair": "bodoni-inter", "fonts": ["bodoni-inter", "syne-space", "italiana-montserrat", "playfair-lato"],
        "backgrounds": ["pattern", "plain", "image"], "background": "pattern", "extra": "Fredoka",
        "palettes": [
            ("silver", "Silver chrome", {"bg": "#0B0B10", "surface": "#17171F", "text": "#F4F4F8", "muted": "#A9A9B9", "accent": "#C9CDD8", "accent2": "#FF6FAE"}),
            ("gold", "Gold chrome", {"bg": "#0E0B07", "surface": "#1B160E", "text": "#FBF3E2", "muted": "#B8A98C", "accent": "#E3C27A", "accent2": "#F2E2BC"}),
            ("pink", "Pink glitter", {"bg": "#FFEFF6", "surface": "#FFFFFF", "text": "#3A0B24", "muted": "#7A4A63", "accent": "#E0428A", "accent2": "#C9CDD8"}),
        ]},
    "matcha": {
        "font_pair": "gloock-dm", "fonts": ["gloock-dm", "fraunces-dm", "instrument-geist", "playfair-lato"],
        "backgrounds": ["plain", "paper", "image"], "background": "plain",
        "palettes": [
            ("matcha-pink", "Matcha and pink", {"bg": "#FFF6F6", "surface": "#FFFFFF", "text": "#2F3A1F", "muted": "#626B4E", "accent": "#E98AA6", "accent2": "#7E8C45"}),
            ("strawberry", "Strawberry milk", {"bg": "#FFF3F3", "surface": "#FFFFFF", "text": "#4A1D24", "muted": "#7B5157", "accent": "#E55B6F", "accent2": "#8FA352"}),
            ("butter", "Butter yellow", {"bg": "#FFF9EA", "surface": "#FFFFFF", "text": "#3B331A", "muted": "#6B6247", "accent": "#E9B53F", "accent2": "#7E8C45"}),
        ]},
    "festive": {
        "font_pair": "playfair-lato", "fonts": ["playfair-lato", "cormorant-jost", "fraunces-dm", "greatvibes-lora"],
        "backgrounds": ["pattern", "plain", "image"], "background": "pattern", "extra": "Great Vibes",
        "palettes": [
            ("candy-cane", "Candy cane red", {"bg": "#FBF5EE", "surface": "#FFFDF8", "text": "#2B1414", "muted": "#6A4E4E", "accent": "#C8102E", "accent2": "#1F5C3A"}),
            ("evergreen", "Evergreen and gold", {"bg": "#0F2A20", "surface": "#16382B", "text": "#F7F1E6", "muted": "#B9C2B4", "accent": "#D9B45F", "accent2": "#C8102E"}),
            ("frost", "Frosted blue", {"bg": "#F2F6FA", "surface": "#FFFFFF", "text": "#172A40", "muted": "#56677C", "accent": "#2F5D8C", "accent2": "#B8C4D3"}),
        ]},
    "cheers": {
        "font_pair": "dmserif-dm", "fonts": ["dmserif-dm", "playfair-lato", "bodoni-inter", "italiana-montserrat"],
        "backgrounds": ["plain", "pattern", "image"], "background": "plain", "extra": "Great Vibes",
        "palettes": [
            ("midnight", "Midnight and gold", {"bg": "#0B1020", "surface": "#151C33", "text": "#F6F1E6", "muted": "#A9AFBF", "accent": "#E2C47A", "accent2": "#F4E3B8"}),
            ("burgundy", "Burgundy and champagne", {"bg": "#2A0710", "surface": "#3A0E19", "text": "#F8EBDD", "muted": "#CDB3AA", "accent": "#E9C46A", "accent2": "#F5DFC0"}),
            ("emerald", "Emerald and gold", {"bg": "#071A14", "surface": "#0E281F", "text": "#F1EEE4", "muted": "#A8B5AC", "accent": "#D8BD74", "accent2": "#EAD9A8"}),
            ("champagne", "Champagne", {"bg": "#F6EEE0", "surface": "#FFFBF3", "text": "#2A2118", "muted": "#6A5D4C", "accent": "#B8913F", "accent2": "#EADCC0"}),
        ]},
    "teddy": {
        "font_pair": "fraunces-dm", "fonts": ["fraunces-dm", "fredoka-nunito", "gloock-dm", "playfair-lato"],
        "backgrounds": ["plain", "paper", "image"], "background": "plain", "extra": "Caveat",
        "palettes": [
            ("sage", "Sage and cream", {"bg": "#F1F3EA", "surface": "#FFFDF7", "text": "#2E3A2C", "muted": "#5F6A5B", "accent": "#7F9670", "accent2": "#E6D3B6"}),
            ("baby-blue", "Baby blue", {"bg": "#EDF4FB", "surface": "#FFFFFF", "text": "#1F3047", "muted": "#566579", "accent": "#7FA7D4", "accent2": "#F1E2C6"}),
            ("blush", "Blush", {"bg": "#FBF0F1", "surface": "#FFFFFF", "text": "#4A2A31", "muted": "#7E5F66", "accent": "#E39AAE", "accent2": "#F2E0C7"}),
        ]},
    "reveal": {
        "font_pair": "fredoka-nunito", "fonts": ["fredoka-nunito", "fraunces-dm", "outfit", "gloock-dm"],
        "backgrounds": ["pattern", "plain", "image"], "background": "pattern",
        "palettes": [
            ("pink-blue", "Pink and blue", {"bg": "#FFF8F9", "surface": "#FFFFFF", "text": "#2B2A3A", "muted": "#64617A", "accent": "#EE7FA6", "accent2": "#6FAEE6"}),
            ("pastel", "Soft pastels", {"bg": "#FCFAF7", "surface": "#FFFFFF", "text": "#2E2B36", "muted": "#67637A", "accent": "#F2A9C2", "accent2": "#9FC9EE"}),
            ("bows-bowties", "Bows or bowties", {"bg": "#F7F5F2", "surface": "#FFFFFF", "text": "#1E2A40", "muted": "#5A6477", "accent": "#E58AA6", "accent2": "#2D4B7A"}),
        ]},
    "memorial": {
        "font_pair": "garamond-franklin", "fonts": ["garamond-franklin", "cormorant-jost", "playfair-lato", "cinzel-marcellus"],
        "backgrounds": ["plain", "paper", "image"], "background": "paper", "extra": "Pinyon Script",
        "palettes": [
            ("ivory", "Ivory and lily", {"bg": "#F7F4EE", "surface": "#FFFFFF", "text": "#1F2530", "muted": "#5B6270", "accent": "#8A7350", "accent2": "#DDE3E8"}),
            ("midnight", "Midnight", {"bg": "#12161D", "surface": "#1B212B", "text": "#EEF0F3", "muted": "#A9B0BC", "accent": "#CDB27C", "accent2": "#2A3240"}),
            ("lavender", "Lavender", {"bg": "#F5F3F8", "surface": "#FFFFFF", "text": "#2A2238", "muted": "#5E5670", "accent": "#6E5A8C", "accent2": "#E3DDEE"}),
            ("sage", "Sage", {"bg": "#F1F3EE", "surface": "#FFFFFF", "text": "#1F2A22", "muted": "#566158", "accent": "#5E7052", "accent2": "#DCE3D6"}),
        ]},
})


# --- Cultural styles for Heritage ----------------------------------------------------------------
# Each is a palette for the page (text contrast checked to WCAG AA) plus six motif colours for the
# beadwork borders, which also take the culture's own pattern (designs.MOTIFS). They are chosen like
# any other palette, so saving, the live preview and custom colours work unchanged.
CULTURES = {
    "ndebele": ("Ndebele", "Painted geometry in bold colour outlined in black, and beaded isigolwani hoops",
                {"bg": "#FBFAF6", "surface": "#FFFFFF", "text": "#141414", "muted": "#555555", "accent": "#D62828", "accent2": "#1D3E8A"},
                ("#D62828", "#F2B705", "#1D5FB8", "#2E8B57", "#111111", "#FFFFFF")),
    "zulu": ("Zulu", "Beadwork diamonds and the isicholo, the wide hat of a married woman",
             {"bg": "#F8F5EE", "surface": "#FFFFFF", "text": "#1A1A1A", "muted": "#5E5A55", "accent": "#C1272D", "accent2": "#1B3F8B"},
             ("#C1272D", "#F2C200", "#1B3F8B", "#2F8F46", "#151515", "#FFFFFF")),
    "xhosa": ("Xhosa", "Umbhaco cloth edged in black braid, with white, turquoise and orange beads",
              {"bg": "#F7F1E6", "surface": "#FFFDF8", "text": "#161616", "muted": "#5D564D", "accent": "#B8541E", "accent2": "#111111"},
              ("#C8642A", "#EFE3C8", "#1FA6A0", "#B23A2E", "#111111", "#FFFFFF")),
    "pedi": ("Pedi", "Turquoise, bright pink and yellow, with ribbon trims",
             {"bg": "#FBF6F4", "surface": "#FFFFFF", "text": "#24132B", "muted": "#67586B", "accent": "#D6337A", "accent2": "#0E8A90"},
             ("#E0338A", "#F5B700", "#19A9B0", "#2D4FB0", "#1B2A4A", "#FFFFFF")),
    "venda": ("Venda", "Minwenda stripes of red, yellow, green and blue between bold black lines, and the ngoma drum",
              {"bg": "#FAF7F0", "surface": "#FFFFFF", "text": "#121212", "muted": "#5A5650", "accent": "#C8102E", "accent2": "#12284C"},
              ("#D7262E", "#F4C20D", "#2457C5", "#229A4C", "#141414", "#FFFFFF")),
    "tsonga": ("Tsonga", "The xibelani's gathered layers of pink, yellow, purple, blue and green",
               {"bg": "#FFF8F4", "surface": "#FFFFFF", "text": "#2A1428", "muted": "#6E5A6A", "accent": "#D63384", "accent2": "#6A2C91"},
               ("#E8478B", "#F7C531", "#1C6FC2", "#2FA36B", "#7A3FA0", "#FFFFFF")),
    "swati": ("Swati", "Red emahiya printed in white, with the shield and spears",
              {"bg": "#FBF7F2", "surface": "#FFFFFF", "text": "#1B1414", "muted": "#625656", "accent": "#B5232A", "accent2": "#1E1E1E"},
              ("#C0262D", "#F2C200", "#2B5CB0", "#2E7D46", "#141414", "#FFFFFF")),
}
DESIGNS["heritage"]["palettes"] = DESIGNS["heritage"]["palettes"] + [(k, v[0], v[2]) for k, v in CULTURES.items()]
DESIGNS["heritage"]["cultures"] = list(CULTURES)
DESIGNS["heritage"]["extra"] = "Great Vibes"


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


def extra_font(key: str) -> str:
    """The design's accent font (a script or hand-writing), or "" when it has none."""
    return design(key).get("extra", "")


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
