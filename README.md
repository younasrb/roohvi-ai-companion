# Roohvi

A voice-first **AI wellness and emotional-support companion** for the desktop.
Talk or type; it listens, offers short coping activities, does optional mood
check-ins, and points to real people and professional help when that is what's needed.

> **Roohvi is an AI. It is not a therapist, doctor or emergency service.**
> It does not diagnose, does not advise on medication, and cannot contact anyone for you.
> If you may be in danger, contact your local emergency services or a crisis line.

Built on the Mark LIV ("Jarvis") desktop-assistant engine: PyQt6 UI, Gemini Live voice,
animated avatar, plugin/action loader. All computer-control tools were removed; the
originals are kept in `_archived_jarvis/` for reference only.

## What it does

| Feature | Where |
|---|---|
| Empathetic voice conversation (Urdu, Roman Urdu, English, more) | `main.py`, `core/prompt.txt` |
| Mood check-in (mood / energy / stress / sleep, 1-5, self-reported) | `actions/mood_checkin.py` |
| Weekly summary (plain averages, only with enough data) | `actions/wellness_summary.py` |
| Coping activities: breathing, grounding, mindfulness, journaling, sleep, break, social, study/work | `actions/coping_activity.py` |
| Support & crisis resources by region | `actions/support_resources.py`, `config/resources.json` |
| Privacy controls: consent, export, delete | `actions/wellness_data.py`, `core/wellness_store.py` |
| Safety layer: input screen, response policy, output check, minor signals, memory guard | `core/safety.py` |
| Knowledge base: reviewed, sourced entries searched before the assistant explains anything | `knowledge/`, `core/knowledge.py`, `actions/search_knowledge.py` |
| Country setting so local helplines come first | `actions/set_region.py` |
| **Nazar**: optional camera. Off at every start; one still photo, only when you ask; shown on screen; never saved | `actions/nazar.py` |

## Interface (designed for wellbeing, not for a sci-fi HUD)

- Calm dusk palette (warm blue-violet, sage accent, warm off-white text), rounded soft cards, no neon.
- **"Need help now?"** is always in the header: emergency numbers and crisis lines are one tap away, no model round-trip.
- **Mood chips** (Good / Okay / Low / Stressed / Anxious) under the face: say how you feel in one tap.
- **Breathing circle** (in 4, hold 1, out 6, six breaths) opens instantly from Quick Actions or when the assistant starts a breathing exercise; tap anywhere to stop.
- "This Week" shows only your own ratings, in neutral colours, never as a health score.
- Footer always says: AI wellness companion, not a therapist, doctor or emergency service.

## Character

The built-in 3D character wears a white coat for an approachable look. Because a white coat can suggest medical
authority, it always carries a badge reading **"AI COMPANION / NOT A DOCTOR"** (drawn on the coat in
`assets/avatar3d/characters.js`) and the dashboard shows the same disclosure as a tag beside the character.
Do not remove either. There is deliberately no stethoscope or medical symbol.

## Safety design (read before relying on it)

1. Every message (typed or spoken) is screened into **low / elevated / high** concern by TWO layers: an instant
   regex screen (`core/safety.py`, offline, cannot fail) and a background semantic screen (`core/safety_llm.py`,
   a small Gemini text call that understands meaning in English/Urdu/Roman Urdu and can only RAISE the level).
   These are internal policy labels, never diagnoses, never shown as a "score".
2. Elevated/high concern shows a **support card on screen immediately** and sends the model a
   policy note (`[SAFETY_POLICY ...]`). The system prompt carries the same rules, so a missed
   keyword does not remove the policy.
3. Replies are checked for diagnosis, medication advice, dependency language, secrecy promises
   and overconfidence; a violation is corrected on the next turn and counted.
4. Only aggregate counters are stored (`memory/safety_events.json`), never message text.

**Measured limits (honest numbers):** the regex layer alone, on lines written fresh and NOT used to tune it, caught
29/48 and then 11/24 (recall on 'elevated' as low as 1 in 8). Adding patterns raises the score on known sets but not on
new wording, which is why the semantic layer exists. The semantic layer was unit- and integration-tested with a fake model
only: measure it on your PC with `python -m tests.run_csv tests/safety_cases_holdout2.csv --llm` before trusting it.

