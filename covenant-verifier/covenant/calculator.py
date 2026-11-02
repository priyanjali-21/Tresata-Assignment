"""Deterministic covenant calculation and reconciliation against the borrower's certificate.

Every number here is reproducible from (approved spec version, quarter package). No LLM.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .schema import CovenantSpec, QuarterPackage

RATIO_TOL = 0.005      # 0.005x
AMOUNT_TOL = 0.005     # 0.5% relative


def select_spec(specs: list[CovenantSpec], test_date: date) -> CovenantSpec:
    live = [s for s in specs if s.approved_by and s.effective_from <= test_date]
    if not live:
        raise ValueError(f"no approved spec in force on {test_date}")
    return max(live, key=lambda s: (s.effective_from, s.version))


def threshold_for(spec: CovenantSpec, test_date: date) -> float:
    dated = sorted((t for t in spec.thresholds if t.through), key=lambda t: t.through)
    for t in dated:
        if test_date <= t.through:
            return t.max_ratio
    return next(t.max_ratio for t in spec.thresholds if t.through is None)


def cap_amount(pct: float, base: float, basis: str) -> float:
    """before_addbacks: A <= p*B.  after_addbacks: A <= p*(B + A)  =>  A <= p*B / (1 - p)."""
    if base <= 0:
        return 0.0
    return pct * base if basis == "before_addbacks" else pct * base / (1 - pct)


@dataclass
class Result:
    status: str                       # PASS | BREACH | NEEDS_REVIEW
    spec_version: int
    test_date: date
    ebitda: float | None = None
    total_debt: float | None = None
    ratio: float | None = None
    max_ratio: float | None = None
    headroom: float | None = None
    lines: list[dict] = field(default_factory=list)       # audit trail
    flags: list[str] = field(default_factory=list)        # machine-detected issues
    review_items: list[str] = field(default_factory=list) # judgment the code cannot make
    variances: list[str] = field(default_factory=list)    # vs borrower certificate


def calculate(specs: list[CovenantSpec], q: QuarterPackage) -> Result:
    spec = select_spec(specs, q.test_date)
    r = Result(status="PASS", spec_version=spec.version, test_date=q.test_date)
    if spec.unresolved:
        r.status = "NEEDS_REVIEW"
        r.flags += [f"spec v{spec.version} has unresolved item: {u}" for u in spec.unresolved]
        return r

    adj = {a.clause: a for a in spec.adjustments}
    eligible: dict[str, float] = defaultdict(float)
    for it in q.items:
        a = adj.get(it.clause)
        if a is None:
            r.flags.append(f"{it.clause} '{it.description}' is not a permitted adjustment; excluded")
            continue
        ok = True
        judgment = []
        for c in a.conditions:
            if c.type == "max_realization_months":
                if it.realization_months is None or it.realization_months > c.value:
                    r.flags.append(f"{it.clause} '{it.description}': realization {it.realization_months} months "
                                   f"exceeds {c.value:g}-month window ({c.citation.section}); excluded")
                    ok = False
            elif c.type == "officer_certification":
                if not it.officer_certified:
                    r.flags.append(f"{it.clause} '{it.description}': no Responsible Officer certification "
                                   f"({c.citation.section}); excluded")
                    ok = False
            elif c.type == "analyst_judgment":
                judgment.append(f"{it.clause} '{it.description}' ({it.amount:,.0f}): {c.description}")
        if ok:
            eligible[it.clause] += it.amount
            r.review_items += judgment

    capped = {m for g in spec.cap_groups for m in g.members}
    running = q.net_income
    r.lines.append({"step": "Consolidated Net Income", "amount": q.net_income, "source": spec.base_metric.section})
    for clause, amt in sorted(eligible.items()):
        if clause in capped:
            continue
        a = adj[clause]
        signed = amt if a.direction == "add" else -amt
        running += signed
        r.lines.append({"step": f"{clause} {a.label}", "amount": signed, "source": a.citation.section})

    for g in sorted(spec.cap_groups, key=lambda g: g.order):
        claimed = sum(eligible.get(m, 0.0) for m in g.members)
        if claimed == 0:
            continue
        limit = cap_amount(g.pct, running, g.basis)
        allowed = min(claimed, limit)
        if claimed > limit + 1e-9:
            r.flags.append(f"cap {g.id} ({g.pct:.0%}, {g.basis.replace('_', ' ')}): claimed {claimed:,.0f}, "
                           f"limit {limit:,.0f}; {claimed - limit:,.0f} disallowed")
        r.lines.append({"step": f"cap group {g.id} {'+'.join(g.members)}", "amount": allowed,
                        "claimed": claimed, "limit": round(limit, 2), "source": g.citation.section})
        running += allowed

    r.ebitda = running
    r.total_debt = 0.0
    comp = {d.id: d for d in spec.debt_components}
    for k, v in q.debt.items():
        d = comp.get(k)
        if d is None:
            r.flags.append(f"debt item '{k}' not classified by the spec; included pending review")
            r.review_items.append(f"classify debt item '{k}' ({v:,.0f})")
            r.total_debt += v
        elif d.include:
            r.total_debt += v
        r.lines.append({"step": f"debt {k}", "amount": v if (d is None or d.include) else 0.0,
                        "source": d.citation.section if d else "unclassified"})

    r.max_ratio = threshold_for(spec, q.test_date)
    if r.ebitda <= 0:
        r.status = "NEEDS_REVIEW"
        r.flags.append("Consolidated EBITDA is not positive; ratio undefined")
        return r
    r.ratio = r.total_debt / r.ebitda
    r.headroom = r.max_ratio - r.ratio
    if r.ratio > r.max_ratio:
        r.status = "BREACH"

    c = q.certificate
    def rel(a, b): return abs(a - b) / max(abs(b), 1.0)
    if rel(c.consolidated_ebitda, r.ebitda) > AMOUNT_TOL:
        r.variances.append(f"EBITDA: borrower {c.consolidated_ebitda:,.0f} vs computed {r.ebitda:,.0f}")
    if rel(c.total_debt, r.total_debt) > AMOUNT_TOL:
        r.variances.append(f"Total Debt: borrower {c.total_debt:,.0f} vs computed {r.total_debt:,.0f}")
    if abs(c.total_leverage_ratio - r.ratio) > RATIO_TOL:
        r.variances.append(f"Leverage: borrower {c.total_leverage_ratio:.2f}x vs computed {r.ratio:.2f}x")
    if abs(c.max_ratio_applied - r.max_ratio) > 1e-9:
        r.variances.append(f"Threshold: borrower applied {c.max_ratio_applied:.2f}x; "
                           f"spec v{spec.version} requires {r.max_ratio:.2f}x on {q.test_date}")
    if r.status == "PASS" and (r.variances or r.review_items):
        r.status = "NEEDS_REVIEW"
    return r
