"""The accessibility menu: F3, or press the right stick in (R3) on a controller.

Keyboard: up and down move, left and right change a setting, Enter switches
an on/off setting, Escape or F3 closes the menu. Controller: the right stick
moves and changes, R3 closes. Everything is spoken.
"""
import ctypes
import logging
import threading
import time

log = logging.getLogger("menu")

# (key, label, kind, extra) - kind: "onoff", "choice" (extra = choices), "volume"
ITEMS = [
    ("fight_sounds", "All fight sounds and combos", "onoff", None),
    ("my_side", "You are player", "choice", [1, 2]),
    ("combos", "Combo hits and damage", "onoff", None),
    ("health_sound", "Health alert at 30 percent", "choice", ["both", "mine", "off"]),
    ("flow_sound", "Flow gauge full sound", "onoff", None),
    ("energy_sound", "Energy sounds", "onoff", None),
    ("opponent_sounds", "Opponent's Flow and energy sounds", "onoff", None),
    ("tutorial_text", "Read tutorial instructions", "onoff", None),
    ("health_volume", "Health alert volume", "volume", None),
    ("energy_volume", "Energy sound volume", "volume", None),
    ("flow_volume", "Flow gauge sound volume", "volume", None),
    ("opponent_volume", "Opponent's Flow and energy volume", "volume", None),
]

CHOICE_WORDS = {"both": "you and your opponent", "mine": "you only", "off": "off"}


class AccessibilityMenu:
    def __init__(self, settings, speaker, on_change=None, preview=None, hotkeys=None, on_open=None):
        self.settings = settings
        self.speaker = speaker
        self.on_change = on_change or (lambda key: None)
        self.preview = preview or (lambda key: None)
        self.hotkeys = hotkeys
        self.on_open = on_open or (lambda: None)
        self.open = False
        self.index = 0
        self._keys = []
        self.lock = threading.Lock()

    # ---- wording --------------------------------------------------------
    def describe(self, i):
        key, label, kind, extra = ITEMS[i]
        v = self.settings[key]
        if kind == "onoff":
            value = "on" if v else "off"
        elif kind == "volume":
            value = "%d percent" % v
        else:
            value = CHOICE_WORDS.get(v, str(v))
        return "%s, %s" % (label, value)

    # ---- opening and closing ----------------------------------------------
    def toggle(self):
        with self.lock:
            if self.open:
                self._close()
            else:
                self._open()

    def _open(self):
        self.open = True
        self._grab_keys()
        try:
            self.on_open()              # picks up new or changed custom sounds
        except Exception as e:
            log.error("menu open: %s", e)
        self.speaker.say("Accessibility menu. %s. Up and down to move, left and right to change, "
                         "Escape or right stick click to close." % self.describe(self.index))

    def _close(self):
        self.open = False
        self._release_keys()
        self.speaker.say("Accessibility menu closed")

    def _grab_keys(self):
        # While the menu is open, these keys go to the menu, not the game.
        if not self.hotkeys:
            return
        for name, fn in (("up", self.up), ("down", self.down), ("left", self.left),
                         ("right", self.right), ("enter", self.activate), ("esc", self.toggle)):
            self._keys.append(self.hotkeys.add(name, fn))

    def _release_keys(self):
        for h in self._keys:
            self.hotkeys.remove(h)
        self._keys = []

    # ---- moving and changing ---------------------------------------------
    def up(self):
        self.index = (self.index - 1) % len(ITEMS)
        self.speaker.say(self.describe(self.index))

    def down(self):
        self.index = (self.index + 1) % len(ITEMS)
        self.speaker.say(self.describe(self.index))

    def left(self):
        self._change(-1)

    def right(self):
        self._change(+1)

    def activate(self):
        key, _, kind, _ = ITEMS[self.index]
        if kind == "onoff":
            self._change(+1)
        else:
            self.speaker.say(self.describe(self.index))

    def _change(self, step):
        key, label, kind, extra = ITEMS[self.index]
        v = self.settings[key]
        if kind == "onoff":
            v = not v
        elif kind == "volume":
            v = max(0, min(100, v + 10 * step))
        else:
            i = extra.index(v) if v in extra else 0
            v = extra[(i + step) % len(extra)]
        self.settings[key] = v
        self.on_change(key)
        self.speaker.say(self.describe(self.index))
        if kind == "volume":
            self.preview(key)


# ---- controller --------------------------------------------------------
class _XInputGamepad(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short)]


class _XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", _XInputGamepad)]


R3 = 0x0080            # pressing the right stick in
STICK_ON, STICK_OFF = 20000, 8000


class ControllerWatcher(threading.Thread):
    """Press the right stick in (R3) to open or close the menu. While it is
    open, push the right stick up or down to move and left or right to
    change. The right stick isn't used in the game's own menus, so the game
    doesn't move along with it (the D-pad and buttons would)."""

    def __init__(self, menu, stop_event):
        super().__init__(daemon=True)
        self.menu = menu
        self.stop_event = stop_event
        self.xinput = None
        for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                self.xinput = getattr(ctypes.windll, dll)
                break
            except Exception:
                continue

    def read(self):
        """Buttons pressed on any controller, and the right stick direction
        of whichever controller is pushing it furthest."""
        buttons, rx, ry = 0, 0, 0
        state = _XInputState()
        for pad in range(4):
            if self.xinput.XInputGetState(pad, ctypes.byref(state)) == 0:
                g = state.Gamepad
                buttons |= g.wButtons
                if abs(g.sThumbRX) > abs(rx):
                    rx = g.sThumbRX
                if abs(g.sThumbRY) > abs(ry):
                    ry = g.sThumbRY
        return buttons, rx, ry

    def run(self):
        if not self.xinput:
            log.warning("no XInput: controller shortcut unavailable")
            return
        prev = 0
        stick_free = True
        while not self.stop_event.is_set():
            try:
                now, rx, ry = self.read()
                if (now & ~prev) & R3:
                    self.menu.toggle()
                elif self.menu.open:
                    if stick_free and max(abs(rx), abs(ry)) > STICK_ON:
                        stick_free = False
                        if abs(ry) >= abs(rx):
                            (self.menu.up if ry > 0 else self.menu.down)()
                        else:
                            (self.menu.right if rx > 0 else self.menu.left)()
                if max(abs(rx), abs(ry)) < STICK_OFF:
                    stick_free = True        # back to the middle: ready for the next push
                prev = now
            except Exception as e:
                log.error("controller: %s", e)
                time.sleep(1)
            time.sleep(0.03)
