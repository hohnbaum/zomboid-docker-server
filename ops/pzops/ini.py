import re
from pathlib import Path
from pzops.util import PZError

KEYS = {"WorkshopItems": "WorkshopItems", "Mods": "Mods", "Maps": "Map"}


class Ini:
    def __init__(self, data):
        self.data = data
        self.bom = data.startswith(b"\xef\xbb\xbf")
        try:
            self.lines = data[(3 if self.bom else 0):].decode("utf-8").splitlines(keepends=True)
        except UnicodeError:
            raise PZError("INI_ENCODING") from None
        self.values = {}
        self.positions = {}
        for i, line in enumerate(self.lines):
            if line.lstrip().startswith(("#", ";")):
                continue
            k, sep, value = line.rstrip("\r\n").partition("=")
            if sep:
                key = k.strip()
                if key in self.values:
                    raise PZError("DUPLICATE_INI_KEY")
                self.values[key] = value
                self.positions[key] = i

    @classmethod
    def read(cls, path):
        try:
            return cls(Path(path).read_bytes())
        except OSError:
            raise PZError("INI_MISSING") from None

    def get(self, key, default=None):
        if key not in self.values and default is None:
            raise PZError("INI_KEY_MISSING")
        return self.values.get(key, default)

    def mod_state(self):
        result = {}
        for prop, key in KEYS.items():
            items = [x.strip() for x in self.get(key).split(";") if x.strip()]
            if len(items) != len(set(items)):
                raise PZError("DUPLICATE_MOD_ENTRY")
            if prop == "WorkshopItems" and any(not re.fullmatch(r"[0-9]+", x) for x in items):
                raise PZError("INVALID_WORKSHOP_ID")
            result[prop] = items
        if not result["Maps"]:
            raise PZError("EMPTY_MAPS")
        return result

    def replace(self, changes):
        lines = self.lines[:]
        for key, value in changes.items():
            if key not in self.positions or "\r" in value or "\n" in value:
                raise PZError("INVALID_INI_EDIT")
            i = self.positions[key]
            line = lines[i]
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            prefix = line.split("=", 1)[0] + "="
            lines[i] = prefix + value + ending
        return (b"\xef\xbb\xbf" if self.bom else b"") + "".join(lines).encode("utf-8")

    def with_state(self, state):
        return self.replace({key: ";".join(state[prop]) for prop, key in KEYS.items()})
