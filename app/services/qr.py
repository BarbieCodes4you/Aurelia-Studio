"""QR Code Model 2 encoder: byte mode, error correction level M, versions 1-10.

Enough for event URLs up to ~210 bytes. Produces a boolean matrix, an SVG or a PNG.
Follows ISO/IEC 18004 (structure after Project Nayuki's reference implementation).
"""
from __future__ import annotations

import struct
import zlib

# version: (ec codewords per block, [(block count, data codewords per block), ...])
BLOCKS_M = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}
ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
         9: [6, 26, 46], 10: [6, 28, 50]}
ECL_BITS_M = 0  # format-information bits for level M


class QRError(ValueError):
    pass


# --- Reed-Solomon over GF(256), polynomial 0x11D ----------------------------------------------
def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


# --- data codewords ---------------------------------------------------------------------------
def _capacity(version: int) -> int:
    _, groups = BLOCKS_M[version]
    return sum(c * d for c, d in groups)


def _choose_version(n: int) -> int:
    for v in range(1, 11):
        cc_bits = 8 if v < 10 else 16
        if 4 + cc_bits + 8 * n <= _capacity(v) * 8:
            return v
    raise QRError("Text is too long for a version 1-10 QR code.")


def _data_codewords(data: bytes, version: int) -> list[int]:
    bits: list[int] = []

    def put(val: int, n: int):
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)

    put(0b0100, 4)
    put(len(data), 8 if version < 10 else 16)
    for b in data:
        put(b, 8)
    cap = _capacity(version) * 8
    put(0, min(4, cap - len(bits)))
    put(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < cap:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    return [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]


def _interleave(data: list[int], version: int) -> list[int]:
    ec_len, groups = BLOCKS_M[version]
    divisor = _rs_divisor(ec_len)
    blocks, ecs = [], []
    k = 0
    for count, size in groups:
        for _ in range(count):
            blk = data[k:k + size]
            k += size
            blocks.append(blk)
            ecs.append(_rs_remainder(blk, divisor))
    out = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ec_len):
        for e in ecs:
            out.append(e[i])
    return out


