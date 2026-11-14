"""Things to hear during a fight: Flow gauge and energy cues, combo results
and health.

All positions are in the 1920x1080 reference frame. Player 2's gauges mirror
Player 1's around the middle of the screen.
"""
import base64
import re
import zlib
import cv2
import numpy as np
import detector as d
import textclean as tc

# Flow gauge: the cyan bar under each health bar.
FLOW_ROWS = (110, 121)
FLOW_X = {0: (535, 861), 1: (1059, 1385)}
# Energy: 7 circles under the Flow gauge, lighting up from the timer outwards.
PIP_Y = 146
PIP_X = {0: [544 + i * 54 for i in range(7)], 1: [1920 - 544 - i * 54 for i in range(7)]}
# Combo counter (big gold number, "HITS", damage under it) and Element Surge
# banner. Player 1's appear on the left; Player 2's mirror them on the right.
COMBO_DIGITS = {0: (40, 215, 250, 350), 1: (1560, 215, 1760, 350)}
COMBO_DAMAGE = {0: (240, 310, 345, 343), 1: (1760, 310, 1890, 343)}
SURGE = {0: (25, 478, 430, 548), 1: (1490, 478, 1895, 548)}


def _flow_columns(img, side):
    x1, x2 = FLOW_X[side]
    hsv = cv2.cvtColor(img[FLOW_ROWS[0]:FLOW_ROWS[1], x1:x2], cv2.COLOR_BGR2HSV).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    fill = ((h >= 80) & (h <= 100) & (s >= 35) & (v >= 170)) | ((s <= 25) & (v >= 200))
    return fill.mean(axis=0) > 0.5


def flow_fraction(img, side):
    """0.0 (empty) to 1.0 (full).

    The gauge drains from its outer end (left for Player 1, right for
    Player 2), so only an empty stretch starting at that end counts. A
    fighter passing in front of the middle of the bar doesn't fool it.
    """
    cols = _flow_columns(img, side)
    if side == 1:
        cols = cols[::-1]
    filled = np.nonzero(cols)[0]
    if len(filled) == 0:
        return 0.0
    start = filled[0]                    # first filled column from the outer end
    # The bar's slanted ends leave ~12 empty columns even when full.
    empty = max(0, start - 12)
    return max(0.0, 1.0 - empty / float(len(cols) - 12))


def energy_level(img, side):
    """Lit circles counted from the timer end; None if the pattern makes no
    sense (something is passing in front of the meter)."""
    lit = []
    for x in PIP_X[side][::-1]:                       # timer end first
        p = img[PIP_Y - 5:PIP_Y + 6, x - 5:x + 6]
        hsv = cv2.cvtColor(p, cv2.COLOR_BGR2HSV)
        lit.append(((hsv[..., 1] >= 110) & (hsv[..., 2] >= 150)).mean() > 0.5)
    n = 0
    while n < 7 and lit[n]:
        n += 1
    if any(lit[n:]):
        return None                                    # gaps: not a real reading
    return n


# Health bars: measured on a band below the training-mode numbers. They drain
# from the outer end. P1 is orange-red and P2 blue, and a bar turns yellow when
# it gets low; the white stretch after a hit is health already lost.
HEALTH_ROWS = (86, 91)
HEALTH_X = {0: (310, 850), 1: (1070, 1610)}


def _health_columns(img, side):
    x1, x2 = HEALTH_X[side]
    hsv = cv2.cvtColor(img[HEALTH_ROWS[0]:HEALTH_ROWS[1], x1:x2], cv2.COLOR_BGR2HSV).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    yellow = (h >= 18) & (h <= 36) & (s >= 100) & (v >= 150)
    if side == 0:
        col = (((h <= 17) | (h >= 165)) & (s >= 60) & (v >= 90)) | yellow
    else:
        col = ((h >= 95) & (h <= 135) & (s >= 40) & (v >= 90)) | yellow
    cols = col.mean(axis=0) > 0.5
    return cols[::-1] if side == 0 else cols                     # inner end first


def health_fraction(img, side):
    """Measured two ways and the larger kept, so a fighter jumping in front of
    one end of the bar doesn't look like lost health: the colored run from the
    inner end, and where the empty stretch from the outer end stops."""
    cols = _health_columns(img, side)
    n, gap = 0, 0
    for i, c in enumerate(cols):
        if c:
            n, gap = i + 1, 0
        else:
            gap += 1
            if gap > 20:
                break
    edge, run = 0, 0
    for i in range(len(cols) - 1, -1, -1):
        run = run + 1 if cols[i] else 0
        if run >= 8:
            edge = i + run
            break
    return max(n, edge) / float(len(cols))


