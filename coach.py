"""
coach.py — Claude API integration with full data context injection
"""

import os
import json
from datetime import date, timedelta
import anthropic
import database as db

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are a personal fitness coach embedded in a training app. You know this athlete well:

ATHLETE PROFILE:
- Age: 38 (turning 39 soon), male, 6'3", ~195 lbs (goal: gradual recomp toward ~183)
- Location: Burlington, VT — cold winters, access to XC skiing, indoor bike trainer, dumbbells (max 25 lbs), yoga mat
- Background: Serious cyclist 2018–2023, ultra-endurance bikepacking races, trained up to 20hrs/week using HR zones. Still rides. Also runs (standard 5-mile jog at 10 min/mile). Yoga practice since 2014.
- Health: Resting HR in the 50s (good aerobic base). BP 120s/80s (borderline — Zone 2 cardio helps). No current injuries.
- Schedule: Kid in daycare 8am–5:30pm weekdays (4pm Thu/Fri). Works remote, flexible until 11am. Workouts in the 8–11am window on weekdays. Weekends: shared childcare, can carve out a couple hours.
- Goals: 1) Feel good, strong, alert  2) Prevent injury (esp. back) while chasing toddler  3) Longevity  4) Sleep well  5) Look good
- Commitment: 3 structured sessions/week as baseline

CURRENT PLAN STRUCTURE:
- Tuesday: Full-body strength (posterior chain focus, dumbbells)
- Wednesday: Zone 2 cardio (trainer / XC ski / run, 45–60 min, HR 130–145)
- Friday: 40-min full-body vinyasa yoga
- Saturday: Longer endurance or adventure (60–90 min, enjoyable)
- Mon/Thu/Sun: Rest or light mobility

YOUR ROLE:
- Answer questions about training, recovery, form, nutrition, and adaptation
- Adapt the weekly plan when sessions are missed, when the athlete feels off, or when big events happen
- Generate new weekly plans when asked, always as structured JSON
- Be direct and specific — this person knows training well from cycling
- Reference their actual logged data when it's provided in context
- Keep responses concise — bullet points over paragraphs when listing things

TONE: Knowledgeable, direct, warm. Like a good coach who respects the athlete's intelligence.

When generating a weekly plan, always return valid JSON in this exact format:
{
  "week_start": "YYYY-MM-DD",
  "days": [
    {
      "day": "Monday",
      "type": "Rest",
      "tag": "Active Recovery",
      "title": "...",
      "duration": "...",
      "window": "...",
      "description": "...",
      "exercises": [{"name": "...", "sets": "..."}],
      "notes": "..."
    }
  ],
  "weekly_focus": "...",
  "coach_notes": "..."
}
"""


def build_context(week_start: str = None) -> str:
    """Build a data context string to inject into every conversation."""
    today = date.today().isoformat()
    if not week_start:
        # Find most recent Monday
        d = date.today()
        week_start = (d - timedelta(days=d.weekday())).isoformat()

    lines = [f"TODAY: {today}", f"CURRENT WEEK START: {week_start}", ""]

    # Recent logs
    logs = db.get_recent_logs(4)
    if logs:
        lines.append("RECENT WORKOUT LOGS (last 4 weeks):")
        for l in logs[:20]:
            status = "✓ completed" if l["completed"] else "✗ skipped"
            rpe = f" | RPE {l['rpe']}/10" if l["rpe"] else ""
            dur = f" | {l['duration_minutes']} min" if l["duration_minutes"] else ""
            note = f" | \"{l['notes']}\"" if l["notes"] else ""
            lines.append(f"  {l['log_date']} {l['day_label']}: {l['session_title']} — {status}{rpe}{dur}{note}")
        lines.append("")

    # This week's logs
    this_week_logs = db.get_logs_for_week(week_start)
    if this_week_logs:
        lines.append("THIS WEEK SO FAR:")
        for l in this_week_logs:
            status = "✓" if l["completed"] else "✗"
            rpe = f" RPE {l['rpe']}" if l["rpe"] else ""
            lines.append(f"  {status} {l['day_label']}: {l['session_title']}{rpe}")
        lines.append("")

    # Recent metrics
    metrics = db.get_metrics(30)
    if metrics:
        lines.append("RECENT METRICS (last 30 days):")
        for m in metrics[:10]:
            parts = [m["metric_date"]]
            if m["weight_lbs"]:
                parts.append(f"weight: {m['weight_lbs']} lbs")
            if m["resting_hr"]:
                parts.append(f"RHR: {m['resting_hr']} bpm")
            if m["sleep_hours"]:
                parts.append(f"sleep: {m['sleep_hours']}h")
            lines.append("  " + " | ".join(parts))
        lines.append("")

    # Stats
    streak = db.get_streak()
    rate = db.get_completion_rate(8)
    lines.append(f"CONSISTENCY: {streak} week streak | {rate:.0%} completion rate (8 weeks)")

    return "\n".join(lines)


def chat(user_message: str, week_start: str = None) -> str:
    """Send a message to Claude with full data context. Persists history."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ No API key found. Add ANTHROPIC_API_KEY to your .env file."

    client = anthropic.Anthropic(api_key=api_key)

    # Build context-enriched system prompt
    context = build_context(week_start)
    full_system = SYSTEM_PROMPT + "\n\n--- LIVE DATA CONTEXT ---\n" + context

    # Save user message
    db.save_message("user", user_message)

    # Get history
    history = db.get_chat_history(limit=30)

    # Build messages list
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=full_system,
        messages=messages,
    )

    reply = response.content[0].text
    db.save_message("assistant", reply)
    return reply


def generate_weekly_plan(week_start: str, notes: str = "") -> dict:
    """Ask Claude to generate a full weekly plan as JSON."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    context = build_context(week_start)
    full_system = SYSTEM_PROMPT + "\n\n--- LIVE DATA CONTEXT ---\n" + context

    user_msg = f"""Generate a weekly training plan for the week starting {week_start}.

Additional notes: {notes if notes else 'None — use your best judgment based on recent data.'}

Return ONLY valid JSON in the format specified in your instructions. No preamble, no markdown fences."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=full_system,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        plan = json.loads(raw)
        db.save_weekly_plan(week_start, plan, notes)
        return plan
    except json.JSONDecodeError:
        return {"error": "Failed to parse plan JSON", "raw": raw}
