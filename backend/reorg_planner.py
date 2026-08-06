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
OPTIONAL_COLUMNS = ["name", "department", "included"]

COLUMN_ALIASES = {
    "employee_id": ["employee_id", "employee id", "id", "emp id", "emp_id"],
    "name": ["name", "employee name", "full name"],
    "jurisdiction": ["jurisdiction", "province", "province/territory"],
    "hire_date": ["hire_date", "hire date", "start date"],
    "weekly_pay": ["weekly_pay", "weekly pay", "weekly salary", "weekly wage"],
    "department": ["department", "dept", "team"],
    "included": ["included", "in scope", "in_scope", "impacted"],
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
            },
            {
                "employee_id": "E002",
                "name": "John Doe",
                "department": "Operations",
                "jurisdiction": "British Columbia",
                "hire_date": "2015-03-15",
                "weekly_pay": 1450,
                "included": "Y",
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
                    f"Must be one of: {', '.join(severance_rules.SUPPORTED_JURISDICTIONS)} (others use Q&A tab)",
                    "YYYY-MM-DD",
                    "Regular weekly pay in CAD",
                    "Any text label",
                    "Any text label",
                    "Y/N — rows marked N are excluded from cost totals",
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
        stat = severance_rules.calculate(r["jurisdiction"], years, payroll_million)
        stat_weeks = stat.total_weeks

        common_law_weeks = min(
            years * common_law_months_per_year * (52 / 12),
            common_law_cap_months * (52 / 12),
        )
        low_weeks = stat_weeks
        high_weeks = max(stat_weeks, common_law_weeks)
        moderate_weeks = (low_weeks + high_weeks) / 2

        row = {
            "employee_id": r["employee_id"],
            "name": r.get("name", ""),
            "department": r.get("department", ""),
            "jurisdiction": r["jurisdiction"],
            "included": r["included"],
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
        rows.append(row)

    return pd.DataFrame(rows)


def summarize(result_df: pd.DataFrame) -> pd.DataFrame:
    in_scope = result_df[result_df["included"]]
    cost_cols = [c for c in ["statutory_cost", "low_cost", "moderate_cost", "high_cost", "custom_cost"] if c in in_scope.columns]
    totals = in_scope[cost_cols].sum().rename("Total ($)")
    counts = pd.Series({"Employees in scope": len(in_scope)})
    return pd.concat([counts, totals]).to_frame()


def build_output_excel(result_df: pd.DataFrame, summary_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary")
        result_df.to_excel(writer, index=False, sheet_name="Employee Detail")
    return buf.getvalue()
