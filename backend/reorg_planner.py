"""Bulk severance cost modeling for reorg scenarios.

Employees are uploaded as an Excel file. For each employee we compute:
- Statutory minimum (deterministic, via severance_rules — same formulas as the single-employee
  calculator, so no per-row LLM cost).
- Low / Moderate / High scenario costs, derived from the statutory minimum and a simple common-law
  "rule of thumb" estimate (~1 month per year of service, capped), both user-adjustable.
- Optional custom-policy cost, using ONE LLM call to extract a structured formula from the pasted/
  uploaded policy, then applied deterministically to every row (not one call per employee).
"""
import io
from dataclasses import dataclass

import pandas as pd

from . import severance_rules

REQUIRED_COLUMNS = ["employee_id", "jurisdiction", "hire_date", "weekly_pay"]
OPTIONAL_COLUMNS = ["name", "department", "included", "unionized", "fixed_term", "excluded_industry"]

COLUMN_ALIASES = {
    "employee_id": ["employee_id", "employee id", "id", "emp id", "emp_id"],
    "name": ["name", "employee name", "full name"],
    "jurisdiction": ["jurisdiction", "province", "province/territory"],
    "hire_date": ["hire_date", "hire date", "start date"],
    "weekly_pay": ["weekly_pay", "weekly pay", "weekly salary", "weekly wage"],
    "department": ["department", "dept", "team"],
    "included": ["included", "in scope", "in_scope", "impacted"],
    "unionized": ["unionized", "unionised", "union", "cba", "collective agreement"],
    "fixed_term": ["fixed_term", "fixed term", "fixed-term", "contract type"],
    "excluded_industry": ["excluded_industry", "excluded industry", "industry exclusion", "construction/agriculture"],
}


class TemplateError(ValueError):
    pass


def build_template_bytes() -> bytes:
    sample = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "name": "Jane Smith",
                "department": "Finance",
                "jurisdiction": "Ontario",
                "hire_date": "2019-06-01",
                "weekly_pay": 1800,
                "included": "Y",
                "unionized": "N",
                "fixed_term": "N",
                "excluded_industry": "N",
            },
            {
                "employee_id": "E002",
                "name": "John Doe",
                "department": "Operations",
                "jurisdiction": "British Columbia",
                "hire_date": "2015-03-15",
                "weekly_pay": 1450,
                "included": "Y",
                "unionized": "N",
                "fixed_term": "N",
                "excluded_industry": "N",
            },
        ]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        sample.to_excel(writer, index=False, sheet_name="Employees")
        instructions = pd.DataFrame(
            {
                "Column": REQUIRED_COLUMNS + OPTIONAL_COLUMNS,
                "Required": ["Yes"] * len(REQUIRED_COLUMNS) + ["No"] * len(OPTIONAL_COLUMNS),
                "Notes": [
                    "Unique identifier",
                    f"Must be one of: {', '.join(severance_rules.SUPPORTED_JURISDICTIONS)}",
                    "YYYY-MM-DD",
                    "Regular weekly pay in CAD",
                    "Any text label",
                    "Any text label",
                    "Y/N — rows marked N are excluded from cost totals",
                    "Y/N — rows marked Y are flagged; statutory ESA/CBA calculator doesn't apply to unionized roles, defer to the collective agreement",
                    "Y/N — contract has a defined end date rather than being indefinite",
                    "Y/N — role/industry (e.g. construction, agriculture) that may be exempt from ESA notice requirements",
                ],
            }
        )
        instructions.to_excel(writer, index=False, sheet_name="Instructions")
    return buf.getvalue()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    lower_map = {c.strip().lower(): c for c in df.columns}
    rename = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_map:
                rename[lower_map[alias]] = canonical
                break
    df = df.rename(columns=rename)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise TemplateError(
            f"Missing required column(s): {', '.join(missing)}. Download the template for the "
            "expected format."
        )
    return df


