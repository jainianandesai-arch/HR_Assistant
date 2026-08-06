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


def _manitoba(years: float, **_) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 3:
        notice = 1.0
    else:
        notice = min(1.0 + (int(years) - 3), 8.0)
    notes = ["Manitoba ESC notice: 1 week (3mo-3yr), then +1 week per additional completed year beyond 3, capped at 8 weeks."]
    return LegislativeResult("Manitoba", notice, 0.0, notes)


def _saskatchewan(years: float, **_) -> LegislativeResult:
    if years < 13 / 52:
        notice = 0.0
    elif years < 1:
        notice = 1.0
    elif years < 3:
        notice = 2.0
    elif years < 5:
        notice = 4.0
    elif years < 10:
        notice = 6.0
    else:
        notice = 8.0
    notes = ["Saskatchewan Employment Act notice table: 1/2/4/6/8 weeks at 13wks/1yr/3yr/5yr/10yr of service."]
    return LegislativeResult("Saskatchewan", notice, 0.0, notes)


def _nova_scotia(years: float, **_) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 2:
        notice = 1.0
    elif years < 5:
        notice = 2.0
    elif years < 10:
        notice = 4.0
    else:
        notice = 8.0
    notes = ["Nova Scotia Labour Standards Code notice table: 1/2/4/8 weeks at 3mo/2yr/5yr/10yr of service."]
    return LegislativeResult("Nova Scotia", notice, 0.0, notes)


def _new_brunswick(years: float, **_) -> LegislativeResult:
    if years < 6 / 12:
        notice = 0.0
    elif years < 5:
        notice = 2.0
    else:
        notice = 4.0
    notes = ["New Brunswick ESA notice: 2 weeks (6mo-5yr), 4 weeks (5yr+). Simple two-tier structure."]
    return LegislativeResult("New Brunswick", notice, 0.0, notes)


def _pei(years: float, **_) -> LegislativeResult:
    if years < 6 / 12:
        notice = 0.0
    elif years < 5:
        notice = 2.0
    else:
        notice = 4.0
    notes = [
        "PEI ESA notice: 2 weeks (6mo-5yr), 4 weeks (5yr+). Note: PEI's Employment Standards Act was "
        "substantially overhauled in 2026 (shorter qualifying period, new group-termination rules) — "
        "verify current thresholds before relying on this."
    ]
    return LegislativeResult("Prince Edward Island", notice, 0.0, notes)


def _newfoundland(years: float, **_) -> LegislativeResult:
    if years < 3 / 12:
        notice = 0.0
    elif years < 2:
        notice = 1.0
    elif years < 5:
        notice = 2.0
    elif years < 10:
        notice = 3.0
    elif years < 15:
        notice = 4.0
    else:
        notice = 6.0
    notes = [
        "NL Labour Standards Act notice table: 1/2/3/4/6 weeks at 3mo/2yr/5yr/10yr/15yr of service. "
        "NL has no statutory severance pay on top of notice."
    ]
    return LegislativeResult("Newfoundland and Labrador", notice, 0.0, notes)


def _yukon(years: float, **_) -> LegislativeResult:
    if years < 6 / 12:
        notice = 0.0
    elif years < 1:
        notice = 1.0
    elif years < 3:
        notice = 2.0
    else:
        notice = min(3.0 + (int(years) - 3), 8.0)
    notes = ["Yukon ESA notice: 1 week (6mo-1yr), 2 weeks (1-3yr), then +1 week/year beyond 3, capped at 8 weeks."]
    return LegislativeResult("Yukon", notice, 0.0, notes)


def _northwest_territories(years: float, **_) -> LegislativeResult:
    if years < 90 / 365:
        notice = 0.0
    elif years < 2:
        notice = 2.0
    else:
        notice = min(2.0 + (int(years) - 2), 8.0)
    notes = ["NWT ESA notice: 2 weeks (90 days-2yr), then +1 week per additional completed year, capped at 8 weeks."]
    return LegislativeResult("Northwest Territories", notice, 0.0, notes)


