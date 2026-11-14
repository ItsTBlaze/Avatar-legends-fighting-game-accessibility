"""Screen analysis for Avatar Legends: The Fighting Game.

Everything works in a 1920x1080 reference frame; other resolutions are scaled
to it first. The game marks the selected menu option in one of three ways:
  * an orange-red brush stroke (pause menus, options tabs)
  * an orange outline box (rows on the Options screens)
  * a black brush stroke (main menu)
  * an orange outline around a white card with dark text (command list)
"""
import cv2
import numpy as np

REF_W, REF_H = 1920, 1080

# Fixed regions (x1, y1, x2, y2) in the reference frame.
TITLE_REGION = (150, 0, 1900, 330)
CHARSEL_TITLE = (700, 10, 1220, 85)
CHARSEL_P1 = (560, 830, 760, 920)
CHARSEL_P2 = (1160, 830, 1420, 920)
# Whole name column per side: fighter, support pick and variation text.
CHARSEL_P1_EXTRA = (470, 825, 765, 950)
CHARSEL_P2_EXTRA = (1155, 825, 1470, 950)
# White card showing the highlighted support variation, beside each portrait.
CHARSEL_P1_CARD = (240, 392, 565, 446)
CHARSEL_P2_CARD = (1355, 392, 1680, 446)
# Custom lobby screen.
LOBBY_SETTINGS = (715, 105, 1225, 145)
LOBBY_CAPACITY = (300, 858, 760, 902)
LOBBY_FOOTER = (700, 972, 1225, 1014)
LOBBY_SLOTS_X = 940          # match slots are right of this line, players left of it
# Heading at the top of character select and stage select.
TOP_HEADING = (600, 15, 1320, 75)
# Online: status line and pick timer on character select.
CHARSEL_STATUS = (690, 905, 1230, 962)
CHARSEL_TIMER = (912, 832, 1008, 908)
# Online: match-found popup.
MATCH_P1_NAME = (170, 505, 720, 565)
MATCH_P1_INFO = (170, 580, 720, 625)
MATCH_P2_NAME = (1205, 505, 1790, 565)
MATCH_P2_INFO = (1205, 580, 1790, 625)
# Results screen after a match.
RESULT_NAMES = (790, 742, 1180, 785)
RESULT_P1 = (745, 812, 955, 868)
RESULT_P2 = (962, 812, 1175, 868)
COMMAND_DESC = (1288, 657, 1752, 912)   # move description card on the command list
# The inner ends of the health bars, next to the timer. They stay full the
# longest (bars drain from the outside in) and no menu tab sits exactly there.
P1_HEALTH_END = (700, 68, 850, 90)
P2_HEALTH_END = (1075, 68, 1220, 90)
HUD_BOTTOM = 110    # during a fight, ignore anything starting above this line


def normalize(frame_bgr):
    h, w = frame_bgr.shape[:2]
    if (w, h) != (REF_W, REF_H):
        frame_bgr = cv2.resize(frame_bgr, (REF_W, REF_H), interpolation=cv2.INTER_AREA)
    return frame_bgr


def crop(img, region):
    x1, y1, x2, y2 = region
    return img[y1:y2, x1:x2]


def orange_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Hue up to 13 keeps the bright highlight orange but not the brown buttons
    # on the controller settings panel (hue 15).
    low = cv2.inRange(hsv, (0, 130, 125), (13, 255, 255))
    high = cv2.inRange(hsv, (172, 130, 125), (180, 255, 255))
    return (cv2.bitwise_or(low, high) > 0).astype(np.uint8)


def black_mask(img):
    b, g, r = cv2.split(img)
    brightest = cv2.max(cv2.max(b, g), r)          # much faster than numpy's max over colors
    return (brightest < 30).astype(np.uint8)


def white_text_mask(img):
    """Bright, low-saturation pixels: the white menu lettering."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 2] >= 185) & (hsv[..., 1] <= 90)).astype(np.uint8)


def light_card(img):
    """True when a box is mostly white/cream inside (dark text on a light card)."""
    h, w = img.shape[:2]
    inner = img[h // 5: h - h // 5, w // 10: w - w // 10]
    return inner.size > 0 and cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY).mean() > 170


def ocr_ready(img, scale=2):
    """Black text on white, upscaled."""
    if light_card(img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        _, out = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        h, w = out.shape
        out[: max(4, h // 12)] = 255; out[h - max(4, h // 12):] = 255   # drop the glowing border
        out[:, : max(4, w // 60)] = 255; out[:, w - max(4, w // 60):] = 255
        return cv2.copyMakeBorder(out, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    m = white_text_mask(img) * 255
    m = cv2.resize(m, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(m, (3, 3), 0)
    out = 255 - m
    return cv2.copyMakeBorder(out, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def ocr_ready_alt(img, scale=3):
    """A second try for a box nothing was read from: plain grey levels with
    the edges trimmed (brush ends and button corners), dark text on white,
    bigger. Thin lettering that the first try broke up often survives this."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(img[h // 7: h - h // 7, w // 14: w - w // 14], cv2.COLOR_BGR2GRAY)
    if g.size == 0:
        return ocr_ready(img)
    if g.mean() < 128:
        g = 255 - g                  # light letters on a dark brush: flip them
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, out = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.copyMakeBorder(out, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)


