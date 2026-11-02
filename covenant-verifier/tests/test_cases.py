"""All test data is SYNTHETIC. Expected values are hand-computed in data/../build_scenarios.py comments."""
import json
from pathlib import Path

import pytest

from covenant.calculator import calculate, cap_amount
from covenant.parser import dependencies, parse
from covenant.schema import CovenantSpec, QuarterPackage
from covenant.validate import validate

ROOT = Path(__file__).resolve().parents[1]
AGR = parse((ROOT / "data/synthetic_agreement_v1.html").read_text())
AMD = parse((ROOT / "data/synthetic_amendment_no1.html").read_text(), require_definitions=False)
V1 = CovenantSpec(**json.loads((ROOT / "data/gold_spec_v1.json").read_text()))
V2 = CovenantSpec(**json.loads((ROOT / "data/gold_spec_v2.json").read_text()))
SCENARIOS = json.loads((ROOT / "data/scenarios/scenarios.json").read_text())


# ---------- P: deterministic retrieval ----------
def test_P1_definition_index_handles_toc_footer_and_multiparagraph():
    ebitda = AGR.definitions["Consolidated EBITDA"]
    assert len(AGR.definitions) == 18
    assert "determined after giving effect to such add-backs" in ebitda   # all three provisos captured
    assert " 12 provided" not in ebitda                                    # page footer stripped
    assert AGR.sections["1.01"].startswith("Section 1.01 Defined Terms. As used")  # body, not TOC


def test_P2_dependencies_longest_match_plurals_and_stop_list():
    deps = dependencies("Consolidated Total Debt", AGR.definitions)
    assert "Restricted Subsidiary" in deps["computational"]   # matched via plural 'Restricted Subsidiaries'
    assert "Swap Contract" in deps["computational"]           # matched via plural 'Swap Contracts'
    assert "Subsidiary" not in deps["computational"] + deps["stop_listed"]  # masked by the longer term
    e = dependencies("Consolidated EBITDA", AGR.definitions)
    assert e["procedural"] == ["Compliance Certificate", "Responsible Officer"]


# ---------- V: spec validation ----------
def test_V1_gold_specs_validate():
    assert validate(V1, AGR.full_text) == []
    assert validate(V2, AGR.full_text + " " + AMD.full_text) == []


def test_V2_paraphrased_quote_is_caught():
    bad = V1.model_copy(deep=True)
    bad.cap_groups[2].citation.quote = "shall not exceed 10% of Consolidated EBITDA (measured after giving effect to such add-backs)"
    assert any("quote not found" in e for e in validate(bad, AGR.full_text))


def test_V3_dangling_cap_group_is_caught():
    bad = V1.model_copy(deep=True)
    bad.adjustments[4].cap_group = "G30"
    assert any("unknown cap group" in e for e in validate(bad, AGR.full_text))


@pytest.mark.xfail(reason="KNOWN LIMITATION: validator checks the quote exists, not that the field matches it", strict=True)
def test_V4_wrong_basis_with_correct_quote_is_caught():
    bad = V1.model_copy(deep=True)
    bad.cap_groups[2].basis = "before_addbacks"      # quote still says 'after'
    assert validate(bad, AGR.full_text) != []


# ---------- C: calculation and reconciliation ----------
def test_C0_circular_cap_formula():
    assert cap_amount(0.10, 106000, "after_addbacks") == pytest.approx(106000 / 9)
    assert cap_amount(0.10, 106000, "before_addbacks") == pytest.approx(10600)


@pytest.mark.parametrize("s", SCENARIOS, ids=[s["scenario"][:3] for s in SCENARIOS])
def test_scenario(s):
    q = QuarterPackage(**s)
    r = calculate([V1, V2], q)
    exp = s["expected"]
    assert r.status == exp["status"], (r.flags, r.variances, r.review_items)
    assert r.ebitda == pytest.approx(exp["ebitda"], abs=0.01)
    for f in exp["flags"]:
        assert any(f in x for x in r.flags), r.flags
    if "max_ratio" in exp:
        assert r.max_ratio == exp["max_ratio"]


def test_C12_unresolved_spec_blocks_calculation():
    v = V1.model_copy(deep=True)
    v.unresolved = ["pro forma treatment of acquisitions referred to elsewhere"]
    r = calculate([v], QuarterPackage(**SCENARIOS[0]))
    assert r.status == "NEEDS_REVIEW" and r.ratio is None


def test_C13_unapproved_spec_is_never_used():
    v2 = V2.model_copy(deep=True)
    v2.approved_by = None
    r = calculate([V1, v2], QuarterPackage(**SCENARIOS[5]))   # 2027 test date
    assert r.spec_version == 1 and r.max_ratio == 4.00
