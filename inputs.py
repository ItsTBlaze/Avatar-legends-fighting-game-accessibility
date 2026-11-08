"""Reads move inputs on the command list: arrow icons, A/B/C/Flow buttons and
the small words between them ("or", "then", "(Hold)")."""
import math
import cv2
import numpy as np

# Directions as named for a fighter facing right (the command list's view).
DIRS = ["forward", "down-forward", "down", "down-back", "back", "up-back", "up", "up-forward"]

MOTIONS = {
    ("down", "down-forward", "forward"): "quarter circle forward",
    ("down", "down-back", "back"): "quarter circle back",
    ("forward", "down", "down-forward"): "dragon punch",
    ("back", "down-back", "down", "down-forward", "forward"): "half circle forward",
    ("forward", "down-forward", "down", "down-back", "back"): "half circle back",
}


def _masks(part):
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    masks = {
        # Slate arrow fill: blue-grey, muted.
        "arrow": (h >= 95) & (h <= 125) & (s >= 45) & (s <= 150) & (v >= 70) & (v <= 165),
        "A": (h >= 98) & (h <= 120) & (s >= 150) & (v >= 140),
        "B": (h >= 15) & (h <= 32) & (s >= 120) & (v >= 150),
        "C": ((h <= 10) | (h >= 170)) & (s >= 140) & (v >= 140),
        "Flow": (h >= 78) & (h <= 98) & (s >= 70) & (v >= 90),
    }
    return {k: m.astype(np.uint8) for k, m in masks.items()}


def _arrow_direction(comp):
    """Direction an arrow points.

    Along the axis the arrow lies on, one end (the head) is much wider than
    the other (the shaft). Try the four axes and keep the most lopsided one.
    """
    ys, xs = np.nonzero(comp)
    if len(xs) < 20:
        return None
    xs = xs - xs.mean()
    ys = ys - ys.mean()
    best = None
    for k in range(4):
        th = math.radians(45 * k)
        u = xs * math.cos(th) + ys * math.sin(th)
        v = -xs * math.sin(th) + ys * math.cos(th)
        L = u.max() - u.min()
        if L <= 0:
            continue
        front = v[u > u.max() - 0.35 * L]
        back = v[u < u.min() + 0.35 * L]
        if len(front) < 3 or len(back) < 3:
            continue
        fw = front.max() - front.min()
        bw = back.max() - back.min()
        asym = (fw - bw) / float(fw + bw + 1e-6)
        if best is None or abs(asym) > abs(best[0]):
            best = (asym, k)
    if best is None or abs(best[0]) < 0.12:
        return None
    asym, k = best
    ang = 45 * k + (0 if asym > 0 else 180)
    return DIRS[(ang // 45) % 8]


def find_icons(part):
    """Icons in a strip, as (x1, x2, token) sorted left to right."""
    found = []
    masks = _masks(part)
    h = part.shape[0]
    for token, m in masks.items():
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
        for i in range(1, n):
            x, y, w, hh, area = (int(v) for v in stats[i])
            if not (12 <= hh <= 1.2 * h and 0.5 <= w / float(hh) <= 2.0 and area >= 60):
                continue
            if token == "arrow":
                if area < 0.25 * w * hh:
                    continue
                name = _arrow_direction(lab[y:y + hh, x:x + w] == i)
                if not name:
                    continue
            else:
                if area < 0.3 * w * hh:
                    continue
                name = token
            found.append((x, x + w, y, y + hh, name))
    found.sort()
    # Drop overlaps (a button can also catch a little arrow colour).
    out = []
    for f in found:
        if out and f[0] < out[-1][1] - 4:
            continue
        out.append(f)
    return out


DIRECTIONS = set(DIRS)
BUTTONS = ("A", "B", "C", "Flow")


def describe(tokens):
    """['down','down-forward','forward','A','B','C'] -> 'quarter circle forward, A plus B plus C'.

    Tokens can also be words that sat between the icons ("or", "then", "(Hold)").
    """
    parts, i = [], 0
    while i < len(tokens):
        hit = None
        for seq, name in MOTIONS.items():
            if tuple(tokens[i:i + len(seq)]) == seq:
                hit = (seq, name)
                break
        if hit:
            parts.append(hit[1])
            i += len(hit[0])
            continue
        t = tokens[i]
        if t in BUTTONS:
            group = [t]
            while i + 1 < len(tokens) and tokens[i + 1] in BUTTONS:
                i += 1
                group.append(tokens[i])
            parts.append(" plus ".join(group))
        else:
            parts.append(t)
        i += 1
    text = ", ".join(parts)
    for word in ("or", "then"):
        text = text.replace(", %s, " % word, " %s " % word)
    return text.replace(", (", " (")


def read_inputs(strip, ocr):
    """Icons and words in an input strip, as one spoken phrase ('' if no icons)."""
    icons = find_icons(strip)
    if not icons:
        return ""
    # Paint the icons out so OCR only sees the words between them.
    clean = strip.copy()
    for x1, x2, y1, y2, _ in icons:
        clean[:, max(0, x1 - 8):x2 + 8] = 245
    g = cv2.cvtColor(clean, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    g = cv2.copyMakeBorder(g, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    pieces = [((x1 + x2) / 2.0, name) for x1, x2, _, _, name in icons]
    for line in ocr.lines(g, scale=2):
        words = "".join(c for c in line.text if c.isalnum() or c in " ()'-").strip()
        kept = [w for w in words.split()
                if w.lower() in ("or", "then", "any") or w.isdigit() and len(w) == 1
                or sum(c.isalpha() for c in w) >= 4 or (w.startswith("(") or w.endswith(")"))]
        if kept and any(sum(c.isalpha() for c in w) >= 2 for w in kept):
            pieces.append((line.x - 10 + line.w / 2.0, " ".join(kept)))
    pieces.sort()
    return describe([p[1] for p in pieces])
