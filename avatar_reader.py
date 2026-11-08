"""Avatar Legends screen reader helper.

Watches the screen while Avatar Legends: The Fighting Game is running and
speaks the highlighted menu option through NVDA.

Hotkeys:
  Ctrl+Shift+R  repeat the last thing said
  Ctrl+Shift+S  read all the text on screen
  Ctrl+Shift+P  pause or resume automatic reading
  Ctrl+Shift+Q  quit

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

POLL_SECONDS = 0.12
BLACK_WARN_SECONDS = 10


def selftest(folder):
    out_path = os.path.join(HERE, "selftest.txt")
    with open(out_path, "w", encoding="utf-8") as out:
        try:
            ocr = make_ocr()
            out.write("OCR engine: %s\n" % ocr.name)
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
        self.reader = Reader(self.ocr)
        self.paused = False
        self.quit = threading.Event()
        self.read_all = threading.Event()
        self.lock = threading.Lock()

    def hotkeys(self):
        import keyboard
        keyboard.add_hotkey("ctrl+shift+r", self.speaker.repeat)
        keyboard.add_hotkey("ctrl+shift+s", self.read_all.set)
        keyboard.add_hotkey("ctrl+shift+p", self.toggle_pause)
        keyboard.add_hotkey("ctrl+shift+q", self.quit.set)

    def toggle_pause(self):
        self.paused = not self.paused
        self.speaker.say("Reading paused" if self.paused else "Reading resumed")
        if not self.paused:
            self.reader = Reader(self.ocr)

    def run(self):
        import mss
        self.hotkeys()
        self.speaker.say("Avatar reader started. Control shift Q to quit.")
        black_since = None
        warned_black = False
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while not self.quit.is_set():
                start = time.perf_counter()
                try:
                    frame = np.asarray(sct.grab(monitor))[:, :, :3]
                    if frame.max() < 12:
                        black_since = black_since or time.time()
                        if not warned_black and time.time() - black_since > BLACK_WARN_SECONDS:
                            warned_black = True
                            self.speaker.say("The screen looks black to me. If the game is in exclusive "
                                             "fullscreen, set its display mode to borderless or windowed.")
                    else:
                        black_since = None
                    if self.read_all.is_set():
                        self.read_all.clear()
                        text = self.reader.read_whole_screen(cv2.resize(frame, (1920, 1080)))
                        self.speaker.say(text or "No text found")
                    elif not self.paused:
                        for text, interrupt in self.reader.process(np.ascontiguousarray(frame)):
                            self.speaker.say(text, interrupt)
                except Exception:
                    log.error(traceback.format_exc())
                    time.sleep(0.5)
                time.sleep(max(0.0, POLL_SECONDS - (time.perf_counter() - start)))
        self.speaker.say("Avatar reader closed.")
        time.sleep(1.5)


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
