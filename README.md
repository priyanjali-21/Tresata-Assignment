# Covenant verifier (prototype)

Verifies a borrower's quarterly **Total Leverage Ratio** Compliance Certificate against the bespoke definitions in its credit agreement. The LLM drafts a reviewable rule specification from retrieved definition text; code checks the specification, an analyst approves it, and deterministic code performs every calculation.

**All agreements and financial figures used as prototype inputs are SYNTHETIC.** The cap structure (a 25% cap and a 10% cap measured before the relevant add-backs, plus a 10% cap measured after the relevant add-back) mirrors the three-bucket pattern researched in the June 2025 Redwire / Edge Autonomy credit agreement filed on SEC EDGAR. The public agreement is a research reference, not an input to the prototype. No real borrower or client data is used.

## Run

```bash
pip install -r requirements.txt
pytest -q tests
jupyter notebook covenant_verifier.ipynb
```

The test suite currently reports **19 passed, 1 xfailed, 0 unexpected failures**. The expected failure documents a known limitation: the quote validator can establish that a quotation exists in the source, but cannot establish that the structured field attached to that quotation is semantically correct.

### Optional LLM extraction (notebook section 3)

The extraction step requires an OpenRouter API key. The model used for the reported experiment was `nvidia/nemotron-3-ultra-550b-a55b:free`.

```bash
export OPENROUTER_API_KEY="YOUR_KEY"
export OPENROUTER_MODEL="nvidia/nemotron-3-ultra-550b-a55b:free"
jupyter notebook covenant_verifier.ipynb
```

In the notebook, run the setup and retrieval cells, then section 3. The extraction is scored field by field against `data/gold_spec_v1.json`.

**Observed LLM experiment (one definition only):** NVIDIA Nemotron 3 Ultra 550B (`nvidia/nemotron-3-ultra-550b-a55b:free`) matched **30 of 31 evaluated fields (96.8%)** for the synthetic Consolidated EBITDA definition. All **13/13 verbatim quotation checks** passed. The evaluated cap-group membership, percentages and denominator bases also passed. The one identified miss was adjustment **(ii)**: the deduction for gains on sales of assets outside the ordinary course of business was not extracted. This is a single-definition result against a hand-built gold specification, not a general model-accuracy estimate or evidence of performance on real credit agreements. The result was generated before the notebook cell was manually interrupted; preserve the output and score table if retaining this experiment in the submission.

The LLM does not calculate EBITDA, debt or leverage. It drafts structured fields and citations. The deterministic validator and analyst review remain necessary; in particular, the current quote validator does not detect every semantic mismatch between a quote and its structured interpretation.

## Prototype status and scope

| Component | Status | Evidence / limitation |
| --- | --- | --- |
| HTML definition parser and Section 1.01 index | Implemented; tested on synthetic HTML | Full EDGAR filing validation has not yet been performed. |
| Dependency detection | Implemented | Longest-match handling, plurals and stop-list. |
| Pydantic covenant specification | Implemented | Two synthetic agreement versions / hand-built gold specifications. |
| Verbatim quotation and structural validation | Implemented | Checks quotation presence and structural consistency; does not prove semantic mapping. |
| LLM extraction | Implemented and run once | 30/31 fields on one synthetic Consolidated EBITDA definition; missed clause (ii) deduction. |
| Deterministic covenant calculator | Implemented and tested | Eligibility, cap order, circular post-add-back cap and dated threshold selection. |
| Amendment version selection | Implemented and tested | Synthetic amendment changes a threshold from 4.50x to 4.25x. |
| Quarterly certificate reconciliation | Implemented and tested | 11 synthetic quarterly scenarios. |
| Real EDGAR agreement end-to-end validation | Not yet performed | Public filings informed research and cap-pattern design; they were not prototype inputs. |
| Full debt-definition and threshold-schedule LLM extraction | Not yet demonstrated | The reported LLM experiment covers Consolidated EBITDA only. |

## Layout

