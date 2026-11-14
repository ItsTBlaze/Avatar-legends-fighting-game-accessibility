"""Short sound cues: made with code, or your own WAV files.

Each cue is a stereo WAV written once to a temporary folder and played with
Windows' own player. Each kind of sound has its own volume. Your cues come
from your side; the opponent's come from their side.

Put a WAV file with the right name in the "Custom sounds" folder (next to
the program) and it's used instead of the built-in sound. See
CUSTOM_HELP below for the names.
"""
import io
import logging
import math
import os
import struct
import tempfile
import wave

import numpy as np

log = logging.getLogger("sounds")
RATE = 44100
MAX_SECONDS = 4.0          # longer custom sounds are cut short

CUSTOM_HELP = """Custom sounds for Avatar Reader

Put your own sounds in this folder to use them instead of the built-in ones.
They must be WAV files (most sound editors, such as Audacity, can save as WAV).
Name each file after the sound it replaces:

  health_low.wav     your health drops to 30 percent
  flow_full.wav      your Flow gauge is full again
  energy.wav         you gain energy (any level)
  energy_1.wav ... energy_7.wav   a different sound for each energy level (optional)

For your opponent, add _opponent to the name, for example
health_low_opponent.wav or energy_opponent.wav. If there is no opponent file,
your opponent gets the same sound as you, coming from their side.

The volumes in the accessibility menu still apply. Sounds longer than 4
seconds are cut short. New or changed files are picked up the next time you
open the accessibility menu (F3) or start Avatar Reader. To go back to a
built-in sound, delete or rename its file.
"""


def _custom_candidates(name):
    """'energy_3_p2' -> file names to look for, most specific first."""
    base, side = name.rsplit("_", 1)
    general = "energy" if base.startswith("energy_") else None
    names = []
    if side == "p2":
        names += [base + "_opponent.wav"] + ([general + "_opponent.wav"] if general else [])
    names += [base + ".wav"] + ([general + ".wav"] if general else [])
    return names


def load_custom(path, vol, pan):
    """Read a WAV file and return it as stereo 16-bit WAV bytes at the given
    volume (0-1) and pan (-1 left, +1 right). None if it can't be read."""
    try:
        with wave.open(path, "rb") as w:
            ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(min(w.getnframes(), int(rate * MAX_SECONDS)))
        if width == 1:
            x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
        elif width == 2:
            x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
        elif width == 3:
            b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            x = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / (1 << 23)
        elif width == 4:
            x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
        else:
            return None
        mono = x.reshape(-1, ch).mean(axis=1)
        left = mono * (1.0 - max(0.0, pan)) * vol
        right = mono * (1.0 + min(0.0, pan)) * vol
        pcm = (np.clip(np.stack([left, right], axis=1), -1, 1) * 32767).astype("<i2")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(pcm.tobytes())
        return buf.getvalue()
    except Exception as e:
        log.warning("custom sound %s not used: %s", os.path.basename(path), e)
        return None


def _tone(freqs, dur, vol=0.5, pan=0.0, attack=0.005, decay=6.0, gap=0.0):
    """A soft bell-like note (or notes played one after another)."""
    left = (1.0 - max(0.0, pan)) * vol
    right = (1.0 + min(0.0, pan)) * vol
    frames = []
    for f in freqs:
        n = int(RATE * dur)
        for i in range(n):
            t = i / RATE
            env = min(1.0, t / attack) * math.exp(-decay * t)
            s = math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t)
            s *= env / 1.3
            frames.append((int(32767 * s * left), int(32767 * s * right)))
        frames.extend([(0, 0)] * int(RATE * gap))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<hh", l, r) for l, r in frames))
    return buf.getvalue()


# Notes for energy levels 1 to 7: a rising scale.
_SCALE = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66]