def load_employees(uploaded_file) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file, sheet_name=0)
    df = _normalize_columns(df)
    df["hire_date"] = pd.to_datetime(df["hire_date"], errors="coerce")
    if df["hire_date"].isna().any():
        raise TemplateError("Some rows have an unparseable hire_date — use YYYY-MM-DD.")
    if "included" in df.columns:
        df["included"] = df["included"].astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])
    else:
        df["included"] = True
    for flag_col in ("unionized", "fixed_term", "excluded_industry"):
        if flag_col in df.columns:
            df[flag_col] = df[flag_col].astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])
        else:
            df[flag_col] = False
    unsupported = sorted(set(df["jurisdiction"]) - set(severance_rules.SUPPORTED_JURISDICTIONS))
    if unsupported:
        raise TemplateError(
            f"Unsupported jurisdiction(s) in file: {', '.join(unsupported)}. Built-in calculator "
            f"covers: {', '.join(severance_rules.SUPPORTED_JURISDICTIONS)}."
        )
    return df


@dataclass
class CustomPolicyParams:
    weeks_per_year: float = 0.0
    flat_weeks: float = 0.0
    min_weeks: float = 0.0
    max_weeks: float | None = None
    summary: str = ""

    def weeks_for(self, years_of_service: float) -> float:
        weeks = self.flat_weeks + self.weeks_per_year * years_of_service
        weeks = max(weeks, self.min_weeks)
        if self.max_weeks is not None:
            weeks = min(weeks, self.max_weeks)
        return weeks


def compute_scenarios(
    df: pd.DataFrame,
    as_of_date,
    payroll_million: float | None,
    common_law_months_per_year: float,
    common_law_cap_months: float,
    custom_policy: CustomPolicyParams | None = None,
) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        years = max((pd.Timestamp(as_of_date) - r["hire_date"]).days / 365.25, 0.0)
        stat = severance_rules.calculate(
            r["jurisdiction"], years, payroll_million,
            fixed_term=bool(r.get("fixed_term")), excluded_industry=bool(r.get("excluded_industry")),
        )
        stat_weeks = stat.total_weeks

        common_law_weeks = min(
            years * common_law_months_per_year * (52 / 12),
            common_law_cap_months * (52 / 12),
        )
        low_weeks = stat_weeks
        high_weeks = max(stat_weeks, common_law_weeks)
        moderate_weeks = (low_weeks + high_weeks) / 2

        notes = [f"Statutory ({r['jurisdiction']}): " + " ".join(stat.notes)]
        if r.get("unionized"):
            notes.append(
                "⚠ UNIONIZED: statutory ESA minimums shown here typically do NOT apply as-is — "
                "termination/layoff entitlements are governed by the collective agreement. Treat "
                "these figures as a reference floor only and confirm with labour relations/legal."
            )
        notes.append(
            f"Low = statutory minimum ({stat_weeks:.2f} wks)."
        )
        notes.append(
            f"High = greater of statutory ({stat_weeks:.2f} wks) or common-law estimate "
            f"({years:.2f} yrs x {common_law_months_per_year} mo/yr, capped at {common_law_cap_months} mo, "
            f"= {common_law_weeks:.2f} wks) -> {high_weeks:.2f} wks."
        )
        notes.append(f"Moderate = midpoint of Low and High = ({low_weeks:.2f} + {high_weeks:.2f}) / 2 = {moderate_weeks:.2f} wks.")

        row = {
            "employee_id": r["employee_id"],
            "name": r.get("name", ""),
            "department": r.get("department", ""),
            "jurisdiction": r["jurisdiction"],
            "included": r["included"],
            "unionized": r.get("unionized", False),
            "fixed_term": r.get("fixed_term", False),
            "excluded_industry": r.get("excluded_industry", False),
            "years_of_service": round(years, 2),
            "weekly_pay": r["weekly_pay"],
            "statutory_weeks": round(stat_weeks, 2),
            "statutory_cost": round(stat_weeks * r["weekly_pay"], 2),
            "low_weeks": round(low_weeks, 2),
            "low_cost": round(low_weeks * r["weekly_pay"], 2),
            "moderate_weeks": round(moderate_weeks, 2),
            "moderate_cost": round(moderate_weeks * r["weekly_pay"], 2),
            "high_weeks": round(high_weeks, 2),
            "high_cost": round(high_weeks * r["weekly_pay"], 2),
        }
        if custom_policy is not None:
            custom_weeks = max(custom_policy.weeks_for(years), stat_weeks)
            row["custom_weeks"] = round(custom_weeks, 2)
            row["custom_cost"] = round(custom_weeks * r["weekly_pay"], 2)
            notes.append(
                f"Custom = greater of policy formula ({custom_policy.weeks_for(years):.2f} wks: "
                f"{custom_policy.summary or 'flat/per-year formula from policy'}) or statutory "
                f"({stat_weeks:.2f} wks) -> {custom_weeks:.2f} wks."
            )

        row["calculation_notes"] = " | ".join(notes)
        rows.append(row)

    return pd.DataFrame(rows)


