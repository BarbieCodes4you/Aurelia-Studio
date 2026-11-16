"""Stock photos for the marketing pages and the template samples.

Drop a photo into static/img/stock/ under one of these names and it is used automatically; until then
the line drawings and colour washes stay. Keep each photo under about 250 KB (1600px wide, JPEG).
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

CREDITS: dict = {}   # slot -> "Photographer, source link, licence"


def url(slot: str) -> str:
    """Web path of the photo for `slot`, or "" when none has been added yet."""
    for ext in ("jpg", "jpeg", "webp", "png"):
        if (DIR / f"{slot}.{ext}").is_file():
            return f"/static/img/stock/{slot}.{ext}"
    return ""
