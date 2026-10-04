"""
Wellness data for Roohvi — check-ins and completed activities.

Privacy rules (PRD sections 11-12):
  * Nothing is saved until the user turns tracking ON (consent). Default is OFF.
  * Only self-reported 1-5 values and an optional short note are stored.
  * No inferred diagnoses, no risk labels, no personality profile.
  * The user can export and delete everything at any time.
Data lives in memory/wellness.json on this machine.
"""
from __future__ import annotations
import json
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path


def _base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


PATH = _base() / "memory" / "wellness.json"
_lock = threading.Lock()
LABELS = {1: "very difficult", 2: "difficult", 3: "okay", 4: "good", 5: "very good"}
MAX_NOTE = 280


def _empty() -> dict:
    return {"tracking": False, "consent_date": None, "checkins": [], "activities": []}


def _load() -> dict:
    if not PATH.exists():
        return _empty()
    try:
        d = json.loads(PATH.read_text(encoding="utf-8"))
        for k, v in _empty().items():
            d.setdefault(k, v)
        return d
    except Exception:
        return _empty()


def _save(d: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def is_tracking() -> bool:
    with _lock:
        return bool(_load()["tracking"])


def set_tracking(on: bool) -> None:
    with _lock:
        d = _load()
        d["tracking"] = bool(on)
        d["consent_date"] = datetime.now().isoformat(timespec="seconds") if on else None
        _save(d)


def _clamp(v) -> int | None:
    try:
        return max(1, min(5, int(round(float(v)))))
    except Exception:
        return None


def add_checkin(mood=None, energy=None, stress=None, sleep=None, note: str = "") -> bool:
    """Returns False (and stores nothing) when tracking consent is off."""
    with _lock:
        d = _load()
        if not d["tracking"]:
            return False
        d["checkins"].append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "mood": _clamp(mood), "energy": _clamp(energy),
            "stress": _clamp(stress), "sleep": _clamp(sleep),
            "note": (note or "").strip()[:MAX_NOTE],
        })
        _save(d)
        return True


def add_activity(kind: str) -> bool:
    with _lock:
        d = _load()
        if not d["tracking"]:
            return False
        d["activities"].append({"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind})
        _save(d)
        return True


def recent(days: int = 7) -> dict:
    with _lock:
        d = _load()
    cut = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    return {
        "checkins": [c for c in d["checkins"] if c["ts"] >= cut],
        "activities": [a for a in d["activities"] if a["ts"] >= cut],
    }


def averages(checkins: list[dict], min_entries: int = 3) -> dict | None:
    """Simple averages, only with enough data (PRD 7B). No clinical reading."""
    if len(checkins) < min_entries:
        return None
    out = {}
    for k in ("mood", "energy", "stress", "sleep"):
        vals = [c[k] for c in checkins if c.get(k)]
        if vals:
            out[k] = round(sum(vals) / len(vals), 1)
    return out


def export_text() -> str:
    with _lock:
        return json.dumps(_load(), indent=2, ensure_ascii=False)


def delete_checkins_and_activities() -> None:
    with _lock:
        d = _load()
        d["checkins"], d["activities"] = [], []
        _save(d)


def delete_everything() -> None:
    """Wellness data, long-term memory, and safety counters."""
    with _lock:
        for p in (PATH, PATH.parent / "long_term.json", PATH.parent / "safety_events.json"):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
