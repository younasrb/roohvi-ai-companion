"""
Run the team's test lines through the safety classifier.

    python -m tests.run_csv tests/safety_cases.sample.csv
    python -m tests.run_csv tests/safety_cases_holdout2.csv --llm     # regex + semantic screen (needs your Gemini key)

CSV columns: id, jumla, zubaan, expected
expected is ONE of:
  low | elevated | high   -> checked against the classifier's level
  scope                    -> a diagnosis / medication ask: classifier must attach a scope note
  refuse                   -> jailbreak / method request: needs the live model, so it is only LISTED here
                              (run those by hand in the app and tick them off)
Exit code 1 if any checkable row fails.
"""
import csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import safety as S


def run(path: str, use_llm: bool = False) -> int:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))
    need = {"id", "jumla", "zubaan", "expected"}
    if not rows or not need <= set(rows[0].keys()):
        print("CSV must have columns:", ", ".join(sorted(need))); return 2
    fails, manual, checked = [], [], 0
    for r in rows:
        exp = (r["expected"] or "").strip().lower()
        res = S.classify(r["jumla"])
        if use_llm:
            from core import safety_llm
            ext = safety_llm.classify(r["jumla"], timeout=15)
            if ext:
                if S.rank(ext["level"]) > S.rank(res.level):
                    res.level = ext["level"]
                if ext["scope"] and not res.scope_note:
                    res.scope_note = "semantic"
        if exp in ("low", "elevated", "high"):
            checked += 1
            if res.level != exp:
                fails.append((r["id"], exp, res.level, r["jumla"]))
        elif exp == "scope":
            checked += 1
            if not res.scope_note:
                fails.append((r["id"], "scope note", "none", r["jumla"]))
        elif exp == "refuse":
            manual.append(r)
        else:
            fails.append((r["id"], "valid expected value", exp or "(empty)", r["jumla"]))
    print(f"{checked - len([f for f in fails if f[0] in {r['id'] for r in rows}])}/{checked} checkable rows passed; "
          f"{len(manual)} need a manual model check")
    for i, e, g, t in fails:
        print(f"  FAIL {i}: expected {e}, got {g}  <- {t[:80]}")
    if manual:
        print("  Manual (live model must refuse):", ", ".join(r["id"] for r in manual))
    by = {}
    for r in rows:
        by[r["expected"]] = by.get(r["expected"], 0) + 1
    print("  Mix:", by)
    return 1 if fails else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(run(args[0] if args else "tests/safety_cases.sample.csv", use_llm="--llm" in sys.argv))
