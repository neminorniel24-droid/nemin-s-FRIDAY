"""
Tests for info_actions.py — focused on the pure parsing/validation logic
that doesn't require live network calls or real credentials.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import info_actions


def test_convert_currency_rejects_malformed_input():
    result = info_actions.convert_currency("garbage input")
    assert "need an amount and two currency codes" in result


def test_convert_currency_rejects_missing_currency_codes():
    result = info_actions.convert_currency("100")
    assert "need an amount and two currency codes" in result


def test_currency_pattern_matches_standard_format():
    match = info_actions.CURRENCY_PATTERN.search("100 USD to INR")
    assert match is not None
    amount, from_cur, to_cur = match.groups()
    assert amount == "100"
    assert from_cur.upper() == "USD"
    assert to_cur.upper() == "INR"


def test_currency_pattern_matches_decimal_amounts():
    match = info_actions.CURRENCY_PATTERN.search("49.99 EUR to GBP")
    assert match is not None
    assert match.group(1) == "49.99"


def test_currency_pattern_case_insensitive():
    match = info_actions.CURRENCY_PATTERN.search("100 usd IN inr")
    assert match is not None
    assert match.group(2).upper() == "USD"
    assert match.group(3).upper() == "INR"


def test_check_github_requires_username_when_none_configured():
    original = info_actions.GITHUB_USERNAME
    info_actions.GITHUB_USERNAME = ""
    try:
        result = info_actions.check_github("")
        assert "No GitHub username configured" in result
    finally:
        info_actions.GITHUB_USERNAME = original


def test_project_status_reports_unconfigured_project():
    result = info_actions.project_status("some-project-that-does-not-exist")
    assert "isn't configured" in result
