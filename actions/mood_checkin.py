"""Mood check-in tool (PRD 7B). Self-reported 1-5 wellness indicators, not medical measurements."""
from core import wellness_store as store

TOOL_NAME = "log_mood_checkin"


def log_mood_checkin(parameters: dict, player=None) -> str:
    p = parameters or {}
    vals = {k: p.get(k) for k in ("mood", "energy", "stress", "sleep")}
    if not any(v is not None and str(v).strip() != "" for v in vals.values()):
        return ("No ratings were given. Ask the user, one at a time and gently, how their mood, energy, "
                "stress and sleep feel today on a scale of 1 (very difficult) to 5 (very good).")
    saved = store.add_checkin(note=p.get("note", ""), **vals)
    if player:
        try:
            shown = ", ".join(f"{k} {v}" for k, v in vals.items() if v not in (None, ""))
            player.write_log(f"SYS: Check-in noted ({shown})" + ("" if saved else " — not saved"))
        except Exception:
            pass
    if saved:
        return ("Check-in saved on this device. These are self-reported indicators, not a medical measurement. "
                "Reflect back what the user said in your own words, without interpreting it clinically.")
    return ("The check-in was NOT saved because the user has not turned on wellness tracking. Use what they told you "
            "in this conversation, and only if it fits, offer once to turn tracking on (manage_wellness_data "
            "action 'enable_tracking') so check-ins can be kept. Do not push.")


TOOL = {
    "name": TOOL_NAME,
    "description": (
        "Record a mood check-in: mood, energy, stress and sleep quality, each 1-5 (1 very difficult, 5 very good), "
        "plus an optional short note. Call after the user has shared how they are, or when they ask for a check-in. "
        "These are self-reported wellness indicators, never a diagnosis. Values only if the user gave them."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mood":   {"type": "INTEGER", "description": "1-5"},
            "energy": {"type": "INTEGER", "description": "1-5"},
            "stress": {"type": "INTEGER", "description": "1-5 (5 = a lot of stress)"},
            "sleep":  {"type": "INTEGER", "description": "1-5 sleep quality"},
            "note":   {"type": "STRING",  "description": "Optional short note in the user's own words, max ~200 chars"},
        },
        "required": [],
    },
    "handler": log_mood_checkin,
}
