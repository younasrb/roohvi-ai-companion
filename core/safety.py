"""
Roohvi — safety layer.

Implements the PRD's policy pipeline around the live voice session:

    user words -> input screen -> risk category -> response policy
                                                    |-> crisis card in the UI
                                                    |-> [SAFETY_POLICY] note to the model
    model words -> output check -> flags (logged, never the text)

IMPORTANT LIMITS (these are product facts, not footnotes):
  * This is a transparent keyword/phrase screen, NOT a clinical instrument. It
    will miss things and it will sometimes fire on things that are not a
    concern. The categories are internal policy labels, never diagnoses, and
    are never shown to the user as a "score".
  * It is a first line. The system prompt (core/prompt.txt) carries the same
    rules for the model itself, so a miss here does not remove the policy.
  * It never stores what the user said. Only aggregate counters are kept.

Categories (PRD section 7G): LOW, ELEVATED, HIGH.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

LOW, ELEVATED, HIGH = "low", "elevated", "high"
_ORDER = {LOW: 0, ELEVATED: 1, HIGH: 2}


def rank(level: str) -> int:
    return _ORDER.get(level, 0)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


EVENTS_PATH = _base_dir() / "memory" / "safety_events.json"
_lock = threading.Lock()


# ── Pattern sets ─────────────────────────────────────────────────────────────
# English, Roman Urdu / Hindi, and Urdu script — the languages this assistant is
# expected to hear. Phrases describe *intent or hopelessness*; none of them
# encode methods, and the app never repeats them back to the user.

_HIGH = [
    # explicit intent / imminence (English)
    r"\b(i('| a)?m|i am|i'?m gonna|i am going to|i will|i'?ll|going to)\b.{0,20}\b(kill myself|end my life|take my (own )?life|end it all|commit suicide)\b",
    r"\b(want|plan(ning)?|decided|ready)\b.{0,15}\bto (kill myself|end my life|die tonight)\b",
    r"\b(have|got) a plan\b.{0,30}\b(die|kill myself|end (my life|it))\b",
    r"\b(kill myself|end my life|commit suicide)\b.{0,25}\b(tonight|right now|today|soon|this (evening|morning))\b",
    r"\b(tonight|right now)\b.{0,25}\b(kill myself|end my life|end it all)\b",
    r"\bsuicide (note|plan)\b",
    r"\b(said|saying) goodbye (to everyone|forever)\b",
    # Roman Urdu / Hindi
    r"\b(main|mein|mai|me)\b.{0,20}\b(khud ?kushi|khudkushi|khudkashi|suicide)\b.{0,20}\b(kar(ne)? (wala|wali|laga|lagi|jaa ?raha|jaa ?rahi)|karunga|karungi|kar lunga|kar lungi)\b",
    r"\b(aaj raat|abhi|aj raat)\b.{0,25}\b(marne|mar jaunga|mar jaungi|jaan de|khatam kar)\b",
    r"\b(apni|apna)\b.{0,10}\b(jaan|zindagi)\b.{0,15}\b(khatam kar|le lunga|le lungi|de dunga|de dungi)\b",
    r"\bmar(ne)? (wala|wali) (hu|hun|hoon)\b",
    # Urdu script
    r"(خودکشی|خود کشی).{0,15}(کرنے والا|کرنے والی|کروں گا|کروں گی|کر لوں گا|کر لوں گی|کا ارادہ)",
    r"(آج رات|ابھی).{0,20}(مر|جان دے|زندگی ختم)",
]

_ELEVATED = [
    r"\b(want|wanna|wish)\b.{0,12}\b(to )?(die|be dead|disappear)\b",
    r"\b(better off (dead|without me)|no (reason|point) (to|in) (live|living|going on))\b",
    r"\b(suicid(e|al)|kill myself|end my life|end it all|self[- ]?harm|hurt myself|cut(ting)? myself)\b",
    r"\b(can'?t|cannot) (go on|do this anymore|take (it|this) anymore)\b",
    r"\b(i('| a)?m|i am) (so )?(hopeless|worthless)\b|\bnothing (matters|will ever get better)\b",
    r"\bnobody (would|will) (miss|care)\b.{0,14}\bif i\b",
    r"\b(life is (pointless|meaningless)|i hate (my life|myself))\b",
    # Roman Urdu / Hindi
    r"\b(marna|mar jana|mar jaana|mar jaun|mar jau|jeena nahi|jeena nahin|jina nahi)\b.{0,15}\b(chahta|chahti|chahiye|chahta hun|chahti hun|hai)?\b",
    r"\b(khud ?kushi|khudkushi|khudkashi|zindagi khatam|jaan de(na)?)\b",
    r"\b(zindagi se (tang|thak)|jeene ka (koi )?(matlab|maqsad) nahi|mere bina (sab|sabhi) behtar)\b",
    r"\bkhud ko (nuqsan|hurt|cut|kaat)\b",
    # Urdu script
    r"(مرنا چاہتا|مرنا چاہتی|جینا نہیں|خودکشی|زندگی ختم|جان دینا|خود کو نقصان)",
]

# Everyday idioms that contain alarming words but are not about the person's
# safety. Checked first so ordinary stress stays in the LOW lane.
_IDIOMS = [
    r"\b(hurt|injured|cut|burnt|burned) myself\b.{0,25}\b(playing|cooking|gym|football|cricket|running|exercis\w*|falling|fell|slipped|accident\w*|vegetables|shaving|chopping|cutting)\b",
    r"\b(playing|cooking|exercising|running|shaving|chopping|cutting|falling)\b.{0,25}\b(hurt|injured|cut|burnt|burned) myself\b",
    r"\b(killing me|dying (of|from) (laughter|embarrassment|boredom|hunger)|dying to (know|see|go)|dead tired|"
    r"kill (for|time)|to die for|murder (this|that) (exam|test|deadline)|this (exam|deadline|work) (is )?(killing|murdering) me)\b",
    r"\b(mar gaya|mar gayi|maar dala)\b.{0,10}\b(hasi|hansi|bhook|thakan)\b",
]

# ── Coverage added after the team's 80-line test set (families, not single sentences) ──
# Roman-Urdu future endings: lunga / loonga / lungi / loongi (+ "le"), and dunga / doonga / dungi.
_LUNGA = r"(?:le\s+)?l(?:oo?|u)n?g[ai]"
_DUNGA = r"d(?:u|oo)n?g[ai]"

_HIGH += [
    # English: decided / intent to hurt oneself
    r"\b(made|make|made up|i'?ve decided|decided)\b.{0,20}\b(my mind|up my mind)?\b.{0,20}\b(to )?(die|end it( all)?|end my life|kill myself)\b.{0,25}\b(tonight|today|now)?",
    r"\b(going to|about to|gonna)\b.{0,8}\b(hurt|harm) myself\b",
    r"\b(can'?t|cannot) (stop|hold on)\b.{0,40}\b(hurt|harm|kill|end)\b.{0,12}\b(myself|my life|it all)\b",
    # Roman Urdu / Hindi
    rf"\bapni\s+(?:jaan|zindagi)\b.{{0,14}}\b(?:{_LUNGA}|khatam\s+kar\s+{_DUNGA}|de\s+{_DUNGA})\b",
    rf"\b(?:main|mein|mai)\b.{{0,14}}\bjaan\s+{_LUNGA}\b",
    r"\b(?:meri|ye meri|yeh meri)\s+(?:aakhri|akhri)\s+(?:raat|din|shaam)\b",
    r"\b(?:main|mein|mai)\s+(?:ab\s+)?nahi\s+rah(?:unga|ungi)\b",
    r"\b(?:sab ko|sabko)\s+alvida\s+(?:keh|kah)\s+(?:diya|chuka|chuki)\b",
    r"\bkhud ko (?:nuqsan|nuksan)\s+poh?nch\w*\s+(?:wala|wali)\b",
    r"\bkhud ko khatam\b.{0,40}\b(?:abhi|aaj|karne wala|karne wali)\b",
    r"\b(?:main|mein|mai)\b.{0,14}\bend kar\s+(?:d|l)(?:u|oo)n?g[ai]\b",
    # Urdu script
    r"(?:آج رات|ابھی|آج).{0,30}(?:جان لینے|جان دینے|جان لوں|خاتمہ کر|ختم کر دوں)",
    r"(?:طے کر لیا|فیصلہ کر لیا).{0,35}(?:ختم کر|مر )",
    r"جان (?:لینے|دینے)\s*(?:والا|والی)",
]

_ELEVATED += [
    # English
    r"\bdon'?t want to be here( anymore)?\b",
    r"\b(want|wanna|wish)\b.{0,22}\b(to )?(die|be dead|disappear)\b",
    r"\bcan'?t hold on( any longer)?\b",
    r"\bnobody would (even )?notice if i (died|was gone|disappeared)\b",
    # Roman Urdu / Hindi
    r"\bzindagi\b.{0,16}\b(?:bojh|bojhal|bekaar|bekar|bezaar|bezar)\b",
    r"\b(?:umeed|ummeed|ummid|umid)\b.{0,16}\b(?:nahi|nahin)\b.{0,10}\b(?:bachi|bacha|raha|rahi|baqi)\b",
    r"\b(?:main|mein|mai)\s+na\s+hota\b.{0,24}\b(?:achha|accha|behtar|better)\b",
    r"\bmere bina\b.{0,22}\b(?:sab|sabhi)\b.{0,16}\b(?:theek|behtar|achha|accha)\b",
    r"\b(?:main|mein|mai)\b.{0,14}\bbojh\s+(?:hoon|hun|hu)\b",
    r"\bjeene ka (?:dil|mann|man)\s+(?:nahi|nahin)\b|\bjeena (?:mushkil|bekar)\b|\bab jeena\b.{0,12}\bmushkil\b",
    r"\bthak (?:gaya|gayi|gaye)\b.{0,16}\bzindagi se\b|\bzindagi se\b.{0,14}\b(?:bezaar|bezar)\b",
    r"\bsab khatam ho (?:jaye|jaaye)\b",
    r"\bsab chhod\w*\b.{0,18}\b(?:ghayab|gaayab|gayab)\b",
    r"\bkhud ko khatam\b",
    r"\bkhud ko (?:nuqsan|nuksan)\s+poh?nch\w*\b",
    # Urdu script
    r"زندگی.{0,14}(?:بوجھ|بیکار|بے معنی)",
    r"(?:مر جاؤں|مر جاوں).{0,12}(?:بہتر|اچھا)",
    r"امید.{0,18}(?:نہیں|نظر نہیں)",
    r"(?:سب|ہر چیز).{0,10}(?:بے معنی|بیکار)",
    r"(?:غائب ہو جاؤں|کہیں غائب)",
]

# ── Second coverage pass (after the held-out set): themes, not sentences ─────
_HIGH += [
    r"\b(goodbye|farewell|final)\s+(note|letter|message)\b",
    r"\b(ending|end)\s+(things|it all|everything)\b.{0,16}\b(tonight|today|right now)\b",
    r"\b(it|this|everything)\s+ends\s+tonight\b|\bdecided\b.{0,25}\bends?\b.{0,14}\btonight\b",
    r"\b(apne aap|khud)\s+ko\s+khatam\s+kar\w*\b.{0,30}\b(faisla|decide|soch liya|tay)\b",
    r"\bfaisla\s+kar\s+liya\b.{0,30}\b(khatam|marne|jaan)\b",
    r"(?:آج رات|ابھی).{0,25}سب ختم",
    r"فیصلہ کر لیا.{0,30}(?:ختم|مرنے|جان)",
]
_ELEVATED += [
    r"\b(burden|liability)\b.{0,25}\b(to|on|for)\b.{0,16}\b(everyone|everybody|my family|others|all of them|people)\b",
    r"\b(everything|life|living|existence|it all)\b.{0,22}\b(pointless|meaningless|futile|worthless)\b|\b(pointless|meaningless)\b.{0,14}\b(life|living)\b",
    r"\bsee no (future|way out|reason to (live|go on)|point (in|to) (living|going on|life))\b|\bno reason to live\b",
    r"\bdon'?t see (the )?(point|purpose|reason)\b.{0,16}\b(going on|living|life|anymore|continuing)\b",
    r"\b(can'?t wait for|before) (tomorrow|tonight)\b.{0,30}\bbecause i won'?t be (here|around|alive)\b",
    r"\b(no ?one|nobody)\s+(would|will)\s+(even\s+)?(care|miss|notice)\b.{0,14}\bif i\b",
    r"\b(want|need)\s+(the|this|it all)?\s*(pain|hurting|suffering)\s+to\s+(stop|end|go away)\b",
    r"\b(think(ing)?|thought)s?\s+(about|of)\s+(hurting|harming|killing)\s+myself\b|\b(hurt|harm)(ing)?\s+myself\b",
    r"\btrapped\b.{0,30}\b(life|living)\b|\bno way out of (this|my) life\b",
    r"\bdon'?t care (how|if i (live|die))\b",
    r"\bhone ya na hone\b|\b(zindagi|jeene|jeevan)\b.{0,25}\b(maqsad|matlab|wajah)\b.{0,22}\b(nazar nahi|nahi (milta|mil raha|dikhta|dikhai))\b",
    r"\bkhud ko saza\b|\bapne aap ko (saza|nuqsan|nuksan)\b",
    r"جی نہیں سک|جینے کا کوئی (?:مقصد|فائدہ)|خود کو سزا",
]

_COMPILED = {
    HIGH: [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _HIGH],
    ELEVATED: [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _ELEVATED],
}
_IDIOM_RE = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _IDIOMS]

# Medical-scope requests: not a risk level, but the policy must hold.
_DIAGNOSIS_ASK = re.compile(
    r"\b(do i have|have i got|am i|diagnos\w*|what (disorder|illness)|is it (depression|anxiety|bipolar|adhd|ocd|ptsd))\b|تشخیص",
    re.IGNORECASE)
_CONDITION = re.compile(
    r"\b(depress\w*|anxiety|bipolar|adhd|ptsd|ocd|schizo\w*|autis\w*|borderline|panic attacks?|disorder|bimari)\b|ڈپریشن|اینزائٹی|بیماری|بائی پولر|اے ڈی ایچ ڈی",
    re.IGNORECASE)
_ASKING = re.compile(
    r"\?|؟|\b(do i|do you think|have i|kya|hai ya nahi|test|bata\w*|check|tell me|sakt[ae]|can you)\b|کیا|بتا",
    re.IGNORECASE)
_MEDICATION_ASK = re.compile(
    r"\b(medication|medicine|medicines|pills?|dose|dosage|antidepressants?|sertraline|prozac|xanax|prescri\w*|"
    r"dawai|dawa|dawaiyan|goli|golian|tablets?|capsules?|miqdar|should i (take|stop))\b|دوا|گولی|ادویات|خوراک|بائی پولر",
    re.IGNORECASE)


def _scope_ask(t: str) -> bool:
    return bool(_DIAGNOSIS_ASK.search(t) or _MEDICATION_ASK.search(t)
                or (_CONDITION.search(t) and _ASKING.search(t)))


def _normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ── Policies handed to the model ─────────────────────────────────────────────

_POLICY = {
    LOW: "",
    ELEVATED: (
        "[SAFETY_POLICY elevated] The user may be in significant distress. "
        "Respond with warmth and without alarm. Do not diagnose, do not argue, do not "
        "minimise. Ask ONE gentle, direct question about whether they are thinking of "
        "harming themselves or ending their life. Encourage them to reach a trusted person "
        "or a professional, and call find_support_resources. Offer no methods or details. "
        "Do not promise secrecy and do not say you can keep them safe. Reply in the user's language."
    ),
    HIGH: (
        "[SAFETY_POLICY high] The user may be in immediate danger. Put safety first. In your "
        "first two sentences: acknowledge them, say you are an AI and cannot keep them safe, and "
        "urge them to contact local emergency services or a crisis line now and to reach a "
        "trusted person who can be with them. Call find_support_resources with urgency 'crisis'. "
        "Keep it short and calm. Do NOT offer coping exercises first, do NOT give any details "
        "about methods, do NOT promise secrecy, do NOT argue. Stay with them and keep the "
        "next step small and concrete. Reply in the user's language."
    ),
}

_NOTE_DIAGNOSIS = (
    "[SAFETY_POLICY scope] The user is asking for a diagnosis or medication advice. Say plainly that "
    "you cannot diagnose or advise on medication, then offer what you can: listen, describe what "
    "they said back to them, and point to a doctor or licensed professional."
)


# ── Minor signals (PRD: age-appropriate, trusted adult) ──────────────────────
_MINOR_AGE = [
    re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?)(?:\s*old)?\b|\b(\d{1,2})\s*(?:y/o|yo)\b|\b(\d{1,2})\s*(?:saal|sal)\b", re.I),
    re.compile(r"\b(?:my age is|age is|meri umar|umar)\s*(\d{1,2})\b", re.I),
    re.compile(r"\b(?:i am|i'm|im|main|mein)\s+(\d{1,2})\b(?=\s*(?:years|yrs|saal|sal|and\b|,|\.|$))", re.I),
]
_MINOR_CONTEXT = re.compile(
    r"\b(i am|i'm|im)\s+(a\s+)?(school|class\s*\d+|grade\s*\d+|matric|o[- ]?levels?|a[- ]?levels?|"
    r"middle school|high school)\b|\b(in|studying in)\s+(class|grade)\s*(\d{1,2})\b|\b(my (parents|mom|dad)\s+(won'?t|don'?t|will not)\s+let me)\b", re.I)


def minor_signal(text: str) -> bool:
    t = _normalise(text)
    if _MINOR_CONTEXT.search(t):
        return True
    for rx in _MINOR_AGE:
        for m in rx.finditer(t):
            for g in m.groups():
                if g and 5 <= int(g) < 18:
                    return True
    return False


_NOTE_MINOR = (
    "[SAFETY_POLICY minor] The user may be under 18. Be extra gentle and age-appropriate. Encourage a trusted adult "
    "(parent, teacher, school counsellor). Do not discuss anything unsuitable for young people. Do not ask them to keep "
    "secrets from a trusted adult."
)

# ── What may be written to long-term memory ──────────────────────────────────
_MEM_BAD = re.compile(
    r"\b(depress(ed|ion|ive)|bipolar|schizo\w*|adhd|ptsd|ocd|borderline|anorex\w*|bulimi\w*|psychosis|"
    r"diagnos\w*|disorder|suicid\w*|self[- ]?harm\w*|kill(ing)? (myself|himself|herself)|overdos\w*|"
    r"sertraline|fluoxetine|prozac|xanax|alprazolam|diazepam|valium|zoloft|antidepressants?|\d+\s?mg)\b|"
    r"(خودکشی|ڈپریشن)|\b(khud ?kushi|khudkushi)\b", re.I)


def memory_allowed(category: str, key: str, value: str) -> tuple[bool, str]:
    """Code-level backstop for the prompt rule: never store diagnoses, medication,
    or self-harm detail, whatever the model decides."""
    blob = f"{category} {key} {value}"
    m = _MEM_BAD.search(blob)
    if m:
        return False, "contains a diagnosis, medication, or self-harm term"
    return True, ""


@dataclass
class SafetyResult:
    level: str = LOW
    signals: list[str] = field(default_factory=list)   # categories only, never the text
    policy: str = ""
    scope_note: str = ""
    escalated: bool = False     # level is higher than the previous turn's
    minor: bool = False         # session has shown signs of a user under 18


class SafetyMonitor:
    """Stateful wrapper: remembers recent concern so one calm sentence after a
    worrying one does not instantly reset the policy."""

    HOLD_TURNS = 3   # turns the floor stays at ELEVATED after any concern

    def __init__(self) -> None:
        self._floor = LOW
        self._hold = 0
        self._last = LOW
        self._minor = False
        self._minor_noted = False

    def reset(self) -> None:
        self._floor, self._hold, self._last = LOW, 0, LOW
        self._minor = self._minor_noted = False

    def apply_external(self, level: str, scope: bool = False, minor: bool = False) -> SafetyResult | None:
        """A second opinion (the semantic screen) arrived after the instant regex pass.
        It can only RAISE the level or add a scope/minor note. Returns what to act on, or None if nothing is new."""
        new_level = _ORDER[level] > _ORDER[self._last]
        new_minor = bool(minor) and not self._minor
        if not (new_level or scope or new_minor):
            return None
        if new_level:
            self._floor, self._hold = level, self.HOLD_TURNS
            self._last = level
            record_event(level, ["semantic"])
        note = (_NOTE_DIAGNOSIS + " " if scope else "")
        if new_minor:
            self._minor = True
            note += _NOTE_MINOR
        cur = level if new_level else self._last
        return SafetyResult(level=cur, signals=["semantic"], policy=_POLICY[level] if new_level else "",
                            scope_note=note.strip(), escalated=new_level, minor=self._minor)

    def observe(self, text: str) -> SafetyResult:
        raw = classify(text)
        level = raw.level

        if _ORDER[level] > _ORDER[LOW]:
            self._floor, self._hold = level, self.HOLD_TURNS
        elif self._hold > 0:
            self._hold -= 1
            # decay: a HIGH floor relaxes to ELEVATED, ELEVATED relaxes to LOW
            level = ELEVATED if _ORDER[self._floor] >= _ORDER[ELEVATED] and self._hold > 0 else LOW
            if level == LOW:
                self._floor = LOW

        scope = raw.scope_note
        if minor_signal(text):
            self._minor = True
        if self._minor and (not self._minor_noted or level != LOW):
            scope = (scope + " " if scope else "") + _NOTE_MINOR
            self._minor_noted = True
        res = SafetyResult(
            level=level, signals=raw.signals, policy=_POLICY[level],
            scope_note=scope, minor=self._minor,
            escalated=_ORDER[level] > _ORDER[self._last],
        )
        self._last = level
        if res.escalated or raw.signals:
            record_event(level, raw.signals)
        return res


def classify(text: str) -> SafetyResult:
    """Stateless single-message screen."""
    t = _normalise(text)
    if not t:
        return SafetyResult()

    scope = ""
    if _scope_ask(t):
        scope = _NOTE_DIAGNOSIS

    scrubbed = t
    for rx in _IDIOM_RE:
        scrubbed = rx.sub(" ", scrubbed)

    for level in (HIGH, ELEVATED):
        hits = [i for i, rx in enumerate(_COMPILED[level]) if rx.search(scrubbed)]
        if hits:
            return SafetyResult(level=level, signals=[f"{level}:{i}" for i in hits],
                                policy=_POLICY[level], scope_note=scope)
    return SafetyResult(level=LOW, scope_note=scope)


# ── Output check (PRD 8.6) ───────────────────────────────────────────────────

_OUT_RULES = [
    ("diagnosis", re.compile(
        r"\byou (have|suffer from|are suffering from|are (clinically )?(depressed|bipolar|anxious disorder))\b"
        r"|\b(this is|that sounds like|you('re| are) showing signs of) (clinical )?(depression|bipolar|ptsd|ocd|adhd|an anxiety disorder)\b"
        r"|\bi (can )?diagnose\b|\byour diagnosis\b", re.I)),
    ("medication", re.compile(
        r"\b(you should|try|i recommend|start|stop|increase|reduce) (taking |to take )?[a-z ]{0,20}"
        r"(\d+\s?(mg|ml)\b|sertraline|fluoxetine|prozac|xanax|alprazolam|diazepam|valium|antidepressants?)", re.I)),
    ("dependency", re.compile(
        r"\b(you don'?t need (anyone|anybody|therapy|a doctor)|only i (understand|care)|i'?ll always be (all )?you need|don'?t tell (anyone|anybody))\b", re.I)),
    ("overconfidence", re.compile(
        r"\b(i (can )?promise (you )?(will be|it will be) (fine|okay)|i('ll| will) keep you safe|i guarantee)\b", re.I)),
    ("secrecy", re.compile(r"\b(i won'?t tell|this stays between us|our (little )?secret)\b", re.I)),
]


def check_output(text: str) -> list[str]:
    """Names of policy rules the assistant's reply appears to break (may be empty)."""
    t = _normalise(text)
    return [name for name, rx in _OUT_RULES if rx.search(t)]


CORRECTION = (
    "[SAFETY_POLICY correction] Your last reply may have broken a Roohvi rule ({rules}). In your next "
    "turn, briefly and naturally correct it: you are an AI wellness companion, you do not diagnose, "
    "do not advise on medication, do not promise secrecy or safety, and you encourage the user's real-world "
    "support. Do not mention this note."
)


# ── Aggregate audit counters (no message content, ever) ──────────────────────

def record_event(level: str, signals: list[str] | None = None) -> None:
    """Count safety events per day and level. Stores NO text."""
    try:
        with _lock:
            data = {}
            if EVENTS_PATH.exists():
                data = json.loads(EVENTS_PATH.read_text(encoding="utf-8") or "{}")
            day = datetime.now().strftime("%Y-%m-%d")
            data.setdefault(day, {LOW: 0, ELEVATED: 0, HIGH: 0})
            data[day][level] = data[day].get(level, 0) + 1
            EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            EVENTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass   # auditing must never break a conversation
