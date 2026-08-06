"""SQLite log of every question asked, for cost tracking and usage analytics.

Note: on Streamlit Community Cloud the filesystem is ephemeral and resets on
redeploy (including the nightly data refresh commit), so this log persists
for the life of a running instance rather than forever. For durable
cross-deploy analytics, point DB_PATH at a mounted volume or swap this for a
hosted database.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "query_log.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    question TEXT NOT NULL,
    jurisdictions TEXT,
    used_web_search INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    num_searches INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0
);
"""


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_query(
    question: str,
    jurisdictions: list[str],
    used_web_search: bool,
    input_tokens: int,
    output_tokens: int,
    num_searches: int,
    cost_usd: float,
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO query_log (ts, question, jurisdictions, used_web_search, "
            "input_tokens, output_tokens, num_searches, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                question,
                ",".join(jurisdictions),
                int(used_web_search),
                input_tokens,
                output_tokens,
                num_searches,
                cost_usd,
            ),
        )


def summary() -> dict:
    with _conn() as conn:
        total_queries = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
        total_cost = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM query_log").fetchone()[0]
        cache_hits = conn.execute(
            "SELECT COUNT(*) FROM query_log WHERE used_web_search = 0"
        ).fetchone()[0]
        top_jurisdictions = conn.execute(
            "SELECT jurisdictions, COUNT(*) c FROM query_log "
            "WHERE jurisdictions != '' GROUP BY jurisdictions ORDER BY c DESC LIMIT 8"
        ).fetchall()
        recent = conn.execute(
            "SELECT ts, question, jurisdictions FROM query_log ORDER BY id DESC LIMIT 10"
        ).fetchall()

    return {
        "total_queries": total_queries,
        "total_cost": total_cost,
        "cache_hit_rate": (cache_hits / total_queries) if total_queries else 0.0,
        "top_jurisdictions": top_jurisdictions,
        "recent": recent,
    }
