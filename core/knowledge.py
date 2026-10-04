"""
Roohvi knowledge base (team-written entries -> searchable, cited answers).

Entries live in knowledge/*.md using the team format (see knowledge/_TEMPLATE.md).
One file may hold several entries separated by a line containing only '---'.

An entry is SERVED only if it passes every gate. Anything else is skipped and
listed by load_report(), so nothing unreviewed ever reaches a user:
  1. has a Title and a Steps/explanation body
  2. has a Source URL starting with http
  3. has a Reviewer name (the team rule: no review, not final)
  4. Audience: 'authors' entries are style guides for the writers and the prompt and are never served.
     'model' entries are served to the assistant only (language and culture notes), never put on screen.
  5. its text does not break the content rules (diagnosis / medication advice /
     secrecy or guarantees), checked with core.safety.check_output and a few
     extra patterns for self-harm detail
Search is plain keyword scoring (works offline, works for Roman Urdu / Urdu
script too). It is deliberately simple and explainable.
"""
from __future__ import annotations
import math
import re
import sys
from pathlib import Path

from core import safety


def _base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


DIR = _base() / "knowledge"

# (field, label-prefix regex). A label starts a field; its value runs to the next label.
_LABELS = [
    ("id",       r"ID"),
    ("title",    r"Title"),
    ("lang",     r"Zubaan"),
    ("when",     r"Kab kaam aata"),
    ("body",     r"Steps ya samjh?aana|Steps ya samjhana|Steps"),
    ("caution",  r"Kab ruk jana ya madad lena zaroori hai|Kab madad"),
    ("avoid",    r"Kisko nahi dena"),
    ("source",   r"Source URL"),
    ("source_note", r"Source ka naam"),
    ("ai_used",  r"AI tool use hua"),
    ("author",   r"Likhne wale ka naam"),
    ("reviewer", r"Reviewer ka naam"),
    ("audience", r"Audience"),
]
# Short labels (ID, Title, Zubaan) must be followed directly by a colon, so an ordinary sentence such as
# "ID kya hai: ..." inside a body is never mistaken for a label. The longer team labels may carry extra
# words before the colon, e.g. "Source ka naam / date jab dekha:" or "AI tool use hua? (NotebookLM / ...):".
_STRICT = {"id", "title", "lang", "audience"}
_LABEL_RE = re.compile(
    r"^\s*(?:" + "|".join(
        f"(?P<{f}>{p})" + (r"\s*[:\uff1a]" if f in _STRICT else r"[^:\uff1a\n]{0,70}?[:\uff1a]")
        for f, p in _LABELS) + r")\s*(?P<val>.*)$", re.IGNORECASE)

# Concrete detail is rejected for EVERY audience. The bare phrase "method of suicide/self-harm" is rejected only in
# user-facing entries: guidance for the assistant legitimately says "never mention any method of self-harm".
_EXTRA_BAD = re.compile(
    r"\b(overdose|lethal dose|how to (kill|hurt|cut)|ways to (die|end))\b", re.I)
_EXTRA_BAD_PHRASE = re.compile(r"\bmethods? (of|for) (suicide|self[- ]?harm)\b", re.I)
_PLACEHOLDER = re.compile(r"^\s*(\(.*\)|todo|tbd|-|\.\.\.|)\s*$", re.I)

_cache: dict | None = None


def _split_entries(text: str) -> list[str]:
    return [c for c in re.split(r"(?m)^\s*---\s*$", text) if c.strip()]


def _parse(chunk: str) -> dict:
    out = {k: "" for k, _ in _LABELS}
    cur = None
    for line in chunk.splitlines():
        m = _LABEL_RE.match(line)
        if m:
            cur = next(f for f, _ in _LABELS if m.group(f))
            out[cur] = (out[cur] + "\n" + m.group("val")).strip() if out[cur] else m.group("val").strip()
        elif cur:
            out[cur] = (out[cur] + "\n" + line).strip()
    return out


def first_line(v: str) -> str:
    return (v or "").strip().split("\n")[0].strip()


def _clean(v: str) -> str:
    return "" if _PLACEHOLDER.match(v or "") else (v or "").strip()