| Path | What it is |
| --- | --- |
| `covenant/parser.py` | Deterministic retrieval: definitions by name, sections by number, dependencies (longest match, plurals, stop-list) |
| `covenant/schema.py` | Pydantic covenant spec: adjustments, conditions, cap groups (percentage, basis, order), debt components, threshold schedule and citations |
| `covenant/extract.py` | LLM prompt, OpenRouter call, cache and field-level scoring against the gold specification |
| `covenant/validate.py` | Verbatim-quote check and structural checks on a specification |
| `covenant/calculator.py` | Eligibility, caps in order (including circular `A <= pB/(1-p)`), threshold by date, spec version by date and reconciliation |
| `data/synthetic_*.html` | Synthetic agreement and Amendment No. 1 |
| `data/gold_spec_v*.json` | Hand-built answer keys; `build_gold.py` writes them |
| `data/scenarios/scenarios.json` | 11 synthetic quarters; expected values hand-computed in `build_scenarios.py` comments |
| `tests/test_cases.py` | Test suite |

## Deterministic tests

| ID | Test | Result |
| --- | --- | --- |
| P1 | Definition index ignores table of contents, strips page footer, captures multi-paragraph definition | Pass |
| P2 | Dependencies: plurals (Restricted Subsidiaries, Swap Contracts), longest match masks "Subsidiary", procedural terms separated | Pass |
| V1 | Gold specs v1 and v2 validate (every quote verbatim) | Pass |
| V2 | Paraphrased quote ("measured after" vs "determined after") rejected | Pass |
| V3 | Adjustment pointing to an undefined cap group rejected | Pass |
| V4 | Wrong cap basis with a correct quote | **Expected failure (known limitation)**: only analyst review catches it |
| C0 | Circular cap: 10% after add-backs = `B/9`, not `B/10` | Pass |
| S01 | Clean quarter | Pass |
| S02 | 25% aggregate cap exceeded; 6,750 disallowed | Pass |
| S03 | Post-add-back cap: borrower used 10% of B; correct limit B/9 | Pass |
| S04 | Synergy outside 24-month window excluded | Pass |
| S05 | Synergy without officer certification excluded | Pass |
| S06 | Borrower applies pre-amendment 4.50x; amended 4.25x gives BREACH | Pass |
| S07 | Test date on the step-down boundary uses 4.50x | Pass |
| S08 | Borrower omits Capitalized Leases from debt | Pass |
| S09 | Debt item the spec never classified flagged | Pass |
| S10 | Add-back with no basis in the definition excluded | Pass |
| S11 | Borrower omits asset-sale gain deduction | Pass |
| C12 | Spec with an unresolved item refuses to calculate | Pass |
| C13 | Unapproved amendment spec is never used | Pass |

## Synthetic quarterly demonstration

All 11 synthetic quarterly scenarios matched their hand-computed expected outcomes. They cover a clean quarter; cap exceedances; the circular post-add-back cap; synergy timing and certification; an amended threshold and its boundary date; omitted capital leases; unclassified debt; an impermissible add-back; and an omitted asset-sale gain deduction. These results test the deterministic prototype, not the LLM's ability to interpret arbitrary agreements.

## Known limitations and next steps

- **Semantic validation:** a valid quotation can be attached to the wrong structured field or denominator basis. The known expected-failure test captures this. A second independent extraction pass and disagreement review are potential next steps, but do not replace analyst approval.
- **LLM extraction coverage:** the observed 30/31 score is for one Consolidated EBITDA definition only. The model missed clause (ii), gains on sales of assets outside the ordinary course of business. Full extraction of debt definitions and dated threshold schedules has not been demonstrated.
- **Real-document validation:** the parser and end-to-end workflow have not yet been validated on a full EDGAR filing. Public agreements were research references only; the prototype inputs remain synthetic.
- **Contractual complexity:** the synthetic agreement omits pro forma provisions and contractual historical overrides found in real agreements.
- **Interpretive choices:** cap evaluation order is recorded as an interpretation for analyst approval. Conditions such as "good faith" and whether synergies are reasonably identifiable or factually supportable require human judgment.
- **Numerical tolerance:** the 0.005x ratio tolerance can hide very small differences.

Before deployment, the next work is to validate retrieval and extraction against real agreements with independently hand-built gold specifications, expand coverage to debt and threshold definitions, improve semantic checks, and confirm legal and operational approval boundaries with counsel and portfolio-monitoring users.
