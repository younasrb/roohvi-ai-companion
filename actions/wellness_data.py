"""Privacy controls (PRD 11-12): consent, export, delete."""
from core import wellness_store as store, confirm as confirm_gate


def manage_wellness_data(parameters: dict, player=None) -> str:
    action = str((parameters or {}).get("action", "status")).strip().lower()

    if action == "status":
        r = store.recent(3650)
        return (f"Wellness tracking is {'ON' if store.is_tracking() else 'OFF'}. "
                f"{len(r['checkins'])} check-ins and {len(r['activities'])} activities are stored on this device only.")
    if action == "enable_tracking":
        store.set_tracking(True)
        return ("Tracking is ON. Check-ins and finished activities will be kept on this device only; "
                "the user can export or delete them any time.")
    if action == "disable_tracking":
        store.set_tracking(False)
        return "Tracking is OFF. Nothing new will be saved. Existing data stays until they delete it."
    if action == "export":
        text = store.export_text()
        if player:
            try:
                player.show_content("YOUR DATA (EXPORT)", text[:6000])
            except Exception:
                pass
        return "Their wellness data is now shown on screen. It is stored only in memory/wellness.json on this device."
    if action == "delete_checkins":
        return confirm_gate.request("delete_checkins", "Delete check-in history",
                                    "Permanently deletes all saved check-ins and activities.",
                                    lambda: (store.delete_checkins_and_activities() or "Check-in history deleted."))
    if action == "delete_everything":
        return confirm_gate.request("delete_everything", "Delete ALL my data",
                                    "Permanently deletes check-ins, activities, everything Roohvi remembers about you, "
                                    "and safety counters from this device.",
                                    lambda: (store.delete_everything() or "All Roohvi data deleted."))
    return "Unknown action. Use status, enable_tracking, disable_tracking, export, delete_checkins or delete_everything."


TOOL = {
    "name": "manage_wellness_data",
    "description": (
        "Privacy controls. action: status | enable_tracking | disable_tracking | export | delete_checkins | delete_everything. "
        "Use enable_tracking ONLY after the user clearly agrees to have check-ins saved. Use delete_* when they ask to "
        "erase their history or everything you remember; a confirmation button appears on screen and nothing is deleted "
        "until they press it."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "description": "status | enable_tracking | disable_tracking | export | delete_checkins | delete_everything"}},
        "required": ["action"]},
    "handler": manage_wellness_data,
}