# --- matrix -------------------------------------------------------------------------------
class _Grid:
    def __init__(self, version: int):
        self.version = version
        self.size = version * 4 + 17
        self.mod = [[False] * self.size for _ in range(self.size)]
        self.func = [[False] * self.size for _ in range(self.size)]

    def set_func(self, x: int, y: int, dark: bool) -> None:
        self.mod[y][x] = dark
        self.func[y][x] = True

    def draw_function_patterns(self) -> None:
        n = self.size
        for i in range(n):
            self.set_func(6, i, i % 2 == 0)
            self.set_func(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        dist = max(abs(dx), abs(dy))
                        self.set_func(x, y, dist not in (2, 4))
        pos = ALIGN[self.version]
        last = len(pos) - 1
        for i, a in enumerate(pos):
            for j, b in enumerate(pos):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_func(a + dx, b + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format(0)
        self.draw_version()

    def draw_format(self, mask: int) -> None:
        data = (ECL_BITS_M << 3) | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((data << 10) | rem) ^ 0x5412
        n = self.size

        def bit(i):
            return ((bits >> i) & 1) != 0

        for i in range(0, 6):
            self.set_func(8, i, bit(i))
        self.set_func(8, 7, bit(6))
        self.set_func(8, 8, bit(7))
        self.set_func(7, 8, bit(8))
        for i in range(9, 15):
            self.set_func(14 - i, 8, bit(i))
        for i in range(0, 8):
            self.set_func(n - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set_func(8, n - 15 + i, bit(i))
        self.set_func(8, n - 8, True)  # dark module

    def draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = (self.version << 12) | rem
        n = self.size
        for i in range(18):
            b = ((bits >> i) & 1) != 0
            a, c = n - 11 + i % 3, i // 3
            self.set_func(a, c, b)
            self.set_func(c, a, b)

    def draw_codewords(self, data: list[int]) -> None:
        n = self.size
        i = 0
        total = len(data) * 8
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = n - 1 - vert if upward else vert
                    if not self.func[y][x] and i < total:
                        self.mod[y][x] = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                        i += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        n = self.size
        for y in range(n):
            for x in range(n):
                if self.func[y][x]:
                    continue
                if mask == 0:
                    inv = (x + y) % 2 == 0
                elif mask == 1:
                    inv = y % 2 == 0
                elif mask == 2:
                    inv = x % 3 == 0
                elif mask == 3:
                    inv = (x + y) % 3 == 0
                elif mask == 4:
                    inv = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    inv = x * y % 2 + x * y % 3 == 0
                elif mask == 6:
                    inv = (x * y % 2 + x * y % 3) % 2 == 0
                else:
                    inv = ((x + y) % 2 + x * y % 3) % 2 == 0
                if inv:
                    self.mod[y][x] = not self.mod[y][x]


def _penalty(m: list[list[bool]]) -> int:
    n = len(m)
    score = 0
    # rule 1: runs of 5+ same colour in rows and columns
    for lines in (m, [list(col) for col in zip(*m)]):
        for line in lines:
            run, prev = 0, None
            for v in line:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + (run - 5)
                    run, prev = 1, v
            if run >= 5:
                score += 3 + (run - 5)
    # rule 2: 2x2 blocks
    for y in range(n - 1):
        for x in range(n - 1):
            c = m[y][x]
            if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                score += 3
    # rule 3: finder-like patterns 1:1:3:1:1 with 4 light on one side
    pats = ([True, False, True, True, True, False, True, False, False, False, False],
            [False, False, False, False, True, False, True, True, True, False, True])
    for lines in (m, [list(col) for col in zip(*m)]):
        for line in lines:
            for x in range(n - 10):
                seg = line[x:x + 11]
                if seg == pats[0] or seg == pats[1]:
                    score += 40
    # rule 4: dark proportion
    dark = sum(v for row in m for v in row)
    total = n * n
    k = abs(dark * 20 - total * 10) // total
    score += k * 10
    return score


def matrix(text: str) -> list[list[bool]]:
    data = text.encode("utf-8")
    version = _choose_version(len(data))
    codewords = _interleave(_data_codewords(data, version), version)
    best, best_score = None, None
    for mask in range(8):
        g = _Grid(version)
        g.draw_function_patterns()
        g.draw_codewords(codewords)
        g.apply_mask(mask)
        g.draw_format(mask)
        s = _penalty(g.mod)
        if best_score is None or s < best_score:
            best, best_score = g, s
    return best.mod


def svg(text: str, size: int = 320, dark: str = "#1B191A", light: str = "#FFFFFF", border: int = 4) -> str:
    m = matrix(text)
    n = len(m) + 2 * border
    path = []
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                path.append(f"M{x + border},{y + border}h1v1h-1z")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{size}" height="{size}" '
            f'shape-rendering="crispEdges" role="img" aria-label="QR code"><rect width="{n}" height="{n}" fill="{light}"/>'
            f'<path d="{"".join(path)}" fill="{dark}"/></svg>')


def png(text: str, scale: int = 10, border: int = 4) -> bytes:
    m = matrix(text)
    n = (len(m) + 2 * border) * scale
    rows = []
    for y in range(n):
        my = y // scale - border
        line = bytearray([0])  # filter type 0
        for x in range(n):
            mx = x // scale - border
            dark = 0 <= my < len(m) and 0 <= mx < len(m) and m[my][mx]
            line.append(0 if dark else 255)
        rows.append(bytes(line))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", n, n, 8, 0, 0, 0, 0)  # 8-bit greyscale
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def read_format(m: list[list[bool]]) -> tuple[int, int]:
    """Decode (ecl_bits, mask) from the top-left format copy. Used by tests."""
    bits = 0
    for i in range(0, 6):
        bits |= int(m[i][8]) << i
    bits |= int(m[7][8]) << 6
    bits |= int(m[8][8]) << 7
    bits |= int(m[8][7]) << 8
    for i in range(9, 15):
        bits |= int(m[8][14 - i]) << i
    data = (bits ^ 0x5412) >> 10
    return data >> 3, data & 7
