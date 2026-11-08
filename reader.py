"""Turns screen frames into things to say. No capture or speech in here, so it
can be tested on saved screenshots."""
import difflib
import re
import logging
import cv2
import detector as d
import inputs
import textclean as tc

log = logging.getLogger("reader")
TITLE_MIN_HEIGHT = 38   # in 1920x1080 pixels; menu items are ~30, titles 45+

# Names as the game prints them on character select. OCR output is matched
# against this list, so a misread like "Ko Rra" still comes out as Korra.
ROSTER = ["Nightmare Korra", "Avatar State Aang", "Aang", "Katara", "Sokka", "Toph", "Toph Beifong", "Fire Lord Ozai", "Avatar Kyoshi", "Zuko", "Azula", "Ozai", "Kyoshi",
          "Korra", "Zaheer", "Iroh", "Roku", "Amon", "Avatar State Aang", "Avatar State Korra",
          "Random"]
_ROSTER_KEYS = {n.replace(" ", "").lower(): n for n in ROSTER}

# Support characters seen so far. Readings close to one of these snap to it.
SUPPORTS = ["June", "Ran and Shaw", "Mai", "Ming-Hua", "Ghazan", "P'Li", "Master Pakku", "Kanna"]
def _skey(text):
    # OCR swaps l, I and 1 freely, so treat them as one letter.
    return "".join("i" if c in "li1|" else c for c in text.lower() if c.isalpha() or c in "1|")


_SUPPORT_KEYS = {_skey(n): n for n in SUPPORTS}


def match_support(text):
    key = _skey(text)
    if len(key) < 3:
        return None
    hit = difflib.get_close_matches(key, list(_SUPPORT_KEYS), n=1, cutoff=0.7)
    return _SUPPORT_KEYS[hit[0]] if hit else None


def _match_one(text):
    key = "".join(c for c in text.lower() if c.isalpha())
    if len(key) < 3:
        return None
    if key in _ROSTER_KEYS:
        return _ROSTER_KEYS[key]
    hit = difflib.get_close_matches(key, list(_ROSTER_KEYS), n=1, cutoff=0.6)
    return _ROSTER_KEYS[hit[0]] if hit else None


def match_roster(text):
    """The fighter named in text. When a support is shown beside the name
    ("KATARA MASTER PAKK"), the first word that is a fighter wins."""
    hit = _match_one(text)
    if hit:
        return hit
    for w in text.split():
        if match_support(w) or len(w) < 3:
            continue
        hit = _match_one(w)
        if hit:
            return hit
    return None


