"""Settings for the accessibility menu, saved next to the program."""
import json
import logging
import os

log = logging.getLogger("settings")

DEFAULTS = {
    "fight_sounds": True,       # all fight sounds and announcements
    "my_side": 1,               # 1 or 2: which player is you
    "flow_sound": True,
    "energy_sound": True,
    "health_sound": "both",     # alert at 30 percent: "both", "mine", "off"
    "opponent_sounds": False,   # opponent's Flow and energy sounds
    "combos": True,             # announce hits and damage
    "tutorial_text": True,
    "health_volume": 70,        # 0 to 100, each kind of sound separately
    "energy_volume": 70,
    "flow_volume": 70,
    "opponent_volume": 40,      # opponent's Flow and energy, compared with yours
}


class Settings:
    def __init__(self, folder):
        self.path = os.path.join(folder, "settings.json")
        self.values = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as fh:
                saved = json.load(fh)
            for k, v in saved.items():
                if k in DEFAULTS and type(v) == type(DEFAULTS[k]):
                    self.values[k] = v
            if "my_volume" in saved and "health_volume" not in saved:
                # Older versions had one volume for all your sounds.
                for k in ("health_volume", "energy_volume", "flow_volume"):
                    self.values[k] = int(saved["my_volume"])
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning("settings not loaded: %s", e)

    def volumes(self):
        return {"health": self["health_volume"], "energy": self["energy_volume"],
                "flow": self["flow_volume"], "opponent": self["opponent_volume"]}

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value
        self.save()

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.values, fh, indent=2)
        except Exception as e:
            log.warning("settings not saved: %s", e)
