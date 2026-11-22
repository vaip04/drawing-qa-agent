"""The evaluator must match by rule AND element, so a right rule on the wrong room is not 'caught'."""

import pandas as pd
from evaluate import score

KEY = pd.DataFrame([
    {"error_id": 1, "rule_id": "R01", "element": "Bedroom 2"},
    {"error_id": 2, "rule_id": "R06", "element": "A201;A301"},
])


def f(rule, el):
    return {"rule_id": rule, "element": el, "group": "RULE_FAILED"}


def test_right_rule_wrong_element_is_missed_and_false_flag():
    caught, missed, ff = score([f("R01", "Kitchen"), f("R06", "A201"), f("R06", "A301")], KEY)
    assert caught == [2] and len(missed) == 1 and ff == ["R01 Kitchen"]


def test_error_on_two_sheets_counts_once_when_both_flagged():
    caught, missed, ff = score([f("R01", "Bedroom 2"), f("R06", "A201"), f("R06", "A301")], KEY)
    assert caught == [1, 2] and not missed and not ff


def test_error_on_two_sheets_missed_if_one_sheet_unflagged():
    caught, missed, ff = score([f("R01", "Bedroom 2"), f("R06", "A201")], KEY)
    assert caught == [1] and missed and ff == ["R06 A201"]
