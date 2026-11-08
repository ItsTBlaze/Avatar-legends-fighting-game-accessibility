"""Speech output: NVDA first, Windows' own voice (SAPI) as a fallback."""
import ctypes
import os
import sys
import logging
import time

log = logging.getLogger("speech")


def _here():
    # Packaged program: bundled files live in the unpack folder (sys._MEIPASS).
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


class Nvda:
    name = "NVDA"

    def __init__(self):
        dll = "nvdaControllerClient64.dll" if ctypes.sizeof(ctypes.c_void_p) == 8 else "nvdaControllerClient32.dll"
        self.lib = ctypes.windll.LoadLibrary(os.path.join(_here(), "lib", dll))
        self.lib.nvdaController_speakText.argtypes = (ctypes.c_wchar_p,)
        self.lib.nvdaController_brailleMessage.argtypes = (ctypes.c_wchar_p,)

    def running(self):
        try:
            return self.lib.nvdaController_testIfRunning() == 0
        except Exception:
            return False

    def speak(self, text, interrupt=True):
        if interrupt:
            self.lib.nvdaController_cancelSpeech()
        self.lib.nvdaController_speakText(text)
        try:
            self.lib.nvdaController_brailleMessage(text)
        except Exception:
            pass


class Sapi:
    name = "Windows voice"

    def __init__(self):
        import comtypes.client
        self.voice = comtypes.client.CreateObject("SAPI.SpVoice")

    def running(self):
        return True

    def speak(self, text, interrupt=True):
        # 1 = speak asynchronously, 2 = purge anything still being spoken
        self.voice.Speak(text, 1 | (2 if interrupt else 0))


class Printer:
    name = "console"

    def running(self):
        return True

    def speak(self, text, interrupt=True):
        print(">>", text, flush=True)


class Speaker:
    def __init__(self):
        self.nvda = self.sapi = None
        try:
            self.nvda = Nvda()
        except Exception as e:
            log.warning("NVDA library not loaded: %s", e)
        try:
            self.sapi = Sapi()
        except Exception as e:
            log.warning("Windows voice not available: %s", e)
        self.printer = Printer()
        self.last = ""
        self.last_time = 0.0

    def _out(self):
        if self.nvda and self.nvda.running():
            return self.nvda
        return self.sapi or self.printer

    def say(self, text, interrupt=True):
        if not text:
            return
        now = time.monotonic()
        if text == self.last and now - self.last_time < 1.5:
            return      # the same words again straight away: skip the echo
        self.last = text
        self.last_time = now
        log.info("SAY: %s", text)
        try:
            self._out().speak(text, interrupt)
        except Exception as e:
            log.error("speech failed: %s", e)

    def repeat(self):
        if self.last:
            self._out().speak(self.last, True)
