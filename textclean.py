import re

_KEEP = re.compile(r"[^A-Za-z0-9%'&:/,\- ]+")


_PLAYER = re.compile(r"\bP\s?[lI|1!]\b")
_PLAYER2 = re.compile(r"\bP\s?[2Z]\b")


def clean(text):
    """Tidy OCR output into something worth speaking, or '' for noise."""
    text = _PLAYER.sub("P1", text.replace("\n", " "))
    text = re.sub(r"\bI\.?obby", "Lobby", text)
    text = re.sub(r"(?:(?<=\s)|(?<=,)|^)--(?=\s|$)", " none", text)   # "--" means no value
    text = _PLAYER2.sub("P2", text)
    text = _KEEP.sub(" ", text)
    text = re.sub(r"\s+,", ",", text)
    words = text.split()
    # Drop stray specks at either end (icons and brush edges read as 'a', 'aq', '4').
    # (A lone capital is kept: OCR often splits a name like "TBlaze" into "T Blaze".)
    while len(words) > 1 and words[0] not in ("P1", "P2") and (
            (len(words[0]) == 1 and not (words[0].isalpha() and words[0].isupper()))
            or (len(words[0]) == 2 and not words[0].isupper())):
        words.pop(0)
    while words and len(words[-1]) <= 2 and not words[-1].isdigit() and not words[-1].isupper():
        words.pop()
    text = " ".join(words)
    letters = sum(c.isalnum() for c in text)
    if letters < 2:
        return ""
    return text


def speakable(text):
    """Menu text in capitals is read letter by letter by some voices; title-case it."""
    words = text.split()
    letters = [c for c in text if c.isalpha()]
    mostly_caps = len(words) >= 3 and sum(c.isupper() for c in letters) >= 0.6 * len(letters)

    def fix(w):
        if not w.isupper() or any(c.isdigit() for c in w):
            return w            # leave P1, P2, EX alone
        if mostly_caps or len(w) > 3:
            return w[0] + w[1:].lower() if w[0].isalpha() else w
        return w
    return " ".join(fix(w) for w in words)


def same(a, b):
    return re.sub(r"\W", "", a).lower() == re.sub(r"\W", "", b).lower()


_PROSE = re.compile(r"[^A-Za-z0-9%'&:/\-+.,!?() ]+")


def clean_prose(text):
    """Lighter cleanup for descriptions: keeps sentence punctuation."""
    text = _PROSE.sub(" ", re.sub(r"\bI\.?obby", "Lobby", text.replace("\n", " ")))
    return " ".join(text.split())


def looks_like_words(text):
    """At least one real-looking word of three or more letters."""
    return any(sum(c.isalpha() for c in w) >= 3 for w in text.split())


_SLOTS = re.compile(r"\b(\d{1,2})\s?/\s?(\d{1,2})\b")


def tidy_settings(text):
    """'Round Timer: Normal I Win Limit: --' -> 'round timer Normal, win limit none'."""
    timer = re.search(r"(?i)round timer:?\s*([A-Za-z]+)", text)
    limit = re.search(r"(?i)win limit:?\s*(\d+)", text)
    if not timer and not limit:
        return ""
    return "round timer %s, win limit %s" % (
        timer.group(1).capitalize() if timer else "unknown", limit.group(1) if limit else "none")


def slots(text):
    """'2/4' -> '2 of 4'."""
    return _SLOTS.sub(lambda m: "%s of %s" % (m.group(1), m.group(2)), text)


def tidy_lobby(text):
    """Make an online lobby row sound natural.

    'Prestidigination 12/16 Settings: Round Timer: Normal I Win Limit:' becomes
    'Prestidigination, 12 of 16 players, round timer Normal, win limit none'.
    """
    if "round timer" not in text.lower():
        return text
    m = re.match(r"(?i)\s*(.*?)\s*(\d{1,2})\s?/\s?(\d{1,2})\s*(?:settings:?)?\s*(.*)$", text)
    if not m:
        return text
    name, have, cap, rest = m.groups()
    timer = re.search(r"(?i)round timer:?\s*([A-Za-z]+)", rest)
    limit = re.search(r"(?i)win limit:?\s*(\d+)", rest)
    parts = [name.strip(" ,") or "Lobby", "%s of %s players" % (have, cap)]
    parts.append("round timer " + (timer.group(1) if timer else "unknown"))
    parts.append("win limit " + (limit.group(1) if limit else "none"))
    return ", ".join(parts)
