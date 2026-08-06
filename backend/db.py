"""Shared database engine — Postgres when a DATABASE_URL secret/env var is configured, local
SQLite file otherwise. Both dialects are addressed with the same SQL (via SQLAlchemy's text()
with named binds), so query_log.py works unmodified against either backend.

This exists because SQLite files on Streamlit Community Cloud are ephemeral and reset on every
redeploy — pointing DATABASE_URL at a hosted Postgres instance (Supabase, Neon, Railway, etc.)
makes the audit trail and query log durable across deploys. Until that secret is set, the app
works exactly as before with a local SQLite file.
"""
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _database_url() -> str:
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", None)
        if url:
            return url
    except Exception:
        pass
    import os
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATA_DIR / 'app.sqlite3'}"


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    url = _database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return sa.create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


def autoincrement_pk_ddl() -> str:
    """Cross-dialect DDL fragment for an auto-incrementing integer primary key column."""
    return "SERIAL PRIMARY KEY" if is_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


def execute(sql: str, params: dict | None = None) -> None:
    with get_engine().begin() as conn:
        conn.execute(sa.text(sql), params or {})


def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    with get_engine().begin() as conn:
        result = conn.execute(sa.text(sql), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one(sql: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
