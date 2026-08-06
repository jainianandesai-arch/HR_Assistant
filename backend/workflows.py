"""Step-by-step guided workflows for common HRBP situations (workplace injury, termination, leave,
human rights concerns) — aimed at new HRBPs who need "what do I do, in order" rather than a single
Q&A answer. Each guide resolves the right form link for the selected jurisdiction at the step
where it's actually needed.
"""
import json
from pathlib import Path

from . import forms

WORKFLOWS_PATH = Path(__file__).resolve().parent.parent / "data" / "workflows.json"


def load_workflows() -> list[dict]:
    if not WORKFLOWS_PATH.exists():
        return []
    return json.loads(WORKFLOWS_PATH.read_text(encoding="utf-8"))


def get_workflow(workflow_id: str) -> dict | None:
    for wf in load_workflows():
        if wf["id"] == workflow_id:
            return wf
    return None


def resolve_form_for_step(workflow: dict, jurisdiction: str) -> dict | None:
    """Find the best-matching form link for this workflow's category and jurisdiction."""
    category = workflow.get("form_category")
    if not category:
        return None
    candidates = [
        f for f in forms.load_forms()
        if f["category"] == category and f["jurisdiction"] in (jurisdiction, "Federal")
    ]
    if not candidates:
        return None
    # Prefer an exact jurisdiction match over the Federal fallback.
    exact = [f for f in candidates if f["jurisdiction"] == jurisdiction]
    return exact[0] if exact else candidates[0]