def check_mass_termination(df: pd.DataFrame) -> list[str]:
    """Return human-readable flags where in-scope headcount per jurisdiction crosses a mass/group
    termination threshold, requiring extended notice and/or a filing with the labour ministry."""
    flags = []
    in_scope = df[df["included"]]
    for jurisdiction, group in in_scope.groupby("jurisdiction"):
        headcount = len(group)
        rule = severance_rules.check_mass_termination(jurisdiction, headcount)
        if rule:
            flags.append(
                f"**{jurisdiction}**: {headcount} in-scope employees meets/exceeds the "
                f"{rule.threshold}-employee mass-termination threshold (within {rule.window}). {rule.note}"
            )
    return flags


def check_unionized(df: pd.DataFrame) -> str | None:
    in_scope = df[df["included"]]
    count = int(in_scope["unionized"].sum()) if "unionized" in in_scope.columns else 0
    if count:
        return (
            f"{count} in-scope employee(s) are flagged as unionized. Statutory ESA figures for them "
            "are shown as a reference floor only — actual entitlements are governed by the applicable "
            "collective agreement. Confirm with labour relations before using these numbers."
        )
    return None


def check_other_flags(df: pd.DataFrame) -> list[str]:
    """Fixed-term and industry-exclusion flags — informational, don't alter the calculation."""
    in_scope = df[df["included"]]
    flags = []
    ft_count = int(in_scope["fixed_term"].sum()) if "fixed_term" in in_scope.columns else 0
    if ft_count:
        flags.append(
            f"{ft_count} in-scope employee(s) are flagged as fixed-term contracts. Statutory notice "
            "typically doesn't apply if the contract completes its scheduled term — verify whether "
            "this is an early termination before relying on the statutory figures shown."
        )
    ind_count = int(in_scope["excluded_industry"].sum()) if "excluded_industry" in in_scope.columns else 0
    if ind_count:
        flags.append(
            f"{ind_count} in-scope employee(s) are flagged for possible industry exclusion (e.g. "
            "construction, agriculture). Some jurisdictions exempt these roles from statutory notice "
            "entirely — verify against the applicable ESA regulations before relying on these figures."
        )
    return flags


def summarize(result_df: pd.DataFrame) -> pd.DataFrame:
    in_scope = result_df[result_df["included"]]
    cost_cols = [c for c in ["statutory_cost", "low_cost", "moderate_cost", "high_cost", "custom_cost"] if c in in_scope.columns]
    totals = in_scope[cost_cols].sum()
    counts = pd.Series({"Employees in scope": len(in_scope)})
    combined = pd.concat([counts, totals])
    combined.name = "Total ($)"
    return combined.to_frame()


def build_output_excel(result_df: pd.DataFrame, summary_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary")
        result_df.to_excel(writer, index=False, sheet_name="Employee Detail")
    return buf.getvalue()
