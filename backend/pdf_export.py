"""One-page PDF summary of a reorg cost scenario — a polished deliverable an HRBP can attach to
a business case, alongside the full Excel detail."""
from datetime import date, datetime, timezone

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


def build_reorg_pdf(
    as_of_date,
    summary_series,
    mass_flags: list[str],
    union_flag: str | None,
    scenario_name: str = "",
) -> bytes:
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

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, "Scenario Totals", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)

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

    if mass_flags or union_flag:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 8, "Flags for Legal/Labour Relations Review", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        for flag in mass_flags:
            clean = flag.replace("**", "")
            pdf.multi_cell(0, 6, f"- {clean}")
        if union_flag:
            pdf.multi_cell(0, 6, f"- {union_flag}")
        pdf.ln(4)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(
        0, 6,
        "Low = statutory minimum. High = greater of statutory minimum or a common-law rule-of-thumb "
        "estimate. Moderate = midpoint of the two. See the accompanying Excel export for full "
        "employee-level calculation detail and audit notes.",
    )

    return bytes(pdf.output())
