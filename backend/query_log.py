"""SQLite log of every question asked, for cost tracking, usage analytics, and audit purposes.

Every answer (Q&A, calculator, or reorg run) is logged with a full snapshot of the answer text,
sources cited, and model version used — so if a number from this tool is ever referenced in an
actual employment decision, there's a durable record of exactly what was shown and why.

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
    cost_usd REAL NOT NULL DEFAULT 0,
    model TEXT,
    answer_snapshot TEXT,
    sources_snapshot TEXT
);
"""


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(SCHEMA)
        _ensure_columns(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(conn) -> None:
    """Add audit columns for databases created before they existed."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(query_log)")}
    for col in ("model", "answer_snapshot", "sources_snapshot"):
        if col not in existing:
            conn.execute(f"ALTER TABLE query_log ADD COLUMN {col} TEXT")


def log_query(
    question: str,
    jurisdictions: list[str],
    used_web_search: bool,
    input_tokens: int,
    output_tokens: int,
    num_searches: int,
    cost_usd: float,
    model: str = "",
    answer_snapshot: str = "",
    sources_snapshot: str = "",
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO query_log (ts, question, jurisdictions, used_web_search, "
            "input_tokens, output_tokens, num_searches, cost_usd, model, answer_snapshot, "
            "sources_snapshot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                question,
                ",".join(jurisdictions),
                int(used_web_search),
                input_tokens,
                output_tokens,
                num_searches,
                cost_usd,
                model,
                answer_snapshot,
                sources_snapshot,
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


def audit_trail(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, ts, question, jurisdictions, used_web_search, model, cost_usd, "
            "answer_snapshot, sources_snapshot FROM query_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