def _boxes(mask, kernel, min_w, min_h, max_h, top=40):
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, kernel))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w >= min_w and min_h <= h <= max_h and y >= top:
            out.append((int(x), int(y), int(w), int(h), int(area)))
    return out


def find_highlights(img, fighting=False):
    """Return a list of (style, (x1, y1, x2, y2)) boxes, top to bottom.

    While a fight is on screen (a menu over a live match, like controller
    settings) the health bars and timer at the top are ignored.
    """
    found = []
    top = HUD_BOTTOM if fighting else 40
    for x, y, w, h, area in _boxes(orange_mask(img), (9, 5), 220, 36, 170, top):
        box = (x, y, x + w, y + h)
        if np.count_nonzero(white_text_mask(crop(img, box))) < 150:
            continue  # no lettering inside: an effect, not a menu highlight
        found.append(("orange", box))
    if not found:
        for x, y, w, h, area in _boxes(black_mask(img), (7, 5), 320, 45, 120, top):
            box = (x, y, x + w, y + h)
            if area / float(w * h) < 0.45:
                continue
            if np.count_nonzero(white_text_mask(crop(img, box))) < 300:
                continue
            found.append(("black", box))
    if not found:
        # Over bright fire (the results screen after a match) the see-through
        # orange brush looks more yellow; try once more allowing that.
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        warm = (cv2.inRange(hsv, (0, 170, 150), (18, 255, 255)) > 0).astype(np.uint8)
        for x, y, w, h, area in _boxes(warm, (9, 5), 220, 36, 170, top):
            box = (x, y, x + w, y + h)
            if np.count_nonzero(white_text_mask(crop(img, box))) < 150:
                continue
            found.append(("orange", box))
    # The button prompt strip along the bottom of training ("Pause,
    # (Hold All) Reset") looks like a black highlight but isn't a menu.
    found = [f for f in found if not (f[0] == "black" and f[1][1] >= 940)]
    found.sort(key=lambda b: (b[1][1], b[1][0]))
    return found


def in_match(img):
    """True while a fight is on screen and not dimmed by a pause menu.

    Checks the inner ends of the health bars (orange, or yellow when low, for
    P1; blue for P2) and the dark centre of the round timer between them.
    """
    hsv1 = cv2.cvtColor(crop(img, P1_HEALTH_END), cv2.COLOR_BGR2HSV).astype(int)
    h, s, v = hsv1[..., 0], hsv1[..., 1], hsv1[..., 2]
    p1 = (((h <= 35) | (h >= 165)) & (s >= 120) & (v >= 120)).mean()
    hsv = cv2.cvtColor(crop(img, P2_HEALTH_END), cv2.COLOR_BGR2HSV).astype(int)
    p2 = ((hsv[..., 0] >= 105) & (hsv[..., 0] <= 130) & (hsv[..., 1] >= 60) & (hsv[..., 2] >= 140)).mean()
    emblem = crop(img, (935, 70, 985, 140))
    dark = (emblem.max(axis=2) < 60).mean()
    return (p1 > 0.5 or p2 > 0.5) and dark > 0.45


# Local VS controller setup, just before character select: each controller
# sits in the middle and moves left to Player 1 or right to Player 2.
CTRL_SLOTS = {0: (530, 450, 680, 555), 1: (1165, 450, 1315, 555)}
CTRL_SLOT_TEXT = {0: (560, 470, 650, 530), 1: (1195, 470, 1285, 530)}
CTRL_CENTER = {1: (910, 550, 1010, 615), 2: (910, 635, 1010, 700)}


def _hsv(img, box):
    hsv = cv2.cvtColor(crop(img, box), cv2.COLOR_BGR2HSV).astype(int)
    return hsv[..., 0], hsv[..., 1], hsv[..., 2]


