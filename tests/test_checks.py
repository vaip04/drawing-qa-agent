"""Unit and integration tests for rule checks in src/checks.py."""

import pytest
from src.loader import load_package, load_rules
from src.checks import (
    run_all_checks,
    check_R01, check_R02, check_R03, check_R04, check_R05,
    check_R06, check_R07, check_R08, check_R09, check_R10,
    check_R11, check_R12, check_R13,
)


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def clean_pkg():
    return load_package("packages/demo_clean")


@pytest.fixture(scope="module")
def seeded_pkg():
    return load_package("packages/demo_seeded")


@pytest.fixture(scope="module")
def mixed_pkg():
    return load_package("packages/demo_mixed")


def test_clean_package_zero_rule_failed(clean_pkg, rules):
    findings = run_all_checks(clean_pkg, rules)
    failed = [f for f in findings if f["group"] == "RULE_FAILED"]
    assert len(failed) == 0, f"Expected 0 RULE_FAILED on demo_clean, got: {failed}"


def test_seeded_package_catches_all_12_errors(seeded_pkg, rules):
    findings = run_all_checks(seeded_pkg, rules)
    failed = [f for f in findings if f["group"] == "RULE_FAILED"]
    review = [f for f in findings if f["group"] == "NEEDS_REVIEW"]

    # Verify that all 12 planted rules fired
    rule_ids_failed = {f["rule_id"] for f in failed}
    expected_rules = {"R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10"}
    assert expected_rules.issubset(rule_ids_failed), f"Missing rules: {expected_rules - rule_ids_failed}"

    # Review traps must land in NEEDS_REVIEW
    review_rule_ids = {f["rule_id"] for f in review}
    assert "R11" in review_rule_ids, "Expected R11 review trap (Mstr Bed) in NEEDS_REVIEW"
    assert "R13" in review_rule_ids, "Expected R13 review trap (narrow passage) in NEEDS_REVIEW"


def test_mixed_package_planted_errors(mixed_pkg, rules):
    findings = run_all_checks(mixed_pkg, rules)
    failed = [f for f in findings if f["group"] == "RULE_FAILED"]
    rule_ids_failed = {f["rule_id"] for f in failed}
    for r in ["R01", "R02", "R03", "R05", "R07", "R08"]:
        assert r in rule_ids_failed, f"Expected {r} in demo_mixed failed checks"
