# Drawing QA Agent — Demo Script (90 Seconds)

**Visual:** Split screen showing terminal and VS Code / browser window.

**[00:00 - 00:15] Introduction & The Problem**
> *"Hi, I'm Vaibhav Patidar. In architectural practice and fit-outs, coordinating drawing sets—ensuring every room matches the brief, door tags match schedules, and area statements add up—takes hours of manual checking. When an AI assists in reviewing drawings, how do we ensure it doesn't hallucinate errors or invent numbers? Here is Drawing QA Agent."*

**[00:15 - 00:35] Architecture & Guardrail Principle**
> *"The foundational rule here is: **AI proposes, code checks, people approve.** We built deterministic pure Python checks using Shapely and pandas for thirteen core drawing rules. A LangChain tool-calling agent orchestrates the review, but we enforce a hard guardrail: the agent cannot alter evidence, and any finding not produced by a deterministic check tool is immediately rejected."*

**[00:35 - 00:55] Running the Review & Inspecting Outputs**
> *(Screen shows `python run.py --package demo_seeded --no-llm` running in 0.8s)*
> *"Watch how fast this runs even without an LLM. On our seeded villa package with 12 planted errors, it catches all 12 defects across room area discrepancies, broken callouts, dimension omissions, and schedule mismatches. It also identifies design-intent questions—like narrow 3.5:1 passages—categorizing them as NEEDS HUMAN REVIEW rather than hard failures."*

**[00:55 - 01:15] The Visual Report & Streamlit Dashboard**
> *(Screen switches to `outputs/demo_seeded/report.html` and Streamlit app)*
> *"The output is an executive HTML report and an annotated drawing plan where failing rooms are highlighted in red with rule tags. Here in the Streamlit interface, an architect can toggle between clean, seeded, and mixed packages, review the guardrail audit log, and approve findings with full transparency."*

**[01:15 - 01:30] Rigorous Evaluation & Closing**
> *(Screen displays `outputs/eval.md` showing 100% recall on planted defects and 0 false positives on clean sets)*
> *"Our automated evaluation benchmarks precision and recall without invented numbers: zero false positives on clean packages, and 100% recall on planted defects. This represents the first reliable module of an agentic architectural documentation pipeline. Thank you!"*
