"""
database.py — PostgreSQL (Supabase) version
Replaces SQLite. All other files (app.py, coach.py) unchanged.
"""

import json
import os
from datetime import date, datetime, timedelta

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS weekly_plans (
                id SERIAL PRIMARY KEY,
                week_start TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS workout_logs (
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
        conn.commit()


# ── Weekly Plans ──────────────────────────────────────────────────────────────

def save_weekly_plan(week_start: str, plan: dict, notes: str = ""):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM weekly_plans WHERE week_start = %s", (week_start,))
            cur.execute(
                "INSERT INTO weekly_plans (week_start, plan_json, generated_at, notes) VALUES (%s, %s, %s, %s)",
                (week_start, json.dumps(plan), datetime.now().isoformat(), notes),
            )
        conn.commit()


def get_weekly_plan(week_start: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM weekly_plans WHERE week_start = %s ORDER BY generated_at DESC LIMIT 1",
                (week_start,),
            )
            row = cur.fetchone()
    if row:
        d = dict(row)
        d["plan"] = json.loads(d["plan_json"])
        return d
    return None


def get_all_plans():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM weekly_plans ORDER BY week_start DESC")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Workout Logs ──────────────────────────────────────────────────────────────

def log_workout(log_date, day_label, session_title, completed,
                rpe=None, duration_minutes=None, notes=""):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM workout_logs WHERE log_date = %s AND day_label = %s",
                (log_date, day_label),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE workout_logs SET completed=%s, rpe=%s, duration_minutes=%s,
                       notes=%s, session_title=%s, created_at=%s
                       WHERE log_date=%s AND day_label=%s""",
                    (int(completed), rpe, duration_minutes, notes, session_title,
                     datetime.now().isoformat(), log_date, day_label),
                )
            else:
                cur.execute(
                    """INSERT INTO workout_logs
                       (log_date, day_label, session_title, completed, rpe, duration_minutes, notes, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (log_date, day_label, session_title, int(completed),
                     rpe, duration_minutes, notes, datetime.now().isoformat()),
                )
        conn.commit()


def get_logs_for_week(week_start: str):
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM workout_logs WHERE log_date BETWEEN %s AND %s ORDER BY log_date",
                (week_start, week_end),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_recent_logs(n_weeks: int = 4):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM workout_logs ORDER BY log_date DESC LIMIT %s",
                (n_weeks * 7,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_all_logs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM workout_logs ORDER BY log_date DESC")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Metrics ───────────────────────────────────────────────────────────────────

def log_metric(metric_date, weight_lbs=None, resting_hr=None, sleep_hours=None,
               bp_systolic=None, bp_diastolic=None, notes=""):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM metrics WHERE metric_date = %s", (metric_date,)
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE metrics SET weight_lbs=%s, resting_hr=%s, sleep_hours=%s,
                       bp_systolic=%s, bp_diastolic=%s, notes=%s, created_at=%s
                       WHERE metric_date=%s""",
                    (weight_lbs, resting_hr, sleep_hours, bp_systolic, bp_diastolic,
                     notes, datetime.now().isoformat(), metric_date),
                )
            else:
                cur.execute(
                    """INSERT INTO metrics
                       (metric_date, weight_lbs, resting_hr, sleep_hours, bp_systolic, bp_diastolic, notes, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (metric_date, weight_lbs, resting_hr, sleep_hours, bp_systolic,
                     bp_diastolic, notes, datetime.now().isoformat()),
                )
        conn.commit()


def get_metrics(n_days: int = 90):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM metrics ORDER BY metric_date DESC LIMIT %s", (n_days,)
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Chat History ──────────────────────────────────────────────────────────────

def save_message(role: str, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_history (role, content, created_at) VALUES (%s, %s, %s)",
                (role, content, datetime.now().isoformat()),
            )
        conn.commit()


def get_chat_history(limit: int = 40):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM chat_history ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    return list(reversed([dict(r) for r in rows]))


def clear_chat_history():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_history")
        conn.commit()


# ── Summary helpers ───────────────────────────────────────────────────────────

def get_streak():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT to_char(to_date(log_date, 'YYYY-MM-DD'), 'IYYY-IW') as week,
                          COUNT(*) as count
                   FROM workout_logs WHERE completed=1
                   GROUP BY week ORDER BY week DESC"""
            )
            rows = cur.fetchall()
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
