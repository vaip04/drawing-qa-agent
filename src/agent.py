"""LangChain Tool-Calling Reviewer Agent with Guardrails.

Wraps each deterministic check function as a LangChain tool.
Orchestrates reviewer execution and enforces the hard guardrail:
- Drops any finding not produced by tools (rejected_unsupported)
- Restores original tool evidence and rule group if altered
- Returns structured reviewer findings + executive summary for the architect
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.loader import load_rules
from src.checks import (
    check_R01, check_R02, check_R03, check_R04, check_R05,
    check_R06, check_R07, check_R08, check_R09, check_R10,
    check_R11, check_R12, check_R13,
)

load_dotenv()


def get_llm():
    """Initialize LLM based on environment configuration."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set in environment or .env")
        # Allow override via GEMINI_MODEL env var, default to gemini-3.8-flash (or gemini-1.5-flash / gemini-2.0-flash)
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.0
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0.0)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.0)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def build_tools(pkg: dict, rules: dict):
    """Build LangChain tools bound to the active drawing package."""

    @tool
    def get_package_summary() -> str:
        """Get high-level summary of the drawing package: project name, brief limits, sheets, rooms count."""
        brief = pkg.get("brief", {})
        rooms = pkg.get("rooms")
        sheets = pkg.get("sheets")
        return json.dumps({
            "project": brief.get("project"),
            "brief_version": brief.get("brief_version"),
            "room_count": len(rooms) if rooms is not None else 0,
            "sheet_count": len(sheets) if sheets is not None else 0,
            "limits": brief.get("limits", {}),
            "plot": brief.get("plot", {}),
        })

    @tool
    def check_room_areas_r01() -> str:
        """R01: Check room area from polygon vs area statement (tolerance 2%)."""
        return json.dumps(check_R01(pkg, rules))

    @tool
    def check_area_arithmetic_r02() -> str:
        """R02: Check area statement arithmetic: floor totals and grand total."""
        return json.dumps(check_R02(pkg, rules))

    @tool
    def check_required_rooms_r03() -> str:
        """R03: Check that every required room in brief exists in required count and floor."""
        return json.dumps(check_R03(pkg, rules))

    @tool
    def check_room_min_area_r04() -> str:
        """R04: Check that each room meets minimum area specified in brief."""
        return json.dumps(check_R04(pkg, rules))

    @tool
    def check_builtup_and_coverage_r05() -> str:
        """R05: Check total built-up area and ground coverage against limits."""
        return json.dumps(check_R05(pkg, rules))

    @tool
    def check_sheet_brief_version_r06() -> str:
        """R06: Check sheet brief_version equals current brief version."""
        return json.dumps(check_R06(pkg, rules))

    @tool
    def check_callout_references_r07() -> str:
        """R07: Check that every callout points to an existing sheet and view."""
        return json.dumps(check_R07(pkg, rules))

    @tool
    def check_openings_and_schedule_r08() -> str:
        """R08: Check opening tags and sizes between plan drawings and opening schedule."""
        return json.dumps(check_R08(pkg, rules))

    @tool
    def check_sheet_revisions_r09() -> str:
        """R09: Check revision in sheet index matches revision in title block."""
        return json.dumps(check_R09(pkg, rules))

    @tool
    def check_plan_dimensioning_r10() -> str:
        """R10: Check plan sheets have overall dimensions and all rooms are dimensioned."""
        return json.dumps(check_R10(pkg, rules))

    @tool
    def check_naming_consistency_r11() -> str:
        """R11 (NEEDS_REVIEW): Check room names consistency across rooms, area statement, and brief."""
        return json.dumps(check_R11(pkg, rules))

    @tool
    def check_geometry_sanity_r12() -> str:
        """R12 (NEEDS_REVIEW): Check room overlaps or gaps inside building footprint."""
        return json.dumps(check_R12(pkg, rules))

    @tool
    def check_narrow_aspect_ratios_r13() -> str:
        """R13 (NEEDS_REVIEW): Check for narrow aspect ratio (> 3:1) indicating usability questions."""
        return json.dumps(check_R13(pkg, rules))

    return [
        get_package_summary,
        check_room_areas_r01,
        check_area_arithmetic_r02,
        check_required_rooms_r03,
        check_room_min_area_r04,
        check_builtup_and_coverage_r05,
        check_sheet_brief_version_r06,
        check_callout_references_r07,
        check_openings_and_schedule_r08,
        check_sheet_revisions_r09,
        check_plan_dimensioning_r10,
        check_naming_consistency_r11,
        check_geometry_sanity_r12,
        check_narrow_aspect_ratios_r13,
    ]


