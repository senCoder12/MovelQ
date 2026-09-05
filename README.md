# MoveIQ - Mobility Decision Intelligence

An agentic mobility intelligence layer that turns fragmented trip, employee, safety, cost and experience signals into business situations, quantifies their impact, compares possible interventions, and recommends—or executes—the best action.

## Core Persona & Question
- **Persona:** Team/Line Manager
- **Core Question:** "Will my team be ready when work starts?"

## Key Capabilities
- **Shift Readiness:** Computes and tracks the percentage of a workforce expected to be on-time for a given shift.
- **Situation Detection:** Elevates raw data signals and alert episodes into meaningful business situations.
- **Alert Episode Aggregation:** Groups raw, noisy, repetitive alerts deterministically into consolidated episodes.
- **Historical Benchmarking:** Compares current metrics against historical contexts (route, shift, vendor).
- **Decision Comparison:** Generates and evaluates candidate actions with their respective impact matrices.
- **What-if Analysis:** Explores potential outcomes of decisions before they are executed.
- **Ask Move Chat:** Context-aware LLM interface to query active situations and decisions.

## Architecture Overview
- **Backend:** Python 3.11+, FastAPI, asyncpg, Pydantic
- **Frontend:** React 18, TypeScript, Tailwind CSS, Vite, Recharts
- **Database:** Neon PostgreSQL (existing schemas: staging, core, analytics; MoveIQ adds `moveiq` schema)

## Prerequisites
- Python 3.11+
- Node.js 18+
- Neon DB connection (URL)

## Setup Instructions

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Fill in NEON_DATABASE_URL and LLM_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend  
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables
- `NEON_DATABASE_URL`: Connection string for Neon database
- `LLM_API_KEY`: API key for LLM provider
- `LLM_MODEL`: e.g., gpt-4o
- `LLM_TEMPERATURE`: e.g., 0.3
- `ALERT_EPISODE_GAP_MINUTES`: Used for grouping alerts
- `READINESS_THRESHOLD`: Determines what constitutes 'ready'
*(See `.env.example` for full list)*

## Database
Data is already loaded in Neon via `db/` SQL scripts (`staging` → `core` → `analytics`). MoveIQ reads this data and writes to its own `moveiq.*` schema for situations, decisions, and episodes.

## Core Commands
- **Data processing:** `python -m app.analytics.preprocessing`
- **Replay engine:** `python -m app.replay.replay_engine --date 2026-07-15`
- **Backend URL:** `http://localhost:8000`
- **Frontend URL:** `http://localhost:5173`
- **Test Backend:** `cd backend && pytest`
- **Test Frontend:** `cd frontend && npm test`

## Demo Flow (10-Step Walkthrough)
1. **Shift Approaching:** System tracks upcoming shifts.
2. **Readiness:** Dashboard shows current shift readiness percentage.
3. **Situation:** System detects a critical situation (e.g., severe delay).
4. **Episode:** Raw alerts are aggregated into an episode.
5. **Evidence:** LLM provided with context packet and evidence.
6. **Recommendation:** System suggests a set of actions.
7. **What-if:** Line Manager simulates impact.
8. **Action:** Line Manager selects the best action.
9. **Outcome:** System tracks the results.
10. **Resolution:** Situation is closed and added to historical context.

## API Overview
- `GET /api/v1/home`: Dashboard summary.
- `GET /api/v1/shifts`: Shift information and readiness.
- `GET /api/v1/readiness`: Granular readiness metrics.
- `GET /api/v1/situations`: Active and past business situations.
- `GET /api/v1/decisions`: Available decisions and history.
- `POST /api/v1/ask`: Chat interface for MoveIQ.

## Project Structure
```
MovelQ/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── services/
│   │   ├── replay/
│   │   └── main.py
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.tsx
│   └── package.json
├── docs/
├── db/
├── .env.example
└── README.md
```

## Troubleshooting & Known Limitations
- LLM response latency may vary. Ensure `LLM_API_KEY` is valid.
- The `pulse/` directory is a separate legacy prototype and not part of the MoveIQ core stack.

## Scaling Notes
- Use `asyncpg` pools effectively.
- Monitor LLM rate limits and use the caching layer for non-material changes.
