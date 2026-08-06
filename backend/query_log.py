"""Log of every question asked, for cost tracking, usage analytics, and audit purposes.

Every answer (Q&A, calculator, or reorg run) is logged with a full snapshot of the answer text,
sources cited, and model version used — so if a number from this tool is ever referenced in an
actual employment decision, there's a durable record of exactly what was shown and why.

Storage: Postgres if DATABASE_URL is configured (see backend/db.py), local SQLite otherwise. The
SQLite fallback is ephemeral on Streamlit Community Cloud (resets on redeploy) — set DATABASE_URL
to a hosted Postgres instance for a durable audit trail across deploys.
"""
from datetime import datetime, timezone

from . import db

_initialized = False


def _ensure_schema() -> None:
    global _initialized
    if _initialized:
        return
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS query_log (
            id {db.autoincrement_pk_ddl()},
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
        )
        """
    )
    _initialized = True


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
    _ensure_schema()
    db.execute(
        """
        INSERT INTO query_log (ts, question, jurisdictions, used_web_search, input_tokens,
            output_tokens, num_searches, cost_usd, model, answer_snapshot, sources_snapshot)
        VALUES (:ts, :question, :jurisdictions, :used_web_search, :input_tokens, :output_tokens,
            :num_searches, :cost_usd, :model, :answer_snapshot, :sources_snapshot)
        """,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "jurisdictions": ",".join(jurisdictions),
            "used_web_search": int(used_web_search),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "num_searches": num_searches,
            "cost_usd": cost_usd,
            "model": model,
            "answer_snapshot": answer_snapshot,
            "sources_snapshot": sources_snapshot,
        },
    )


def summary() -> dict:
    _ensure_schema()
    total_queries = db.fetch_one("SELECT COUNT(*) AS c FROM query_log")["c"]
    total_cost = db.fetch_one("SELECT COALESCE(SUM(cost_usd), 0) AS c FROM query_log")["c"]
    cache_hits = db.fetch_one(
        "SELECT COUNT(*) AS c FROM query_log WHERE used_web_search = 0"
    )["c"]
    top_jurisdictions = db.fetch_all(
        "SELECT jurisdictions, COUNT(*) AS c FROM query_log "
        "WHERE jurisdictions != '' GROUP BY jurisdictions ORDER BY c DESC LIMIT 8"
    )
    recent = db.fetch_all(
        "SELECT ts, question, jurisdictions FROM query_log ORDER BY id DESC LIMIT 10"
    )

    return {
        "total_queries": total_queries,
        "total_cost": total_cost,
        "cache_hit_rate": (cache_hits / total_queries) if total_queries else 0.0,
        "top_jurisdictions": [(r["jurisdictions"], r["c"]) for r in top_jurisdictions],
        "recent": recent,
    }


def audit_trail(limit: int = 50) -> list[dict]:
    _ensure_schema()
    return db.fetch_all(
        "SELECT id, ts, question, jurisdictions, used_web_search, model, cost_usd, "
        "answer_snapshot, sources_snapshot FROM query_log ORDER BY id DESC LIMIT :limit",
        {"limit": limit},
    )
