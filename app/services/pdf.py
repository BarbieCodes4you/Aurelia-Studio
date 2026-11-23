"""A small hand-written PDF 1.4 writer for reports.

Base-14 Helvetica fonts with WinAnsi encoding, A4 pages, wrapped text, key/value blocks and
tables that break across pages with their header repeated. No dependencies.

    doc = PDF("Guest list", "Sarah & John · 12 December 2026")
    doc.heading("Totals"); doc.kv([("Invited", "150")])
    doc.table(["Name", "Status"], [["Thandi", "Attending"]])
    data = doc.output()
"""
from __future__ import annotations

import zlib
from datetime import datetime
from typing import Optional

PAGE_W, PAGE_H = 595.28, 841.89
MARGIN = 48
CONTENT_W = PAGE_W - 2 * MARGIN
TOP = PAGE_H - MARGIN
BOTTOM = MARGIN + 28          # leave room for the footer

INK = (0.114, 0.114, 0.122)        # #1D1D1F
MUTED = (0.404, 0.404, 0.424)      # #67676C
GOLD = (0.702, 0.576, 0.380)       # accent rule, champagne thread #B39361
LINE = (0.882, 0.882, 0.902)       # #E1E1E6
FILL = (0.957, 0.957, 0.965)       # #F4F4F6

_REG = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + \
       [278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556,
        278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334,
        260, 334, 584]
_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + \
        [333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556,
         333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389,
         280, 389, 584]


def _encode(text: str) -> bytes:
    text = str(text if text is not None else "")
    text = text.replace("\r", "").replace("\t", "    ")
    return text.encode("cp1252", errors="replace")


def width(text: str, size: float, bold: bool = False) -> float:
    table = _BOLD if bold else _REG
    total = 0
    for b in _encode(text):
        total += table[b - 32] if 32 <= b <= 126 else 556
    return total * size / 1000


def _pdf_str(raw: bytes) -> bytes:
    out = bytearray(b"(")
    for b in raw:
        if b in (0x28, 0x29, 0x5C):
            out += b"\\" + bytes([b])
        elif b < 32 or b > 126:
            out += b"\\%03o" % b
        else:
            out.append(b)
    out += b")"
    return bytes(out)


def wrap(text: str, size: float, max_w: float, bold: bool = False) -> list[str]:
    lines: list[str] = []
    for para in str(text if text is not None else "").split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w) if cur else w
            if width(trial, size, bold) <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            # break very long words
            while width(w, size, bold) > max_w and len(w) > 1:
                cut = len(w)
                while cut > 1 and width(w[:cut], size, bold) > max_w:
                    cut -= 1
                lines.append(w[:cut])
                w = w[cut:]
            cur = w
        lines.append(cur)
    return lines or [""]


def _fmt(n: float) -> str:
    return ("%.2f" % n).rstrip("0").rstrip(".")


