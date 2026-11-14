"""Avatar Legends screen reader helper.

Watches the screen while Avatar Legends: The Fighting Game is running and
speaks the highlighted menu option through NVDA.

Hotkeys:
  Ctrl+Shift+R  repeat the last thing said
  Ctrl+Shift+S  read all the text on screen
  Ctrl+Shift+P  pause or resume automatic reading
  Ctrl+Shift+Q  quit
  Ctrl+Shift+G  hear health, Flow gauge and energy (yours and your opponent's)
  Ctrl+Shift+D  save a picture of the screen (to share when something isn't read)
  F3            accessibility menu (controller: press the right stick in, R3)

Run with --selftest FOLDER to read saved screenshots instead of the screen.
"""
import glob
import logging
import os
import sys
import threading
import time
import traceback

FROZEN = getattr(sys, "frozen", False)      # running as the packaged Avatar Reader.exe
# Logs and self-test results go next to the program the person double-clicked.
HERE = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(HERE, "avatar_reader.log")
logging.basicConfig(
    filename=LOG_PATH, filemode="w", level=logging.INFO,
    format="%(asctime)s [%(process)d] %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")

import cv2                      # noqa: E402
import numpy as np              # noqa: E402
from ocr import make_ocr        # noqa: E402
from reader import Reader       # noqa: E402
from speech import Speaker      # noqa: E402
from sounds import Player       # noqa: E402
from settings import Settings   # noqa: E402
from menu import AccessibilityMenu, ControllerWatcher  # noqa: E402
from hotkeys import Hotkeys     # noqa: E402

VERSION = "0.2.0"
POLL_SECONDS = 0.08     # up to about 12 looks a second
BLACK_WARN_SECONDS = 10


def selftest(folder):
    out_path = os.path.join(HERE, "selftest.txt")
    with open(out_path, "w", encoding="utf-8") as out:
        try:
            ocr = make_ocr()
            out.write("Avatar Reader %s\nOCR engine: %s\n" % (VERSION, ocr.name))
            reader = Reader(ocr)
            files = sorted(glob.glob(os.path.join(folder, "*.jpg")) + glob.glob(os.path.join(folder, "*.png")))
            out.write("Screenshots: %d\n" % len(files))
            for f in files:
                img = cv2.imdecode(np.fromfile(f, dtype=np.uint8), cv2.IMREAD_COLOR)
                said = []
                t0 = time.perf_counter()
                for _ in range(6):
                    said += reader.process(img)
                ms = (time.perf_counter() - t0) * 1000 / 6
                out.write("%s  (%.0f ms per frame)  %s\n" % (os.path.basename(f), ms, [s for s, _ in said]))
            spk = Speaker()
            out.write("NVDA loaded: %s, NVDA running: %s, Windows voice: %s\n" % (
                bool(spk.nvda), bool(spk.nvda and spk.nvda.running()), bool(spk.sapi)))
        except Exception:
            out.write(traceback.format_exc())
    print(open(out_path, encoding="utf-8").read())


