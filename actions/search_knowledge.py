"""Search the reviewed Roohvi knowledge base and answer with a source."""
from core import knowledge
from core.knowledge import first_line


def search_knowledge(parameters: dict, player=None) -> str:
    q = str((parameters or {}).get("query", "")).strip()
    if not q:
        return "No query given."
    hits = knowledge.search(q, limit=2)
    if not hits:
        return ("Nothing reviewed in the knowledge base matches this. Do NOT invent facts. Answer only from "
                "general, non-clinical warmth and, if it fits, suggest a professional (find_support_resources). "
                "Be honest that you do not have a reliable source on this.")
    parts, screen = [], []
    for e in hits:
        on_screen = not (e.get('audience') or '').lower().startswith('model')
        parts.append(
            f"[{e['id'] or e['title']}] {e['title']}\n{e['body']}\n"
            + (f"When to get help: {e['caution']}\n" if e["caution"] else "")
            + (f"Not for: {e['avoid']}\n" if e["avoid"] else "")
            + f"Source: {first_line(e['source_note']) or first_line(e['source'])} ({first_line(e['source'])})")
        if on_screen:
            screen.append(f"{e['title']}\n{e['body']}\n\nSource: {first_line(e['source_note']) or first_line(e['source'])}\n{e['source']}")
    if player and screen:
        try:
            player.show_content("FROM THE KNOWLEDGE BASE", "\n\n---\n\n".join(screen))
        except Exception:
            pass
    return ("Use ONLY the material below. Remarks addressed to the writers or team lead (such as 'Note for the team lead', "
            "'UNVERIFIED', or 'to be confirmed') are NOT for the user: ignore them, never repeat them, and get phone numbers only from "
            "find_support_resources. Say it in your own words, in the user's language, gently and briefly. "
            "Mention the source by NAME (not the URL) in one short clause, and say the user can read more on screen. "
            "Do not add diagnoses, medication advice or promises. Include the 'when to get help' part if present.\n\n"
            + "\n\n====\n\n".join(parts))


TOOL = {
    "name": "search_knowledge",
    "description": (
        "Look up reviewed wellness information (coping techniques, stress/sleep/loneliness explainers, how to find "
        "professional help, safe ways to support someone, how to respond to risk). Call it BEFORE explaining a technique or giving "
        "general wellness information. Write the query as a few ENGLISH keywords even if the user speaks Urdu. If it returns nothing, do not make "
        "facts up."),
    "parameters": {"type": "OBJECT", "properties": {
        "query": {"type": "STRING", "description": "What the user needs, a few keywords"}}, "required": ["query"]},
    "handler": search_knowledge,
}
