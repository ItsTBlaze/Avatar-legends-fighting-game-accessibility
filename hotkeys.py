"""Global hotkeys through Windows' own RegisterHotKey.

Earlier versions used a keyboard hook, which sees every key pressed in every
program. While the reader was busy reading the screen, that hook could delay
keys on their way to NVDA and make it act strangely. Registered hotkeys only
ever see the keys listed here, and Windows delivers them without any delay
to other programs.
"""
import ctypes
import ctypes.wintypes as wt
import logging
import queue
import threading

log = logging.getLogger("hotkeys")

MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0002, 0x0004, 0x4000
WM_HOTKEY, WM_USER = 0x0312, 0x0400

VK = {"f3": 0x72, "r": 0x52, "s": 0x53, "p": 0x50, "q": 0x51, "g": 0x47, "d": 0x44,
      "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "enter": 0x0D, "esc": 0x1B}


def parse(combo):
    """'ctrl+shift+r' -> (modifiers, virtual key)."""
    mods = MOD_NOREPEAT
    key = None
    for part in combo.lower().split("+"):
        if part == "ctrl":
            mods |= MOD_CONTROL
        elif part == "shift":
            mods |= MOD_SHIFT
        else:
            key = VK[part]
    return mods, key


class Hotkeys(threading.Thread):
    """Runs a small Windows message loop. Hotkeys can be added and removed
    from any thread; callbacks run on this thread, so keep them short."""

    def __init__(self):
        super().__init__(daemon=True)
        self.user32 = ctypes.windll.user32
        self.callbacks = {}
        self.next_id = 1
        self.requests = queue.Queue()
        self.thread_id = None
        self.ready = threading.Event()
        self.lock = threading.Lock()

    def add(self, combo, callback):
        with self.lock:
            hid = self.next_id
            self.next_id += 1
        self._request(("add", hid, combo, callback))
        return hid

    def remove(self, hid):
        self._request(("remove", hid, None, None))

    def _request(self, req):
        if threading.current_thread() is self:
            self._apply(req)                 # asked from a hotkey callback
            return
        self.ready.wait(5)
        self.requests.put(req)
        self.user32.PostThreadMessageW(self.thread_id, WM_USER, 0, 0)

    def _apply(self, req):
        what, hid, combo, callback = req
        if what == "add":
            mods, vk = parse(combo)
            if self.user32.RegisterHotKey(None, hid, mods, vk):
                self.callbacks[hid] = callback
            else:
                log.warning("could not register %s (another program may use it)", combo)
        else:
            if self.callbacks.pop(hid, None) is not None:
                self.user32.UnregisterHotKey(None, hid)

    def run(self):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wt.MSG()
        # Make sure this thread has a message queue before anyone posts to it.
        self.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self.ready.set()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_USER:
                while not self.requests.empty():
                    self._apply(self.requests.get())
            elif msg.message == WM_HOTKEY:
                cb = self.callbacks.get(msg.wParam)
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        log.error("hotkey: %s", e)
