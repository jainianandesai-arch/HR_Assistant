"""Nightly refresh: fetch curated official government pages into a local cache.

Run manually with `python scripts/refresh_knowledge.py`, or via the scheduled
GitHub Actions workflow (.github/workflows/refresh.yml), which commits the
updated data/knowledge_cache.json back to the repo every morning.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "data" / "sources.json"
CACHE_PATH = ROOT / "data" / "knowledge_cache.json"

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


def main() -> None:
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    results = []
    failures = []

    for entry in sources:
        record = fetch_source(entry)
        results.append(record)
        marker = "OK" if record["status"] == "ok" else "FAIL"
        print(f"[{marker}] {entry['jurisdiction']} — {entry['topic']}: {record['status']}")
        if record["status"] != "ok":
            failures.append(entry["url"])

    cache = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "pages": results,
    }
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(results)} pages to {CACHE_PATH} ({len(failures)} failed).")

    if failures:
        print("Failed URLs (left in cache with empty text, check data/sources.json):")
        for url in failures:
            print(f"  - {url}")


if __name__ == "__main__":
    sys.exit(main())
