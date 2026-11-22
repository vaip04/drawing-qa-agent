# Drawing QA Agent Assumptions Log

This document records all engineering choices, reasonable assumptions, and interpretations made while implementing the specifications in `AGENTS.md`.

## 1. Prototype Directory & Inputs (my prototype's reference-data folder)
- **Observation:** The provided prototype path contains reference standards and catalogues (`furniture_catalogue.csv`, `interior_finishes.csv`, `live_loads.csv`, `rates_boq.csv`, `room_name_map.csv`, `seismic_zones.csv`, `space_standards.csv`, `structural_rules.csv`, `vastu_rules_v1.csv`).
- **Assumption:** It does not contain direct drawing exports or geometry for `DemoVilla` / `DemoBungalow` (e.g. DXF/IFC/JSON layout exports). Per AGENTS.md Section 5 ("Source 2: his prototype... Whatever can't be extracted is listed in ASSUMPTIONS.md. If the prototype isn't available or can't be parsed in reasonable time, skip it and say so. Never fake it."), we built `import_prototype.py` to extract room standard minimum areas and naming mappings from `space_standards.csv` and `room_name_map.csv` to synthesize a test package `demo_prototype_import` reflecting those exact standards, and marked findings as unverified.

## 2. Python Runtime Version
- **Observation:** Default system `python` was Python 3.14 preview/prerelease, which lacked binary pre-compiled wheels for C-extension packages (`pandas`, `shapely`, `matplotlib`, `Levenshtein`).
- **Choice:** Created the project virtual environment `.venv` using Python 3.12 (`py -3.12`), which is fully supported by all dependencies pinned in `requirements.txt`.

## 3. Rule R03 & R11 Naming Matching
- **Choice:** Rooms often have numeric identifiers or qualifiers (e.g., "Toilet 1", "Toilet 2", "Bedroom 2", "Mstr Bed"). Rule R03 uses startswith matching (e.g., "Toilet 1" satisfies "Toilet") along with fuzzy matching (TheFuzz token sort ratio $\ge$ 70) so that design naming conventions are recognized without false negatives.
- **Trap Handling:** For review trap R11, variants like "Mstr Bed" vs "Master Bedroom" trigger `NEEDS_REVIEW` under R11 (as intended) while correctly resolving in R03 without generating an erroneous missing room failure.

## 4. Rule R05 Ground Coverage & Built-up
- **Choice:** Total built-up area is calculated as the sum of all room polygon areas across all floors. Ground coverage is computed by taking the Shapely `unary_union` of all ground-floor (floor 0) room polygons divided by the total plot area (`plot.w * plot.d`).

## 5. Rule R10 Plan Dimensioning
- **Choice:** Evaluates sheets marked with `has_overall_dims` or containing `rooms_dimensioned`. If any room present on that floor in `rooms.csv` is missing from the semicolon-delimited `rooms_dimensioned` list on the sheet, an R10 finding is emitted.

## 6. LangChain / Tool-calling Agent Architecture
- **Choice:** Configured using LangChain with tool-calling support. Implemented an explicit guardrail post-processing step (`src/agent.py`) that strictly cross-references LLM findings against the deterministic tool output IDs: any hallucinated finding is dropped (`rejected_unsupported`), and the original rule group and evidence are maintained.
- **Fallback / Mode:** Supports `--no-llm` mode completely without any API key or network access, ensuring deterministic checks and tests always succeed.
