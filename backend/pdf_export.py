"""PDF export of a reorg cost scenario — a self-contained deliverable an HRBP can hand to a VP or
attach to a business case: assumptions, totals, flags for legal review, and full employee-level
detail with the methodology behind every number."""
from datetime import datetime, timezone

from fpdf import FPDF

NAVY = (11, 31, 58)
GOLD = (185, 139, 42)
GREY = (90, 90, 90)


class ReorgPDF(FPDF):
    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 22, "F")
        self.set_xy(10, 6)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "Reorg Scenario Cost Summary", ln=True)
        self.set_y(24)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GREY)
        self.cell(
            0, 8,
            "Planning estimate only, not legal advice. Confirm with employment counsel before "
            "relying on these figures for an actual reorg.",
            align="C",
        )
        self.set_y(-10)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")


def _section_title(pdf: ReorgPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, text, ln=True)
    pdf.set_text_color(0, 0, 0)


def build_reorg_pdf(
    as_of_date,
    summary_series,
    result_df,
    mass_flags: list[str],
    union_flag: str | None,
    other_flags: list[str] | None = None,
    common_law_months_per_year: float | None = None,
    common_law_cap_months: float | None = None,
    scenario_name: str = "",
) -> bytes:
    other_flags = other_flags or []
    pdf = ReorgPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_text_color(*GREY)
    pdf.set_font("Helvetica", "", 10)
    title = scenario_name or "Untitled scenario"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 6, f"Scenario: {title}", ln=True)
    pdf.cell(0, 6, f"Effective / as-of date: {as_of_date}", ln=True)
    pdf.cell(0, 6, f"Generated: {generated}", ln=True)
    pdf.ln(4)

    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.6)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(6)

    # --- Methodology ---
    _section_title(pdf, "How These Numbers Are Calculated")
    pdf.set_font("Helvetica", "", 9)
    methodology = (
        "Low = statutory minimum notice/severance under the applicable provincial or federal "
        "employment standards legislation for each employee's jurisdiction and years of service.\n\n"
    )
    if common_law_months_per_year is not None and common_law_cap_months is not None:
        methodology += (
            f"High = the greater of the statutory minimum or a common-law rule-of-thumb estimate "
            f"({common_law_months_per_year} month(s) of notice per year of service, capped at "
            f"{common_law_cap_months} months).\n\n"
        )
    else:
        methodology += "High = the greater of the statutory minimum or a common-law rule-of-thumb estimate.\n\n"
    methodology += (
        "Moderate = the midpoint between Low and High.\n\n"
        "Custom (if shown) = the greater of the statutory minimum or the entitlement calculated "
        "from the company policy text provided, parsed once and applied to every employee."
    )
    pdf.multi_cell(0, 5, methodology)
    pdf.ln(4)

    # --- Scenario totals ---
    _section_title(pdf, "Scenario Totals (In-Scope Employees)")
    pdf.set_font("Helvetica", "", 10)

    label_map = {
        "Employees in scope": "Employees in scope",
        "statutory_cost": "Statutory minimum",
        "low_cost": "Low scenario",
        "moderate_cost": "Moderate scenario",
        "high_cost": "High scenario",
        "custom_cost": "Custom policy",
    }
    for key, label in label_map.items():
        if key not in summary_series.index:
            continue
        value = summary_series[key]
        display = f"{value:,.0f}" if key == "Employees in scope" else f"${value:,.0f}"
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(80, 8, label, border="B")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, display, border="B", ln=True, align="R")

    pdf.ln(8)

    # --- Flags ---
    all_flags = list(mass_flags)
    if union_flag:
        all_flags.append(union_flag)
    all_flags.extend(other_flags)
    if all_flags:
        _section_title(pdf, "Flags for Legal/Labour Relations Review")
        pdf.set_font("Helvetica", "", 9)
        for flag in all_flags:
            clean = flag.replace("**", "").replace("⚠", "").strip()
            pdf.multi_cell(0, 6, f"- {clean}")
        pdf.ln(4)

    # --- Employee-level detail ---
    if result_df is not None and len(result_df):
        in_scope = result_df[result_df["included"]] if "included" in result_df.columns else result_df
        pdf.add_page()
        _section_title(pdf, "Employee-Level Detail")
        pdf.set_font("Helvetica", "", 8)

        cols = [
            ("employee_id", "ID", 18),
            ("name", "Name", 30),
            ("jurisdiction", "Jurisdiction", 32),
            ("years_of_service", "Yrs", 12),
            ("low_cost", "Low ($)", 24),
            ("moderate_cost", "Moderate ($)", 26),
            ("high_cost", "High ($)", 24),
        ]
        if "custom_cost" in in_scope.columns:
            cols.append(("custom_cost", "Custom ($)", 24))

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        for key, label, width in cols:
            pdf.cell(width, 7, label, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 0, 0)
        for _, row in in_scope.iterrows():
            for key, _, width in cols:
                val = row.get(key, "")
                if key in ("low_cost", "moderate_cost", "high_cost", "custom_cost"):
                    text = f"${val:,.0f}"
                elif key == "years_of_service":
                    text = f"{val:.1f}"
                else:
                    text = str(val)[: int(width / 1.7)]
                pdf.cell(width, 6, text, border=1)
            pdf.ln()

        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(
            0, 5,
            "Per-employee calculation notes (which statutory rule applied, common-law formula, "
            "any flags) are available in the Excel export's calculation_notes column.",
        )

    return bytes(pdf.output())
