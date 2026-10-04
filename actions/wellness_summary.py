"""Weekly wellness summary (PRD 7D): plain averages, only with enough data, no scores."""
from core import wellness_store as store


def wellness_summary(parameters: dict, player=None) -> str:
    days = 7
    try:
        days = max(1, min(30, int((parameters or {}).get("days", 7))))
    except Exception:
        pass
    if not store.is_tracking():
        return ("Wellness tracking is off, so nothing has been kept. Tell the user, and offer once to turn it on "
                "(manage_wellness_data action 'enable_tracking') if they want a history.")
    r = store.recent(days)
    n = len(r["checkins"])
    if n == 0:
        return "No check-ins in that period yet. Offer a quick check-in."
    avg = store.averages(r["checkins"])
    done = {}
    for a in r["activities"]:
        done[a["kind"]] = done.get(a["kind"], 0) + 1
    lines = [f"Last {days} days: {n} check-in(s)."]
    if avg:
        lines.append("Averages (1-5, self-reported): " + ", ".join(f"{k} {v}" for k, v in avg.items()))
    else:
        lines.append("Not enough check-ins yet for averages (need 3).")
    if done:
        lines.append("Activities tried: " + ", ".join(f"{k} x{v}" for k, v in done.items()))
    text = "\n".join(lines)
    if player:
        try:
            player.show_content("YOUR WEEK", text + "\n\nSelf-reported indicators, not medical measurements.")
        except Exception:
            pass
    return (text + "\nDescribe this plainly and kindly. These are NOT medical measurements: do not interpret them "
            "clinically, do not call them a score, and do not shame a quiet week.")


TOOL = {
    "name": "wellness_summary",
    "description": ("Summarise the user's recent check-ins (averages and activities tried) when they ask how their "
                    "week has been or to see their trend. Plain numbers only; never a diagnosis."),
    "parameters": {"type": "OBJECT", "properties": {
        "days": {"type": "INTEGER", "description": "Look-back window in days, default 7"}}, "required": []},
    "handler": wellness_summary,
}
