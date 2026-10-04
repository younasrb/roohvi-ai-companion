"""Support-resource lookup for Roohvi (PRD 7F). Data lives in config/resources.json."""
from __future__ import annotations
import json
import sys
from pathlib import Path


def _base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


PATH = _base() / "config" / "resources.json"
DISCLAIMER = ("Availability and emergency response depend on where you are and on current service status. "
              "Please confirm numbers before relying on them.")


def _load() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"default_region": "INTL", "records": []}


def default_region() -> str:
    try:
        from memory.config_manager import load_api_keys
        r = (load_api_keys().get("region") or "").strip().upper()
        if r:
            return r
    except Exception:
        pass
    return _load().get("default_region", "INTL")


def find(region: str = "", kind: str = "all") -> list[dict]:
    """Resources for a region plus international fallbacks.

    region is a country code (PK) or a country-province code (PK-SD, PK-PB).
      * "PK-SD" -> records for PK-SD, country-wide PK records, and INTL
      * "PK"    -> country-wide records and EVERY province record (each is labelled with its province)
    kind: all | emergency | crisis | counselling | abuse"""
    data = _load()
    region = (region or default_region()).strip().upper()
    base = region.split("-")[0]
    out = []
    for r in data.get("records", []):
        rr = r.get("region", "")
        if "-" in region:
            ok = rr in (region, base, "INTL")
        else:
            ok = rr == region or rr == "INTL" or rr.startswith(region + "-")
        if not ok:
            continue
        t = r.get("type", "")
        if kind == "emergency" and not r.get("emergency"):
            continue
        if kind == "crisis" and t not in ("crisis_helpline", "emergency", "directory"):
            continue
        if kind == "counselling" and t not in ("counselling", "crisis_helpline", "directory"):
            continue
        if kind == "abuse" and t not in ("abuse_helpline", "emergency", "directory"):
            continue
        out.append(r)
    # most local first, emergency before the rest
    out.sort(key=lambda r: (r.get("region") == "INTL", r.get("region") == base and region != base, not r.get("emergency", False)))
    return out


def format_for_screen(records: list[dict]) -> str:
    lines = []
    for r in records:
        line = f"• {r['name']}: {r['contact']}"
        if r.get("availability"):
            line += f"  ({r['availability']})"
        lines.append(line)
        if r.get("note"):
            lines.append(f"    {r['note']}")
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
