"""Persistence of named reorg scenarios, so an HRBP can save inputs and reload them later instead
of re-uploading Excel and re-typing assumptions every session.

Storage: Postgres if DATABASE_URL is configured (see backend/db.py), local SQLite otherwise —
same durability caveat as query_log.py.
"""
import io
from datetime import datetime, timezone

import pandas as pd

from . import db, reorg_planner

_initialized = False


def _ensure_schema() -> None:
    global _initialized
    if _initialized:
        return
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS scenarios (
            id {db.autoincrement_pk_ddl()},
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            payroll_million REAL,
            months_per_year REAL NOT NULL,
            cap_months REAL NOT NULL,
            employees_json TEXT NOT NULL,
            policy_text TEXT
        )
        """
    )
    _initialized = True


def save_scenario(
    name: str,
    as_of_date,
    payroll_million: float | None,
    months_per_year: float,
    cap_months: float,
    employees_df,
    policy_text: str = "",
) -> None:
    _ensure_schema()
    db.execute(
        """
        INSERT INTO scenarios (name, created_at, as_of_date, payroll_million, months_per_year,
            cap_months, employees_json, policy_text)
        VALUES (:name, :created_at, :as_of_date, :payroll_million, :months_per_year,
            :cap_months, :employees_json, :policy_text)
        ON CONFLICT (name) DO UPDATE SET
            created_at = excluded.created_at,
            as_of_date = excluded.as_of_date,
            payroll_million = excluded.payroll_million,
            months_per_year = excluded.months_per_year,
            cap_months = excluded.cap_months,
            employees_json = excluded.employees_json,
            policy_text = excluded.policy_text
        """,
        {
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "as_of_date": str(as_of_date),
            "payroll_million": payroll_million,
            "months_per_year": months_per_year,
            "cap_months": cap_months,
            "employees_json": employees_df.to_json(orient="records", date_format="iso"),
            "policy_text": policy_text,
        },
    )


def list_scenarios() -> list[str]:
    _ensure_schema()
    rows = db.fetch_all("SELECT name FROM scenarios ORDER BY created_at DESC")
    return [r["name"] for r in rows]


def load_scenario(name: str) -> dict | None:
    _ensure_schema()
    return db.fetch_one("SELECT * FROM scenarios WHERE name = :name", {"name": name})


def delete_scenario(name: str) -> None:
    _ensure_schema()
    db.execute("DELETE FROM scenarios WHERE name = :name", {"name": name})


def compute_summary(name: str) -> pd.Series | None:
    """Recompute a saved scenario's cost summary from its stored assumptions.

    Note: this does NOT re-apply a custom company-policy formula (that would require re-running
    the one-time LLM extraction) — comparison is on statutory/low/moderate/high figures only, so
    it stays instant and free.
    """
    loaded = load_scenario(name)
    if loaded is None:
        return None
    employees_df = pd.read_json(io.StringIO(loaded["employees_json"]), orient="records")
    employees_df["hire_date"] = pd.to_datetime(employees_df["hire_date"])
    result_df = reorg_planner.compute_scenarios(
        employees_df,
        datetime.fromisoformat(loaded["as_of_date"]).date(),
        loaded["payroll_million"],
        loaded["months_per_year"],
        loaded["cap_months"],
        custom_policy=None,
    )
    summary_df = reorg_planner.summarize(result_df)
    return summary_df["Total ($)"]
