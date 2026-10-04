"""Semantic screen: parsing, graceful failure, and that it can only RAISE the level.
    python -m tests.test_safety_llm
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import safety as S, safety_llm as L

# parse
assert L.parse('{"level":"high","scope":false,"minor":true}') == {"level": "high", "scope": False, "minor": True}
assert L.parse('```json\n{"level": "Elevated", "scope": true}\n```')["level"] == "elevated"
assert L.parse("sorry I cannot") is None and L.parse('{"level":"banana"}') is None

# classify with a fake model call
L._state.update(off=False, client=object(), model="fake")
L._cfg = lambda: {"safety_llm": True}
L._call = lambda text: {"level": "elevated", "scope": False, "minor": False}
assert L.classify("anything")["level"] == "elevated"

# a slow answer is ignored once but does NOT switch the feature off
L._call = lambda text: (time.sleep(0.5), {"level": "high", "scope": False, "minor": False})[1]
assert L.classify("x", timeout=0.05) is None and L.enabled()

# an error switches it off after ONE attempt, then it stays quiet
calls = []
def boom(text): calls.append(1); raise RuntimeError("404 model not found")
L._call = boom
assert L.classify("x") is None and not L.enabled()
assert L.classify("y") is None and len(calls) == 1
L._state["off"] = False

# monitor: the second opinion can only raise
m = S.SafetyMonitor()
r0 = m.observe("I feel nobody gets me and everything is heavy")          # regex says low
assert r0.level == S.LOW
up = m.apply_external(S.ELEVATED)
assert up and up.level == S.ELEVATED and "elevated" in up.policy and up.escalated
assert m.apply_external(S.LOW) is None                                    # never lowers
assert m.apply_external(S.ELEVATED) is None                               # nothing new
hi = m.apply_external(S.HIGH, scope=True)
assert hi.level == S.HIGH and "high" in hi.policy and hi.scope_note
m2 = S.SafetyMonitor()
mn = m2.apply_external(S.LOW, minor=True)
assert mn and "minor" in mn.scope_note and mn.minor
print("safety_llm logic OK")
