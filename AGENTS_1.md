# AGENTS.md · Project 2 · drawing-qa-agent
### An AI drawing-set reviewer: checks a set against its brief, separates "rule failed" from "needs human review", never edits drawings

> **To the coding agent reading this (OpenAI Codex, Google Antigravity or similar):** this file is the complete brief. **Build the whole project in one go.** Don't stop for approval between steps. When something is unclear, make the most reasonable choice, write it in `ASSUMPTIONS.md`, and keep going. Stop only at the **two hard stops** in section 10. The user builds by prompting, not by writing code. Keep code simple and readable, and finish with a plain-language walkthrough of every file so he can explain it in an interview.

---

## 1. Context
**User:** Ar. Vaibhav Patidar. COA-registered architect (B.Arch), Master's in Building Engineering and Management (SPA New Delhi), trainee project manager on interior fit-outs, freelance Revit/BIM documentation for about 14 residential sets. He has built an offline **Architectural AI prototype** (Streamlit app “Project Brain”) that turns a client brief into plan options, structure, services, BOQ and drawing sets, with demo projects **DemoVilla** and **DemoBungalow**. Its rule: **AI proposes, code checks, people approve.**

**Why this project:** he is applying to Superbuilt AI for *Associate Architect – AI Evaluation*. That role evaluates agent outputs against drawings, codes and briefs, records root causes, and builds evaluation sets. Their form also defines agentic-AI level 3 as “built a simple agent with LangChain”. This project is a working drawing reviewer with a measured evaluation. It's the first module of his prototype's rebuild, done properly.

**Deadline:** working, evaluated, documented and on GitHub by **Sunday 22 Nov 2026, night (IST)**.

## 2. What it does, in one paragraph
Given a **drawing package** (a project brief, an area statement, room geometry, a sheet index with callouts and revisions, and door/window tags and schedules), it runs deterministic checks, then a LangChain tool-calling agent writes a reviewer's report. Every finding has a **rule ID, sheet number, element, evidence and severity**, and is grouped as **RULE FAILED** (objective, code-measured) or **NEEDS HUMAN REVIEW** (judgement: design intent or code interpretation). The agent **never edits drawings or data**. A guardrail drops any finding the tools did not produce.

## 3. Rules
1. **Data:** only (a) synthetic packages this project generates, and (b) outputs from his own prototype's demo projects. **No employer (Awfis) data and no real client drawings.**
2. The API key lives only in `.env` (git-ignored). Never print it or ask for it in chat.
3. `python run.py --no-llm` must work with no API key, so the demo never fails.
4. **Check current LangChain / LangGraph documentation** before writing the agent and use the currently recommended tool-calling agent. Pin versions.
5. **No invented numbers.** The README and report use only figures produced by `evaluate.py`.
6. Don't claim code compliance. Rule thresholds are **project rules from the brief**, not statutory checks. Anything that needs code interpretation goes to NEEDS HUMAN REVIEW.

## 4. Stack
Python 3.10+ · pandas · shapely (polygon areas, overlaps) · **ezdxf** (read DXF exports, if the prototype has them) · matplotlib (annotated plan images) · langchain + langgraph · **LLM: Gemini via `langchain-google-genai`** by default (free key from Google AI Studio), switchable with `LLM_PROVIDER=gemini|openai|anthropic` (via `langchain-openai` / `langchain-anthropic`) if he has those keys · python-dotenv · pytest · Streamlit (one simple page).

## 5. Input format: one "drawing package" per folder
```
packages/<name>/
  brief.json            project, brief_version, plot (w, d, setbacks), limits (max_builtup_sqft, max_ground_coverage_pct, floors),
                        required_rooms: [{name, floor, min_area_sqft, count}]
  rooms.csv             room_id, floor, name, polygon (list of x,y in feet)  ← geometry "from the model"
  area_statement.csv    floor, room_name, area_sqft (as written on the sheet), floor_total_sqft, grand_total_sqft
  sheets.csv            sheet_no, title, brief_version, revision_index, revision_titleblock, has_overall_dims, rooms_dimensioned (list)
  callouts.csv          on_sheet, callout_type (section/detail/elevation), label, target_sheet, target_view
  openings.csv          tag, type (door/window), floor, room, width_mm, height_mm      ← tags as placed on plans
  opening_schedule.csv  tag, type, width_mm, height_mm                                  ← schedule on the sheet
  plans/*.png           optional plan images, for the annotated report
```
**Source 1: synthetic.** `make_packages.py` generates **three** packages:
- `demo_clean`: correct in every respect. Tests false positives; the expected result is zero RULE FAILED findings.
- `demo_seeded`: the same project with **exactly 12 planted errors** (section 7) and an `answer_key.csv`.
- `demo_mixed`: a second, different layout with **6 planted errors**, so the checker isn't tuned to one project.

