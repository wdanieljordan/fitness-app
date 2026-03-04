# 🏔️ Fitness Tracker

Personal fitness tracking app with embedded Claude coach.

## Setup (Mac)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API key
cp .env.example .env
# Open .env and paste your key from https://console.anthropic.com

# 3. Run
streamlit run app.py
```

App opens at http://localhost:8501

## Deploy to Streamlit Community Cloud (free)

1. Push this folder to a GitHub repo (can be private)
2. Go to https://share.streamlit.io
3. Connect your GitHub → select the repo → set `app.py` as main file
4. In Settings → Secrets, add:
   ```
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   ```
5. Deploy — you get a public URL that works on your phone

## Features

- **This Week** — view your current plan, log sessions with RPE + notes
- **Log** — manual workout and metrics entry (weight, resting HR, sleep)
- **Trends** — charts for consistency, weight, HR, sleep, RPE over time
- **Coach** — Claude chat with full data context; generates and adapts weekly plans

## File Structure

```
fitness-app/
├── app.py          # Streamlit UI (4 tabs)
├── coach.py        # Claude API + context injection
├── database.py     # SQLite read/write
├── requirements.txt
├── .env.example
└── README.md
```
