"""
app.py — main Streamlit fitness tracking app
"""

import os
import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()
import database as db
import coach

# ── Init ──────────────────────────────────────────────────────────────────────

db.init_db()

st.set_page_config(
    page_title="Fitness Tracker",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_week_start(offset: int = 0) -> str:
    """Get ISO date string for Monday of current week + offset weeks."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return (monday + timedelta(weeks=offset)).isoformat()


def week_label(week_start: str) -> str:
    d = date.fromisoformat(week_start)
    end = d + timedelta(days=6)
    return f"{d.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"


TAG_COLORS = {
    "Strength":        "#FFD3B6",
    "Cardio":          "#A8E6CF",
    "Mobility":        "#C9B8FF",
    "Active Recovery": "#B8E0FF",
}

def tag_badge(tag: str) -> str:
    color = TAG_COLORS.get(tag, "#eee")
    return f'<span style="background:{color};padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600">{tag}</span>'


DEFAULT_PLAN = {
    "weekly_focus": "Base building — strength + Zone 2 + mobility",
    "coach_notes": "Generate your first week's plan using the Coach tab.",
    "days": [
        {"day": "Monday",    "type": "Rest",       "tag": "Active Recovery", "title": "Mobility Reset",
         "duration": "10–20 min", "window": "Optional evening",
         "description": "Short yoga flow or bodyweight mobility. Hip circles, cat-cow, thoracic rotation.",
         "exercises": [{"name": "Cat-cow / thoracic rotation", "sets": "2 min"},
                       {"name": "Hip flexor stretch", "sets": "90 sec/side"},
                       {"name": "World's greatest stretch", "sets": "5 reps/side"}],
         "notes": "Can do this on the living room floor with the kid around."},
        {"day": "Tuesday",   "type": "Workout 1",  "tag": "Strength",        "title": "Full-Body Strength",
         "duration": "40–50 min", "window": "8–10am",
         "description": "Posterior chain focus. Builds the foundation for chasing a toddler without breaking down.",
         "exercises": [{"name": "Romanian deadlift (DBs)", "sets": "3×10–12"},
                       {"name": "Single-leg glute bridge", "sets": "3×12/side"},
                       {"name": "Dumbbell row", "sets": "3×10"},
                       {"name": "Goblet squat (25 lb)", "sets": "3×12"},
                       {"name": "Overhead press", "sets": "3×10"},
                       {"name": "Dead bug", "sets": "3×8/side"}],
         "notes": "Rest 60–90 sec between sets."},
        {"day": "Wednesday", "type": "Workout 2",  "tag": "Cardio",          "title": "Zone 2 Cardio",
         "duration": "45–60 min", "window": "8–10am",
         "description": "Conversational pace, HR 130–145 bpm. Trainer / XC ski / run. Your aerobic base maintenance session.",
         "exercises": [{"name": "Trainer ride OR XC ski OR jog", "sets": "45–60 min"},
                       {"name": "Target HR: 130–145 bpm", "sets": "Zone 2"}],
         "notes": "Rotate modality by season and weather."},
        {"day": "Thursday",  "type": "Rest",       "tag": "Active Recovery", "title": "Full Rest",
         "duration": "—", "window": "Passive",
         "description": "Real rest. Adaptation from Tue/Wed happens today.",
         "exercises": [],
         "notes": "A walk counts. A nap counts more."},
        {"day": "Friday",    "type": "Workout 3",  "tag": "Mobility",        "title": "Full-Body Yoga",
         "duration": "40 min", "window": "8–10am",
         "description": "40-min vinyasa with your preferred internet yogi. Flexibility, balance, breath.",
         "exercises": [{"name": "40-min vinyasa flow", "sets": "1 class"},
                       {"name": "Focus: hip openers + twists + backbends", "sets": "—"}],
         "notes": "Even a 20-min class is worth doing if time is short."},
        {"day": "Saturday",  "type": "Bonus",      "tag": "Cardio",          "title": "Longer Endurance",
         "duration": "60–90 min", "window": "Morning",
         "description": "Use weekend childcare window. XC ski, longer ride, or solo run. Enjoy it.",
         "exercises": [{"name": "XC ski OR trainer OR longer run", "sets": "60–90 min easy-moderate"}],
         "notes": "Pick one. No performance pressure."},
        {"day": "Sunday",    "type": "Rest",       "tag": "Active Recovery", "title": "Family Day",
         "duration": "—", "window": "Passive",
         "description": "Full rest or unstructured family movement — snowshoe, walk, sledding.",
         "exercises": [],
         "notes": "Protect this. The plan is sustainable because Sunday is always off."},
    ]
}

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🏔️ Fitness Tracker")
    st.markdown("---")
    streak = db.get_streak()
    rate = db.get_completion_rate(8)
    st.metric("Streak", f"{streak} weeks 🔥")
    st.metric("8-week completion", f"{rate:.0%}")
    st.markdown("---")
    st.markdown("**Quick log today**")
    quick_note = st.text_input("Note", placeholder="Felt great, knee a bit stiff…")
    quick_rpe = st.slider("RPE", 1, 10, 7)
    if st.button("Log today's session"):
        today_str = date.today().isoformat()
        day_name = date.today().strftime("%A")
        db.log_workout(today_str, day_name, "Today's session", True, quick_rpe, notes=quick_note)
        st.success("Logged!")
        st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["📅  This Week", "📝  Log", "📈  Trends", "🤖  Coach"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — THIS WEEK
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.markdown("## This Week's Plan")
    with col_right:
        week_offset = st.number_input("Week offset", min_value=-8, max_value=4, value=0, step=1,
                                      label_visibility="collapsed",
                                      help="0 = this week, -1 = last week, +1 = next week")

    week_start = get_week_start(week_offset)
    st.caption(f"📆 {week_label(week_start)}")

    # Load plan
    saved = db.get_weekly_plan(week_start)
    plan = saved["plan"] if saved else DEFAULT_PLAN
    this_week_logs = {l["day_label"]: l for l in db.get_logs_for_week(week_start)}

    if saved:
        focus = plan.get("weekly_focus", "")
        coach_notes = plan.get("coach_notes", "")
        if focus:
            st.info(f"**Weekly focus:** {focus}")
        if coach_notes:
            with st.expander("💬 Coach notes for this week"):
                st.markdown(coach_notes)
    else:
        st.warning("No plan generated yet for this week. Head to the **Coach** tab and ask it to generate one, or the default template is shown below.")

    st.markdown("---")

    days = plan.get("days", DEFAULT_PLAN["days"])
    for day_data in days:
        day_name = day_data["day"]
        tag = day_data.get("tag", "")
        title = day_data.get("title", "")
        duration = day_data.get("duration", "—")
        window = day_data.get("window", "")
        description = day_data.get("description", "")
        exercises = day_data.get("exercises", [])
        notes = day_data.get("notes", "")

        log = this_week_logs.get(day_name)
        is_completed = log and log["completed"]
        is_rest = tag == "Active Recovery"

        with st.expander(
            f"{'✅' if is_completed else ('😴' if is_rest else '⬜')}  **{day_name}** — {title}  ·  _{duration}_",
            expanded=(day_name == date.today().strftime("%A"))
        ):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(tag_badge(tag), unsafe_allow_html=True)
                st.markdown(f"**{description}**")
                if exercises:
                    st.markdown("**Exercises:**")
                    for ex in exercises:
                        st.markdown(f"- {ex['name']} — `{ex['sets']}`")
                if notes:
                    st.caption(f"💡 {notes}")

            with col2:
                if not is_rest:
                    st.markdown("**Log this session:**")
                    completed_cb = st.checkbox("Completed", value=bool(is_completed),
                                               key=f"done_{day_name}")
                    rpe_val = st.slider("RPE", 1, 10,
                                        value=log["rpe"] if (log and log["rpe"]) else 7,
                                        key=f"rpe_{day_name}")
                    dur_val = st.number_input("Minutes", 0, 180,
                                              value=log["duration_minutes"] if (log and log["duration_minutes"]) else 45,
                                              key=f"dur_{day_name}")
                    note_val = st.text_area("Notes", value=log["notes"] if (log and log["notes"]) else "",
                                            key=f"note_{day_name}", height=68)
                    if st.button("Save", key=f"save_{day_name}"):
                        # Find the log_date for this day in the current week
                        day_index = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].index(day_name)
                        log_date = (date.fromisoformat(week_start) + timedelta(days=day_index)).isoformat()
                        db.log_workout(log_date, day_name, title, completed_cb,
                                       rpe_val, dur_val, note_val)
                        st.success("Saved!")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LOG
# ═══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.markdown("## Log a Session / Metrics")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏋️ Workout")
        log_date = st.date_input("Date", value=date.today(), key="log_date")
        log_day = log_date.strftime("%A")
        st.caption(f"Day: {log_day}")
        session_title = st.text_input("Session name", placeholder="Zone 2 ride, Yoga, Strength…")
        completed = st.checkbox("Completed", value=True)
        rpe = st.slider("RPE (effort 1–10)", 1, 10, 7)
        duration = st.number_input("Duration (minutes)", 0, 240, 45)
        session_notes = st.text_area("Notes", placeholder="How did it feel? Anything notable…", height=100)
        if st.button("💾 Save workout", type="primary"):
            if session_title:
                db.log_workout(log_date.isoformat(), log_day, session_title,
                               completed, rpe, duration, session_notes)
                st.success(f"Logged: {session_title} on {log_date}")
                st.rerun()
            else:
                st.error("Add a session name.")

    with col2:
        st.markdown("### 📊 Daily Metrics")
        metric_date = st.date_input("Date", value=date.today(), key="metric_date")
        weight = st.number_input("Weight (lbs)", 0.0, 400.0, 195.0, step=0.5)
        rhr = st.number_input("Resting HR (bpm)", 0, 200, 55)
        sleep_h = st.number_input("Sleep (hours)", 0.0, 24.0, 7.5, step=0.25)
        st.markdown("**Blood Pressure**")
        bp_col1, bp_col2 = st.columns(2)
        with bp_col1:
            bp_sys = st.number_input("Systolic", 0, 250, 120, help="Top number, e.g. 122")
        with bp_col2:
            bp_dia = st.number_input("Diastolic", 0, 150, 80, help="Bottom number, e.g. 82")
        metric_notes = st.text_input("Notes", placeholder="Felt rested, slight headache…")
        if st.button("💾 Save metrics", type="primary"):
            db.log_metric(metric_date.isoformat(), weight or None,
                          rhr or None, sleep_h or None,
                          bp_sys or None, bp_dia or None, metric_notes)
            st.success(f"Metrics saved for {metric_date}")
            st.rerun()

    st.markdown("---")
    st.markdown("### Recent Logs")
    logs = db.get_all_logs()
    if logs:
        df = pd.DataFrame(logs)[["log_date", "day_label", "session_title", "completed", "rpe", "duration_minutes", "notes"]]
        df.columns = ["Date", "Day", "Session", "Done", "RPE", "Min", "Notes"]
        df["Done"] = df["Done"].map({1: "✅", 0: "✗"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No workouts logged yet.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRENDS
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.markdown("## Trends")

    metrics = db.get_metrics(90)
    all_logs = db.get_all_logs()

    if not metrics and not all_logs:
        st.info("Start logging workouts and metrics to see trends here.")
    else:
        if metrics:
            df_m = pd.DataFrame(metrics)
            df_m["metric_date"] = pd.to_datetime(df_m["metric_date"])
            df_m = df_m.sort_values("metric_date")

            col1, col2 = st.columns(2)

            with col1:
                if df_m["weight_lbs"].notna().any():
                    fig = px.line(df_m.dropna(subset=["weight_lbs"]),
                                  x="metric_date", y="weight_lbs",
                                  title="Weight (lbs)",
                                  markers=True)
                    fig.update_layout(height=280, margin=dict(t=40, b=20))
                    fig.add_hline(y=183, line_dash="dash", line_color="green",
                                  annotation_text="Goal: 183")
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                if df_m["resting_hr"].notna().any():
                    fig2 = px.line(df_m.dropna(subset=["resting_hr"]),
                                   x="metric_date", y="resting_hr",
                                   title="Resting HR (bpm)",
                                   markers=True, color_discrete_sequence=["#e07b54"])
                    fig2.update_layout(height=280, margin=dict(t=40, b=20))
                    st.plotly_chart(fig2, use_container_width=True)
                if df_m["bp_systolic"].notna().any():
                                fig_bp = go.Figure()
                                fig_bp.add_trace(go.Scatter(
                                    x=df_m.dropna(subset=["bp_systolic"])["metric_date"],
                                    y=df_m.dropna(subset=["bp_systolic"])["bp_systolic"],
                                    name="Systolic", mode="lines+markers", line=dict(color="#e07b54")
                                ))
                                fig_bp.add_trace(go.Scatter(
                                    x=df_m.dropna(subset=["bp_diastolic"])["metric_date"],
                                    y=df_m.dropna(subset=["bp_diastolic"])["bp_diastolic"],
                                    name="Diastolic", mode="lines+markers", line=dict(color="#7ab8f5")
                                ))
                                fig_bp.add_hline(y=120, line_dash="dash", line_color="#e07b54",
                                                 annotation_text="120 target")
                                fig_bp.add_hline(y=80, line_dash="dash", line_color="#7ab8f5",
                                                 annotation_text="80 target")
                                fig_bp.update_layout(title="Blood Pressure (mmHg)", height=280,
                                                     margin=dict(t=40, b=20))
                                st.plotly_chart(fig_bp, use_container_width=True)
                    
            if df_m["sleep_hours"].notna().any():
                fig3 = px.bar(df_m.dropna(subset=["sleep_hours"]),
                              x="metric_date", y="sleep_hours",
                              title="Sleep (hours)", color_discrete_sequence=["#7a8fff"])
                fig3.add_hline(y=7, line_dash="dash", line_color="gray",
                               annotation_text="7h target")
                fig3.update_layout(height=240, margin=dict(t=40, b=20))
                st.plotly_chart(fig3, use_container_width=True)

        if all_logs:
            st.markdown("### Weekly Consistency")
            df_l = pd.DataFrame(all_logs)
            df_l["log_date"] = pd.to_datetime(df_l["log_date"])
            df_l["week"] = df_l["log_date"].dt.to_period("W").dt.start_time
            weekly = df_l[df_l["completed"] == 1].groupby("week").size().reset_index(name="sessions")
            fig4 = px.bar(weekly, x="week", y="sessions",
                          title="Completed sessions per week",
                          color_discrete_sequence=["#C8F04A"])
            fig4.add_hline(y=3, line_dash="dash", line_color="gray",
                           annotation_text="3-session goal")
            fig4.update_layout(height=280, margin=dict(t=40, b=20),
                               plot_bgcolor="#111", paper_bgcolor="#111",
                               font_color="#ccc")
            st.plotly_chart(fig4, use_container_width=True)

            # RPE over time
            df_rpe = df_l[df_l["rpe"].notna()]
            if not df_rpe.empty:
                fig5 = px.scatter(df_rpe, x="log_date", y="rpe",
                                  color="session_title", title="RPE over time",
                                  hover_data=["notes"])
                fig5.update_layout(height=280, margin=dict(t=40, b=20))
                st.plotly_chart(fig5, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — COACH
# ═══════════════════════════════════════════════════════════════════════════════

with tab4:
    st.markdown("## 🤖 Coach")
    st.caption("Your personal Claude coach — knows your full training history. Ask anything.")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("No API key found. Add `ANTHROPIC_API_KEY=your_key` to your `.env` file and restart the app.")
        st.code("ANTHROPIC_API_KEY=sk-ant-...")
        st.stop()

    # Generate plan button
    with st.expander("⚡ Generate / Regenerate Weekly Plan"):
        gen_week = st.date_input("Week starting (Monday)", value=date.today() - timedelta(days=date.today().weekday()))
        gen_notes = st.text_area("Any notes for this week?",
                                 placeholder="Missed Tuesday, big ski day Saturday planned, feeling tired…",
                                 height=80)
        if st.button("🗓️ Generate plan for this week", type="primary"):
            with st.spinner("Claude is building your plan…"):
                result = coach.generate_weekly_plan(gen_week.isoformat(), gen_notes)
            if "error" in result:
                st.error(f"Error: {result['error']}")
                st.code(result.get("raw", ""))
            else:
                st.success("Plan generated and saved! Switch to the 'This Week' tab.")

    st.markdown("---")

    # Chat interface
    history = db.get_chat_history(limit=50)

    chat_container = st.container(height=480)
    with chat_container:
        if not history:
            st.markdown(
                '<div style="color:#888;text-align:center;padding:40px">Start a conversation — ask about your plan, how to adapt it, recovery, nutrition, anything.</div>',
                unsafe_allow_html=True
            )
        for msg in history:
            with st.chat_message(msg["role"], avatar="🏔️" if msg["role"] == "assistant" else "🧑"):
                st.markdown(msg["content"])

    user_input = st.chat_input("Ask your coach…")
    if user_input:
        with st.spinner("Thinking…"):
            reply = coach.chat(user_input, get_week_start())
        st.rerun()

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🗑️ Clear chat history"):
            db.clear_chat_history()
            st.rerun()

    # Quick prompts
    st.markdown("**Quick prompts:**")
    quick_prompts = [
        "Generate next week's plan",
        "I skipped Wednesday — adapt the rest of the week",
        "I have a big ski day Saturday, adjust accordingly",
        "How is my consistency trending?",
        "What should I focus on this month?",
    ]
    cols = st.columns(len(quick_prompts))
    for i, (col, prompt) in enumerate(zip(cols, quick_prompts)):
        with col:
            if st.button(prompt, key=f"qp_{i}", use_container_width=True):
                with st.spinner("Thinking…"):
                    coach.chat(prompt, get_week_start())
                st.rerun()