**Source 2: his prototype (if available).** Ask once, at the first hard stop, for the path to his prototype folder. If it holds DemoVilla/DemoBungalow outputs (JSON, CSV, DXF or IFC), write `import_prototype.py` to convert one project into the package format. Rooms and areas come from DXF polylines and text or from its JSON; whatever can't be extracted is listed in `ASSUMPTIONS.md`. Run the checker on it and report findings **as unverified**. He checks them by hand afterwards. If the prototype isn't available or can't be parsed in reasonable time, skip it and say so. Never fake it.

## 6. Checks (`src/checks.py`): one pure function per rule
Each returns findings: `{finding_id, rule_id, group: RULE_FAILED|NEEDS_REVIEW, severity: high|medium|low, sheet_no, element, issue, evidence, values}`.

| Rule | Check | Group |
|---|---|---|
| R01 | Room area from polygon vs area statement (tolerance 2%, configurable) | RULE_FAILED |
| R02 | Area statement arithmetic: rooms sum to the floor total; floors sum to the grand total | RULE_FAILED |
| R03 | Every room required by the brief exists, in the required count and on the required floor | RULE_FAILED |
| R04 | Each required room meets the brief's min_area_sqft | RULE_FAILED |
| R05 | Built-up area and ground coverage within the brief's limits | RULE_FAILED |
| R06 | Sheet brief_version equals the current brief.json version (sheet drawn on an old brief) | RULE_FAILED |
| R07 | Every callout points to an existing sheet and view (broken section or detail reference) | RULE_FAILED |
| R08 | Every opening tag on the plans exists in the schedule, and vice versa; sizes match | RULE_FAILED |
| R09 | Revision in the sheet index equals the revision in the title block | RULE_FAILED |
| R10 | Plan sheets have overall dimensions, and every room is dimensioned | RULE_FAILED |
| R11 | Room names consistent across rooms.csv, area statement and brief (fuzzy match, e.g. “Mstr Bed” vs “Master Bedroom”) | NEEDS_REVIEW |
| R12 | Rooms overlap or leave gaps inside the footprint (geometry sanity) | NEEDS_REVIEW |
| R13 | Area within tolerance but the room is noticeably narrow (aspect ratio > 3:1) → usability question | NEEDS_REVIEW |

Keep tolerances in `rules.yaml` so he can change them without touching code.

## 7. Planted errors for `demo_seeded` (exactly 12, recorded in `answer_key.csv`)
1. Bedroom area on the statement 8% higher than its polygon (R01)
2. Ground-floor total doesn't equal the sum of its rooms (R02)
3. Grand total arithmetic error (R02)
4. Brief requires 2 toilets on the first floor; only 1 exists (R03)
5. Study is 20 sq ft below the brief minimum (R04)
6. Built-up area exceeds the brief limit (R05)
7. Two sheets still carry brief_version v1 when the brief is v2 (R06)
8. Section callout “A” points to a sheet that doesn't exist (R07)
9. Door tag D07 on the plan but missing from the schedule (R08)
10. Window W04 is 1200 mm wide on the plan list and 1500 mm in the schedule (R08)
11. Sheet A102: index says rev C, title block says rev B (R09)
12. Kitchen not dimensioned on its plan sheet (R10)

Plus 2 **review traps** that must land in NEEDS_REVIEW, not RULE_FAILED: a name variant (“Mstr Bed”) and a 3.5:1 passage-like room.

