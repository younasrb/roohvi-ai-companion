"""Low-risk coping activities (PRD 7C). Education and self-guided practice, never treatment."""
from core import wellness_store as store

ACTIVITIES = {
    "breathing": ("Slow breathing (about 2 minutes)",
        ["Sit comfortably and let your shoulders drop.",
         "Breathe in gently through your nose for 4 counts.",
         "Breathe out slowly through your mouth for 6 counts.",
         "Repeat for about 6 breaths, letting the out-breath be a little longer than the in-breath.",
         "Notice if anything feels even slightly softer. If breathing exercises feel uncomfortable, stop."]),
    "grounding": ("5-4-3-2-1 grounding",
        ["Look around and name 5 things you can see.",
         "Name 4 things you can feel, like your feet on the floor or the chair under you.",
         "Name 3 things you can hear.",
         "Name 2 things you can smell, or like the smell of.",
         "Name 1 thing you can taste, or one slow breath. Then notice where you are right now."]),
    "mindfulness": ("One-minute mindful pause",
        ["Put down what you are holding and let your eyes rest on one spot.",
         "Follow three natural breaths without changing them.",
         "When a thought arrives, label it 'thinking' and come back to the breath.",
         "Finish by noticing how your body feels."]),
    "journaling": ("Three-line journal",
        ["Write one sentence on what is on your mind.",
         "Write one sentence on what you need right now (rest, a plan, someone to talk to).",
         "Write one small thing you can do in the next hour.",
         "You do not have to keep or share this."]),
    "sleep": ("Sleep wind-down (education, not treatment)",
        ["Keep a regular time to go to bed and to wake up.",
         "Dim lights and put screens away for 30 minutes before bed if you can.",
         "Try to keep caffeine to the earlier part of the day.",
         "If you are awake and restless, get up, do something quiet and dim, and return when sleepy.",
         "If sleep trouble goes on for weeks, a doctor is the right person to talk to."]),
    "break": ("Reset break (5 minutes)",
        ["Stand up and step away from what you were doing.",
         "Drink some water and stretch your neck, shoulders and hands.",
         "Look at something far away for 20 seconds.",
         "Decide the very next small step, and only that."]),
    "social": ("Reach out to one person",
        ["Think of one person who feels safe, even if you have not talked in a while.",
         "Send a short message, such as: 'Thinking of you, do you have time for a chat this week?'",
         "It does not have to be about how you feel. Connection counts.",
         "If nobody comes to mind, a helpline or community group is also a real option."]),
    "study_work": ("Study / work overwhelm: one small block",
        ["Write everything on your mind in a quick list, no ordering.",
         "Circle the single item that matters most today.",
         "Set a 20-minute timer for just that item.",
         "When it ends, take a 5-minute break before deciding what is next."]),
}
ALIASES = {"breathe": "breathing", "anxiety": "breathing", "panic": "grounding", "stress": "breathing",
           "meditation": "mindfulness", "journal": "journaling", "writing": "journaling", "insomnia": "sleep",
           "rest": "break", "lonely": "social", "loneliness": "social", "study": "study_work", "work": "study_work",
           "exam": "study_work", "burnout": "study_work"}


def coping_activity(parameters: dict, player=None) -> str:
    p = parameters or {}
    kind = str(p.get("activity", "")).strip().lower().replace(" ", "_").replace("-", "_")
    kind = ALIASES.get(kind, kind)
    if p.get("completed") in (True, "true", "True"):
        if kind in ACTIVITIES and store.add_activity(kind):
            return "Noted that they did it. Acknowledge it warmly without making it a streak or a grade."
        return "Fine, nothing stored. Acknowledge it warmly."
    if kind not in ACTIVITIES:
        return ("Unknown activity. Available: " + ", ".join(ACTIVITIES)
                + ". Pick the lowest-risk one that fits what the user described and offer it as optional.")
    title, steps = ACTIVITIES[kind]
    body = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    orb = False
    if player:
        try:
            if kind == "breathing" and hasattr(player, "show_breathing"):
                player.show_breathing()          # a slow circle on screen sets the pace
                orb = True
            else:
                player.show_content(title.upper(), body + "\n\nOptional. You can stop any time.")
        except Exception:
            pass
    orb_note = (" A slow breathing circle is now on the user's screen and sets the pace (in 4, hold 1, out 6, six breaths). "
                "Invite them to follow the circle, say very little while it runs, and check in gently when it ends. ") if orb else ""
    return (orb_note + f"{title}. Offer it as optional and say briefly why it might help, without claiming it treats anything. "
            f"Guide the user through it ONE step at a time, in your own words and the user's language, pausing for them. "
            f"If they say it is not working or they feel worse, stop and ask what would help instead.\n{body}")


TOOL = {
    "name": "coping_activity",
    "description": (
        "Start a short, low-risk coping activity the user can choose or dismiss. activity is one of: breathing, grounding, "
        "mindfulness, journaling, sleep, break, social, study_work. Pick what fits (stress/anxious feelings -> breathing or "
        "grounding; racing thoughts -> journaling; loneliness -> social; exams/work -> study_work). Offer it first; "
        "set completed=true only after the user says they did it. Never present it as treatment."),
    "parameters": {"type": "OBJECT", "properties": {
        "activity": {"type": "STRING", "description": "breathing | grounding | mindfulness | journaling | sleep | break | social | study_work"},
        "completed": {"type": "BOOLEAN", "description": "true only when the user says they finished it"}},
        "required": ["activity"]},
    "handler": coping_activity,
}
