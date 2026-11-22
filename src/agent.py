"""LangChain tool-calling reviewer agent with a code guardrail.

How it works, in plain words:
1. Each of the 13 rule checks is wrapped as a LangChain *tool*.
2. The language model is given those tools and decides which to call. LangChain runs
   each tool it asks for and hands the result back to the model.
3. Every finding a tool returns is written into a "ledger" by our own code.
4. When the model has finished, it returns its review as JSON.
5. The guardrail compares that JSON with the ledger:
   - a finding whose ID is not in the ledger was invented by the model -> dropped and logged;
   - if the model changed a finding's group, rule, element, sheet or evidence -> the tool's
     original values are restored and the change is logged;
   - if the model skipped a check, our code runs it anyway and logs that it had to.
Rule: AI proposes, code checks, people approve. The model never produces a number or a finding.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.tools import tool

from src.loader import load_rules
from src.checks import (
    check_R01, check_R02, check_R03, check_R04, check_R05,
    check_R06, check_R07, check_R08, check_R09, check_R10,
    check_R11, check_R12, check_R13,
)

load_dotenv()

PROTECTED_FIELDS = ("rule_id", "group", "severity", "sheet_no", "element", "evidence")


def get_llm():
    """Create the chat model from .env settings.

    LLM_PROVIDER = gemini (default) | openai | anthropic
    GEMINI_MODEL / OPENAI_MODEL / ANTHROPIC_MODEL override the model name.
    If a model name stops working, set the variable to any current model listed by the provider.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set in .env")
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            google_api_key=api_key,
            temperature=0.0,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), temperature=0.0)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"), temperature=0.0)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


CHECKS = [
    ("check_room_areas_r01", check_R01, "R01: room area from polygon vs area statement (tolerance from rules.yaml)."),
    ("check_area_arithmetic_r02", check_R02, "R02: area statement arithmetic: floor totals and grand total."),
    ("check_required_rooms_r03", check_R03, "R03: every room required by the brief exists in the required count and floor."),
    ("check_room_min_area_r04", check_R04, "R04: each required room meets the brief's minimum area."),
    ("check_builtup_and_coverage_r05", check_R05, "R05: built-up area and ground coverage within the brief's limits."),
    ("check_sheet_brief_version_r06", check_R06, "R06: every sheet is drawn on the current brief version."),
    ("check_callout_references_r07", check_R07, "R07: every section/detail callout points to an existing sheet."),
    ("check_openings_and_schedule_r08", check_R08, "R08: door/window tags on plans match the schedule, with matching sizes."),
    ("check_sheet_revisions_r09", check_R09, "R09: revision in the sheet index equals the title-block revision."),
    ("check_plan_dimensioning_r10", check_R10, "R10: plan sheets have overall dimensions and every room is dimensioned."),
    ("check_naming_consistency_r11", check_R11, "R11 (needs human review): room names consistent across drawings and brief."),
    ("check_geometry_sanity_r12", check_R12, "R12 (needs human review): rooms overlapping or leaving gaps."),
    ("check_narrow_aspect_ratios_r13", check_R13, "R13 (needs human review): very narrow rooms (aspect ratio above threshold)."),
]


def build_tools(pkg: dict, rules: dict, ledger: Dict[str, Dict], called: List[str]):
    """Wrap each check as a LangChain tool. Every finding a tool returns goes into the ledger."""

    def make_tool(name, fn, doc):
        def _run() -> str:
            found = fn(pkg, rules)
            for f in found:
                ledger[f["finding_id"]] = f
            called.append(name)
            return json.dumps(found)
        _run.__name__ = name
        _run.__doc__ = doc + " Takes no arguments. Returns a JSON list of findings."
        return tool(_run)

    @tool
    def get_package_summary() -> str:
        """Summary of the drawing package: project, brief version, limits, number of rooms and sheets. Takes no arguments."""
        brief = pkg.get("brief", {})
        rooms, sheets = pkg.get("rooms"), pkg.get("sheets")
        return json.dumps({
            "project": brief.get("project"),
            "brief_version": brief.get("brief_version"),
            "room_count": 0 if rooms is None else len(rooms),
            "sheet_count": 0 if sheets is None else len(sheets),
            "limits": brief.get("limits", {}),
        })

    return [get_package_summary] + [make_tool(n, f, d) for n, f, d in CHECKS]


