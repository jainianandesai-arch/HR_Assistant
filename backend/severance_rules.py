"""Simplified statutory termination-notice / severance-pay calculators.

These formulas are simplified summaries of publicly available employment
standards legislation, current as of this writing, for common non-unionized,
non-just-cause terminations. They are NOT a substitute for legal advice —
always confirm with employment counsel before relying on a number here for
an actual termination, especially near a threshold (e.g. mass termination
triggers, industry-specific exclusions, or common-law reasonable notice
which is typically higher than the statutory minimum calculated here).
"""
from dataclasses import dataclass, field


@dataclass
class LegislativeResult:
    jurisdiction: str
    notice_weeks: float
    severance_weeks: float
    notes: list[str] = field(default_factory=list)
    supported: bool = True

    @property
    def total_weeks(self) -> float:
        return self.notice_weeks + self.severance_weeks


def _ontario(years: float, monthly_payroll_million: float | None) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 1:
        notice = 1.0
    else:
        notice = min(float(int(years)), 8.0)

    severance = 0.0
    notes = ["ESA notice: 1 week per completed year of service (min 1 week after 3 months), capped at 8 weeks."]
    if years >= 5 and (monthly_payroll_million or 0) >= 2.5:
        severance = min(years, 26.0)
        notes.append(
            "ESA statutory severance pay also applies (5+ years service, employer payroll ≥ $2.5M): "
            "~1 week per year of service, capped at 26 weeks, in addition to notice."
        )
    else:
        notes.append(
            "Statutory severance pay (on top of notice) only applies with 5+ years service AND "
            "employer Ontario payroll ≥ $2.5M."
        )
    return LegislativeResult("Ontario", notice, severance, notes)


def _british_columbia(years: float, **_) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 1:
        notice = 1.0
    elif years < 3:
        notice = 2.0
    else:
        notice = min(3.0 + (int(years) - 3), 8.0)
    notes = [
        "BC ESA notice: 1 week (3mo-1yr), 2 weeks (1-3yr), then 3 weeks at 3 years plus 1 week per "
        "additional completed year, capped at 8 weeks."
    ]
    return LegislativeResult("British Columbia", notice, 0.0, notes)


def _alberta(years: float, **_) -> LegislativeResult:
    if years < 90 / 365:
        notice = 0.0
    elif years < 2:
        notice = 1.0
    elif years < 4:
        notice = 2.0
    elif years < 6:
        notice = 4.0
    elif years < 8:
        notice = 5.0
    elif years < 10:
        notice = 6.0
    else:
        notice = 8.0
    notes = ["Alberta ESA graduated notice table by completed years of service (90 days to 10+ years)."]
    return LegislativeResult("Alberta", notice, 0.0, notes)


def _quebec(years: float, **_) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 1:
        notice = 1.0
    elif years < 5:
        notice = 2.0
    elif years < 10:
        notice = 4.0
    else:
        notice = 8.0
    notes = ["Quebec Act respecting Labour Standards notice of termination table."]
    return LegislativeResult("Quebec", notice, 0.0, notes)


def _federal(years: float, **_) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 3:
        notice = 2.0
    else:
        notice = min(2.0 + (int(years) - 2), 8.0)
    severance = 0.0
    notes = [
        "Canada Labour Code notice: 2 weeks minimum after 3 months, graduated up to 8 weeks for 3+ "
        "years of service (1 additional week per year beyond 2 years, capped at 8)."
    ]
    if years >= 1:
        severance = max(2 * years / 5, 5 / 5)  # 2 days/year of service, min 5 days — expressed in weeks (5-day week)
        notes.append(
            "Statutory severance pay also applies (12+ months service): greater of 2 days' wages per "
            "year of service, or 5 days' wages — shown here converted to weeks assuming a 5-day work week."
        )
    return LegislativeResult("Federal", notice, severance, notes)


CALCULATORS = {
    "Ontario": _ontario,
    "British Columbia": _british_columbia,
    "Alberta": _alberta,
    "Quebec": _quebec,
    "Federal": _federal,
}

SUPPORTED_JURISDICTIONS = list(CALCULATORS.keys())


def calculate(jurisdiction: str, years_of_service: float, employer_payroll_million: float | None = None) -> LegislativeResult:
    fn = CALCULATORS.get(jurisdiction)
    if not fn:
        return LegislativeResult(
            jurisdiction,
            0.0,
            0.0,
            notes=[
                f"{jurisdiction} isn't in the built-in calculator yet. Ask the Q&A tab for the "
                "applicable notice period, or add a formula to backend/severance_rules.py."
            ],
            supported=False,
        )
    return fn(years_of_service, monthly_payroll_million=employer_payroll_million)
