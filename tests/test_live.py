"""Live-data adapters, tested on real public SEC data (Apple 10-K filed 2026-11-03)."""
import json
from pathlib import Path

import pytest

from taxkit import api
from taxkit.live import sec_tax_profile, underpayment_rate

FIX = json.loads((Path(__file__).parent / "fixtures/aapl_10k_2026_tax_facts.json").read_text())


@pytest.fixture(scope="module")
def prof():
    return sec_tax_profile(FIX["facts"], "Apple Inc.", FIX["source"], "2026-11-03")


def test_three_years_newest_first(prof):
    assert [y.fiscal_year_end for y in prof.years] == ["2026-09-26", "2025-09-27", "2024-09-28"]


def test_etr_ties_to_tagged(prof):
    y = prof.years[0]
    assert y.etr_computed == pytest.approx(27_062 / 159_237, rel=1e-9)
    assert not any("differs from tagged" in c for c in y.checks)


def test_segmented_fact_excluded(prof):
    # FY2024 has an EU State Aid row with a dimension axis; only the consolidated $5,571M is used.
    assert prof.years[2].components["current_federal"] == 5_571_000_000


def test_flags_rate_gap_and_valuation_allowance(prof):
    assert any("vs the 21% statutory" in c for c in prof.years[1].checks)
    assert any("Valuation allowance moved +2,294,000,000" in o for o in prof.observations)


def test_api_command():
    out = api.run("sec_tax_profile", {"facts": FIX["facts"], "company": "Apple Inc."})
    assert out["result"]["years"][0]["income_tax_expense"] == 27_062_000_000


def test_underpayment_rate_override():
    assert underpayment_rate("2026Q2")["rate"] == 0.06
    assert underpayment_rate("2027Q1", {"2027Q1": 0.07})["source"].startswith("caller-supplied")
    with pytest.raises(ValueError):
        underpayment_rate("2027Q1")
