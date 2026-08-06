"""Local persistence of named reorg scenarios, so an HRBP can save inputs and reload them later
instead of re-uploading Excel and re-typing assumptions every session.

Note: same ephemeral-filesystem caveat as query_log — persists for the life of a running instance,
not across Streamlit Cloud redeploys.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "scenarios.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    payroll_million REAL,
    months_per_year REAL NOT NULL,
    cap_months REAL NOT NULL,
    employees_json TEXT NOT NULL,
    policy_text TEXT
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


def save_scenario(
    name: str,
    as_of_date,
    payroll_million: float | None,
    months_per_year: float,
    cap_months: float,
    employees_df,
    policy_text: str = "",
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO scenarios (name, created_at, as_of_date, payroll_million, months_per_year, "
            "cap_months, employees_json, policy_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET created_at=excluded.created_at, as_of_date=excluded.as_of_date, "
            "payroll_million=excluded.payroll_million, months_per_year=excluded.months_per_year, "
            "cap_months=excluded.cap_months, employees_json=excluded.employees_json, "
            "policy_text=excluded.policy_text",
            (
                name,
                datetime.now(timezone.utc).isoformat(),
                str(as_of_date),
                payroll_million,
                months_per_year,
                cap_months,
                employees_df.to_json(orient="records", date_format="iso"),
                policy_text,
            ),
        )


def list_scenarios() -> list[str]:
    with _conn() as conn:
        rows = conn.execute("SELECT name FROM scenarios ORDER BY created_at DESC").fetchall()
    return [r[0] for r in rows]


def load_scenario(name: str) -> dict | None:
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scenarios WHERE name = ?", (name,)).fetchone()
    if row is None:
        return None
    return dict(row)


def delete_scenario(name: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM scenarios WHERE name = ?", (name,))