def gold_mask(part):
    """The gold brush-stroke combo number, with the brush gaps filled in."""
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    yellow = cv2.cvtColor(part, cv2.COLOR_BGR2LAB)[..., 2].astype(int)
    m = ((h >= 12) & (h <= 38) & (s >= 45) & (v >= 120) & (yellow >= 150)).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def _mode(values):
    values = [v for v in values if v]
    return max(set(values), key=values.count) if values else None


def _best_damage(values):
    """The most common damage reading, unless a longer one starts the same way
    (text recognition sometimes drops the last digit: "11" for "117")."""
    best = _mode(values)
    if best:
        longer = [v for v in values if v and len(v) > len(best) and v.startswith(best)]
        if longer:
            best = _mode(longer)
    return best


# Shapes of the gold combo numbers seen so far (24x32, from a training
# recording). Other numbers fall back to text recognition.
_DIGIT_DATA = {2: 'eJwlyrEJwDAMRNEPKVxqhKyQDbKaR8soHkGQJoXQWSjwqvuHORZYNnH8kpG9f60+C3uwiWb1iqPj6df9hpRStKVEXi8CHDYEFyvE', 3: 'eJw9ysENgCAQRNFPSORoCdAJpWFplEIJHPdAGNdonLzTzxSomk3bZe2ghYw8qYN2oe4lvUwH4rMJi+iMODn//5OTEQax47sBLEQp5w==', 4: 'eJxVwjEOQEAQQNE/UdDRKddBJONISoUYR3CkvYELKBxBSbLZkei8PCqwFgu44iZ5kZSLlMq7r5+5PsdwDhpXPdCIZjxjju0gHXIh2/f+ZfqO0Lzl9CDp', 5: 'eJwdyrENwCAMRNGPXKQkE8SbJKPBaIzCCJQUlh1Aerri7uAlOWE5hkbXaOpoR9vJZZdrssP5HHGSbTKRwTX2rzSJmgM1ykQrD9zwAzvoJ7I='}
DIGITS = {k: np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:24 * 32]
          .reshape(32, 24).astype(bool) for k, v in _DIGIT_DATA.items()}


def _digit_shaped(mask):
    """The combo number is a tall brush stroke about 85 pixels high; gold
    scenery behind the fighters isn't shaped like that."""
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return False
    x, y, w, h, _ = stats[1 + int(np.argmax(stats[1:, 4]))]
    return 60 <= h <= 115 and w <= 2.6 * h


