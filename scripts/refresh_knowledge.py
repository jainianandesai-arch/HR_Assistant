"""Nightly refresh: fetch curated official government pages into a local cache.

Run manually with `python scripts/refresh_knowledge.py`, or via the scheduled
GitHub Actions workflow (.github/workflows/refresh.yml), which commits the
updated data/knowledge_cache.json back to the repo every morning.
"""
import difflib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "data" / "sources.json"
CACHE_PATH = ROOT / "data" / "knowledge_cache.json"
CHANGELOG_PATH = ROOT / "data" / "refresh_changelog.json"
CHANGELOG_MAX_ENTRIES = 200
CHANGE_SIMILARITY_THRESHOLD = 0.97  # below this ratio, treat the page as materially changed

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}
MAX_CHARS_PER_PAGE = 12_000
TIMEOUT_SECONDS = 30
RETRY_COUNT = 2


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup
    text = " ".join(main.get_text(separator=" ").split())
    return text[:MAX_CHARS_PER_PAGE]


def fetch_source(entry: dict) -> dict:
    url = entry["url"]
    text, status = "", "error: unknown"
    for attempt in range(RETRY_COUNT):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            text = extract_text(resp.text)
            status = "ok" if text else "empty"
            break
        except requests.RequestException as exc:
            text, status = "", f"error: {exc}"

    return {
        **entry,
        "text": text,
        "status": status,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def load_previous_pages() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        old_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {p["url"]: p for p in old_cache.get("pages", []) if p.get("status") == "ok"}


def detect_changes(old_pages: dict, new_records: list[dict], refreshed_at: str) -> list[dict]:
    changes = []
    for record in new_records:
        if record["status"] != "ok":
            continue
        old = old_pages.get(record["url"])
        if old is None:
            continue  # first successful fetch of this page — not a "change", just new coverage
        ratio = difflib.SequenceMatcher(None, old["text"], record["text"]).ratio()
        if ratio < CHANGE_SIMILARITY_THRESHOLD:
            changes.append(
                {
                    "detected_at": refreshed_at,
                    "jurisdiction": record["jurisdiction"],
                    "topic": record["topic"],
                    "url": record["url"],
                    "similarity": round(ratio, 3),
                }
            )
    return changes


def append_changelog(new_changes: list[dict]) -> None:
    existing = []
    if CHANGELOG_PATH.exists():
        try:
            existing = json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    combined = (new_changes + existing)[:CHANGELOG_MAX_ENTRIES]
    CHANGELOG_PATH.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    old_pages = load_previous_pages()
    results = []
    failures = []

    for entry in sources:
        record = fetch_source(entry)
        results.append(record)
        marker = "OK" if record["status"] == "ok" else "FAIL"
        print(f"[{marker}] {entry['jurisdiction']} — {entry['topic']}: {record['status']}")
        if record["status"] != "ok":
            failures.append(entry["url"])

    refreshed_at = datetime.now(timezone.utc).isoformat()
    cache = {"refreshed_at": refreshed_at, "pages": results}
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(results)} pages to {CACHE_PATH} ({len(failures)} failed).")

    changes = detect_changes(old_pages, results, refreshed_at)
    if changes:
        append_changelog(changes)
        print(f"\nDetected {len(changes)} page(s) with material content changes:")
        for c in changes:
            print(f"  - {c['jurisdiction']} — {c['topic']} (similarity {c['similarity']})")

    if failures:
        print("\nFailed URLs (left in cache with empty text, check data/sources.json):")
        for url in failures:
            print(f"  - {url}")


if __name__ == "__main__":
    sys.exit(main())
