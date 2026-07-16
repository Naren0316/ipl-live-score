# 🏏 ipl-live-score-backend

A real-time IPL score tracker backend — polls a live cricket API, detects **every new ball bowled**, and updates the score automatically. Terminal-first, API-driven, built to later plug into a web frontend.

## Status: Day 7/8 — Deployment-ready

## Features
- Polls live match data on an interval (default: every 5s)
- Detects new balls by diffing overs/runs/wickets against the last poll (not just raw score snapshots)
- Auto-finds a live IPL match, or track a specific match via `MATCH_ID`
- Retry + backoff on flaky network/API responses
- Proper domain models (`Match`, `Innings`, `Ball`) instead of raw dicts
- Ball detection logic is pure and independently unit-tested — no network needed
- Every ball is logged to SQLite — history survives restarts, and the app resumes correctly after a crash
- Event-driven core: the polling loop only publishes `"new_ball"` events; printing, DB saving, and WebSocket broadcasting are independent subscribers
- FastAPI server (`api.py`) serves the API, WebSocket, **and the frontend itself** — one deployed service, one URL
- `frontend/index.html` — LED-style live scoreboard with ball-by-ball feed, auto-reconnect, loads history on connect
- CORS origins and port are environment-configurable for production
- `history.py` CLI to query saved match history

> Note: true single-delivery ball-by-ball commentary is a paid feature on the underlying API. The free tier gives over-level score snapshots, which this backend diffs to detect individual balls where possible (`balls_covered == 1`), and falls back to reporting a combined update when polling missed more than one ball.

## Tech
- Python 3.10+
- [CricketData.org](https://cricketdata.org) (formerly CricAPI) — free tier, ball-by-ball data
- `requests` for HTTP

## Project structure
```
ipl-live-score/
├── config.py               # API key, endpoints, polling, DB path
├── cricket_api.py          # API client — all HTTP/network logic lives here
├── models.py                # Match / Innings / Ball domain models
├── ball_detector.py         # Pure diffing logic — turns state changes into Ball events
├── db.py                     # SQLite persistence — all SQL logic lives here
├── event_bus.py              # Pub/sub — decouples the loop from what reacts to a ball
├── connection_manager.py     # Tracks/broadcasts to connected WebSocket clients
├── api.py                    # FastAPI app — REST endpoints + WebSocket, runs polling in background
├── frontend/
│   └── index.html             # Live scoreboard UI (LED-style score + ball feed)
├── main.py                   # Original terminal-only entry point (still works standalone)
├── history.py                # CLI to query saved match history
├── test_client.html          # Zero-build browser page to test the WebSocket
├── test_ball_detector.py     # Unit tests for ball detection (no network required)
├── test_db.py                # Unit tests for persistence (uses temp DB, no network)
├── test_event_bus.py         # Unit tests for the event bus
├── test_connection_manager.py # Unit tests for websocket connection handling
├── requirements.txt
├── Procfile                  # Tells Render/Railway/Heroku how to start the app
├── Dockerfile                 # Alternative: container-based deployment
├── .env.example               # Documents required env vars (no real secrets)
├── push.sh
└── README.md
```

## Running the web layer (Day 5+)

Install dependencies:
```bash
pip install -r requirements.txt
```

Start the server:
```bash
uvicorn api:app --reload --port 8000
```

Then open `frontend/index.html` in a browser (just double-click it, no build/server needed for the frontend itself), enter a match_id in the top-right box, click **Watch**. You'll see:
- Existing ball history load in immediately (via `GET /matches/{id}/history`)
- A live-updating LED-style score display
- A ball-by-ball feed streaming in as new deliveries are detected, with wickets in red and boundaries in green
- Automatic reconnection if the WebSocket drops

The original terminal-only version (`python3 main.py`) still works exactly as before — `api.py` and `frontend/` are additive, not a replacement.

As of Day 7, `api.py` also serves the frontend itself — visiting `http://localhost:8000` directly shows the scoreboard, no need to open the HTML file separately.

## Deploying (Day 8)

Recommended host: **[Render](https://render.com)** (free tier, supports the persistent background thread this app needs — platforms like Vercel don't, since they're built for stateless serverless functions).

1. Push this repo to GitHub (already done, day by day)
2. On Render: **New → Web Service** → connect this GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT` (or Render will detect the `Procfile` automatically)
5. Add environment variables under **Environment**:
   - `CRICKET_API_KEY` = your real key
   - `ALLOWED_ORIGINS` = your Render URL once you know it, e.g. `https://ipl-live-score.onrender.com`
6. Deploy. Visit the URL Render gives you — the scoreboard loads directly.

**Known limitation to be upfront about:** Render's free tier uses an ephemeral filesystem, meaning the SQLite database (`ipl_scores.db`) gets wiped on every redeploy or restart. For an 8-day project this is a fine tradeoff — score history just starts fresh after a restart, live tracking still works perfectly. If persistent history across restarts matters later, that means moving to a hosted database (e.g. Render's managed Postgres) instead of local SQLite — a real change, not a config tweak, so worth knowing now rather than being surprised by it.

Alternative: `Dockerfile` is included if you'd rather deploy via a container-based platform (Railway, Fly.io, etc.) instead of a buildpack.

Run all tests:
```bash
python3 -m unittest discover -p "test_*.py" -v
```

Query saved history:
```bash
python3 history.py --list                # see all matches you've tracked
python3 history.py --match <match_id>     # full ball-by-ball log for one match
```

## Setup

1. Get a free API key from [cricketdata.org](https://cricketdata.org)
2. Clone this repo:
   ```bash
   git clone https://github.com/<your-username>/ipl-live-score-backend.git
   cd ipl-live-score-backend
   ```
3. Install dependencies:
   ```bash
   pip install requests
   ```
4. Set your API key:
   ```bash
   export CRICKET_API_KEY="your-key-here"
   ```

## Usage

Inspect the raw API response first (recommended before your first real run):
```bash
python3 main.py --dump-raw
```

Fetch once and exit:
```bash
python3 main.py --once
```

Run the live polling loop:
```bash
python3 main.py
```

Track a specific match instead of auto-finding one:
```bash
export MATCH_ID="the-match-id-from-currentMatches"
python3 main.py
```

## Roadmap
- [x] Day 1 — Backend core: API client + polling engine + terminal output
- [x] Day 2 — Proper `Match` / `Innings` / `Ball` models, unit-tested ball detection logic
- [x] Day 3 — SQLite persistence, resumable state, ball history logged permanently
- [x] Day 4 — Event bus (pub/sub): loop publishes events, printing/DB are independent subscribers
- [x] Day 5 — FastAPI + WebSocket: live ball events pushed to any connected browser
- [x] Day 6 — Real frontend: LED-style live scoreboard + ball-by-ball feed, auto-reconnect
- [x] Day 7 — Deployment-ready: dynamic frontend URLs, configurable CORS, Procfile, Dockerfile, .env.example
- [ ] Day 5–6 — FastAPI + WebSocket layer to push live updates
- [ ] Day 7 — Frontend consuming the WebSocket
- [ ] Day 8 — Deployment

## License
MIT
