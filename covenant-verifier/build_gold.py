"""Writes the hand-built gold specs (the answer key). Kept as code so every quote is easy to audit."""
import json
S = "1.01 Consolidated EBITDA"
def cit(section, quote): return {"section": section, "quote": quote}
judgment = {"type": "analyst_judgment",
            "description": "contract requires good-faith projection that is reasonably identifiable and factually supportable; code cannot judge this",
            "citation": cit(S, "reasonably identifiable and factually supportable")}
v1 = {
  "agreement_id": "NORTHWIND-2026-CA", "version": 1, "effective_from": "2026-03-01",
  "source_file": "data/synthetic_agreement_v1.html",
  "base_metric": cit(S, "Consolidated Net Income for such Test Period, plus, without duplication"),
  "adjustments": [
    {"clause": "(a)", "label": "interest expense", "direction": "add", "citation": cit(S, "(a) Consolidated Interest Expense;")},
    {"clause": "(b)", "label": "income taxes", "direction": "add", "citation": cit(S, "(b) provision for taxes based on income, profits or capital;")},
    {"clause": "(c)", "label": "D&A", "direction": "add", "citation": cit(S, "(c) depreciation and amortization expense;")},
    {"clause": "(d)", "label": "non-cash charges", "direction": "add", "citation": cit(S, "(d) non-cash charges, excluding any non-cash charge that represents an accrual of or reserve for cash payments in any future period;")},
    {"clause": "(e)", "label": "restructuring, integration, severance", "direction": "add", "cap_group": "G25", "citation": cit(S, "(e) restructuring, integration and severance costs;")},
    {"clause": "(f)", "label": "run-rate cost savings and synergies", "direction": "add", "cap_group": "G25",
     "conditions": [
        {"type": "max_realization_months", "value": 24, "citation": cit(S, "to be realized within 24 months after the date of the related action")},
        {"type": "officer_certification", "citation": cit(S, "are certified by a Responsible Officer in the Compliance Certificate")},
        judgment],
     "citation": cit(S, "(f) the amount of run-rate cost savings and synergies projected by the Borrower in good faith")},
    {"clause": "(g)", "label": "new contracts, pricing and volume", "direction": "add", "cap_group": "G10_PRE", "citation": cit(S, "(g) adjustments in respect of new contracts and increased pricing or volume under existing customer contracts;")},
    {"clause": "(h)", "label": "estimates at completion", "direction": "add", "cap_group": "G10_POST", "citation": cit(S, "(h) adjustments in respect of changes in estimates at completion on long-term contracts;")},
    {"clause": "(i)", "label": "non-cash gains", "direction": "deduct", "citation": cit(S, "(i) non-cash gains")},
    {"clause": "(ii)", "label": "gains on asset sales", "direction": "deduct", "citation": cit(S, "(ii) gains on sales of assets outside the ordinary course of business")},
  ],
  "cap_groups": [
    {"id": "G25", "pct": 0.25, "basis": "before_addbacks", "order": 1, "members": ["(e)", "(f)"],
     "citation": cit(S, "pursuant to clauses (e) and (f) for any Test Period shall not exceed 25% of Consolidated EBITDA for such Test Period (determined before giving effect to such add-backs)")},
    {"id": "G10_PRE", "pct": 0.10, "basis": "before_addbacks", "order": 2, "members": ["(g)"],
     "citation": cit(S, "pursuant to clause (g) for any Test Period shall not exceed 10% of Consolidated EBITDA for such Test Period (determined before giving effect to such add-backs)")},
    {"id": "G10_POST", "pct": 0.10, "basis": "after_addbacks", "order": 3, "members": ["(h)"],
     "citation": cit(S, "pursuant to clause (h) for any Test Period shall not exceed 10% of Consolidated EBITDA for such Test Period (determined after giving effect to such add-backs)")},
  ],
  "debt_components": [
    {"id": "term_loans", "label": "borrowed money: term loans", "include": True, "citation": cit("1.01 Consolidated Total Debt", "(a) borrowed money")},
    {"id": "revolver", "label": "borrowed money: revolver", "include": True, "citation": cit("1.01 Consolidated Total Debt", "(a) borrowed money")},
    {"id": "capital_leases", "label": "Capitalized Leases", "include": True, "citation": cit("1.01 Consolidated Total Debt", "(b) obligations under Capitalized Leases")},
    {"id": "purchase_money", "label": "purchase money obligations", "include": True, "citation": cit("1.01 Consolidated Total Debt", "(c) purchase money obligations")},
    {"id": "undrawn_lc", "label": "undrawn letters of credit", "include": False, "citation": cit("1.01 Consolidated Total Debt", "(x) undrawn letters of credit")},
    {"id": "swaps", "label": "Swap Contracts", "include": False, "citation": cit("1.01 Consolidated Total Debt", "(y) obligations under Swap Contracts")},
  ],
  "thresholds": [
    {"through": "2026-12-31", "max_ratio": 4.50, "citation": cit("7.11", "ending on or before December 31, 2026 to exceed 4.50 to 1.00")},
    {"through": None, "max_ratio": 4.00, "citation": cit("7.11", "ending thereafter to exceed 4.00 to 1.00")},
  ],
  "interpretations": [
    "Caps are applied in order G25, G10_PRE, G10_POST. 'Before giving effect to such add-backs' excludes only that group; earlier groups' allowed amounts are included in later bases.",
    "G10_POST is circular: A <= 0.10 x (B + A), so A <= B / 9.",
  ],
  "approved_by": "analyst (synthetic approval for prototype)",
}
v2 = json.loads(json.dumps(v1))
v2.update({"version": 2, "effective_from": "2026-12-15", "source_file": "data/synthetic_amendment_no1.html"})
v2["thresholds"][1] = {"through": None, "max_ratio": 4.25, "citation": cit("7.11 (Amendment No. 1)", "ending thereafter to exceed 4.25 to 1.00")}
json.dump(v1, open("data/gold_spec_v1.json", "w"), indent=2)
json.dump(v2, open("data/gold_spec_v2.json", "w"), indent=2)
print("written")
