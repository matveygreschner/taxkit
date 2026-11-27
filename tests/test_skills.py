"""The packaged Claude skills: valid, in sync with src/, and runnable from an unpacked archive."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_skills_valid_and_in_sync():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_skills.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.fixture(scope="module")
def unpacked(tmp_path_factory):
    subprocess.run([sys.executable, str(ROOT / "scripts/build_skills.py")], check=True, capture_output=True)
    d = tmp_path_factory.mktemp("installed")
    for name in ("us-tax-calculator", "business-tax-optimizer", "tax-memo-writer", "estimated-tax-planner"):
        with zipfile.ZipFile(ROOT / "dist" / f"{name}.zip") as z:
            z.extractall(d)
    return d


def _run(script: Path, *args, cwd):
    # -I: isolated mode, so only the skill's vendored engine can be imported (not ./src or site-packages taxkit)
    r = subprocess.run([sys.executable, "-I", "-B", str(script), *args], capture_output=True, text=True, cwd=cwd)
    return r.returncode, json.loads(r.stdout) if r.stdout.strip().startswith("{") else r.stdout


def test_calculator_from_archive(unpacked, tmp_path):
    code, out = _run(unpacked / "us-tax-calculator/scripts/tax.py", "income_tax",
                     '{"taxable_income": 400000, "status": "MFJ"}', cwd=tmp_path)
    assert code == 0 and out["result"]["tax"] == 81_196.0


def test_optimizer_from_archive(unpacked, tmp_path):
    profile = json.loads((ROOT / "examples/acme_s_corp.json").read_text())
    code, out = _run(unpacked / "business-tax-optimizer/scripts/optimize.py", "business_scan",
                     json.dumps({"profile": profile, "only_applicable": True}), cwd=tmp_path)
    assert code == 0
    ids = {o["id"] for o in out["result"]}
    assert {"cost_seg", "bonus_179", "rd_credit"} <= ids


def test_estimator_from_archive(unpacked, tmp_path):
    ret = {"year": 2025, "status": "MFJ", "wages": 120_000, "schedule_c_profit": 80_000,
           "qualifying_children": 1, "withholding": 12_000}
    pays = [{"date": d, "amount": 3_000} for d in ("2025-04-15", "2025-06-16", "2025-09-15", "2026-01-15")]
    code, out = _run(unpacked / "estimated-tax-planner/scripts/estimate.py", "year_end_projection",
                     json.dumps({"return_inputs": ret, "estimated_payments": pays, "as_of": "2025-11-26",
                                 "prior_year": {"tax": 24_000, "agi": 160_000, "status": "MFJ"}}), cwd=tmp_path)
    assert code == 0 and out["result"]["penalty_if_nothing_changes"] == 110.63


def test_archive_layout(unpacked):
    for name in ("us-tax-calculator", "business-tax-optimizer", "tax-memo-writer", "estimated-tax-planner"):
        assert (unpacked / name / "SKILL.md").exists()
        # Check the archive itself: running the scripts in other tests may create __pycache__ on disk.
        with zipfile.ZipFile(ROOT / "dist" / f"{name}.zip") as z:
            assert not [n for n in z.namelist() if "__pycache__" in n or n.endswith(".pyc")]