def _nunavut(years: float, **_) -> LegislativeResult:
    if years < 90 / 365:
        notice = 0.0
    elif years < 3:
        notice = 2.0
    else:
        notice = min(2.0 + (int(years) - 3), 8.0)
    notes = ["Nunavut Labour Standards Act notice: 2 weeks (90 days-3yr), then +1 week per additional completed year, capped at 8 weeks."]
    return LegislativeResult("Nunavut", notice, 0.0, notes)


CALCULATORS = {
    "Ontario": _ontario,
    "British Columbia": _british_columbia,
    "Alberta": _alberta,
    "Quebec": _quebec,
    "Federal": _federal,
    "Manitoba": _manitoba,
    "Saskatchewan": _saskatchewan,
    "Nova Scotia": _nova_scotia,
    "New Brunswick": _new_brunswick,
    "Prince Edward Island": _pei,
    "Newfoundland and Labrador": _newfoundland,
    "Yukon": _yukon,
    "Northwest Territories": _northwest_territories,
    "Nunavut": _nunavut,
}

SUPPORTED_JURISDICTIONS = list(CALCULATORS.keys())


def calculate(
    jurisdiction: str,
    years_of_service: float,
    employer_payroll_million: float | None = None,
    fixed_term: bool = False,
    excluded_industry: bool = False,
) -> LegislativeResult:
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
    result = fn(years_of_service, monthly_payroll_million=employer_payroll_million)

    if fixed_term:
        result.notes.append(
            "⚠ FIXED-TERM CONTRACT: most jurisdictions do NOT require statutory notice if the "
            "contract completes its full term as scheduled. The figures above assume an "
            "indefinite-term employee — if this is an early termination of a fixed-term contract, "
            "the employee may instead be owed wages for the remainder of the term (potentially "
            "more than these statutory figures). Confirm with legal."
        )
    if excluded_industry:
        result.notes.append(
            "⚠ POSSIBLE INDUSTRY EXCLUSION: some jurisdictions exempt certain industries/roles "
            "(e.g. construction, agriculture, seasonal work) from termination notice or severance "
            "pay requirements entirely. The figures above assume no exclusion applies — verify "
            "this employee's role/industry against the applicable ESA regulations before relying "
            "on this number."
        )
    return result


@dataclass
class MassTerminationRule:
    threshold: int
    window: str
    note: str


# Simplified group/mass-termination triggers: crossing the threshold within the stated window
# typically adds extended employee notice AND a separate notice obligation to the
# provincial/federal labour ministry — always confirm exact tiers and filing steps with counsel.
MASS_TERMINATION_RULES = {
    "Ontario": MassTerminationRule(50, "4 weeks", "Extended notice (8-16 wks by headcount tier) + Form 1 filing with the Ministry of Labour."),
    "British Columbia": MassTerminationRule(50, "2 months", "Group termination notice (8-16 wks by headcount tier) + notice to the Minister."),
    "Alberta": MassTerminationRule(50, "4 weeks", "Group termination provisions apply — extended notice + notice to the Minister."),
    "Quebec": MassTerminationRule(10, "2 months", "Collective dismissal rules apply (8-16 wks by headcount tier) + notice to Emploi-Québec/CNESST."),
    "Federal": MassTerminationRule(50, "4 weeks", "Minimum 16 weeks' notice to Minister + affected employees, plus joint consultation committee obligations."),
    "Manitoba": MassTerminationRule(50, "4 weeks", "Group termination provisions apply — extended notice + notice to the Director."),
    "Saskatchewan": MassTerminationRule(10, "4 weeks", "Group termination notice to the Minister required (4-16 wks by headcount tier)."),
    "Prince Edward Island": MassTerminationRule(10, "2 months", "6 weeks' notice required if 10+ employees or 25%+ of workforce affected within 2 months."),
    "Northwest Territories": MassTerminationRule(25, "4 weeks", "Mass termination notice to the Director required in addition to individual notice."),
    "Nunavut": MassTerminationRule(25, "4 weeks", "Mass termination notice to the Labour Standards Office required in addition to individual notice."),
}


def check_mass_termination(jurisdiction: str, headcount: int) -> MassTerminationRule | None:
    rule = MASS_TERMINATION_RULES.get(jurisdiction)
    if rule and headcount >= rule.threshold:
        return rule
    return None