## 8. Agent (`src/agent.py`)
- Wrap each check as a LangChain tool with a clear docstring. Add one extra read-only tool, `get_package_summary`.
- System prompt (adapt as needed): *“You are a drawing-set reviewer for an architecture studio. Run every check tool on the package. Never change drawings or data. Keep each finding's evidence exactly as the tool returned it. Group findings as RULE FAILED or NEEDS HUMAN REVIEW. Write one plain sentence per finding saying what is wrong and what the architect should look at. Do not interpret building codes; if a finding needs interpretation, it is NEEDS HUMAN REVIEW. End with a 3-line summary for the project architect.”*
- **Guardrail (“code checks”):** after the LLM answers, keep only findings whose finding_id came from a tool. Log dropped items as `rejected_unsupported` and count them in the report. If the LLM changes a finding's group or evidence, restore the tool's version and log it.
- `--no-llm` mode: the same report from the tool outputs, without the prose.

## 9. Outputs
- `outputs/<package>/findings.csv`, plus **`report.html`**: header (project, brief version, date, mode), counts by group and severity, a findings table sorted by severity (rule, sheet, element, issue, evidence), the review list, and the guardrail log.
- `outputs/<package>/plan_annotated.png`: room polygons drawn with matplotlib, with failing rooms outlined in red and labelled with rule IDs. This becomes the portfolio image.
- `evaluate.py` → `outputs/eval.md`: for `demo_clean`, `demo_seeded` and `demo_mixed`, in both `--no-llm` and LLM mode, report caught / missed / false flags / correct grouping (RULE_FAILED vs NEEDS_REVIEW), plus precision and recall.
- `app.py`: a Streamlit page to pick a package, click Run (with or without the LLM), and see the table, review list and annotated plan.
- `README.md`: what it is, the rule *AI proposes, code checks, people approve*, a text architecture diagram, how to run it, evaluation results copied from eval.md, limitations (synthetic data; project rules, not statutory code; small test set; single run), and next steps.
- `WALKTHROUGH.md`: every file explained in 1–2 plain sentences, then “how a tool-calling agent works” in 5 sentences, then 5 likely interview questions with answers based on this repo.
- `outputs/demo_script.md`: a 90-second screen-recording script. `outputs/cv_bullet.md`: one CV bullet with the real numbers. `outputs/portfolio_page.md`: text for one portfolio page.

## 10. Order of work, with only two hard stops
**HARD STOP 1 (first message, 2 minutes).** Ask, in one message: (a) the path to his prototype folder, or “skip”; (b) whether `.env` holds `GOOGLE_API_KEY` (tell him the exact line to write, he creates the file himself); (c) whether he has an OpenAI or Anthropic key he wants as a fallback. Then **work without stopping**:

1. Set up a virtual environment, `requirements.txt` (pinned), `.gitignore`, `.env.example`, `rules.yaml`.
2. Write `make_packages.py` and generate the three packages with their answer keys.
3. Write `checks.py` and `tests/test_checks.py`. Get pytest green.
4. Write `run.py --no-llm` and `report.py`. Produce reports and annotated plans for all packages.
5. Write `evaluate.py` and run it in `--no-llm` mode. Fix genuine bugs only; don't tune rules to the answer key beyond the stated tolerances.
6. Check the current LangChain docs, write `agent.py` with the guardrail, run it in LLM mode, and evaluate again.
7. *(If he gave a prototype path)* `import_prototype.py`, then run it on one demo project, with findings marked unverified.
8. `app.py` (Streamlit), README, WALKTHROUGH, demo script, CV bullet, portfolio text.
9. `git init` and commit locally.

**HARD STOP 2 (before publishing).** Show the eval table and the file list, then ask before creating the public GitHub repo `drawing-qa-agent` and pushing. Use `gh` if he is logged in; otherwise give him 4 simple steps.

If time runs out, finish in this priority order: steps 1–5 (works and is evaluated), then step 6 (agent), then step 8, then step 7.

## 11. Definition of done
- `python run.py --package demo_seeded --no-llm` and `python run.py --package demo_seeded` both work from a fresh clone (with `.env`)
- pytest passes. `demo_clean` produces zero RULE FAILED findings, or the false flags are reported honestly in eval.md
- eval.md shows caught / missed / false flags / grouping for all packages in both modes
- An annotated plan image and an HTML report exist for each package
- README and WALKTHROUGH are written in plain language, with real numbers only
- Public GitHub repo, `.env` not committed, no real client or employer data
