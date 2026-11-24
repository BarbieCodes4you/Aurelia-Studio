"""Stock photos for the marketing pages and the template samples.

Drop a photo into static/img/stock/ under one of these names and it is used automatically; until then
the line drawings and colour washes stay. Sample gallery photos go in static/img/stock/gallery/<slot>/.
`python3 tools/add_photos.py PHOTOS_FOLDER_OR_ZIP` resizes and files them for you. Keep each photo under about 250 KB (1600px wide, JPEG).
Record where each photo came from and its licence in CREDITS below (Unsplash and Pexels photos are free
for commercial use without attribution, but keeping the source makes them easy to check or replace).
"""
from __future__ import annotations

from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "static" / "img" / "stock"

SLOTS = {
    "weddings": "Couple at a South African wedding (home page tile, wedding template samples)",
    "traditional": "Traditional or lobola celebration (traditional template samples)",
    "baby": "Baby shower or new parents (home page tile, baby template samples)",
    "parties": "Birthday or dinner party (home page tile, party template samples)",
    "other": "Graduation, family gathering or corporate event (home page tile, other samples)",
}

# Each template can also have its own main photo, static/img/stock/tpl-<template>.jpg (e.g. tpl-heritage.jpg),
# shown in that template's samples instead of the occasion photo.
TEMPLATES = ("nguni", "terracotta", "ribbon", "weave", "glitter", "matcha", "festive", "cheers", "heritage",
             "atelier", "folio", "bloom", "champagne", "linea", "confetti", "pulse", "aurora", "laureate", "cradle")

CREDITS: dict = {}   # slot -> "Photographer, source link, licence" (or the AI tool used)


def url(slot: str) -> str:
    """Web path of the photo for `slot`, or "" when none has been added yet."""
    for ext in ("jpg", "jpeg", "webp", "png"):
        if (DIR / f"{slot}.{ext}").is_file():
            return f"/static/img/stock/{slot}.{ext}"
    return ""


def gallery(slot: str) -> list[str]:
    """Web paths of the sample gallery photos for `slot` (static/img/stock/gallery/<slot>/), sorted by name."""
    folder = DIR / "gallery" / slot
    if not folder.is_dir():
        return []
    return [f"/static/img/stock/gallery/{slot}/{f.name}" for f in sorted(folder.iterdir())
            if f.suffix.lower() in (".jpg", ".jpeg", ".webp", ".png")]
