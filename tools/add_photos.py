#!/usr/bin/env python3
"""Add photos for the home page tiles and the template sample galleries.

    python3 tools/add_photos.py PHOTOS_FOLDER_OR_ZIP

Put each photo in a sub-folder named after where it goes (or start its file name with that word):
  weddings/  traditional/  baby/  parties/  other/
The first photo in each folder (by name) becomes that occasion's main photo (home page tile and the
big picture in the template samples); all of them go into the sample gallery.
A photo named after a template (atelier, folio, bloom, heritage, champagne, linea, confetti, pulse,
aurora, laureate, cradle), e.g. heritage.jpg, becomes that template's own main photo. Photos are resized to
1600px on the long side and saved as JPEG, so they stay small. Needs Pillow (pip install Pillow);
the website itself doesn't.
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / "static" / "img" / "stock"
SLOTS = ("weddings", "traditional", "baby", "parties", "other")
TEMPLATES = ("festive", "matcha", "heritage", "nguni", "terracotta", "ribbon", "weave", "teddy", "reveal", "glitter",
             "cheers", "memorial", "atelier", "folio", "bloom", "champagne", "linea", "confetti", "pulse", "aurora", "laureate", "cradle")


def template_of(path: str) -> str:
    stem = Path(path).stem.lower()
    return next((t for t in TEMPLATES if stem == t or stem.startswith(t + "-") or stem.startswith(t + "_")), "")
EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic")


def slot_of(path: str) -> str:
    parts = [p.lower() for p in Path(path).parts]
    for p in parts[::-1]:
        for s in SLOTS:
            if p == s or p.startswith(s):
                return s
    return ""


def items(src: str):
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(EXT) and not n.startswith("__MACOSX"):
                    yield n, z.read(n)
    else:
        for dirpath, _, files in os.walk(src):
            for f in sorted(files):
                if f.lower().endswith(EXT):
                    full = os.path.join(dirpath, f)
                    yield os.path.relpath(full, src), open(full, "rb").read()


def main(src: str) -> None:
    counts: dict = {}
    for name, data in items(src):
        tpl = template_of(name)
        if tpl:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            img.thumbnail((1600, 1600))
            STOCK.mkdir(parents=True, exist_ok=True)
            img.save(STOCK / f"tpl-{tpl}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
            counts[tpl] = counts.get(tpl, 0) + 1
            print(f"{tpl}: {name} -> tpl-{tpl}.jpg (the {tpl.capitalize()} template's main photo)")
            continue
        slot = slot_of(name)
        if not slot:
            print(f"skipped (put it in a weddings/traditional/baby/parties/other folder): {name}")
            continue
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        img.thumbnail((1600, 1600))
        n = counts.get(slot, 0) + 1
        counts[slot] = n
        folder = STOCK / "gallery" / slot
        folder.mkdir(parents=True, exist_ok=True)
        img.save(folder / f"{n:02d}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
        if n == 1:
            img.save(STOCK / f"{slot}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
        print(f"{slot}: {name} -> gallery/{slot}/{n:02d}.jpg")
    print("Done:", ", ".join(f"{k} {v}" for k, v in counts.items()) or "no photos found")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
