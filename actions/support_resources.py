"""Professional / crisis resource finder (PRD 7F, 7G)."""
from core import resources


def find_support_resources(parameters: dict, player=None) -> str:
    p = parameters or {}
    urgency = str(p.get("urgency", "support")).lower()
    region = str(p.get("region", "")).strip()
    kind = {"crisis": "crisis", "emergency": "emergency", "support": "counselling", "abuse": "abuse"}.get(urgency, "counselling")
    recs = resources.find(region, kind)
    if urgency == "crisis":   # crisis card always includes emergency numbers first
        recs = resources.find(region, "emergency") + [r for r in resources.find(region, "crisis") if not r.get("emergency")]
    text = resources.format_for_screen(recs)
    title = "SUPPORT NOW" if urgency in ("crisis", "emergency") else "SUPPORT RESOURCES"
    if player:
        try:
            player.show_content(title, text)
        except Exception:
            pass
    spoken = "; ".join(f"{r['name']} {r['contact']}" for r in recs[:4])
    return (f"Resources are now on the user's screen. Say the one or two most relevant ones aloud, slowly, "
            f"for example: {spoken}. Tell them numbers and availability depend on their location and should be confirmed. "
            f"Do not read the whole list. If they are in immediate danger, emergency services come first and a trusted "
            f"person nearby comes second. Region used: {region or resources.default_region()} "
            f"(ask which country they are in if that is wrong).")


TOOL = {
    "name": "find_support_resources",
    "description": (
        "Show professional, counselling, crisis-helpline or emergency resources for the user's region. Call with "
        "urgency='crisis' whenever there are signs of possible self-harm or danger, or [SAFETY_POLICY] says so. Call "
        "with urgency='abuse' when the user mentions violence or abuse at home or from someone close; "
        "with urgency='support' when the user asks where to find a counsellor or a professional, or when distress "
        "seems persistent. region is an ISO country code such as PK, US, GB, IN; omit to use the saved region."),
    "parameters": {"type": "OBJECT", "properties": {
        "urgency": {"type": "STRING", "description": "crisis | emergency | support | abuse"},
        "region": {"type": "STRING", "description": "Country code like PK, US, GB, IN (optional)"}},
        "required": ["urgency"]},
    "handler": find_support_resources,
}