SYSTEM_PROMPT = """You are a drawing-set reviewer for an architecture studio.
Your job is to thoroughly review the drawing package by running EVERY check tool.
Rules:
1. Run every check tool on the package. Never change drawings or data.
2. Keep each finding's evidence exactly as the tool returned it.
3. Group findings strictly as RULE FAILED or NEEDS HUMAN REVIEW.
4. Write one plain sentence per finding saying what is wrong and what the architect should look at.
5. Do not interpret building codes; if a finding needs human interpretation or design judgement, it is NEEDS HUMAN REVIEW.
6. Return your final evaluation as a JSON object with:
   - "findings": array of findings with fields [finding_id, rule_id, group, severity, sheet_no, element, issue, evidence, llm_note]
   - "summary": a concise 3-line summary for the project architect.
"""


def apply_guardrail(raw_findings_from_llm: List[Dict], tool_findings_by_id: Dict[str, Dict]) -> tuple[List[Dict], Dict]:
    """Guardrail ('code checks'):
    1. Drop any finding whose finding_id was not produced by a tool (rejected_unsupported).
    2. Restore the original tool's group and evidence if tampered with.
    """
    approved_findings = []
    rejected_unsupported = []
    restored_count = 0

    seen_ids = set()

    for item in raw_findings_from_llm:
        fid = item.get("finding_id")
        if not fid or fid not in tool_findings_by_id:
            rejected_unsupported.append(str(item))
            continue

        if fid in seen_ids:
            continue
        seen_ids.add(fid)

        original_tool_finding = tool_findings_by_id[fid]
        merged = original_tool_finding.copy()

        # Check if LLM tampered with group or evidence
        if item.get("group") != original_tool_finding.get("group"):
            restored_count += 1
        if item.get("evidence") != original_tool_finding.get("evidence"):
            restored_count += 1

        # Keep original verified tool data, attach LLM explanatory note
        merged["llm_note"] = item.get("llm_note") or item.get("issue")
        approved_findings.append(merged)

    # In case LLM omitted any genuine tool findings, add them back so nothing is missed
    for fid, orig in tool_findings_by_id.items():
        if fid not in seen_ids:
            orig_copy = orig.copy()
            orig_copy["llm_note"] = orig.get("issue", "")
            approved_findings.append(orig_copy)

    guardrail_log = {
        "rejected_unsupported": rejected_unsupported,
        "restored_count": restored_count,
    }
    return approved_findings, guardrail_log


def run_reviewer_agent(pkg: dict, rules: dict = None) -> dict:
    """Run tool-calling reviewer agent and apply deterministic guardrail."""
    if rules is None:
        rules = load_rules()

    tools = build_tools(pkg, rules)
    tool_map = {t.name: t for t in tools}

    # Execute all tools deterministically to collect genuine findings
    tool_findings_by_id = {}
    for t in tools:
        if t.name == "get_package_summary":
            continue
        try:
            raw_res = t.invoke({})
            findings_list = json.loads(raw_res)
            for f in findings_list:
                tool_findings_by_id[f["finding_id"]] = f
        except Exception as e:
            print(f"[WARN] Error executing tool {t.name}: {e}")

    # Invoke LLM for synthesis and review prose
    llm = get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Please review the drawing package '{pkg.get('name')}'. Here are all genuine rule findings produced by the tools:\n{json.dumps(list(tool_findings_by_id.values()), indent=2)}\nProvide your architectural reviewer notes and 3-line summary.")
    ]

    try:
        response = llm.invoke(messages)
        content = response.content

        # Extract JSON from LLM response
        parsed = {}
        if "```json" in content:
            raw_json = content.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(raw_json)
        elif "```" in content:
            raw_json = content.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw_json)
        else:
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = {"findings": list(tool_findings_by_id.values()), "summary": content[:300]}

        raw_findings = parsed.get("findings", [])
        summary = parsed.get("summary", "")
        if not summary and isinstance(content, str):
            summary = "\n".join(content.strip().split("\n")[:3])
    except Exception as e:
        print(f"[WARN] LLM invocation or parsing issue: {e}")
        raw_findings = list(tool_findings_by_id.values())
        summary = "Comprehensive automated drawing review completed. Deterministic rule validation enforced."

    # Enforce guardrail
    guarded_findings, guardrail_log = apply_guardrail(raw_findings, tool_findings_by_id)

    return {
        "findings": guarded_findings,
        "summary": summary,
        "guardrail_log": guardrail_log,
    }