class App:
    def __init__(self):
        self.speaker = Speaker()
        self.ocr = make_ocr()
        self.settings = Settings(HERE)
        st = self.settings
        self.player = Player(st.volumes(), st["my_side"], os.path.join(HERE, "Custom sounds"))
        self.reader = Reader(self.ocr, self.player, self.settings)
        self.hotkeys_thread = Hotkeys()
        self.menu = AccessibilityMenu(self.settings, self.speaker, self.setting_changed, self.preview_volume,
                                      self.hotkeys_thread, on_open=self.player.rebuild)
        self.paused = False
        self.was_in_front = True
        self.quit = threading.Event()
        self.read_all = threading.Event()
        self.save_screen = threading.Event()
        self.lock = threading.Lock()

    def hotkeys(self):
        hk = self.hotkeys_thread
        hk.start()
        hk.add("ctrl+shift+r", self.speaker.repeat)
        hk.add("ctrl+shift+s", self.read_all.set)
        hk.add("ctrl+shift+p", self.toggle_pause)
        hk.add("ctrl+shift+q", self.quit.set)
        hk.add("ctrl+shift+g", self.say_gauges)
        hk.add("ctrl+shift+d", self.save_screen.set)
        hk.add("f3", self.menu.toggle)
        ControllerWatcher(self.menu, self.quit).start()

    def say_gauges(self):
        self.speaker.say(self.reader.fight.status(self.reader.last_img))

    def setting_changed(self, key):
        st = self.settings
        if key.endswith("_volume") or key == "my_side":
            self.player.rebuild(st.volumes(), st["my_side"])

    def preview_volume(self, key):
        # Play the sound whose volume just changed.
        self.player.play({"health_volume": "health_low_p1", "energy_volume": "energy_3_p1",
                          "flow_volume": "flow_full_p1"}.get(key, "energy_3_p2"))

    def toggle_pause(self):
        self.paused = not self.paused
        self.speaker.say("Reading paused" if self.paused else "Reading resumed")
        if not self.paused:
            self.reader = Reader(self.ocr, self.player, self.settings)

    def run(self):
        import mss
        self.hotkeys()
        self.speaker.say("Avatar reader %s started. Control shift Q to quit." % VERSION)
        black_since = None
        warned_black = False
        grab_failing = False
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while not self.quit.is_set():
                start = time.perf_counter()
                try:
                    # One step from the captured BGRA picture to a tidy BGR one.
                    frame = cv2.cvtColor(np.asarray(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
                    grab_failing = False
                    if frame[::8, ::8].max() < 12:          # a quick look is enough
                        black_since = black_since or time.time()
                        if not warned_black and time.time() - black_since > BLACK_WARN_SECONDS:
                            warned_black = True
                            self.speaker.say("The screen looks black to me. If the game is in exclusive "
                                             "fullscreen, set its display mode to borderless or windowed.")
                    else:
                        black_since = None
                    in_front = game_in_front()
                    if in_front != self.was_in_front:
                        self.was_in_front = in_front
                        log.info("game window %s", "in front" if in_front else "not in front: reading paused")
                        if in_front:
                            self.reader = Reader(self.ocr, self.player, self.settings)
                    if self.save_screen.is_set():
                        # Keep a picture of exactly what the reader sees, to
                        # share when something isn't read right.
                        self.save_screen.clear()
                        folder = os.path.join(HERE, "Saved screens")
                        os.makedirs(folder, exist_ok=True)
                        name = time.strftime("%Y-%m-%d %H-%M-%S") + ".png"
                        cv2.imwrite(os.path.join(folder, name), frame)
                        self.speaker.say("Screen saved")
                    if self.read_all.is_set():
                        self.read_all.clear()
                        text = self.reader.read_whole_screen(cv2.resize(frame, (1920, 1080)))
                        self.speaker.say(text or "No text found")
                    elif not self.paused and in_front:
                        for text, interrupt in self.reader.process(frame):
                            self.speaker.say(text, interrupt)
                except Exception as e:
                    if "BitBlt" in traceback.format_exc() or "gdi" in str(e).lower():
                        # The screen can't be captured while Windows shows the lock
                        # screen or a permission prompt: wait quietly and retry.
                        if not grab_failing:
                            log.warning("screen capture unavailable: %s", e)
                        grab_failing = True
                        time.sleep(1.0)
                        continue
                    log.error(traceback.format_exc())
                    time.sleep(0.5)
                time.sleep(max(0.0, POLL_SECONDS - (time.perf_counter() - start)))
        self.speaker.say("Avatar reader closed.")
        time.sleep(1.5)


_front_cache = {}


def game_in_front():
    """True when the game's window is the one in front. When you switch to
    Steam, OBS or the desktop, the reader stays quiet so it doesn't read
    other programs or talk over NVDA. If Windows can't say, keep reading."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd in _front_cache:            # same window as last time: same answer
            return _front_cache[hwnd]
        if len(_front_cache) > 50:
            _front_cache.clear()
        _front_cache[hwnd] = answer = _check_window(hwnd)
        return answer
    except Exception:
        return True


def _check_window(hwnd):
    try:
        import ctypes
        import ctypes.wintypes as wt
        user32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        if not hwnd:
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if "avatar legends" in buf.value.lower():
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc = k32.OpenProcess(0x1000, False, pid.value)       # query limited information
        if not proc:
            return True
        try:
            size = wt.DWORD(512)
            if k32.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(size)):
                return "avatar" in buf.value.lower()
            return True
        finally:
            k32.CloseHandle(proc)
    except Exception:
        return True


def already_running():
    """Only one reader at a time: a named Windows mutex marks a running copy."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        main._mutex = k32.CreateMutexW(None, False, "AvatarReaderSingleInstance")
        return k32.GetLastError() == 183          # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2])
        return
    if already_running():
        Speaker().say("Avatar reader is already running.")
        time.sleep(2)
        return
    try:
        App().run()
    except Exception:
        log.error(traceback.format_exc())
        try:
            Speaker().say("Avatar reader hit an error and closed. Details are in avatar reader dot log.")
            time.sleep(3)
        except Exception:
            pass


if __name__ == "__main__":
    main()
