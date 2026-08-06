"""Lightweight retrieval over the nightly-refreshed government page cache.

No embeddings/vector DB — the cache is small (a few dozen curated official
pages), so a simple keyword/jurisdiction overlap score is enough to pick the
most relevant pages to hand to Claude as context, avoiding a paid web search
on every question.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "knowledge_cache.json"
CHANGELOG_PATH = ROOT / "data" / "refresh_changelog.json"

PROVINCE_ALIASES = {
    "ontario": "Ontario", "on": "Ontario",
    "quebec": "Quebec", "qc": "Quebec", "québec": "Quebec",
    "british columbia": "British Columbia", "bc": "British Columbia",
    "alberta": "Alberta", "ab": "Alberta",
    "manitoba": "Manitoba", "mb": "Manitoba",
    "saskatchewan": "Saskatchewan", "sk": "Saskatchewan",
    "nova scotia": "Nova Scotia", "ns": "Nova Scotia",
    "new brunswick": "New Brunswick", "nb": "New Brunswick",
    "prince edward island": "Prince Edward Island", "pei": "Prince Edward Island", "pe": "Prince Edward Island",
    "newfoundland": "Newfoundland and Labrador", "nl": "Newfoundland and Labrador",
    "yukon": "Yukon", "yt": "Yukon",
    "northwest territories": "Northwest Territories", "nwt": "Northwest Territories", "nt": "Northwest Territories",
    "nunavut": "Nunavut", "nu": "Nunavut",
    "federal": "Federal", "federally regulated": "Federal",
}


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"refreshed_at": None, "pages": []}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def detect_jurisdictions(question: str) -> list[str]:
    q = question.lower()
    found = {full for alias, full in PROVINCE_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", q)}
    return sorted(found)


def _score(question_words: set[str], page: dict, mentioned: list[str]) -> float:
    haystack = f"{page['topic']} {page['jurisdiction']} {page['text'][:2000]}".lower()
    hay_words = set(re.findall(r"[a-z]+", haystack))
    overlap = len(question_words & hay_words)
    score = float(overlap)
    if page["jurisdiction"] in mentioned:
        score += 10
    if not mentioned and page["jurisdiction"] == "Federal":
        score += 1
    return score


def retrieve(question: str, top_k: int = 6) -> list[dict]:
    cache = load_cache()
    pages = [p for p in cache.get("pages", []) if p.get("status") == "ok" and p.get("text")]
    if not pages:
        return []

    question_words = set(re.findall(r"[a-z]+", question.lower()))
    mentioned = detect_jurisdictions(question)

    scored = sorted(pages, key=lambda p: _score(question_words, p, mentioned), reverse=True)
    return scored[:top_k]


def format_context(pages: list[dict]) -> str:
    blocks = []
    for p in pages:
        blocks.append(
            f"### {p['jurisdiction']} — {p['topic']}\nSource: {p['url']}\n\n{p['text']}"
        )
    return "\n\n---\n\n".join(blocks)


def refreshed_at() -> str | None:
    return load_cache().get("refreshed_at")


def recent_changes(limit: int = 8) -> list[dict]:
    if not CHANGELOG_PATH.exists():
        return []
    try:
        entries = json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return entries[:limit]
