"""Deterministic checks on a spec before any analyst sees it, and before any number depends on it."""
from __future__ import annotations

from .parser import quote_in_source
from .schema import CovenantSpec


def all_citations(spec: CovenantSpec):
    yield "base_metric", spec.base_metric
    for a in spec.adjustments:
        yield f"adjustment {a.clause}", a.citation
        for c in a.conditions:
            yield f"condition {c.type} on {a.clause}", c.citation
    for g in spec.cap_groups:
        yield f"cap group {g.id}", g.citation
    for d in spec.debt_components:
        yield f"debt {d.id}", d.citation
    for t in spec.thresholds:
        yield f"threshold {t.max_ratio}", t.citation


def validate(spec: CovenantSpec, source_text: str) -> list[str]:
    errors: list[str] = []
    for where, cit in all_citations(spec):
        if not quote_in_source(cit.quote, source_text):
            errors.append(f"quote not found verbatim ({where}): {cit.quote[:70]!r}")

    clauses = {a.clause for a in spec.adjustments}
    group_ids = {g.id for g in spec.cap_groups}
    for a in spec.adjustments:
        if a.cap_group and a.cap_group not in group_ids:
            errors.append(f"adjustment {a.clause} references unknown cap group {a.cap_group!r}")
    for g in spec.cap_groups:
        for m in g.members:
            if m not in clauses:
                errors.append(f"cap group {g.id} lists unknown clause {m}")
            elif next(a for a in spec.adjustments if a.clause == m).cap_group != g.id:
                errors.append(f"cap group {g.id} lists {m}, but {m} points to another group")
    if len({g.order for g in spec.cap_groups}) != len(spec.cap_groups):
        errors.append("cap groups share an evaluation order; order must be explicit")

    open_ended = [t for t in spec.thresholds if t.through is None]
    if len(open_ended) != 1:
        errors.append("threshold schedule needs exactly one open-ended step")
    return errors
