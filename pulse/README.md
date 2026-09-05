# Pulse

Monorepo for Pulse: a Python agent (data + stats + LLM), a Java backend API, and an
Angular frontend.

```
pulse/
├── agent/       Python — FastAPI, DuckDB, pandas          :8000
├── backend/     Java — Spring Boot 3, H2, Flyway          :8080
├── frontend/    Angular 17 — standalone + ng-zorro-antd   :4200
├── contracts/   Shared JSON schemas
└── data/        Raw CSVs + local databases (gitignored)
```

## Prerequisites

| Tool   | Version                                                     |
| ------ | ----------------------------------------------------------- |
| Python | 3.11+                                                        |
| JDK    | 21+ (bytecode target is 21)                                  |
| Maven  | 3.9+                                                         |
| Node   | 18.13+ (Angular 17 officially supports 18.x / 20.x — see note below) |

## Start all three services

Run each step in its own terminal, **in this order**. The backend calls the agent, and
the frontend calls the backend, so starting them in order means the first page load is
already green.

### 1. Agent (Python) — port 8000

```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # optional; defaults work as-is
./run.sh
```

Verify: <http://localhost:8000/health> → `{"status":"UP","service":"pulse-agent",...}`

`run.sh` activates `agent/.venv` if it exists, then runs
`uvicorn app.main:app --reload --port 8000`.

### 2. Backend (Java) — port 8080

```bash
cd backend
mvn spring-boot:run
```

Verify: <http://localhost:8080/api/health> →

```json
{
  "status": "UP",
  "service": "pulse-backend",
  "version": "0.1.0",
  "agent": { "status": "UP", "service": "pulse-agent", "version": "0.1.0" }
}
```

The backend calls the agent's `/health` over `RestClient`. If the agent is down the
backend still answers, reporting `agent.status = "DOWN"`.

H2 runs in file mode; Maven is configured to run the app from the repo root, so the
database lands at `pulse/data/pulse-db.mv.db`. Flyway applies `db/migration` on boot.

### 3. Frontend (Angular) — port 4200

```bash
cd frontend
npm install
npm start
```

Open <http://localhost:4200>. The page shows a status badge for both the Java backend
and the Python agent.

`npm start` runs `ng serve --proxy-config proxy.conf.json`, which forwards `/api` to
`http://localhost:8080`.

> **Node 24 note:** Angular 17's CLI rejects Node majors it predates. On Node 22/24,
> export `NG_DISABLE_VERSION_CHECK=1` before `npm install` / `npm start`, or use Node 20.

#### UI library

The UI uses [ng-zorro-antd](https://ng.ant.design) 17, installed with
`ng add ng-zorro-antd@17` (locale `en_US`, no custom theme, static icons, blank
template). It added `provideNzI18n` / `provideAnimationsAsync` to
[`app.config.ts`](frontend/src/app/app.config.ts) and `ng-zorro-antd.min.css` to
`angular.json`.

`@ctrl/tinycolor` is pinned as a direct dependency: ng-zorro-antd 17.4.1 imports it
but does not declare it, so the build fails to resolve it otherwise.

`ng add` changes `angular.json` and installs packages, so **restart `ng serve`** after
running it — a running dev server will not pick up either.

## Configuration

| Where                                   | Setting              | Default                 |
| --------------------------------------- | -------------------- | ----------------------- |
| `agent/.env`                            | `PORT`               | `8000`                  |
| `agent/.env`                            | `DUCKDB_PATH`        | `data/warehouse.duckdb` |
| `agent/.env`                            | `RAW_DATA_DIR`       | `data/raw`              |
| `backend/src/main/resources/application.yml` | `server.port`   | `8080`                  |
| `backend/src/main/resources/application.yml` | `pulse.agent.base-url` | `http://localhost:8000` |
| `frontend/proxy.conf.json`              | `/api` target        | `http://localhost:8080` |

Agent paths in `.env` are relative to the repo root.

## Tests

```bash
cd agent   && .venv/bin/pytest
cd backend && mvn test
cd frontend && npm test
```

## Data

Drop the hackathon CSVs into `data/raw/`. That directory, `*.duckdb`, and
`data/pulse-db*` are gitignored.
