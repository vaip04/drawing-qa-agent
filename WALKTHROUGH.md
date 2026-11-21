# WALKTHROUGH.md

This document provides a plain-language explanation of every file in this repository, explains how tool-calling agents operate in architecture, and outlines 5 realistic interview questions and answers based on this implementation.

---

## 1. File-by-File Walkthrough

- **`AGENTS.md`**: The master project brief defining the problem statement, rules, data schemas, planted errors, and evaluation constraints for the Drawing QA Agent.
- **`ASSUMPTIONS.md`**: Engineering record documenting practical decisions, including handling prototype catalogue inputs, Python 3.12 environment setup, and rule tolerances.
- **`requirements.txt`**: Pinned dependency list guaranteeing reproducible builds across Shapely, pandas, matplotlib, LangChain, and Streamlit.
- **`rules.yaml`**: Externalized configuration file defining numerical thresholds and tolerances (e.g., 2% area difference, 3:1 aspect ratio) so architects can tune checks without code changes.
- **`make_packages.py`**: Generates synthetic drawing packages (`demo_clean`, `demo_seeded`, `demo_mixed`) representing architectural drawing sets and exports the 12-error answer key.
- **`import_prototype.py`**: Reads space standards and naming catalogues from the prototype folder and maps them into an unverified test drawing package.
- **`src/loader.py`**: Loads package folders into clean pandas DataFrames and dictionaries, parsing geometry polygons and sheet metadata.
- **`src/checks.py`**: The core deterministic checking engine containing pure functions for R01 through R13, returning structured findings with IDs, severity, element, and evidence.
- **`src/report.py`**: Renders comprehensive HTML reports and generates annotated plan images where failing spaces are highlighted in red with rule tags.
- **`src/agent.py`**: LangChain tool-calling agent wrapping check functions into LLM tools and enforcing the hard guardrail that drops hallucinations and preserves evidence.
- **`run.py`**: Command-line entry point to run drawing set reviews across any package in either `--no-llm` mode or full LLM agent mode.
- **`evaluate.py`**: Automated evaluation script measuring precision, recall, caught defects, false flags, and review grouping against the answer key without invented figures.
- **`app.py`**: Interactive Streamlit web application enabling architects to pick a package, trigger reviews, view metric cards, inspect findings, and see highlighted plans.
- **`tests/test_checks.py`**: Pytest test suite verifying that clean packages yield zero rule failures and that all planted defects in seeded sets are accurately caught.

---

## 2. How a Tool-Calling Agent Works (In 5 Sentences)

1. A tool-calling agent receives a user prompt and an architectural package along with a defined registry of callable Python tools representing deterministic validation checks.
2. Rather than relying on fuzzy model weights to calculate polygon areas or schedule counts, the agent inspects the available tools and issues structured function calls with exact parameters.
3. The host runtime executes each tool in code, returning verified mathematical truths and rule outputs back into the conversation context as tool messages.
4. The language model synthesizes these factual findings into human-readable executive summaries, clarifying which items require architectural redesign versus builder coordination.
5. Finally, a deterministic guardrail intercepts the model's response, immediately dropping any finding that was not produced by a registered tool and guaranteeing zero hallucinated defects.

---

## 3. Interview Questions & Model Answers

### Q1: Why separate findings into "RULE FAILED" and "NEEDS HUMAN REVIEW" instead of just listing everything as an error?
**Answer:** Architectural documentation involves two fundamentally different categories of problems. Objective discrepancies—such as a schedule showing 1200mm while the plan shows 1500mm, or floor areas that don't add up arithmetically—are mathematical errors governed by hard project rules. Conversely, aspects like a room having a 3.5:1 aspect ratio or subtle name variants like "Mstr Bed" reflect design intent, circulation trade-offs, or code interpretation that code cannot unilaterally fail. Forcing subjective observations into "rule failures" produces alert fatigue; categorizing them into human review respects professional judgment while keeping hard errors actionable.

### Q2: How do you guarantee the LLM doesn't hallucinate non-existent drawing errors or alter critical measurements?
**Answer:** We enforce the core principle: *AI proposes, code checks, people approve.* The LLM is never given direct write access to drawings or data, and it does not perform spatial calculations in its prompt. Every check is a pure Python function returning a unique UUID finding ID, numeric values, and raw evidence. Our post-processing guardrail (`src/agent.py`) cross-references every finding emitted by the model against the dictionary of genuine tool outputs; if an ID was not generated by code, it is dropped as `rejected_unsupported`, and if any evidence or rule group was altered, the verified tool version is restored.

### Q3: Why did you implement a `--no-llm` mode?
**Answer:** In production engineering environments, mission-critical QA pipelines must never fail simply because an external API is down, rate-limited, or running without internet access. By decoupling the deterministic checking suite (`src/checks.py`) from the generative prose layer, the entire reviewer functions standalone with zero API keys. This ensures that CI/CD test runners, local drafting setups, and evaluation benchmarks remain 100% reliable, fast, and deterministic.

### Q4: How does your system evaluate polygon geometry against tabular schedules?
**Answer:** We parse the vector room boundaries into 2D Cartesian polygons using Shapely. From these polygons, we calculate the true geometric area and aspect ratio via minimum rotated bounding rectangles. We then join the geometric model with tabular records extracted from the area statement and door/window schedules using exact and fuzzy matching heuristics. This allows us to catch discrepancies between the drawn geometry and the written sheet notes, which is one of the most common sources of contractor RFIs and site variation claims.

### Q5: How would you extend this system from synthetic 2D packages to production BIM or CAD drawing sets?
**Answer:** The architecture is deliberately decoupled into loader, checks, and reviewer layers. To ingest live CAD or Revit packages, we would extend `src/loader.py` using `ezdxf` to extract polylines, room boundary hatch layers, and text blocks from DXF/DWG exports, or `ifcopenshell` to parse native IFC spatial containers and property sets. Because `src/checks.py` operates on standardized pandas DataFrames and Shapely geometry, the downstream validation rules, guardrails, and reporting remain completely unchanged.
