# 🏏 ipl-live-score-backend

A real-time IPL score tracker backend — polls a live cricket API, detects **every new ball bowled**, and updates the score automatically. Terminal-first, API-driven, built to later plug into a web frontend.

## Status: Day 2/8 — Models + testable ball detection

## Features
- Polls live match data on an interval (default: every 5s)
- Detects new balls by diffing overs/runs/wickets against the last poll (not just raw score snapshots)
- Auto-finds a live IPL match, or track a specific match via `MATCH_ID`
- Retry + backoff on flaky network/API responses
- Clean separation: API layer (`cricket_api.py`) knows nothing about scoring logic, which knows nothing about printing — three independent layers
- Proper domain models (`Match`, `Innings`, `Ball`) instead of raw dicts
- Ball detection logic (`ball_detector.py`) is pure and independently unit-tested — no network needed to verify scoring logic is correct

> Note: true single-delivery ball-by-ball commentary is a paid feature on the underlying API. The free tier gives over-level score snapshots, which this backend diffs to detect individual balls where possible (`balls_covered == 1`), and falls back to reporting a combined update when polling missed more than one ball.

## Tech
- Python 3.10+
- [CricketData.org](https://cricketdata.org) (formerly CricAPI) — free tier, ball-by-ball data
- `requests` for HTTP

## Project structure
```
ipl-live-score/
├── config.py            # API key, endpoints, polling settings
├── cricket_api.py       # API client — all HTTP/network logic lives here
├── models.py             # Match / Innings / Ball domain models
├── ball_detector.py      # Pure diffing logic — turns state changes into Ball events
├── main.py                # Polling loop — fetch, detect, print (no logic of its own)
├── test_ball_detector.py  # Unit tests for ball detection (no network required)
├── push.sh
└── README.md
```

Run the tests:
```bash
python3 -m unittest test_ball_detector.py -v
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
- [ ] Day 3 — SQLite persistence (score history survives restarts)
- [ ] Day 4 — Event system (pub/sub) so multiple consumers can listen for `new_ball` events
- [ ] Day 5–6 — FastAPI + WebSocket layer to push live updates
- [ ] Day 7 — Frontend consuming the WebSocket
- [ ] Day 8 — Deployment

## License
MIT
