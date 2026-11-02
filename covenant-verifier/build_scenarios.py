"""SYNTHETIC quarterly packages. Expected values are computed by hand in the comments, not by the engine."""
import json
A = lambda c, amt, d="", **kw: {"clause": c, "amount": amt, "description": d, **kw}
BASE = [A("(a)", 18000, "interest"), A("(b)", 12000, "taxes"), A("(c)", 20000, "D&A"),
        A("(d)", 5000, "non-cash charges"), A("(i)", 2000, "non-cash gains")]
# NI 40,000 + 18,000 + 12,000 + 20,000 + 5,000 - 2,000 = 93,000 = base before capped groups
DEBT = {"term_loans": 380000, "revolver": 40000, "capital_leases": 10000, "purchase_money": 5000,
        "undrawn_lc": 15000, "swaps": 3000}   # included: 435,000
def cert(e, d, r, m): return {"consolidated_ebitda": e, "total_debt": d, "total_leverage_ratio": r, "max_ratio_applied": m}
S = []
# S01 clean: 93,000 + e 8,000 (G25 limit 23,250) + g 5,000 (limit 10,100) + h 4,000 (limit 11,778) = 110,000; 435,000/110,000 = 3.95x
S.append({"scenario": "S01 clean quarter", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT, "certificate": cert(110000, 435000, 3.95, 4.50),
  "expected": {"status": "PASS", "ebitda": 110000, "flags": []}})
# S02 25% cap: e 20,000 + f 10,000 = 30,000 > 23,250 -> 23,250 allowed; +g 5,000 +h 4,000 = 125,250. Borrower takes all: 132,000
S.append({"scenario": "S02 aggregate 25% cap exceeded", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 20000, "restructuring"), A("(f)", 10000, "procurement synergies", realization_months=12, officer_certified=True),
                   A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT, "certificate": cert(132000, 435000, 3.30, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 125250, "flags": ["cap G25"]}})
# S03 circular post-add-back cap: before (h) = 93,000 + 8,000 + 5,000 = 106,000. Limit = 106,000/9 = 11,777.78.
# Borrower naively uses 10% x 106,000 = 10,600 -> 116,600. Correct: 117,777.78 (borrower understated EBITDA)
S.append({"scenario": "S03 post-add-back (circular) 10% cap", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 15000, "EAC change")],
  "debt": DEBT, "certificate": cert(116600, 435000, 3.73, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 117777.78, "flags": ["cap G10_POST"]}})
# S04 synergy outside 24-month window: f excluded -> 110,000 (as S01). Borrower includes it: 116,000
S.append({"scenario": "S04 synergy outside 24-month window", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(f)", 6000, "footprint synergies", realization_months=30, officer_certified=True),
                   A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT, "certificate": cert(116000, 435000, 3.75, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 110000, "flags": ["24-month window"]}})
# S05 synergy without officer certification: excluded -> 110,000
S.append({"scenario": "S05 synergy without officer certification", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(f)", 6000, "headcount synergies", realization_months=12, officer_certified=False),
                   A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT, "certificate": cert(116000, 435000, 3.75, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 110000, "flags": ["no Responsible Officer certification"]}})
# S06 amended threshold: 2027-03-31 -> spec v2 (4.25x). Debt 484,000/110,000 = 4.40x. Borrower applies old 4.50x and reports compliance.
DEBT_HI = dict(DEBT, term_loans=429000)   # included 484,000
S.append({"scenario": "S06 borrower ignores amended threshold", "test_date": "2027-03-31", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT_HI, "certificate": cert(110000, 484000, 4.40, 4.50),
  "expected": {"status": "BREACH", "ebitda": 110000, "flags": [], "max_ratio": 4.25}})
# S07 boundary date: 2026-12-31 is 'on or before' -> 4.50x; 4.40x passes
S.append({"scenario": "S07 threshold boundary date", "test_date": "2026-12-31", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT_HI, "certificate": cert(110000, 484000, 4.40, 4.50),
  "expected": {"status": "PASS", "ebitda": 110000, "flags": [], "max_ratio": 4.50}})
# S08 borrower leaves out Capitalized Leases: reports 425,000 vs 435,000
S.append({"scenario": "S08 borrower omits Capitalized Leases from debt", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT, "certificate": cert(110000, 425000, 3.86, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 110000, "flags": []}})
# S09 debt item the spec never classified (seller note 12,000): included, flagged for analyst
S.append({"scenario": "S09 unclassified debt item", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": dict(DEBT, seller_note=12000), "certificate": cert(110000, 435000, 3.95, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 110000, "flags": ["not classified"]}})
# S10 add-back with no basis in the definition (sponsor management fee 3,000): excluded
S.append({"scenario": "S10 add-back not permitted by the definition", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change"),
                   A("(z)", 3000, "sponsor management fee")],
  "debt": DEBT, "certificate": cert(113000, 435000, 3.85, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 110000, "flags": ["not a permitted adjustment"]}})
# S11 borrower omits deduction (ii) gain on asset sale 4,000: correct 106,000 (G10_POST limit changes but 4,000 still fits)
S.append({"scenario": "S11 borrower omits asset-sale gain deduction", "test_date": "2026-09-30", "net_income": 40000,
  "items": BASE + [A("(ii)", 4000, "gain on sale of hangar"), A("(e)", 8000, "plant consolidation"), A("(g)", 5000, "new contract"), A("(h)", 4000, "EAC change")],
  "debt": DEBT, "certificate": cert(110000, 435000, 3.95, 4.50),
  "expected": {"status": "NEEDS_REVIEW", "ebitda": 106000, "flags": []}})
json.dump(S, open("data/scenarios/scenarios.json", "w"), indent=2)
print(len(S), "scenarios")
