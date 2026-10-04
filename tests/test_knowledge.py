"""Knowledge gate test: only reviewed + sourced + rule-abiding entries are served.
    python -m tests.test_knowledge
"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import knowledge as K

GOOD = """ID: T-01
Title: Slow breathing
Zubaan: English
Kab kaam aata: feeling stressed or anxious, racing heart
Steps ya samjhana (150-300 words):
Breathe in gently for four counts and out for six. Repeat for about two minutes.
Kab ruk jana ya madad lena zaroori hai:
Stop if you feel dizzy. If distress lasts for weeks, see a doctor.
Source URL: https://example.org/breathing
Source ka naam / date jab dekha: Example Health, 2026-10-03
Likhne wale ka naam: A
Reviewer ka naam: B
"""
def variant(**kw):
    t = GOOD
    for k, v in kw.items():
        t = "\n".join(f"{k}: {v}" if l.startswith(k) else l for l in t.splitlines())
    return t

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "good.md").write_text(GOOD + "\n---\n" + variant(ID="T-02", Title="Grounding").replace("Slow breathing", "x"), encoding="utf-8")
    (d / "noreview.md").write_text(variant(ID="T-03", **{"Reviewer ka naam": ""}), encoding="utf-8")
    (d / "nosource.md").write_text(variant(ID="T-04", **{"Source URL": "none"}), encoding="utf-8")
    (d / "diag.md").write_text(variant(ID="T-05").replace("Breathe in gently", "You have depression. Breathe in gently"), encoding="utf-8")
    (d / "_template.md").write_text(GOOD, encoding="utf-8")
    # guidance FOR the assistant may quote forbidden phrases in order to forbid them; user-facing text may not
    quoted = GOOD.replace("ID: T-01", "ID: T-07").replace("Breathe in gently", "Never say \"I won't tell anyone\" or mention any method of self-harm. Breathe in gently")
    (d / "modelguide.md").write_text(quoted + "Audience: model\n", encoding="utf-8")
    (d / "userquoted.md").write_text(quoted.replace("ID: T-07", "ID: T-08"), encoding="utf-8")
    # the same entry in three languages must come back once
    (d / "multi.md").write_text("\n---\n".join(GOOD.replace("ID: T-01", "ID: T-09").replace("Zubaan: English", f"Zubaan: L{i}") for i in range(3)), encoding="utf-8")
    (d / "guide.md").write_text(GOOD.replace("ID: T-01", "ID: T-06") + "Audience: authors\n", encoding="utf-8")
    K.DIR = d; K._cache = None
    rep = K.load(force=True)
    served = {e["id"] for e in rep["entries"]}
    skipped = {i: r for _, i, r in rep["skipped"]}
    print("served:", sorted(served)); print("skipped:", skipped)
    assert "T-01" in served and "T-02" in served, served
    assert "not reviewed yet" in skipped["T-03"]
    assert "source" in skipped["T-04"]
    assert "content rule" in skipped["T-05"]
    assert "T-07" in served, "model guidance that forbids a phrase must be served"
    assert "T-08" not in served, "the same text in a user-facing entry must be rejected"
    assert [e["id"] for e in K.search("slow breathing stress")].count("T-09") <= 1
    assert "T-06" not in served and "style guide" in skipped["T-06"]
    assert "T-ID-template" not in served
    e1 = next(e for e in rep["entries"] if e["id"] == "T-01")
    assert e1["source"] == "https://example.org/breathing", repr(e1["source"])          # not polluted by the next line
    assert e1["source_note"].startswith("Example Health"), repr(e1["source_note"])
    assert "AI tool" not in e1["source_note"]
    hit = K.search("I feel stressed with a racing heart")
    assert hit and hit[0]["id"] == "T-01", hit
    assert K.search("football scores") == []
    from actions.search_knowledge import search_knowledge
    out = search_knowledge({"query": "breathing for stress"})
    assert "Source:" in out and "Use ONLY the material below" in out
    assert "Nothing reviewed" in search_knowledge({"query": "football"})
print("knowledge gates OK")
