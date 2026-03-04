"""
database.py — all SQLite read/write for the fitness app
"""

import sqlite3
import json
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "fitness.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS workout_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            day_label TEXT NOT NULL,
            session_title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            rpe INTEGER,
            duration_minutes INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date TEXT NOT NULL,
            weight_lbs REAL,
            resting_hr INTEGER,
            sleep_hours REAL,
            bp_systolic INTEGER,
            bp_diastolic INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


# ── Weekly Plans ──────────────────────────────────────────────────────────────

def save_weekly_plan(week_start: str, plan: dict, notes: str = ""):
    with get_conn() as conn:
        conn.execute("DELETE FROM weekly_plans WHERE week_start = ?", (week_start,))
        conn.execute(
            "INSERT INTO weekly_plans (week_start, plan_json, generated_at, notes) VALUES (?, ?, ?, ?)",
            (week_start, json.dumps(plan), datetime.now().isoformat(), notes),
        )


def get_weekly_plan(week_start: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM weekly_plans WHERE week_start = ? ORDER BY generated_at DESC LIMIT 1",
            (week_start,),
        ).fetchone()
    if row:
        return {**dict(row), "plan": json.loads(row["plan_json"])}
    return None


def get_all_plans():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM weekly_plans ORDER BY week_start DESC").fetchall()
    return [dict(r) for r in rows]


# ── Workout Logs ──────────────────────────────────────────────────────────────

def log_workout(log_date, day_label, session_title, completed,
                rpe=None, duration_minutes=None, notes=""):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM workout_logs WHERE log_date = ? AND day_label = ?",
            (log_date, day_label),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE workout_logs SET completed=?, rpe=?, duration_minutes=?,
                   notes=?, session_title=?, created_at=? WHERE log_date=? AND day_label=?""",
                (int(completed), rpe, duration_minutes, notes, session_title,
                 datetime.now().isoformat(), log_date, day_label),
            )
        else:
            conn.execute(
                """INSERT INTO workout_logs
                   (log_date, day_label, session_title, completed, rpe, duration_minutes, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_date, day_label, session_title, int(completed),
                 rpe, duration_minutes, notes, datetime.now().isoformat()),
            )


def get_logs_for_week(week_start: str):
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM workout_logs WHERE log_date BETWEEN ? AND ? ORDER BY log_date",
            (week_start, week_end),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_logs(n_weeks: int = 4):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM workout_logs ORDER BY log_date DESC LIMIT ?",
            (n_weeks * 7,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_logs():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM workout_logs ORDER BY log_date DESC").fetchall()
    return [dict(r) for r in rows]


# ── Metrics ───────────────────────────────────────────────────────────────────

def log_metric(metric_date, weight_lbs=None, resting_hr=None, sleep_hours=None,
               bp_systolic=None, bp_diastolic=None, notes=""):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM metrics WHERE metric_date = ?", (metric_date,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE metrics SET weight_lbs=?, resting_hr=?, sleep_hours=?,
                   bp_systolic=?, bp_diastolic=?, notes=?, created_at=? WHERE metric_date=?""",
                (weight_lbs, resting_hr, sleep_hours, bp_systolic, bp_diastolic,
                 notes, datetime.now().isoformat(), metric_date),
            )
        else:
            conn.execute(
                """INSERT INTO metrics (metric_date, weight_lbs, resting_hr, sleep_hours,
                   bp_systolic, bp_diastolic, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (metric_date, weight_lbs, resting_hr, sleep_hours, bp_systolic,
                 bp_diastolic, notes, datetime.now().isoformat()),
            )


def get_metrics(n_days: int = 90):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics ORDER BY metric_date DESC LIMIT ?", (n_days,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Chat History ──────────────────────────────────────────────────────────────

def save_message(role: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_history (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, datetime.now().isoformat()),
        )


def get_chat_history(limit: int = 40):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))


def clear_chat_history():
    with get_conn() as conn:
        conn.execute("DELETE FROM chat_history")


# ── Summary helpers ───────────────────────────────────────────────────────────

def get_streak():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT strftime('%Y-W%W', log_date) as week, COUNT(*) as count
               FROM workout_logs WHERE completed=1
               GROUP BY week ORDER BY week DESC"""
        ).fetchall()
    streak = 0
    for row in rows:
        if row["count"] >= 2:
            streak += 1
        else:
            break
    return streak


def get_completion_rate(n_weeks: int = 8):
    logs = get_recent_logs(n_weeks)
    if not logs:
        return 0.0
    completed = sum(1 for l in logs if l["completed"])
    return completed / len(logs)
