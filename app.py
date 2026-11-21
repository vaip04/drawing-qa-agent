"""Streamlit Dashboard for Drawing QA Agent.

Interactive web interface to:
- Select drawing packages (demo_clean, demo_seeded, demo_mixed, demo_prototype_import)
- Toggle execution mode (Deterministic Rule Suite vs LangChain LLM Tool-Calling Agent)
- Inspect high-level metrics (RULE FAILED vs NEEDS REVIEW)
- View interactive findings table with rule IDs, severity, elements, and evidence
- Review annotated floor plan drawings with failing rooms outlined in red
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from PIL import Image

from src.loader import load_package, load_rules
from src.checks import run_all_checks
from src.report import generate_annotated_plan, render_html_report

st.set_page_config(
    page_title="Drawing QA Agent — AI Drawing Set Reviewer",
    page_icon="📐",
    layout="wide",
)

st.title("📐 Drawing QA Agent")
st.subheader("Automated Drawing-Set Reviewer: Objective Checks & Human Review Categorization")
st.caption("AI proposes, code checks, people approve.")

# Sidebar controls
st.sidebar.header("Review Configuration")
pkg_dir = Path("packages")
available_pkgs = [p.name for p in pkg_dir.iterdir() if p.is_dir()] if pkg_dir.exists() else []

selected_pkg_name = st.sidebar.selectbox("Select Drawing Package", available_pkgs, index=available_pkgs.index("demo_seeded") if "demo_seeded" in available_pkgs else 0)
use_llm = st.sidebar.checkbox("Enable LLM Reviewer Agent (Gemini)", value=False, help="Uses LangChain tool-calling agent to review findings and synthesize report. When unchecked, runs purely deterministic rule suite.")

run_btn = st.sidebar.button("Run Drawing Review", type="primary")

if run_btn or f"results_{selected_pkg_name}" in st.session_state:
    with st.spinner("Analyzing drawing set package..."):
        pkg_path = Path("packages") / selected_pkg_name
        pkg = load_package(pkg_path)
        rules = load_rules()
        out_dir = Path("outputs") / selected_pkg_name
        out_dir.mkdir(parents=True, exist_ok=True)

        if use_llm:
            try:
                from src.agent import run_reviewer_agent
                agent_res = run_reviewer_agent(pkg, rules)
                findings = agent_res["findings"]
                llm_summary = agent_res.get("summary", "")
                guardrail_log = agent_res.get("guardrail_log", {"rejected_unsupported": [], "restored_count": 0})
                mode_str = "LLM"
            except Exception as e:
                st.warning(f"LLM agent encountered an error ({e}). Defaulting to deterministic check suite.")
                findings = run_all_checks(pkg, rules)
                llm_summary = "Evaluated via deterministic rule suite."
                guardrail_log = {"rejected_unsupported": [], "restored_count": 0}
                mode_str = "NO-LLM (Fallback)"
        else:
            findings = run_all_checks(pkg, rules)
            llm_summary = ""
            guardrail_log = {"rejected_unsupported": [], "restored_count": 0}
            mode_str = "NO-LLM"

        # Generate outputs
        plan_out = out_dir / "plan_annotated.png"
        generate_annotated_plan(pkg, findings, plan_out)

        html_out = out_dir / "report.html"
        render_html_report(pkg, findings, html_out, mode=mode_str, llm_summary=llm_summary, guardrail_log=guardrail_log)

        failed_findings = [f for f in findings if f.get("group") == "RULE_FAILED"]
        review_findings = [f for f in findings if f.get("group") == "NEEDS_REVIEW"]

    # Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Project Name", pkg["brief"].get("project", selected_pkg_name))
    m2.metric("Brief Version", pkg["brief"].get("brief_version", "v1"))
    m3.metric("RULE FAILED (Objective)", len(failed_findings), delta=None, delta_color="inverse")
    m4.metric("NEEDS HUMAN REVIEW", len(review_findings))

    if llm_summary:
        st.info(f"**Architectural Review Summary:**\n\n{llm_summary}")

    # Tabs for Details
    tab_failed, tab_review, tab_plan, tab_guardrail = st.tabs([
        f"🚨 Rule Failed ({len(failed_findings)})",
        f"📋 Needs Human Review ({len(review_findings)})",
        "🗺️ Annotated Plan",
        "🛡️ Guardrail Log"
    ])

    with tab_failed:
        if failed_findings:
            df_failed = pd.DataFrame(failed_findings)
            cols = [c for c in ["rule_id", "severity", "sheet_no", "element", "issue", "evidence"] if c in df_failed.columns]
            st.dataframe(df_failed[cols], use_container_width=True)
        else:
            st.success("Zero rule failures detected! Drawing package passes all deterministic checks.")

    with tab_review:
        if review_findings:
            df_review = pd.DataFrame(review_findings)
            cols = [c for c in ["rule_id", "severity", "sheet_no", "element", "issue", "evidence"] if c in df_review.columns]
            st.dataframe(df_review[cols], use_container_width=True)
        else:
            st.info("No items requiring human architectural judgement or design review.")

    with tab_plan:
        if plan_out.exists():
            st.image(Image.open(plan_out), caption=f"Annotated Drawing Layout — {selected_pkg_name}", use_column_width=True)
        else:
            st.write("Plan visualization not available.")

    with tab_guardrail:
        st.write("**Code Checks Guardrail Status:** Active")
        st.write(f"- Unsupported / Hallucinated findings dropped: {len(guardrail_log.get('rejected_unsupported', []))}")
        st.write(f"- Altered fields restored to original tool values: {guardrail_log.get('restored_count', 0)}")
        if guardrail_log.get("rejected_unsupported"):
            st.write("Dropped Findings:")
            st.json(guardrail_log["rejected_unsupported"])