class Reader:
    def __init__(self, ocr):
        self.ocr = ocr
        self.mode = None            # 'menu', 'charsel', 'match', 'none'
        self.scene = None
        self.spoken_items = ()
        self.candidate = None
        self.names = (None, None)
        self.title = ""
        self.tick = 0
        self.charsel = False

    # ---- OCR helpers -------------------------------------------------
    def read_box(self, img, box):
        prepared = d.ocr_ready(d.crop(img, box))
        # Skip OCR when the lettering looks the same as last time.
        small = cv2.resize(prepared, (max(1, prepared.shape[1] // 8), max(1, prepared.shape[0] // 8)))
        key = (box[0] // 8, box[1] // 8, box[2] // 8, box[3] // 8, (small < 128).tobytes())
        cache = self.__dict__.setdefault("_cache", {})
        if key not in cache:
            if len(cache) > 300:
                cache.clear()
            cache[key] = tc.clean(self.ocr.text(prepared, scale=2))
        return cache[key]

    def read_gray(self, img, region, scale=2):
        g = cv2.cvtColor(d.crop(img, region), cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        return self.ocr.lines(g, scale=scale)

    def screen_title(self, img, exclude=()):
        # Titles are bright cream/gold lettering; keep only bright pixels.
        hsv = cv2.cvtColor(d.crop(img, d.TITLE_REGION), cv2.COLOR_BGR2HSV)
        m = ((hsv[..., 2] >= 200) & (hsv[..., 1] <= 150)).astype("uint8") * 255
        m = 255 - cv2.GaussianBlur(m, (3, 3), 0)
        best = None
        for line in self.ocr.lines(m):
            text = tc.clean(line.text)
            letters = [c for c in text if c.isalpha()]
            if len(letters) < 4:
                continue
            caps = sum(c.isupper() for c in letters) >= 0.8 * len(letters)
            if not any(sum(c.isalpha() for c in w) >= 4 for w in text.split()):
                continue    # a real title has at least one proper word ("HP ES" is not)
            if caps:
                if not (TITLE_MIN_HEIGHT <= line.h <= 75) or line.w < 2.5 * line.h:
                    continue
            else:
                # Mixed case ("Custom Lobby") is a title only when big and near the top.
                if not (48 <= line.h <= 115) or line.y > 320 or line.w < 2.5 * line.h:
                    continue
            if any(tc.same(text, e) for e in exclude):
                continue
            rank = (caps, line.h)            # capital-letter titles beat mixed case
            if best is None or rank > best[0]:
                best = (rank, text)
        return best[1] if best else ""

    def read_whole_screen(self, img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lines = self.ocr.lines(g)
        lines.sort(key=lambda l: (round(l.y / 25), l.x))
        parts = [tc.clean(l.text) for l in lines]
        return ". ".join(tc.speakable(p) for p in parts if p)

    # ---- main entry --------------------------------------------------
    def process(self, img):
        """Return a list of (text, interrupt) to speak for this frame."""
        self.tick += 1
        img = d.normalize(img)

        fighting = d.in_match(img)
        self.charsel = (not fighting) and d.charsel_layout(img)
        if self.charsel:
            # Stage select has the same Player 1 / Player 2 banners; the heading
            # says CHARACTER SELECT there, or the stage name here.
            heading = self.top_heading(img)
            if heading and "CHARACTER" not in heading.upper() and "SELECT" not in heading.upper():
                return self._stage(img, heading)
            return self._charsel(img)
        return self._menu(img, fighting)

    def top_heading(self, img):
        part = d.crop(img, d.TOP_HEADING)
        sig = (cv2.resize(cv2.cvtColor(part, cv2.COLOR_BGR2GRAY), (48, 6)) // 24).tobytes()
        cache = self.__dict__.setdefault("_cache", {})
        key = ("heading", sig)
        if key not in cache:
            text = tc.clean(self.ocr.text(d.bright_text(part, v=170, s=120), scale=2))
            words = [w for w in text.split() if len(w) > 2 or w.isupper()]
            cache[key] = " ".join(words)
        return cache[key]

    def _stage(self, img, heading):
        name = tc.speakable(heading)
        out = []
        if self.mode != "stage":
            self.mode = "stage"
            self.stage = None
            self.candidate = None
            self.prefix = "Stage select"
        if name != self.candidate:          # wait one frame for the name to settle
            self.candidate = name
            return out
        if name != self.stage:
            text = name if not getattr(self, "prefix", "") else self.prefix + ". " + name
            self.prefix = ""
            out.append((text, True))
            self.stage = name
        return out

    def _name_images(self, img, region):
        """A few versions of the name area; Windows OCR prefers some sizes."""
        part = d.crop(img, region)
        hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
        mask = ((hsv[..., 2] >= 190) & (hsv[..., 1] <= 160)).astype("uint8") * 255
        mask = 255 - cv2.GaussianBlur(mask, (3, 3), 0)
        gray = cv2.cvtColor(part, cv2.COLOR_BGR2GRAY)
        for im, scale in ((mask, 1), (mask, 0.6), (gray, 1), (mask, 2), (255 - gray, 1)):
            if scale != 1:
                im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
            yield cv2.copyMakeBorder(im, 20, 20, 20, 20, cv2.BORDER_REPLICATE), scale

    def read_name(self, img, region):
        part = d.crop(img, region)
        sig = (cv2.resize(cv2.cvtColor(part, cv2.COLOR_BGR2GRAY), (25, 12)) // 32).tobytes()
        key = ("name", region, sig)
        cache = self.__dict__.setdefault("_cache", {})
        if key in cache:
            return cache[key]
        raw = []
        name = None
        for im, scale in self._name_images(img, region):
            text = tc.clean(self.ocr.text(im, scale=scale))
            raw.append(text)
            name = match_roster(text)
            if name:
                break
        if not name:
            name = "?" + next((t for t in raw if t), "")   # unmatched: raw reading
        log.info("name region %s read %r -> %r", region, raw, name)
        cache[key] = name
        return name

    def fighter_name(self, img, side):
        # The cursor's place on the grid names the fighter reliably; the name
        # text is the fallback (the cursor hides once a pick is locked in).
        cell = (d.grid_highlight if side == 0 else d.grid_cursor_p2)(img)
        if cell:
            return "Random" if cell == "CENTER" else cell
        name = self.read_name(img, (d.CHARSEL_P1, d.CHARSEL_P2)[side])
        if not name.startswith("?"):
            return name
        # Try every word in the whole name column against the roster.
        part = d.crop(img, (d.CHARSEL_P1_EXTRA, d.CHARSEL_P2_EXTRA)[side])
        hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
        mask = ((hsv[..., 2] >= 175) & (hsv[..., 1] <= 170)).astype("uint8") * 255
        mask = cv2.copyMakeBorder(255 - mask, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        for line in sorted(self.ocr.lines(mask), key=lambda l: -l.h):
            for w in line.text.split():
                hit = match_roster(w)
                if hit:
                    return hit
        return name[1:]

    def read_extra(self, img, region, main):
        """Support name and variation text printed under a fighter's name."""
        part = d.crop(img, region)
        sig = (cv2.resize(cv2.cvtColor(part, cv2.COLOR_BGR2GRAY), (30, 10)) // 32).tobytes()
        key = ("extra", region, sig, main)
        cache = self.__dict__.setdefault("_cache", {})
        if key in cache:
            return cache[key]
        hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
        mask = ((hsv[..., 2] >= 175) & (hsv[..., 1] <= 170)).astype("uint8") * 255
        mask = 255 - cv2.GaussianBlur(mask, (3, 3), 0)
        mask = cv2.copyMakeBorder(mask, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        parts = []
        for line in sorted(self.ocr.lines(mask), key=lambda l: l.y):
            text = tc.clean(line.text)
            if main and _match_one(text) == main:
                continue    # the fighter's own name again, e.g. "OZ I" for Ozai
            words = [w for w in text.split() if not (main and _match_one(w) == main)]
            text = " ".join(words)
            support = match_support(text)
            if support:
                parts.append(support)
                continue
            if len(words) == 1 and sum(c.isalpha() for c in text) < 5:
                continue    # a lone short fragment ("Ans", "Xtar") is usually an emblem
            if sum(c.isalpha() for c in text) >= 3:
                parts.append(tc.speakable(text))
        # The variation is also printed larger on a white card; prefer that copy.
        card_region = d.CHARSEL_P1_CARD if region == d.CHARSEL_P1_EXTRA else d.CHARSEL_P2_CARD
        card = d.crop(img, card_region)
        if d.light_card(card):
            card_text = tc.clean(self.ocr.text(d.ocr_ready(card), scale=2))
            if card_text:
                key_c = card_text.lower()
                parts = [p for p in parts
                         if difflib.SequenceMatcher(None, p.lower(), key_c).ratio() < 0.5
                         and key_c not in p.lower()]
                parts.append(tc.speakable(card_text))
        extra = ", ".join(parts)
        log.info("extra region %s read %r", region, extra)
        cache[key] = extra
        return extra

    def _settled(self, key, value, frames=3):
        """value once it has been read the same way `frames` times in a row."""
        st = self.__dict__.setdefault("_settle", {})
        prev, count = st.get(key, (None, 0))
        count = count + 1 if value == prev else 1
        st[key] = (value, count)
        return value if count >= frames else None

    @staticmethod
    def _similar(a, b):
        if not a or not b:
            return a == b
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.75

    def _charsel(self, img):
        names = tuple(tc.speakable(self.fighter_name(img, i)) for i in (0, 1))
        extras = tuple(self.read_extra(img, r, n) for r, n in zip((d.CHARSEL_P1_EXTRA, d.CHARSEL_P2_EXTRA), names))
        out = []
        if self.mode != "charsel":
            self.mode = "charsel"
            self.scene = None
            self.spoken_items = ()
            self.names = [None, None]
            self.extras = ["", ""]
            self.prefix = "Character select"
            self.__dict__["_settle"] = {}
        changed = []
        status = self._bright(img, d.CHARSEL_STATUS)
        status = tc.speakable(tc.clean(status))
        if len(status.split()) < 2 or sum(c.isalpha() for c in status) < 8:
            status = ""         # "Searching for players", "Waiting for everyone to accept"
        status = self._settled("status", status, 2)
        if status is not None:
            if status and not tc.same(status, getattr(self, "status", "")):
                changed.append(status)
            self.status = status
        timer = re.sub(r"\D", "", self._bright(img, d.CHARSEL_TIMER))
        if timer and timer != getattr(self, "timer", "") and timer.lstrip("0") in ("10", "5", "3"):
            changed.append("%s seconds" % timer.lstrip("0"))
        self.timer = timer
        # Each side settles on its own, so one side's shimmering text never
        # holds back the other side (online, the opponent's side animates).
        for i in range(2):
            name = self._settled(("name", i), names[i])
            extra = self._settled(("extra", i), extras[i])
            who = "Player %d, " % (i + 1)
            if name and name != self.names[i]:
                self.names[i] = name
                ex = extra if extra is not None else extras[i]
                changed.append(who + name + (", " + ex if ex else ""))
                self.extras[i] = ex or ""
            elif extra and not self._similar(extra, self.extras[i]):
                changed.append(who + extra)
                self.extras[i] = extra
            elif extra == "":
                self.extras[i] = ""
        if changed:
            if getattr(self, "prefix", ""):
                changed.insert(0, self.prefix)
                self.prefix = ""
            out.append((". ".join(changed), True))
        return out

    def read_description(self, img):
        part = d.crop(img, d.COMMAND_DESC)
        if not d.light_card(part):
            return ""
        g = cv2.cvtColor(part, cv2.COLOR_BGR2GRAY)
        sig = (cv2.resize(g, (40, 20)) // 32).tobytes()
        cache = self.__dict__.setdefault("_cache", {})
        key = ("desc", sig)
        if key not in cache:
            lines = self.ocr.lines(cv2.copyMakeBorder(g, 10, 10, 10, 10, cv2.BORDER_REPLICATE))
            cache[key] = tc.clean_prose(" ".join(l.text for l in sorted(lines, key=lambda l: (l.y, l.x))))
        return cache[key]

    # ---- tutorial instructions ---------------------------------------------
    def _instruction(self, img):
        """Tutorial text during play, with button icons spoken in place."""
        self.tick_i = getattr(self, "tick_i", 0) + 1
        if self.tick_i % 2:
            return []                       # every other frame is plenty
        part = d.crop(img, d.INSTRUCTION_REGION)
        textpx = d.text_on_dark(part) > 0
        if textpx.sum() < 600:
            text = ""
        else:
            sig = (cv2.resize(textpx.astype("uint8") * 255, (60, 8)) // 64).tobytes()
            cache = self.__dict__.setdefault("_cache", {})
            key = ("instr", sig)
            if key not in cache:
                cache[key] = self._read_instruction(part)
            text = cache[key]
        text = self._settled("instruction", text, 2)
        if text is None or self._similar(text, getattr(self, "instruction", "")):
            return []
        self.instruction = text
        return [(text, True)] if text else []

    def _read_instruction(self, part):
        mask = d.text_on_dark(part)
        dark = cv2.blur(cv2.cvtColor(part, cv2.COLOR_BGR2GRAY), (41, 41)) < 120
        # Button icons only count when they sit on the dark band too (not on ice).
        icons = [i for i in inputs.find_icons(part)
                 if i[4] in ("A", "B", "C") and dark[(i[2] + i[3]) // 2, (i[0] + i[1]) // 2]]
        for x1, x2, y1, y2, _ in icons:
            mask[max(0, y1 - 6):y2 + 6, max(0, x1 - 6):x2 + 6] = 0
        img2 = cv2.resize(255 - mask, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        img2 = cv2.copyMakeBorder(img2, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        lines = self.ocr.lines(img2, scale=2)
        pieces = [((l.y + l.h / 2.0) - 20, l.x - 20, l.text) for l in lines]
        pieces += [((y1 + y2) / 2.0, x1, name) for x1, x2, y1, y2, name in icons]
        pieces.sort(key=lambda p: (round(p[0] / 30), p[1]))
        text = tc.clean_prose(" ".join(p[2] for p in pieces))
        text = re.sub(r"\s+,", ",", text)
        words = text.split()
        while words and sum(c.isalpha() for c in words[0]) < 3 and words[0] not in ("A", "B", "C", "I"):
            words.pop(0)        # specks before the first real word
        text = " ".join(words)
        real = [w for w in words if sum(c.isalpha() for c in w) >= 3 or w in ("A", "B", "C", "a", "I")]
        if len(real) < 4 or len(real) < 0.7 * len(words):
            return ""           # not a sentence: effects or scenery
        return text

    # ---- online screens ----------------------------------------------------
    def special_screen(self, img, items):
        """A summary to use as the title on the match-found popup or results."""
        joined = " ".join(items).lower()
        self.results = bool(re.search(r"rematch|back to matchmaking", joined))
        popup = bool(re.search(r"(accept|decline) match|frame delay", joined))
        if not (self.results or popup):
            return ""
        region = (700, 480, 1220, 880) if popup else (740, 740, 1180, 870)
        sig = (cv2.resize(cv2.cvtColor(d.crop(img, region), cv2.COLOR_BGR2GRAY), (16, 8)) // 40).tobytes()
        cache = self.__dict__.setdefault("_cache", {})
        key = ("special", popup, sig)
        if key not in cache:
            cache[key] = self._match_found(img) if popup else self._results(img)
        return cache[key]

    def _gray(self, img, region):
        g = cv2.cvtColor(d.crop(img, region), cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        return " ".join(self.ocr.text(cv2.copyMakeBorder(g, 10, 10, 10, 10, cv2.BORDER_REPLICATE), scale=2).split())

    def _results(self, img):
        names = [w for w in self._bright(img, d.RESULT_NAMES).split() if len(w) >= 3]
        names = (names + ["Player 1", "Player 2"])[:2] if len(names) < 2 else names[:2]

        def side(name, region):
            text = self._bright(img, region) + " " + self._gray(img, region)
            word = ""
            if re.search(r"(?i)\bw\W?[o0q]\W?n", text):
                word = "won"
            elif re.search(r"(?i)\bl\W?[o0]\W?[s5]\W?t", text):
                word = "lost"
            elif re.search(r"(?i)draw", text):
                word = "draw"
            num = re.search(r"\d+", text)
            return ", ".join(p for p in (name, word, num.group(0) if num else "") if p)
        return "Results. %s. %s" % (side(names[0], d.RESULT_P1), side(names[1], d.RESULT_P2))

    def _match_found(self, img):
        def info(text):
            text = re.sub(r"(?i)(\d+)\s*[mi]n?s\b", r"\1 milliseconds", text)
            text = re.sub(r"(?i)level\s*[O0o]\s*-\s*", "Level 0, ", text)
            text = re.sub(r"(?i)level\s*(\d+)\s*-\s*", r"Level \1, ", text)
            return text.replace("DISCONNECT", "disconnect rate")
        p1, p1i = self._bright(img, d.MATCH_P1_NAME), info(self._bright(img, d.MATCH_P1_INFO))
        p2, p2i = self._bright(img, d.MATCH_P2_NAME), info(self._bright(img, d.MATCH_P2_INFO))
        parts = ["Match found"]
        if p2:
            parts.append("Opponent %s, %s" % (p2, p2i) if p2i else "Opponent " + p2)
        if p1:
            parts.append("You, %s, %s" % (p1, p1i) if p1i else "You, " + p1)
        return ". ".join(parts)

    # ---- custom lobby ----------------------------------------------------
    def _bright(self, img, region):
        return tc.clean_prose(self.ocr.text(d.bright_text(d.crop(img, region)), scale=2))

    def is_custom_lobby(self, img):
        part = d.crop(img, d.LOBBY_CAPACITY)
        sig = (cv2.resize(cv2.cvtColor(part, cv2.COLOR_BGR2GRAY), (24, 6)) // 32).tobytes()
        cache = self.__dict__.setdefault("_cache", {})
        key = ("lobbycap", sig)
        if key not in cache:
            cache[key] = "capacity" in self._bright(img, d.LOBBY_CAPACITY).lower()
        return cache[key]

    def lobby_info(self, img):
        parts = []
        settings = tc.tidy_settings(self._bright(img, d.LOBBY_SETTINGS))
        if settings:
            parts.append(settings[0].upper() + settings[1:])
        cap = self._bright(img, d.LOBBY_CAPACITY)
        m = re.search(r"(?i)capacity\W*([0-9Il|]{1,2})\W+(\d{1,2})\b", cap)
        if m:
            have = m.group(1).replace("I", "1").replace("l", "1").replace("|", "1")
            cap = "Lobby capacity %s of %s" % (have, m.group(2))
        if cap:
            parts.append(tc.slots(cap))
        foot = self._bright(img, d.LOBBY_FOOTER)
        if foot:
            foot = re.sub(r"\s*[|I]\s+(?=Invite)", ", ", foot)
            parts.append(foot.replace("Invite Code:", "invite code"))
        return ". ".join(parts)

    def lobby_row(self, img, box, text):
        x1, y1, x2, y2 = box
        if x1 >= d.LOBBY_SLOTS_X:
            # A match slot: number on the right edge, two names either side of VS.
            num = re.sub(r"\D", "", self.ocr.text(d.bright_text(d.crop(img, (x2 - 40, y1, min(x2 + 30, d.REF_W), y2))), scale=2))
            if not num:
                # Slots are 120 pixels apart, slot 1 centred at y 228.
                num = str(max(1, int(round(((y1 + y2) / 2 - 228) / 120.0)) + 1))
            label = "Slot %s" % num
            lines = self.ocr.lines(d.ocr_ready(d.crop(img, box)), scale=2)
            names = [tc.clean(l.text) for l in sorted(lines, key=lambda l: l.x)]
            names = [n for n in names if tc.looks_like_words(n) and n.upper() != "VS"]
            if not names:
                return label + ", empty"
            return label + ", " + " versus ".join(names[:2])
        # A player row; VS means they are in a match, the crown marks the host.
        # Read from just left of the name, skipping the rank and platform icons.
        text = tc.clean(self.ocr.text(d.ocr_ready(d.crop(img, (x1 + 295, y1, x2, y2))), scale=2)) or text
        in_match = bool(re.search(r"\bv[s5]\b\W*$", text, re.I))
        text = re.sub(r"\s*\bv[s5]\b\W*$", "", text, flags=re.I)
        words = text.split()
        while len(words) > 1 and len(words[-1].strip(":;.,")) <= 2:
            words.pop()     # icon specks after the name
        text = " ".join(words)
        extras = []
        if d.has_crown(img, box):
            extras.append("host")
        if in_match:
            extras.append("in a match")
        return ", ".join([text] + extras)

    def read_move_card(self, img, box):
        """A command list card: name and tags on top, an input row below.

        Returns '' when the card has no input icons (plain text cards).
        """
        x1, y1, x2, y2 = box
        h = y2 - y1
        left = x1 + 190                      # past the move's thumbnail picture
        top = (left, y1 + 6, x2 - 8, y1 + int(h * 0.52))
        strip = (left, y1 + int(h * 0.55), x2 - 8, y2 - 4)
        part = d.crop(img, strip)
        sig = (cv2.resize(cv2.cvtColor(d.crop(img, box), cv2.COLOR_BGR2GRAY), (60, 8)) // 32).tobytes()
        cache = self.__dict__.setdefault("_cache", {})
        key = ("move", sig)
        if key not in cache:
            moves = inputs.read_inputs(part, self.ocr)
            if not moves:
                cache[key] = ""
            else:
                head = tc.speakable(tc.clean(self.ocr.text(d.dark_text(d.crop(img, top)), scale=2)))
                head = head.replace(";", ",")
                cache[key] = "%s. Input: %s" % (head, moves) if head else "Input: " + moves
        return cache[key]

    def _menu(self, img, fighting=False):
        boxes = d.find_highlights(img, fighting)
        mode = "fight" if fighting else "menu"
        if self.mode != mode:
            self.mode = mode
            self.scene = None
            self.title_scene = None

        # A "scene" is the highlight style plus the rough size of each box:
        # a different screen almost always has differently sized highlights.
        scene = tuple((s, (b[2] - b[0]) // 60, (b[3] - b[1]) // 20) for s, b in boxes)
        if boxes and scene != getattr(self, "title_scene", None):
            # Work out the screen title first, so rows are read the right way.
            self.title_scene = scene
            dialog = d.find_dialog(img, boxes)
            if dialog:
                q = tc.clean_prose(self.ocr.text(d.dark_text(d.crop(img, dialog)), scale=2))
                self.new_title = q or self.screen_title(img)
            else:
                self.new_title = self.screen_title(img)

        title = getattr(self, "new_title", "") if boxes else self.title
        grid_cell = None if (boxes or fighting) else d.grid_highlight(img)
        if grid_cell and getattr(self, "title_scene", None) != "grid":
            # A fighter grid with no menu highlight (tutorial select): read the title once.
            self.title_scene = "grid"
            self.new_title = self.screen_title(img)
        if grid_cell:
            title = getattr(self, "new_title", "") or title
            scene = ("grid",)
        lobby = bool(boxes) and self.is_custom_lobby(img)
        if lobby and "LOBBY" not in title.upper():
            title = "Custom Lobby"
        items = []
        for style, box in boxes:
            text = self.read_box(img, box)
            if fighting and not tc.looks_like_words(text):
                continue    # fire and sparks can look like a highlight mid-fight
            if lobby:
                text = self.lobby_row(img, box, text)
            if "COMMAND" in title.upper() and d.light_card(d.crop(img, box)):
                text = self.read_move_card(img, box) or text
            if re.fullmatch(r"(?i)win limit", text.strip(" ,")):
                text = "Win Limit, none"     # the "--" value is too thin for OCR
            if text:
                items.append(tc.tidy_lobby(tc.speakable(text)))
        if "TUTORIAL" in title.upper():
            cell = grid_cell or d.grid_highlight(img)
            if cell == "CENTER":
                scroll = tc.clean(self.ocr.text(d.bright_text(d.crop(img, (200, 85, 600, 165)), v=200, s=90), scale=2))
                cell = scroll or "General tutorials"
            if cell:
                items.insert(0, cell)
            items = [re.sub(r"(?i)\bnovise\b", "Novice", t) for t in items]
        special = self.special_screen(img, items)
        if special:
            title = special
        if items and "COMMAND" in title.upper():
            desc = self.read_description(img)
            if desc:
                items.append(desc)
        items = tuple(items)
        if fighting and not items:
            return self._instruction(img)
        if not items and getattr(self, "empty_frames", 0) <= 8 and self.spoken_items:
            self.empty_frames = getattr(self, "empty_frames", 0) + 1
            return []           # a flicker: keep everything as it was
        if items != self.candidate:          # wait one frame so animations settle
            self.candidate = items
            return []
        if not items:
            # The highlight glow can flicker off for a frame or two; only treat
            # it as gone after about a second.
            self.empty_frames = getattr(self, "empty_frames", 0) + 1
            if self.empty_frames > 8:
                self.spoken_items = ()
                self.scene = None
            return []
        self.empty_frames = 0

        out = []
        fresh = [t for t in items if t not in self.spoken_items]
        # The opponent's pick on the results screen (blue brush on the right).
        opp = d.opponent_choice_box(img) if getattr(self, "results", False) else None
        opp_text = tc.speakable(self.read_box(img, opp)) if opp else ""
        opp_new = opp_text and opp_text != getattr(self, "opp_text", "")
        self.opp_text = opp_text
        if scene != self.scene:
            self.scene = scene
            if title and not tc.same(title, self.title) and not any(tc.same(title, t) for t in items):
                out.append((tc.speakable(title), True))
                if lobby:
                    info = self.lobby_info(img)
                    if info:
                        out.append((info, False))
                fresh = list(items)      # a new screen: say the highlight again too
            self.title = title
        if opp_new:
            fresh.append("Opponent chose " + opp_text)
        if fresh:
            out.append((", ".join(fresh), not out))
        self.spoken_items = items
        return out
