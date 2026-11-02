"""The covenant spec: the only thing the LLM produces, and the only thing the calculator trusts."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    section: str
    quote: str  # must appear verbatim in the source (checked by validate.py)


class Condition(BaseModel):
    # machine_checkable: code can decide it. analyst_judgment: code can only flag it.
    type: Literal["max_realization_months", "officer_certification", "analyst_judgment"]
    value: Optional[float] = None
    description: str = ""
    citation: Citation


class Adjustment(BaseModel):
    clause: str                      # e.g. "(f)"
    label: str
    direction: Literal["add", "deduct"]
    cap_group: Optional[str] = None
    conditions: list[Condition] = Field(default_factory=list)
    citation: Citation


class CapGroup(BaseModel):
    id: str
    pct: float = Field(gt=0, lt=1)
    basis: Literal["before_addbacks", "after_addbacks"]
    order: int                       # evaluation order; an approved interpretation, not a fact
    members: list[str]               # adjustment clauses
    citation: Citation


class DebtComponent(BaseModel):
    id: str
    label: str
    include: bool
    citation: Citation


class ThresholdStep(BaseModel):
    through: Optional[date] = None   # applies to test dates <= through; None = all later dates
    max_ratio: float
    citation: Citation


class CovenantSpec(BaseModel):
    agreement_id: str
    version: int
    effective_from: date
    source_file: str
    base_metric: Citation            # e.g. Consolidated Net Income
    adjustments: list[Adjustment]
    cap_groups: list[CapGroup]
    debt_components: list[DebtComponent]
    thresholds: list[ThresholdStep]
    unresolved: list[str] = Field(default_factory=list)
    interpretations: list[str] = Field(default_factory=list)  # analyst decisions, written down
    approved_by: Optional[str] = None


class ClaimedItem(BaseModel):
    clause: str
    amount: float
    description: str = ""
    realization_months: Optional[float] = None
    officer_certified: Optional[bool] = None


class BorrowerCertificate(BaseModel):
    consolidated_ebitda: float
    total_debt: float
    total_leverage_ratio: float
    max_ratio_applied: float


class QuarterPackage(BaseModel):
    """SYNTHETIC test data: LTM figures for one test date plus the borrower's own certificate."""
    scenario: str
    test_date: date
    net_income: float
    items: list[ClaimedItem]
    debt: dict[str, float]
    certificate: BorrowerCertificate
    expected: dict = Field(default_factory=dict)  # what the test expects the system to report
