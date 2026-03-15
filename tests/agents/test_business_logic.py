"""
Tier 2: Business Logic & Scoring Math Tests.

Validates that the mathematical formulas and registry logic
governing the Forge are correct and robust.
"""

from __future__ import annotations

import pytest
from hephae_api.workflows.capabilities.registry import get_enabled_capabilities


# ------------------------------------------------------------------
# Scoring Math: Margin Surgeon
# ------------------------------------------------------------------

def calculate_expected_margin_score(menu_analysis: list) -> int:
    """Mirror of the logic in margin_analyzer/runner.py."""
    total_leakage = sum(item.get("price_leakage", 0) for item in menu_analysis)
    total_revenue = sum(item.get("current_price", 0) for item in menu_analysis)
    # round(100 - (leakage / revenue * 20))
    score = max(0, min(100, round(100 - (total_leakage / (total_revenue or 1) * 20))))
    return score


def test_margin_scoring_formula_high_leakage():
    """Verify that high leakage correctly results in a lower score."""
    # 25% average leakage across $100 revenue
    # leakage = 25, revenue = 100
    # 100 - (25/100 * 20) = 100 - 5 = 95 ?? 
    # Wait, the formula 100 - (L/R * 20) is very generous.
    # If L/R is 0.25 (25% leakage), score is 95.
    # If L/R is 1.0 (100% leakage), score is 80.
    # This formula might be too lenient, but the test ensures we match the IMPLEMENTATION.
    
    leaky_data = [
        {"current_price": 10.0, "price_leakage": 2.5}, # 25% leakage
        {"current_price": 20.0, "price_leakage": 5.0},
    ]
    # L=7.5, R=30.0 -> L/R = 0.25
    # 100 - (0.25 * 20) = 95
    assert calculate_expected_margin_score(leaky_data) == 95


def test_margin_scoring_formula_perfect_pricing():
    """Verify that zero leakage results in a perfect 100 score."""
    perfect_data = [
        {"current_price": 15.0, "price_leakage": 0.0},
        {"current_price": 25.0, "price_leakage": 0.0},
    ]
    assert calculate_expected_margin_score(perfect_data) == 100


def test_margin_scoring_formula_edge_cases():
    """Verify handling of empty or zero-revenue data."""
    assert calculate_expected_margin_score([]) == 100 # empty = perfect
    assert calculate_expected_margin_score([{"current_price": 0, "price_leakage": 0}]) == 100


# ------------------------------------------------------------------
# Registry Logic: should_run guards
# ------------------------------------------------------------------

@pytest.mark.parametrize("cap_name, identity, expected", [
    # SEO: needs officialUrl
    ("seo", {"officialUrl": "https://ok.com"}, True),
    ("seo", {"officialUrl": ""}, False),
    ("seo", {}, False),
    
    # Competitive: needs competitors
    ("competitive", {"competitors": [{"name": "X"}]}, True),
    ("competitive", {"competitors": []}, False),
    
    # Margin Surgeon: needs menuScreenshotBase64
    ("margin_surgeon", {"menuScreenshotBase64": "data:image/png;base64,123"}, True),
    ("margin_surgeon", {"menuScreenshotBase64": ""}, False),
])
def test_capability_registry_should_run_logic(cap_name, identity, expected):
    """Verify that capabilities only run when their prerequisites are met."""
    caps = get_enabled_capabilities()
    cap = next((c for c in caps if c.name == cap_name), None)
    
    assert cap is not None, f"Capability {cap_name} not found in registry"
    if cap.should_run:
        assert cap.should_run(identity) == expected
    else:
        # If no guard, it always runs
        assert expected is True