SYSTEM_PROMPT = """You are a drawing-set reviewer for an architecture studio.
1. Call get_package_summary, then call EVERY check tool exactly once. Never change drawings or data.
2. Use only findings returned by the tools. Copy finding_id, rule_id, group, severity, sheet_no, element and evidence exactly.
3. Group is RULE_FAILED or NEEDS_REVIEW, as the tool returned it. Do not interpret building codes.
4. For each finding write one plain sentence in "llm_note": what is wrong and what the architect should look at.
5. Reply with ONLY a JSON object: {"findings": [...], "summary": "3 lines for the project architect"}."""


def _message_text(msg: Any) -> str:
    """Plain text of a chat message (some models return a list of content parts)."""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    parts = []
    for p in content or []:
        if isinstance(p, dict) and p.get("type") == "text":
            parts.append(p.get("text", ""))
        elif isinstance(p, str):
            parts.append(p)
    return "".join(parts)


def _parse_json(text: str) -> dict:
    """Pull the JSON object out of the model's reply (with or without ``` fences)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def apply_guardrail(llm_findings: List[Dict], ledger: Dict[str, Dict]):
    """Keep only findings the tools produced; restore any field the model changed."""
    approved, rejected, restored, seen = [], [], [], set()
    for item in llm_findings:
        fid = item.get("finding_id")
        if not fid or fid not in ledger:
            rejected.append({"finding_id": fid, "element": item.get("element"), "issue": item.get("issue")})
            continue
        if fid in seen:
            continue
        seen.add(fid)
        original = ledger[fid]
        for k in PROTECTED_FIELDS:
            if k in item and str(item[k]) != str(original.get(k)):
                restored.append({"finding_id": fid, "field": k, "llm_value": item[k], "tool_value": original.get(k)})
        merged = dict(original)
        merged["llm_note"] = item.get("llm_note") or ""
        approved.append(merged)
    added_back = []
    for fid, original in ledger.items():
        if fid not in seen:
            merged = dict(original)
            merged["llm_note"] = ""
            approved.append(merged)
            added_back.append(fid)
    log = {"rejected_unsupported": rejected, "restored_fields": restored,
           "restored_count": len(restored), "added_back": added_back}
    return approved, log


def run_reviewer_agent(pkg: dict, rules: Optional[dict] = None, llm=None) -> dict:
    """Run the tool-calling agent on one package, then apply the guardrail.

    Raises on LLM failure: callers must report it, never silently fall back.
    """
    from langchain.agents import create_agent

    rules = rules or load_rules()
    ledger: Dict[str, Dict] = {}
    called: List[str] = []
    tools = build_tools(pkg, rules, ledger, called)
    llm = llm or get_llm()

    agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Review drawing package '{pkg.get('name')}'."}]},
        config={"recursion_limit": 60},
    )
    final_text = _message_text(result["messages"][-1])
    try:
        parsed = _parse_json(final_text)
    except Exception:
        parsed = {"findings": [], "summary": final_text[:500]}

    # Completeness: run any check the agent skipped, and log that code had to do it.
    check_names = [n for n, _, _ in CHECKS]
    skipped = [n for n in check_names if n not in called]
    for name in skipped:
        fn = dict((n, f) for n, f, _ in CHECKS)[name]
        for f in fn(pkg, rules):
            ledger[f["finding_id"]] = f

    findings, log = apply_guardrail(parsed.get("findings", []), ledger)
    log["tools_called_by_agent"] = sorted(set(n for n in called if n in check_names))
    log["tools_run_by_code_after_agent_skipped"] = skipped
    log["model"] = getattr(llm, "model", None) or getattr(llm, "model_name", None) or type(llm).__name__
    return {"findings": findings, "summary": parsed.get("summary", ""), "guardrail_log": log}
