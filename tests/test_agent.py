"""Agent + guardrail tests with a fake tool-calling model (no API key or internet needed).

The fake model behaves like a real one would at its worst: it calls the tools, then returns
a review that invents one finding and tampers with another. The guardrail must catch both.
"""

import json
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.loader import load_package, load_rules
from src.agent import run_reviewer_agent, apply_guardrail


class FakeToolCallingModel(BaseChatModel):
    tool_names: List[str] = []
    skip: List[str] = []

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def bind_tools(self, tools, **kwargs):
        self.tool_names = [t.name for t in tools]
        return self

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Any = None, **kw) -> ChatResult:
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        if not tool_msgs:
            calls = [{"name": n, "args": {}, "id": f"call_{i}", "type": "tool_call"}
                     for i, n in enumerate(self.tool_names) if n not in self.skip]
            msg = AIMessage(content="", tool_calls=calls)
        else:
            findings = []
            for m in tool_msgs:
                try:
                    data = json.loads(m.content)
                except Exception:
                    continue
                if isinstance(data, list):
                    findings += data
            for f in findings:
                f["llm_note"] = f"Check {f['element']}."
            if findings:
                findings[0]["evidence"] = "tampered by model"
                findings[0]["group"] = "NEEDS_REVIEW"
            findings.append({"finding_id": "FAKE-123", "rule_id": "R99", "group": "RULE_FAILED",
                             "element": "Roof", "issue": "Invented by the model"})
            msg = AIMessage(content="```json\n" + json.dumps({"findings": findings, "summary": "ok"}) + "\n```")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def test_agent_calls_every_check_and_guardrail_blocks_invention():
    pkg, rules = load_package("packages/demo_seeded"), load_rules()
    res = run_reviewer_agent(pkg, rules, llm=FakeToolCallingModel())
    log = res["guardrail_log"]
    assert len(log["tools_called_by_agent"]) == 13
    assert [r["finding_id"] for r in log["rejected_unsupported"]] == ["FAKE-123"]
    assert {r["field"] for r in log["restored_fields"]} == {"evidence", "group"}
    assert all(f["finding_id"] != "FAKE-123" for f in res["findings"])
    assert all(f["evidence"] != "tampered by model" for f in res["findings"])


def test_skipped_checks_are_run_by_code():
    pkg, rules = load_package("packages/demo_seeded"), load_rules()
    res = run_reviewer_agent(pkg, rules, llm=FakeToolCallingModel(skip=["check_room_areas_r01"]))
    assert res["guardrail_log"]["tools_run_by_code_after_agent_skipped"] == ["check_room_areas_r01"]
    assert any(f["rule_id"] == "R01" for f in res["findings"])


def test_guardrail_adds_back_findings_the_model_left_out():
    ledger = {"R01-a": {"finding_id": "R01-a", "rule_id": "R01", "group": "RULE_FAILED", "element": "X", "evidence": "e"}}
    out, log = apply_guardrail([], ledger)
    assert [f["finding_id"] for f in out] == ["R01-a"] and log["added_back"] == ["R01-a"]
