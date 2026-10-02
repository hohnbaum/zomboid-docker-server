import math
import re
from pzops.ini import Ini
from pzops.util import read_json


def settings(layout):
    ini = Ini.read(layout.ini)
    # Explicit safe display fields: never return the raw configuration.
    allowed = {"MaxPlayers", "PVP", "PauseEmpty", "PlayerSafehouse", "SleepAllowed", "SleepNeeded"}
    values = {k: literal(ini.get(k)) for k in allowed if k in ini.values and literal(ini.get(k)) is not None}
    world = sandbox((layout.ini.with_name(layout.server + "_SandboxVars.lua")).read_text(encoding="utf-8-sig")) if layout.ini.with_name(layout.server + "_SandboxVars.lua").is_file() else {}
    return {"server": layout.server, "settings": values, "world": world, "managed": ini.mod_state(),
            "imported": bool(read_json(layout.data / ".import-complete.json"))}


def literal(value):
    value = value.strip()
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if len(value) > 32 or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return None
    result = float(value) if "." in value else int(value)
    return result if math.isfinite(result) else None


def sandbox(text):
    roots = {"DayLength", "MultiHitZombies", "StarterKit", "Nutrition", "MinutesPerPage", "InjurySeverity", "Zombies", "ZombieRespawn", "WaterShut", "ElecShut", "FoodLootNew", "HoursForCorpseRemoval", "FireSpread", "EnableVehicles", "CarSpawnRate", "VehicleEasyUse", "InitialGas", "CarGeneralCondition", "HoursForLootRespawn"}
    sections = {"ZombieLore": {"Speed", "Strength", "Toughness", "Cognition", "Transmission", "Mortality"}, "ZombieConfig": {"PopulationMultiplier"}}
    result, section = {}, None
    for line in text.splitlines():
        clean = line.split("--", 1)[0]
        match = re.fullmatch(r"    (ZombieLore|ZombieConfig)\s*=\s*\{\s*", clean)
        if match:
            section = match[1]
            continue
        if re.fullmatch(r"    },?\s*", clean):
            section = None
            continue
        match = re.fullmatch(r"( +)([A-Za-z_]+)\s*=\s*([^,]+),?\s*", clean)
        if not match:
            continue
        indent, key, raw = match.groups()
        val = literal(raw)
        if val is not None and ((section is None and len(indent) == 4 and key in roots) or (section and len(indent) == 8 and key in sections[section])):
            result[(section + "." if section else "") + key] = val
    return result
