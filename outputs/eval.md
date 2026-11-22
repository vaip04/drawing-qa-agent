# Drawing QA Agent — Evaluation Report

> Generated automatically by `evaluate.py`. No invented numbers.

## Performance Summary

| Package | Mode | Planted Errors | Caught | Missed | False Flags | Precision | Recall | Review Traps Grouped | Guardrail Dropped |
|---|---|---|---|---|---|---|---|---|---|
| `demo_clean` | **NO-LLM** | 0 | 0 | 0 | 0 | n/a: 0 flags on a clean set | n/a: 0 planted errors | Pass (Review) (0) | 0 |
| `demo_seeded` | **NO-LLM** | 12 | 12 | 0 | 0 | 100.0% | 100.0% | Pass (Review) (3) | 0 |
| `demo_mixed` | **NO-LLM** | 6 | 6 | 0 | 0 | 100.0% | 100.0% | Pass (Review) (0) | 0 |

**LLM mode not yet benchmarked.** Guardrail drops have not been measured on a live model run.

## Definitions
- **Planted Errors:** Known errors authored in `answer_key.csv`.
- **Caught:** Planted errors successfully identified by rule tools.
- **Missed:** Planted errors not triggered.
- **False Flags:** Findings emitted under `RULE_FAILED` that were not in the answer key or brief.
- **Precision:** `Caught / (Caught + False Flags)`
- **Recall:** `Caught / Planted`
- **Review Traps Grouped:** Verification that non-deterministic / design-intent items (e.g. aspect ratio > 3:1, fuzzy name variants) land strictly in `NEEDS_REVIEW` and never in `RULE_FAILED`.
- **Guardrail Dropped:** Hallucinated or unauthorized findings dropped by the guardrail post-processor.

## Evaluation Notes
- In `demo_seeded`, Error #7 consists of two drawing sheets (`A201` and `A301`) carrying legacy brief version `v1`. Each sheet emits an R06 violation. Both findings count toward the one planted error, with no false flag.
- In `demo_clean`, zero `RULE_FAILED` items are emitted across all rules, so precision and recall have no denominator.