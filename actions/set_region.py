"""Remember the user's country so local helplines come first (PRD 7F)."""
from memory import config_manager


def set_region(parameters: dict, player=None) -> str:
    code = str((parameters or {}).get("country_code", "")).strip().upper()
    import re as _re
    if not _re.fullmatch(r"[A-Z]{2}(-[A-Z]{2})?", code):
        return "Need a country code such as PK, US, GB, IN (or PK-SD / PK-PB for a Pakistani province). Ask the user which country or city they are in."
    config_manager.save_region(code)
    return (f"Region saved as {code}. Support resources will now show {code} helplines first. "
            "Say this in one short sentence.")


TOOL = {
    "name": "set_region",
    "description": ("Save where the user is so the right helplines are shown: a country code like PK, US, GB, IN, or for Pakistan "
                    "a province code (PK-SD for Sindh/Karachi, PK-PB for Punjab/Lahore/Islamabad area). Ask once, lightly, only when "
                    "resources are needed and the region is unknown or wrong."),
    "parameters": {"type": "OBJECT", "properties": {
        "country_code": {"type": "STRING", "description": "PK, US, GB, IN ... or PK-SD / PK-PB"}}, "required": ["country_code"]},
    "handler": set_region,
}