def match_digit(mask):
    """The combo number from its shape, or None when unsure."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return None
    i = 1 + int(np.argmax(stats[1:, 4]))
    x, y, w, h, _ = stats[i]
    if w > 1.3 * h:
        return None                     # two digits: leave it to text recognition
    shape = cv2.resize(mask[y:y + h, x:x + w] * 255, (24, 32), interpolation=cv2.INTER_AREA) > 127
    scores = sorted(((shape & t).sum() / float(max(1, (shape | t).sum())), k) for k, t in DIGITS.items())
    best, second = scores[-1], scores[-2]
    if best[0] >= 0.55 and best[0] - second[0] >= 0.12:
        return best[1]
    return None


class Settle:
    """A value that only changes after being read the same way a few times."""

    def __init__(self, frames=3):
        self.frames, self.value, self.cand, self.count = frames, None, None, 0

    def feed(self, v):
        if v == self.cand:
            self.count += 1
        else:
            self.cand, self.count = v, 1
        if self.count >= self.frames and v != self.value:
            old, self.value = self.value, v
            return True, old
        return False, self.value


class FightCues:
    def __init__(self, ocr, player=None, settings=None):
        self.ocr = ocr
        self.player = player
        self.settings = settings or {}
        self.reset()

    # Settings (from the accessibility menu), with defaults when there are none.
    def opt(self, key, default):
        try:
            return self.settings[key]
        except (KeyError, TypeError):
            return default

    @property
    def me(self):
        return self.opt("my_side", 1) - 1

    def reset(self):
        self.flow = {s: Settle(5) for s in (0, 1)}
        self.flow_low = {0: False, 1: False}
        self.low_frames = {0: 0, 1: 0}
        self.energy = {s: Settle(3) for s in (0, 1)}
        self.health = {s: Settle(4) for s in (0, 1)}
        # Kept through pauses; a full bar (a new round) clears them.
        self.health_marks = getattr(self, "health_marks", None) or {0: set(), 1: set()}
        self.combo = {0: None, 1: None}
        self.combo_gone = {0: 0, 1: 0}
        self.combo_last = {0: (-99, None, None), 1: (-99, None, None)}
        self.combo_start = {0: 0, 1: 0}
        self.surge_cool = {0: 0, 1: 0}
        self.last_flow = {0: None, 1: None}
        self.last_energy = {0: None, 1: None}
        self.last_health = {0: None, 1: None}
        self.tick = 0

    def _play(self, name, side, always_opponent=False):
        if not self.player:
            return
        mine = side == self.me
        if not mine and not (always_opponent or self.opt("opponent_sounds", False)):
            return
        self.player.play("%s_%s" % (name, "p1" if mine else "p2"))

    def _who(self, side):
        return "" if side == self.me else "Opponent "

    # ---- per frame ----------------------------------------------------
    def update(self, img):
        """Play cues and return things to say for this fight frame."""
        if not self.opt("fight_sounds", True):
            return []
        self.tick += 1
        out = []
        for side in (0, 1):
            self._gauges(img, side)
            self._health(img, side)
            if self.opt("combos", True):
                out += self._combo(img, side)
        return out

    def _gauges(self, img, side):
        f = flow_fraction(img, side)
        self.last_flow[side] = f
        state = "full" if f >= 0.95 else ("low" if f <= 0.9 else "mid")
        changed, _ = self.flow[side].feed(state)
        # A real Flow drain lasts seconds while it refills; a fighter passing
        # in front of the gauge doesn't, so "low" must hold for ~1.5 seconds.
        self.low_frames[side] = self.low_frames[side] + 1 if state == "low" else 0
        if self.low_frames[side] >= 12:
            self.flow_low[side] = True
        if changed and state == "full" and self.flow_low[side]:
            self.flow_low[side] = False
            if self.opt("flow_sound", True):
                self._play("flow_full", side)
        e = energy_level(img, side)
        if e is not None:
            changed, old = self.energy[side].feed(e)
            if changed:
                self.last_energy[side] = e
                if old is not None and e > old and self.opt("energy_sound", True):
                    self._play("energy_%d" % e, side)

    def _health(self, img, side):
        """An alert when a fighter's health drops to 30 percent."""
        f = health_fraction(img, side)
        self.last_health[side] = f
        # Back to full for two seconds: a new round (or a training refill),
        # so the alert is ready again. A flash over the bar is shorter.
        full = self.__dict__.setdefault("full_frames", {0: 0, 1: 0})
        full[side] = full[side] + 1 if f >= 0.95 else 0
        if full[side] >= 25:
            self.health_marks[side].clear()
        changed, _ = self.health[side].feed(f <= 0.30)
        if not changed or not self.health[side].value or 30 in self.health_marks[side]:
            return
        self.health_marks[side].add(30)
        mode = self.opt("health_sound", "both")
        if mode == "both" or (mode == "mine" and side == self.me):
            self._play("health_low", side, always_opponent=True)

    def _combo(self, img, side):
        part = d.crop(img, COMBO_DIGITS[side])
        gold = gold_mask(part)
        if gold.sum() >= 600 and _digit_shaped(gold):
            if self.combo[side] is None:
                self.combo_start[side] = self.tick
                # A new popup: forget the last one's numbers so they're read fresh.
                cache = self.__dict__.setdefault("_ocr_cache", {})
                cache.pop(("hits", side), None)
                cache.pop(("dmg", side), None)
            self.combo_gone[side] = 0
            if True:  # every frame: unchanged numbers come from the cache
                known = match_digit(gold)
                hits = str(known) if known else self._cached(
                    ("hits", side), gold, lambda: self._read_number(255 - gold * 255))
                dmg = self._cached(("dmg", side), self._damage_sig(img, side),
                                   lambda: self._read_damage(img, side))
                if hits and int(hits) >= 2:
                    readings = self.combo[side] or []
                    readings.append((int(hits), dmg, bool(known)))
                    self.combo[side] = readings[-40:]
            return []
        # Popup gone for a moment: the combo is over. The counter stayed up
        # for a second or so after the last hit, so the most common reading
        # among the last few is the final count.
        # Announced as soon as the counter goes away; the short flash that
        # sometimes follows shows the same count and is skipped below.
        self.combo_gone[side] += 1
        if self.combo[side] and self.combo_gone[side] >= 3:
            readings, self.combo[side] = self.combo[side], None
            if len(readings) < 2:
                return []               # a flicker, not a combo
            # The final count stays up longest: take the highest count read
            # at least twice, and the damage read alongside it.
            # Shape matches are more trustworthy than text recognition, which
            # can turn a half-covered 2 into a 4: use them when there are any.
            # Only counts the shape matching has confirmed at least once.
            confirmed = {h for h, _, k in readings if k}
            shape_reads = sum(1 for _, _, k in readings if k)
            if confirmed:
                readings = [r for r in readings if r[0] in confirmed]
            readings = [(h, x) for h, x, _ in readings]
            counts = [h for h, _ in readings]
            repeated = [h for h in set(counts) if counts.count(h) >= 2]
            hits = max(repeated) if repeated else _mode(counts)
            dmg = _best_damage([x for h, x in readings if h == hits]) or _best_damage([x for _, x in readings])
            if dmg == "0":
                dmg = None
            if not dmg and shape_reads < 2:
                return []               # neither a damage number nor a clear combo digit: scenery
            last_tick, last_hits, last_dmg = self.combo_last[side]
            self.combo_last[side] = (self.tick, hits, dmg)
            same_dmg = bool(dmg and last_dmg and (dmg.startswith(last_dmg) or last_dmg.startswith(dmg)))
            if self.combo_start[side] - last_tick <= 6 and (same_dmg or hits == last_hits or not dmg):
                # The same numbers back within half a second: the same popup,
                # hidden for an instant by a fighter, an assist or its own
                # closing flash.
                return []
            text = "%s%d hits" % (self._who(side), hits)
            if dmg:
                text += ", %s damage" % dmg
            return [(text, False)]
        return []

    def _cached(self, key, mask, read):
        """Text recognition is the slow part: only read again when the
        number's shape has changed since the last reading."""
        sig = (cv2.resize(mask.astype(np.uint8) * 255, (24, 12)) // 86).tobytes()
        cache = self.__dict__.setdefault("_ocr_cache", {})
        old_sig, value, when = cache.get(key, (None, None, -99))
        if old_sig != sig and self.tick - when >= 2:     # at most every other frame
            value = read()
            cache[key] = (sig, value, self.tick)
        return value

    def _damage_sig(self, img, side):
        hsv = cv2.cvtColor(d.crop(img, COMBO_DAMAGE[side]), cv2.COLOR_BGR2HSV)
        return (hsv[..., 2] >= 200) & (hsv[..., 1] <= 60)

    def _read_damage(self, img, side):
        """The small white damage number under the hit count."""
        part = d.crop(img, COMBO_DAMAGE[side])
        for prep in (lambda p: d.bright_text(p, v=200, s=60, scale=3),
                     lambda p: d.dark_text(255 - p, scale=3)):
            try:
                n = self._read_number(prep(part), white=True, scale=3)
            except Exception:
                n = None
            if n and int(n) >= 10:          # a combo always does at least 10 damage
                return n
        return None

    def _read_number(self, mask, white=False, scale=None):
        if white:
            img = mask
        else:
            img = cv2.copyMakeBorder(cv2.resize(mask, None, fx=1.0, fy=1.0), 20, 20, 20, 20,
                                     cv2.BORDER_CONSTANT, value=255)
        text = self.ocr.text(img, scale=scale or (2 if white else 1))
        text = text.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1")
        m = re.search(r"\d{1,3}", text)
        return m.group(0) if m else None

    def _surge(self, img, side):
        if self.surge_cool[side] > 0:
            self.surge_cool[side] -= 1
            return []
        part = d.crop(img, SURGE[side])
        mask = d.text_on_dark(part)
        if mask.sum() < 255 * 400:
            return []
        text = self.ocr.text(cv2.copyMakeBorder(255 - mask, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255))
        if re.search(r"(?i)s\s*u\s*r\s*g", text) or re.search(r"(?i)element", text):
            self.surge_cool[side] = 25                  # about 3 seconds
            return [("%sElement Surge" % self._who(side), True)]
        return []

    # ---- on demand ----------------------------------------------------
    def status(self, img=None):
        """'Flow 100 percent, 3 energy. Opponent: Flow 80 percent, 1 energy.'"""
        parts = []
        for side in (self.me, 1 - self.me):
            f, e = self.last_flow[side], self.last_energy[side]
            if img is not None:
                f = flow_fraction(img, side)
                e2 = energy_level(img, side)
                e = e2 if e2 is not None else e
            bits = []
            if f is not None:
                bits.append("Flow %d percent" % min(100, round(f * 100)))
            if e is not None:
                bits.append("%d energy" % e)
            hl = health_fraction(img, side) if img is not None else self.last_health[side]
            if hl is not None:
                bits.insert(0, "Health %d percent" % round(hl * 100))
            if bits:
                parts.append(("" if side == self.me else "Opponent: ") + ", ".join(bits))
        return ". ".join(parts) or "No gauges found"