def controller_setup(img):
    h, s, v = _hsv(img, CTRL_SLOTS[0])
    red = (((h <= 10) | (h >= 165)) & (s >= 80) & (v >= 60)).mean()
    h, s, v = _hsv(img, CTRL_SLOTS[1])
    blue = ((h >= 105) & (h <= 130) & (s >= 80) & (v >= 60)).mean()
    if red < 0.4 or blue < 0.4:
        return False
    above = crop(img, (870, 445, 1050, 530)).max(axis=2)
    h, s, v = _hsv(img, (300, 240, 1620, 330))
    cream = ((s <= 110) & (v >= 120)).mean()
    return (above < 70).mean() > 0.6 and cream > 0.6


def controller_in_middle(img, n):
    h, s, v = _hsv(img, CTRL_CENTER[n])
    return ((s <= 50) & (v >= 200)).mean() > 0.35


def slot_text_width(img, side):
    """Width of the white lettering on a Player slot: wide for "CPU",
    narrow for a controller number."""
    h, s, v = _hsv(img, CTRL_SLOT_TEXT[side])
    ys, xs = np.nonzero((v >= 190) & (s <= 110))
    return int(xs.max() - xs.min()) if len(xs) > 20 else 0


# The versus screen after picking: a big gold "VS" in the middle of the bottom.
VS_EMBLEM = (860, 800, 1060, 1010)
VS_STAGE = (580, 85, 1340, 145)          # the stage name across the top


def versus_screen(img):
    hsv = cv2.cvtColor(crop(img, VS_EMBLEM), cv2.COLOR_BGR2HSV)
    gold = cv2.inRange(hsv, (12, 45, 120), (38, 255, 255))
    # The gold letters sit on a dark round badge; a golden sky has no dark.
    dark = (hsv[..., 2] < 70).mean()
    return cv2.countNonZero(gold) >= 12000 and dark >= 0.25


# Arcade mode select: the fighter grid, with three difficulty buttons on the
# right (green Novice, yellow Intermediate, red Expert).
ARCADE_BUTTONS = (("Novice", (1340, 262, 1765, 334), (35, 75)),
                  ("Intermediate", (1340, 400, 1765, 472), (18, 34)),
                  ("Expert", (1340, 538, 1765, 610), (0, 12)))


def arcade_select(img):
    for _, box, (h1, h2) in ARCADE_BUTTONS:
        h, s, v = _hsv(img, box)
        if (((h >= h1) & (h <= h2)) & (s >= 70) & (v >= 80)).mean() < 0.5:
            return False
    return True


def arcade_difficulty(img):
    """The difficulty button that stands out (brighter than the other two),
    or None while none is picked out."""
    bright = []
    for name, (x1, y1, x2, y2), _ in ARCADE_BUTTONS:
        h, s, v = _hsv(img, (x1 - 12, y1 - 12, x2 + 12, y2 + 12))
        bright.append((float(v.mean()), name))
    bright.sort(reverse=True)
    return bright[0][1] if bright[0][0] - bright[1][0] > 12 else None


# A white popup card in the middle of the screen ("Leave the lobby?").
def popup_card(img):
    small = img[::2, ::2]
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (0, 0, 215), (180, 40, 255))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(m)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        cx, cy = (x + w / 2) * 2, (y + h / 2) * 2
        if 200 <= w <= 500 and h >= 75 and area >= 0.6 * w * h and 700 <= cx <= 1220 and 200 <= cy <= 850:
            card = cv2.cvtColor(small[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
            paper = card[card > 150]
            # A real card is flat white paper with dark writing; a glow fades.
            if paper.size and paper.std() < 12 and (card < 100).mean() > 0.005:
                return (x * 2, y * 2, (x + w) * 2, (y + h) * 2)
    return None


def timer_running(img):
    """A real match shows a countdown (tall digits) in the round timer;
    training and tutorials show a short, wide infinity sign instead."""
    part = crop(img, (905, 55, 1015, 150))
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] >= 170) & (hsv[..., 1] <= 90)).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(m)
    return any(40 <= stats[i][3] <= 65 and stats[i][2] <= 45 and stats[i][4] >= 300 for i in range(1, n))


# Dialogue before a fight: a line at the top with the speaker's portrait on
# the right, and a reply at the bottom with the portrait on the left.
INTRO_TOP = (90, 100, 1330, 240)
INTRO_TOP_NAME = (1690, 250, 1890, 310)
INTRO_BOTTOM = (590, 800, 1700, 940)
INTRO_BOTTOM_NAME = (40, 950, 220, 1015)

# Big round announcements in the middle of the screen ("ROUND 2", "FINISH").
ANNOUNCE_REGION = (420, 380, 1500, 720)


def charsel_layout(img):
    """Character (and stage) select: a red banner behind "PLAYER 1" and a blue
    one behind "PLAYER 2", in the middle where the fighters never stand."""
    b1, g1, r1 = crop(img, (560, 768, 850, 800)).reshape(-1, 3).mean(0)
    b2, g2, r2 = crop(img, (1075, 768, 1360, 800)).reshape(-1, 3).mean(0)
    return (r1 - b1 > 35 and 85 <= r1 <= 145) and (b2 - r2 > 15 and 90 <= b2 <= 145)


