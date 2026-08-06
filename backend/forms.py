"""Curated directory of official HR-relevant forms/links (injury reporting, ROE, human rights
complaints, etc.), surfaced both inline in Q&A answers and as a browsable reference panel."""
import json
import re
from pathlib import Path

FORMS_PATH = Path(__file__).resolve().parent.parent / "data" / "forms.json"

CATEGORY_KEYWORDS = {
    "Workplace Injury Reporting": ["injury", "injured", "accident", "wsib", "worksafe", "wcb", "workers' compensation", "workers compensation", "claim"],
    "Record of Employment": ["roe", "record of employment", "employment insurance", " ei "],
    "Human Rights Complaint": ["human rights", "discrimination", "harassment", "accommodation", "tribunal"],
    "Workplace Health and Safety": ["health and safety", "ohs", "occupational health"],
}


def load_forms() -> list[dict]:
    if not FORMS_PATH.exists():
        return []
    return json.loads(FORMS_PATH.read_text(encoding="utf-8"))


def all_jurisdictions() -> list[str]:
    return sorted({f["jurisdiction"] for f in load_forms()})


def forms_for_jurisdiction(jurisdiction: str | None = None) -> list[dict]:
    forms = load_forms()
    if jurisdiction:
        forms = [f for f in forms if f["jurisdiction"] in (jurisdiction, "Federal")]
    return forms


def relevant_forms(question: str, jurisdictions: list[str]) -> list[dict]:
    q = question.lower()
    matched_categories = {
        cat for cat, kws in CATEGORY_KEYWORDS.items() if any(kw in q for kw in kws)
    }
    if not matched_categories:
        return []

    forms = load_forms()
    results = [
        f for f in forms
        if f["category"] in matched_categories
        and (not jurisdictions or f["jurisdiction"] in jurisdictions or f["jurisdiction"] == "Federal")
    ]
    return results[:5]