def cue_bank(volumes, my_side=1):
    """name -> wav bytes. 'p1' is you, 'p2' your opponent; each comes from
    that player's side of the screen (Player 1 left, Player 2 right).

    volumes: 0-100 for "health", "energy" and "flow", and "opponent", how
    loud the opponent's Flow and energy sounds are compared with yours."""
    bank = {}
    mine = -0.7 if my_side == 1 else 0.7

    def amp(kind, opponent=False):
        v = max(0, min(100, volumes.get(kind, 70))) / 100.0
        if opponent:
            v *= max(0, min(100, volumes.get("opponent", 40))) / 100.0
        return 0.8 * v

    for side, pan in (("p1", mine), ("p2", -mine)):
        opp = side == "p2"
        # Flow gauge full again: a quick rising two-note chime.
        bank["flow_full_" + side] = _tone([988.0, 1480.0], 0.11, amp("flow", opp), pan, decay=9.0)
        # Energy gained: one plucked note, higher for each level.
        for lvl, f in enumerate(_SCALE, 1):
            bank["energy_%d_%s" % (lvl, side)] = _tone([f * 0.5], 0.22, amp("energy", opp), pan, decay=10.0)
    # Health down to 30 percent: a two-tone alarm played twice, at full health
    # volume for both fighters. Yours is higher; your opponent's is lower and
    # comes from their side.
    bank["health_low_p1"] = _tone([784.0, 587.0, 784.0, 587.0], 0.12, amp("health"), mine, decay=4.0)
    bank["health_low_p2"] = _tone([392.0, 294.0, 392.0, 294.0], 0.12, amp("health"), -mine, decay=4.0)
    return bank


def custom_bank(folder, volumes, my_side=1):
    """name -> wav bytes for the cues that have a custom file."""
    bank = {}
    if not folder or not os.path.isdir(folder):
        return bank
    files = {f.lower(): os.path.join(folder, f) for f in os.listdir(folder)}
    mine = -0.7 if my_side == 1 else 0.7
    names = ["health_low", "flow_full"] + ["energy_%d" % i for i in range(1, 8)]
    for base in names:
        kind = base.split("_")[0]
        for side in ("p1", "p2"):
            name = "%s_%s" % (base, side)
            for cand in _custom_candidates(name):
                if cand in files:
                    vol = max(0, min(100, volumes.get(kind, 70))) / 100.0
                    if side == "p2" and kind != "health":
                        vol *= max(0, min(100, volumes.get("opponent", 40))) / 100.0
                    data = load_custom(files[cand], 0.9 * vol, mine if side == "p1" else -mine)
                    if data:
                        bank[name] = data
                    break
    return bank


class Player:
    def __init__(self, volumes=None, my_side=1, custom_folder=None):
        self.ok = False
        self.paths = {}
        self.custom_folder = custom_folder
        self.volumes, self.my_side = volumes or {}, my_side
        try:
            import winsound
            self.winsound = winsound
            self.folder = os.path.join(tempfile.gettempdir(), "AvatarReaderSounds")
            os.makedirs(self.folder, exist_ok=True)
            self._help_file()
            self.rebuild(self.volumes, my_side)
            self.ok = True
        except Exception as e:
            log.warning("sound cues unavailable: %s", e)

    def _help_file(self):
        if not self.custom_folder:
            return
        try:
            os.makedirs(self.custom_folder, exist_ok=True)
            path = os.path.join(self.custom_folder, "How to use custom sounds.txt")
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(CUSTOM_HELP)
        except Exception as e:
            log.warning("custom sounds folder: %s", e)

    def rebuild(self, volumes=None, my_side=None):
        """Write the cue files again: new volumes, the other side, or new
        custom sounds."""
        if volumes is not None:
            self.volumes = volumes
        if my_side is not None:
            self.my_side = my_side
        bank = cue_bank(self.volumes, self.my_side)
        custom = custom_bank(self.custom_folder, self.volumes, self.my_side)
        bank.update(custom)
        if custom:
            log.info("custom sounds: %s", ", ".join(sorted(custom)))
        import hashlib
        for name, data in bank.items():
            digest = hashlib.md5(data).hexdigest()[:12]      # same sound, same file
            path = os.path.join(self.folder, "%s_%s.wav" % (name, digest))
            if not os.path.exists(path):
                with open(path, "wb") as fh:
                    fh.write(data)
            self.paths[name] = path

    def play(self, name):
        log.info("CUE: %s", name)
        if not self.ok or name not in self.paths:
            return
        try:
            ws = self.winsound
            ws.PlaySound(self.paths[name], ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_NODEFAULT)
        except Exception as e:
            log.error("sound failed: %s", e)