**Other limits:** the screen is not a clinical instrument. It will
miss things and sometimes over-trigger. In voice mode the model starts answering while the screen
runs, so the screen's note shapes the *next* turn; the prompt covers the turn in flight.
Treat this as a prototype, test it with your own scenarios (`python -m tests.test_safety`), and
have a qualified professional review it before real-world use.

## Knowledge base (team entries)

Put entries in `knowledge/` using `knowledge/_TEMPLATE.md`. Optional `Audience:` line: `authors` = style guide for writers
(never served), `model` = language/culture notes the assistant may use but that are never put on screen. An entry is served **only** if it has a
Source URL (http...) and a Reviewer name, and passes the content rules (no diagnosis, medication
advice, secrecy/guarantees, or self-harm detail). Anything else is skipped; see
`python -c "from core import knowledge; print(knowledge.load_report())"`.

## What is in the knowledge base now

PRO (10, professional help in Pakistan), EDU (10, psychoeducation), LNG (6 served + 4 style guides folded into the prompt),
SAF (10 x 3 languages, guidance for the assistant, never shown on screen). Source lists and trackers are in `knowledge/sources/`.
Helpline numbers come from `config/resources.json` (province-aware: PK-SD, PK-PB; abuse line 1099), never from the entries.

## Tests

```
python -m tests.test_safety                       # classifier cases
python -m tests.test_knowledge                    # knowledge gates
python -m tests.test_safety_llm                   # semantic screen logic (fake model)
python -m tests.run_csv tests/safety_cases.csv    # the team's CSV (columns: id,jumla,zubaan,expected)
python -m tests.run_csv tests/safety_cases_holdout.csv   # 48 extra lines
python -m tests.run_csv tests/safety_cases_holdout2.csv --llm   # fresh lines, regex + semantic screen
```

## Privacy

- Nothing about check-ins is saved until you turn **tracking ON** (default OFF).
- Data stays on this machine (`memory/`). Export or delete any time ("delete everything" asks for confirmation).
- No clipboard watching, no phone-remote server, no screen capture.
- **Nazar (camera) is the user's choice:** OFF every time the app starts; turned on only with the NAZAR button in Settings; then it takes ONE still photo only when you ask to be seen (never video, never in the background), shows you exactly that photo, sends it to Gemini with your message, and does not save it. It switches itself off after 30 minutes. The assistant is told not to infer emotions or health from your face, and never to identify anyone.
- Speech and text are sent to Google's Gemini API. On a **free** API key Google may use content to
  improve its products; a billing-enabled key is more private. First run shows a consent notice.

## Run

```
Windows:    start_windows.bat
Linux/Mac:  ./start_linux_mac.sh
```
Python 3.11-3.13. On first run enter your Gemini API key and accept the notice.
Set your country in `config/api_keys.json` (`"region": "PK"`) so local helplines are shown first.

## Before you share or ship it

- **Verify every number** in `config/resources.json`. Pakistan entries were checked against public
  listings in Oct 2026 and Umang's number differs between sources; other regions were not re-checked.
- Wake word is optional (off by default). Until you train a custom "Hey Roohvi" model (see `docs/WAKE_WORD.md`, drop it in `models/wake/`) it uses the stock "Hey Mycroft" phrase. The WAKE NOW button always works.
- The 3D avatar is the stock character; add your own `assets/avatar/photo.jpg` + `face.json` if wanted.

## Team

Designed by the Roohvi team.

| Role | Name | Area |
|---|---|---|
| Team Lead | Muhammad Younas | Direction, final review |
| Member | Saifullah | Coping techniques (COP) |
| Member | Bibi Hani | Psychoeducation (EDU) |
| Member | Zuhaib Ahmed | Safety and crisis (SAF) |
| Member | Amir Khan | Professional help, Pakistan (PRO) |
| Member | Maria | Language, culture, testing (LNG + test lines) |

The same names appear in the "Designed by" card on the home screen (`TEAM_LEAD` / `TEAM_MEMBERS` in `core/zehan_ui.py`).

## Voice model

`main.py` tries `gemini-3.8-live` first and falls back to the older `gemini-3.1-flash-live-preview` if the
server says a model is unavailable. To force one, add `"live_model": "gemini-3.8-live"` to `config/api_keys.json`.
Connection problems now appear as a message above the mood chips (the log panel is not shown on the home screen).

## License / attribution

Derived from **Mark LIV** by FatihMakes, licensed **CC BY-NC 4.0**: keep attribution; commercial use is not allowed.