def load(force: bool = False) -> dict:
    """-> {"entries": [...served...], "skipped": [(file, id, reason)]}"""
    global _cache
    if _cache is not None and not force:
        return _cache
    served, skipped = [], []
    if DIR.exists():
        for f in sorted(DIR.glob("*.md")):
            if f.name.startswith("_"):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except Exception as e:
                skipped.append((f.name, "", f"unreadable: {e}")); continue
            for chunk in _split_entries(text):
                e = {k: _clean(v) for k, v in _parse(chunk).items()}
                eid = e["id"] or f.stem
                reason = None
                if (e["audience"] or "").lower().startswith("author"):
                    reason = "style guide for writers (Audience: authors), not shown to users"
                elif not e["title"] or not e["body"]:
                    reason = "missing title or steps"
                elif not first_line(e["source"]).lower().startswith("http"):
                    reason = "no valid source URL"
                elif not e["reviewer"]:
                    reason = "not reviewed yet"
                else:
                    blob = " ".join((e["title"], e["body"], e["caution"], e["when"]))
                    # Guidance written FOR the assistant ('model') quotes forbidden phrases to forbid them
                    # ("never say 'I won't tell anyone'"), so the phrase rules would reject it by mistake.
                    # Self-harm detail is still rejected for every audience.
                    is_model = (e["audience"] or "").lower().startswith("model")
                    hits = [] if is_model else safety.check_output(blob)
                    if _EXTRA_BAD.search(blob) or (not is_model and _EXTRA_BAD_PHRASE.search(blob)):
                        hits.append("self-harm detail")
                    if hits:
                        reason = "content rule: " + ", ".join(hits)
                if reason:
                    skipped.append((f.name, eid, reason)); continue
                e["_file"] = f.name
                e["_tokens"] = _tokens(" ".join((e["title"], e["when"], e["body"], e["caution"], e["id"])))
                e["_title_tokens"] = _tokens(e["title"])
                e["_when_tokens"] = _tokens(e["when"])
                e["_counts"] = _counts(" ".join((e["body"], e["caution"])))
                served.append(e)
    _cache = {"entries": served, "skipped": skipped}
    return _cache


def load_report() -> str:
    d = load(force=True)
    lines = [f"Knowledge base: {len(d['entries'])} entries served, {len(d['skipped'])} skipped."]
    for f, i, r in d["skipped"]:
        lines.append(f"  skipped {f} [{i}]: {r}")
    return "\n".join(lines)


_STOP = set("a an the is are am to of and or in on at for my me i you it this that with be was were do does did "
            "hai hain ho hoon hun main mein mai mujhe mera meri ka ki ke ko se me par pe aur kya kyun nahi nahin "
            "kar karna karo raha rahi rahe tha thi the bhi yeh woh is us ek".split())


def _stem(t: str) -> str:
    """Very light stemmer: strips common English endings, then keeps the first five characters.
    lonely / loneliness -> lonel, sleeping / sleep -> sleep, stressed / stress -> stres."""
    if not t.isascii():
        return t
    for suf in ("ness", "ing", "ed", "es", "s"):
        if t.endswith(suf) and len(t) > len(suf) + 3:
            t = t[: -len(suf)]
            break
    if t.endswith("y"):
        t = t[:-1] + "i"
    return t[:5]


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE) if len(t) > 1 and t not in _STOP}


def _counts(text: str) -> dict:
    c: dict = {}
    for t in re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE):
        t = _stem(t)
        c[t] = c.get(t, 0) + 1
    return c


def search(query: str, limit: int = 3, min_score: float = 1.0) -> list[dict]:
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for e in load()["entries"]:
        # title match counts most, then the "when this helps" line, then how often the word appears in the body.
        s = 3.0 * len(q & e["_title_tokens"]) + 1.5 * len(q & e["_when_tokens"])
        for t in q & e["_tokens"]:
            s += 1.0 + 0.35 * math.log(e["_counts"].get(t, 1))
        if (e.get("audience") or "").lower().startswith("model"):
            s -= 0.4            # prefer entries written for users when the match is close
        if s >= min_score:
            scored.append((s, e))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for _, e in scored:                       # one entry may exist in several languages: keep the best match only
        key = e["id"] or e["title"]
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= limit:
            break
    return out
