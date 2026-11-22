"""One test per rule: each planted error is flagged on the right element, and clean data stays clean."""

import pytest
from src.loader import load_package, load_rules
from src import checks


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def seeded():
    return load_package("packages/demo_seeded")


@pytest.fixture(scope="module")
def clean():
    return load_package("packages/demo_clean")


def elements(findings, group="RULE_FAILED"):
    return {f["element"] for f in findings if f["group"] == group}


# rule -> elements that must be flagged in demo_seeded
EXPECTED = {
    "R01": {"Bedroom 2"},
    "R02": {"Floor 0 total", "Grand total"},
    "R03": {"Toilet (floor 1)"},
    "R04": {"Study"},
    "R05": {"Built-up area"},
    "R06": {"A201", "A301"},
    "R07": {"section A"},
    "R08": {"D07", "W04"},
    "R09": {"A102"},
    "R10": {"Kitchen"},
}


@pytest.mark.parametrize("rule", sorted(EXPECTED))
def test_rule_flags_planted_error(rule, seeded, rules):
    found = getattr(checks, f"check_{rule}")(seeded, rules)
    assert EXPECTED[rule] <= elements(found), f"{rule} missed {EXPECTED[rule] - elements(found)}"


@pytest.mark.parametrize("rule", sorted(EXPECTED))
def test_rule_has_no_extra_failures(rule, seeded, rules):
    found = getattr(checks, f"check_{rule}")(seeded, rules)
    extra = elements(found) - EXPECTED[rule]
    assert not extra, f"{rule} flagged elements that are not planted errors: {extra}"


@pytest.mark.parametrize("rule", [f"R{i:02d}" for i in range(1, 14)])
def test_rule_silent_on_clean_package(rule, clean, rules):
    found = getattr(checks, f"check_{rule}")(clean, rules)
    assert not elements(found), f"{rule} raised RULE_FAILED on the clean package"


def test_r11_name_variant_is_review_not_failure(seeded, rules):
    found = checks.check_R11(seeded, rules)
    assert "Mstr Bed" in elements(found, "NEEDS_REVIEW")
    assert not elements(found)


def test_r12_overlap_is_review(seeded, rules):
    found = checks.check_R12(seeded, rules)
    assert found and all(f["group"] == "NEEDS_REVIEW" for f in found)


def test_r13_narrow_room_is_review(seeded, rules):
    found = checks.check_R13(seeded, rules)
    assert "Passage" in elements(found, "NEEDS_REVIEW")
    assert not elements(found)


def test_ids_are_stable_and_sheets_filled(seeded, rules):
    a = checks.run_all_checks(seeded, rules)
    b = checks.run_all_checks(seeded, rules)
    assert [f["finding_id"] for f in a] == [f["finding_id"] for f in b]
    for f in a:
        if f["rule_id"] in {"R01", "R02", "R03", "R04", "R05", "R08", "R10"}:
            assert f["sheet_no"], f"{f['rule_id']} {f['element']} has no sheet number"
