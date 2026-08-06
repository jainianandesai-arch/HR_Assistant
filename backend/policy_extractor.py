"""One-shot LLM extraction of a structured severance formula from free-text company policy.

Called once per reorg scenario run (not once per employee) to keep bulk cost-modeling cheap —
the extracted parameters are then applied deterministically to every row.
"""
import json

from .reorg_planner import CustomPolicyParams

EXTRACTION_TOOL = {
    "name": "record_severance_formula",
    "description": "Record the severance/termination pay formula extracted from a company policy document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "weeks_per_year": {
                "type": "number",
                "description": "Weeks of pay per completed year of service. 0 if the policy has no per-year component.",
            },
            "flat_weeks": {
                "type": "number",
                "description": "Flat/base weeks of pay regardless of tenure. 0 if none.",
            },
            "min_weeks": {
                "type": "number",
                "description": "Minimum weeks guaranteed by policy, if stated. 0 if none.",
            },
            "max_weeks": {
                "type": ["number", "null"],
                "description": "Maximum/cap weeks, if the policy states one. null if uncapped.",
            },
            "confident": {
                "type": "boolean",
                "description": "True only if the policy clearly states a numeric formula you extracted with confidence.",
            },
            "summary": {
                "type": "string",
                "description": "One or two sentence plain-English summary of the formula found, or why extraction wasn't confident.",
            },
        },
        "required": ["weeks_per_year", "flat_weeks", "min_weeks", "max_weeks", "confident", "summary"],
    },
}

SYSTEM_PROMPT = """Extract a severance/termination-pay formula from the company policy text provided. \
Express it purely in terms of: a flat number of weeks, weeks per completed year of service, a minimum \
weeks floor, and an optional maximum weeks cap. If the policy uses months instead of weeks, convert \
(1 month ≈ 4.33 weeks). If the policy is tiered by role/level and no single formula applies, or the \
policy doesn't clearly state a numeric severance formula, set confident=false and explain why in the \
summary rather than guessing. Always call the record_severance_formula tool with your result."""


def extract_policy_formula(client, model: str, policy_text: str) -> tuple[CustomPolicyParams, bool, object]:
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_severance_formula"},
        messages=[{"role": "user", "content": f"Company policy text:\n\n{policy_text}"}],
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "record_severance_formula":
            data = block.input
            params = CustomPolicyParams(
                weeks_per_year=float(data.get("weeks_per_year") or 0),
                flat_weeks=float(data.get("flat_weeks") or 0),
                min_weeks=float(data.get("min_weeks") or 0),
                max_weeks=(float(data["max_weeks"]) if data.get("max_weeks") is not None else None),
                summary=data.get("summary", ""),
            )
            return params, bool(data.get("confident")), response.usage

    raise RuntimeError("Model did not return a structured policy formula.")