def is_character_select(title_text):
    return "CHARACTER" in title_text.upper() or "SELECT" in title_text.upper()


def bright_text(img, v=175, s=170, scale=2):
    """Light lettering on a dark background, as black-on-white for OCR."""
    if scale != 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] >= v) & (hsv[..., 1] <= s)).astype(np.uint8) * 255
    m = 255 - cv2.GaussianBlur(m, (3, 3), 0)
    return cv2.copyMakeBorder(m, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def has_crown(img, box):
    """The lobby host has a small gold crown just left of their name."""
    x1, y1 = box[0], box[1]
    part = img[max(0, y1 - 15): y1 + 40, x1 + 280: x1 + 335]
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    gold = (hsv[..., 0] >= 18) & (hsv[..., 0] <= 35) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 200)
    return int(gold.sum()) >= 40


def find_dialog(img, boxes):
    """A white popup card whose bottom edge holds the highlighted button.

    Returns the card's question area (x1, y1, x2, y2) or None.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] >= 215) & (hsv[..., 1] <= 40)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(m)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if w < 400 or h < 150 or area < 0.6 * w * h:
            continue
        for _, (bx1, by1, bx2, by2) in boxes:
            if y + h - 70 <= by1 <= y + h + 20 and bx1 < x + w and bx2 > x:
                return (x, y, x + w, min(y + h, by1))
    return None


def dark_text(img, scale=2):
    """Dark lettering on a light card, as black-on-white for OCR."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, out = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.copyMakeBorder(out, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def opponent_choice_box(img):
    """On the results screen the opponent's pick is a blue brush on the right."""
    part = img[700:1060, 1400:1920]
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] >= 105) & (hsv[..., 0] <= 128) & (hsv[..., 1] >= 150) & (hsv[..., 2] >= 150)).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((5, 9), np.uint8)))
    best = None
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if w >= 250 and 40 <= h <= 120 and (best is None or area > best[4]):
            best = (x, y, w, h, area)
    if not best:
        return None
    x, y, w, h, _ = best
    return (1400 + x, 700 + y, 1400 + x + w, 700 + y + h)


# The fighter grid (character select and tutorial select share it).
GRID_CELLS = {
    (960, 170): "Nightmare Korra",
    (825, 305): "Sokka", (960, 305): "Toph", (1095, 305): "Katara",
    (690, 440): "Ozai", (825, 440): "Aang", (960, 440): "CENTER", (1095, 440): "Korra", (1230, 440): "Zaheer",
    (825, 575): "Zuko", (960, 575): "Kyoshi", (1095, 575): "Azula",
    (960, 710): "Avatar State Aang",
}


def _grid_cell(mask):
    n, _, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(mask, np.ones((5, 5), np.uint8)))
    for i in range(1, n):
        x, y, w, h, _ = (int(v) for v in stats[i])
        if 115 <= w <= 155 and 115 <= h <= 155 and abs(w - h) <= 14:
            cx, cy = 600 + x + w // 2, 100 + y + h // 2
            cell = min(GRID_CELLS, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
            if (cell[0] - cx) ** 2 + (cell[1] - cy) ** 2 <= 40 ** 2:
                return GRID_CELLS[cell]
    return None


def grid_highlight(img):
    """Name of the grid cell with the orange hexagon outline (Player 1's cursor)."""
    return _grid_cell(orange_mask(img[100:790, 600:1320]))


def grid_cursor_p2(img):
    """Name of the grid cell with the blue hexagon outline (Player 2's cursor)."""
    hsv = cv2.cvtColor(img[100:790, 600:1320], cv2.COLOR_BGR2HSV)
    blue = ((hsv[..., 0] >= 100) & (hsv[..., 0] <= 125) & (hsv[..., 1] >= 130) & (hsv[..., 2] >= 160))
    return _grid_cell(blue.astype(np.uint8))


# Tutorial instructions appear as light text on a dark band near the bottom.
INSTRUCTION_REGION = (40, 820, 1880, 1015)


def text_on_dark(part):
    """Light lettering whose surroundings are dark: subtitle-style text.

    Bright snow, sky or effects have bright surroundings and are left out.
    """
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    light = (hsv[..., 2] >= 200) & (hsv[..., 1] <= 70)
    around = cv2.blur(cv2.cvtColor(part, cv2.COLOR_BGR2GRAY), (41, 41))
    return ((light & (around < 120)).astype(np.uint8)) * 255
