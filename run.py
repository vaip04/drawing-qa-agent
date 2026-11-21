"""Drawing QA Agent runner.

Usage:
  python run.py --package demo_seeded --no-llm
  python run.py --package demo_seeded
  python run.py --all --no-llm
"""

import argparse
import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

from src.loader import load_package, load_rules
from src.checks import run_all_checks
from src.report import generate_annotated_plan, render_html_report

load_dotenv()


def run_package(pkg_name: str, no_llm: bool = False, rules=None) -> dict:
    pkg_path = Path("packages") / pkg_name
    if not pkg_path.exists():
        raise FileNotFoundError(f"Package directory not found: {pkg_path}")

    print(f"\n========================================================")
    print(f"Running Drawing QA Review on: {pkg_name} ({'NO-LLM' if no_llm else 'LLM Mode'})")
    print(f"========================================================")

    pkg = load_package(pkg_path)
    if rules is None:
        rules = load_rules()

    out_dir = Path("outputs") / pkg_name
    out_dir.mkdir(parents=True, exist_ok=True)

    findings = []
    llm_summary = ""
    guardrail_log = {"rejected_unsupported": [], "restored_count": 0}

    if no_llm:
        findings = run_all_checks(pkg, rules)
    else:
        # LLM tool-calling agent flow
        try:
            from src.agent import run_reviewer_agent
            agent_result = run_reviewer_agent(pkg, rules)
            findings = agent_result["findings"]
            llm_summary = agent_result.get("summary", "")
            guardrail_log = agent_result.get("guardrail_log", guardrail_log)
        except Exception as e:
            print(f"[WARN] LLM Agent failed or not configured: {e}. Falling back to deterministic checks.")
            findings = run_all_checks(pkg, rules)
            llm_summary = f"Review conducted via deterministic rule suite (LLM fallback: {e})"

    # Save findings.csv
    findings_df = pd.DataFrame(findings)
    if not findings_df.empty:
        # Keep clean columns
        cols = [c for c in ["finding_id", "rule_id", "group", "severity", "sheet_no", "element", "issue", "evidence"] if c in findings_df.columns]
        findings_df[cols].to_csv(out_dir / "findings.csv", index=False)
    else:
        pd.DataFrame(columns=["finding_id", "rule_id", "group", "severity", "sheet_no", "element", "issue", "evidence"]).to_csv(out_dir / "findings.csv", index=False)

    # Generate annotated plan
    plan_out = out_dir / "plan_annotated.png"
    generate_annotated_plan(pkg, findings, plan_out)

    # Render HTML report
    report_out = out_dir / "report.html"
    render_html_report(
        pkg=pkg,
        findings=findings,
        out_path=report_out,
        mode="NO-LLM" if no_llm else "LLM",
        llm_summary=llm_summary,
        guardrail_log=guardrail_log
    )

    failed_count = sum(1 for f in findings if f.get("group") == "RULE_FAILED")
    review_count = sum(1 for f in findings if f.get("group") == "NEEDS_REVIEW")

    print(f"Results for {pkg_name}:")
    print(f"  • RULE_FAILED: {failed_count}")
    print(f"  • NEEDS_REVIEW: {review_count}")
    print(f"  • Report: {report_out}")
    print(f"  • Plan: {plan_out}")

    return {
        "pkg_name": pkg_name,
        "findings": findings,
        "failed_count": failed_count,
        "review_count": review_count,
        "llm_summary": llm_summary,
        "guardrail_log": guardrail_log,
    }


def main():
    parser = argparse.ArgumentParser(description="Drawing QA Agent Runner")
    parser.add_argument("--package", type=str, default="demo_seeded", help="Package to review (in packages/)")
    parser.add_argument("--no-llm", action="store_true", help="Run deterministic checks only without calling LLM")
    parser.add_argument("--all", action="store_true", help="Run on all packages")
    args = parser.parse_args()

    if args.all:
        pkgs = [p.name for p in Path("packages").iterdir() if p.is_dir()]
        for p in pkgs:
            run_package(p, no_llm=args.no_llm)
    else:
        run_package(args.package, no_llm=args.no_llm)


if __name__ == "__main__":
    main()