class PDF:
    def __init__(self, title: str, subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle
        self.pages: list[list[str]] = []
        self.y = TOP
        self._new_page(first=True)

    # --- low level --------------------------------------------------------------------------
    def _ops(self) -> list[str]:
        return self.pages[-1]

    def _text(self, x: float, y: float, text: str, size: float = 10, bold: bool = False, color=INK) -> None:
        raw = _pdf_str(_encode(text)).decode("latin-1")
        self._ops().append(f"BT /{'F2' if bold else 'F1'} {_fmt(size)} Tf {_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} rg "
                           f"{_fmt(x)} {_fmt(y)} Td {raw} Tj ET")

    def _line(self, x1, y1, x2, y2, color=LINE, w: float = 0.6) -> None:
        self._ops().append(f"{_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} RG {_fmt(w)} w "
                           f"{_fmt(x1)} {_fmt(y1)} m {_fmt(x2)} {_fmt(y2)} l S")

    def _rect(self, x, y, w, h, color=FILL) -> None:
        self._ops().append(f"{_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} rg {_fmt(x)} {_fmt(y)} {_fmt(w)} {_fmt(h)} re f")

    def _new_page(self, first: bool = False) -> None:
        self.pages.append([])
        self.y = TOP
        if first:
            self._text(MARGIN, self.y - 20, self.title, 20, bold=True)
            self.y -= 30
            if self.subtitle:
                self._text(MARGIN, self.y - 10, self.subtitle, 10, color=MUTED)
                self.y -= 16
            self.y -= 6
            self._line(MARGIN, self.y, MARGIN + 56, self.y, GOLD, 1.6)
            self.y -= 22
        else:
            self._text(MARGIN, self.y - 9, self.title, 9, bold=True, color=MUTED)
            self.y -= 16
            self._line(MARGIN, self.y, PAGE_W - MARGIN, self.y, LINE, 0.5)
            self.y -= 16

    def _ensure(self, h: float) -> bool:
        """Start a new page if `h` points don't fit. Returns True when a page was added."""
        if self.y - h < BOTTOM:
            self._new_page()
            return True
        return False

    # --- public API ---------------------------------------------------------------------------
    def heading(self, text: str) -> None:
        self._ensure(40)
        self.y -= 6
        self._text(MARGIN, self.y - 12, text, 13, bold=True)
        self.y -= 24

    def text(self, text: str, size: float = 10, muted: bool = False) -> None:
        lead = size * 1.4
        for line in wrap(text, size, CONTENT_W):
            self._ensure(lead)
            self._text(MARGIN, self.y - size, line, size, color=MUTED if muted else INK)
            self.y -= lead
        self.y -= 4

    def kv(self, pairs: list) -> None:
        key_w = CONTENT_W * 0.36
        for k, v in pairs:
            vlines = wrap(str(v), 10, CONTENT_W - key_w - 8)
            h = 14 * len(vlines) + 6
            self._ensure(h)
            self._text(MARGIN, self.y - 10, str(k), 10, color=MUTED)
            for n, line in enumerate(vlines):
                self._text(MARGIN + key_w, self.y - 10 - n * 14, line, 10, bold=n == 0 and len(vlines) == 1)
            self.y -= h
            self._line(MARGIN, self.y + 2, PAGE_W - MARGIN, self.y + 2)
        self.y -= 8

    def table(self, headers: list, rows: list, widths: Optional[list] = None) -> None:
        n = len(headers)
        fr = widths or [1] * n
        total = float(sum(fr))
        cols = [CONTENT_W * f / total for f in fr]
        size, lead, pad = 8.5, 11, 5

        def draw_header():
            hl = [wrap(h, size, c - 2 * pad, bold=True) for h, c in zip(headers, cols)]
            h = max(len(x) for x in hl) * lead + 2 * pad
            self._ensure(h + lead + 2 * pad)
            self._rect(MARGIN, self.y - h, CONTENT_W, h)
            x = MARGIN
            for lines, c in zip(hl, cols):
                for k, line in enumerate(lines):
                    self._text(x + pad, self.y - pad - size - k * lead + 1, line, size, bold=True)
                x += c
            self.y -= h

        draw_header()
        if not rows:
            self._ensure(lead + 2 * pad)
            self._text(MARGIN + pad, self.y - pad - size, "Nothing to show yet.", size, color=MUTED)
            self.y -= lead + 2 * pad
        for row in rows:
            cells = [wrap("" if v is None else str(v), size, c - 2 * pad) for v, c in zip(list(row) + [""] * n, cols)]
            h = max(len(x) for x in cells) * lead + 2 * pad
            if self._ensure(h):
                draw_header()
            x = MARGIN
            for lines, c in zip(cells, cols):
                for k, line in enumerate(lines):
                    self._text(x + pad, self.y - pad - size - k * lead + 1, line, size)
                x += c
            self.y -= h
            self._line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= 14

    def spacer(self, h: float = 8) -> None:
        self.y -= h
        if self.y < BOTTOM:
            self._new_page()

    def page_break(self) -> None:
        self._new_page()

    def output(self) -> bytes:
        total = len(self.pages)
        stamp = datetime.now().strftime("%d %b %Y, %H:%M")
        objs: list[bytes] = []
        # 1 catalog, 2 pages, 3 F1, 4 F2, 5 info, then (page, content) pairs
        page_ids = [6 + 2 * k for k in range(total)]
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        kids = " ".join(f"{p} 0 R" for p in page_ids)
        objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {total} >>".encode())
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        objs.append(b"<< /Producer (Aurelia Studio reports) /Title " + _pdf_str(_encode(self.title)) + b" >>")
        for k, ops in enumerate(self.pages):
            self.pages[k] = ops  # keep list
            footer = [
                f"{_fmt(LINE[0])} {_fmt(LINE[1])} {_fmt(LINE[2])} RG 0.5 w {MARGIN} {MARGIN + 14} m {_fmt(PAGE_W - MARGIN)} {MARGIN + 14} l S",
                f"BT /F1 8 Tf {_fmt(MUTED[0])} {_fmt(MUTED[1])} {_fmt(MUTED[2])} rg {MARGIN} {MARGIN} Td "
                + _pdf_str(_encode(f"Generated {stamp}")).decode("latin-1") + " Tj ET",
            ]
            label = f"Page {k + 1} of {total}"
            footer.append(f"BT /F1 8 Tf {_fmt(MUTED[0])} {_fmt(MUTED[1])} {_fmt(MUTED[2])} rg "
                          f"{_fmt(PAGE_W - MARGIN - width(label, 8))} {MARGIN} Td "
                          + _pdf_str(_encode(label)).decode("latin-1") + " Tj ET")
            stream = zlib.compress("\n".join(ops + footer).encode("latin-1"))
            objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_fmt(PAGE_W)} {_fmt(PAGE_H)}] "
                        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {page_ids[k] + 1} 0 R >>".encode())
            objs.append(f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode() + stream + b"\nendstream")
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for n, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)
