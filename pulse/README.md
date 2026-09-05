# Pulse

Monorepo for Pulse: a Python agent (data + stats + LLM), a Java backend API, and an
Angular frontend.

```
pulse/
├── agent/       Python — FastAPI, DuckDB, pandas          :8000
├── backend/     Java — Spring Boot 3, Neon Postgres, Flyway  :8080
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

The platform database is **Neon Postgres**. DuckDB is unchanged and still the analytical
warehouse, owned by the Python agent.

Credentials live in `backend/.env`, which is gitignored and is the only copy. Paste the
`postgres://` URI exactly as Neon gives it:

```bash
cd backend
cp .env.example .env
# NEON_DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

The application splits that at startup: host and database into the JDBC URL, credentials
into separate JDBC properties. Credentials stay out of the URL deliberately — the URL is
what appears in connection errors, Flyway output and startup logs, and a password
embedded in it appears there too. `channel_binding` is dropped automatically because the
JDBC driver rejects it. `scripts/migrate.sh` does the same split.

To set any part explicitly instead, use `PULSE_DB_URL` / `PULSE_DB_USER` /
`PULSE_DB_PASSWORD`; those win over `NEON_DATABASE_URL`.

Then apply the schema, load the demo data, and start:

```bash
./scripts/migrate.sh        # flyway:migrate — applies V1 and V2
./scripts/seed.sh           # two tenants of demo data; idempotent
mvn spring-boot:run
```

Verify: <http://localhost:8080/api/health> →

```json
{
  "status": "UP",
  "service": "pulse-backend",
  "version": "0.1.0",
  "platform_db": { "reachable": true, "latency_ms": 214, "migration_version": "2" },
  "agent": { "reachable": true, "status": "UP", "service": "pulse-agent" },
  "warehouse": { "present": true, "readable": true, "size_bytes": 60829696 }
}
```

The three dependencies are reported separately, so a failure names itself. `status` is
`UP` only when all three are healthy and `DEGRADED` otherwise.

**Neon cold starts are normal.** Neon suspends a branch that has been idle, and the
first connection afterwards can take several seconds. The pool allows for that
(`connection-timeout: 10000`) and the application starts even when Neon does not answer
at all — it logs a warning, skips schema validation for that boot, and reports the
platform database as unreachable on `/api/health`. A slow first request is not a bug.

**Latency.** Neon is in `us-east-2` and we demo from India. Measured, not assumed: a
round trip is **~300ms** when the connection is busy and **550-800ms** after a quiet
gap. Three things follow from that, in the order they were worth doing:

| | brief, median |
| --- | --- |
| one query, but wrapped in a read-only transaction | 880ms |
| same query in autocommit (the COMMIT round trip removed) | 312ms |
| plus the per-tenant cache | 1-2ms |

- The brief is **one** statement, pinned by a test that fails at two.
- Reads run in **autocommit**. `TenantFilterAspect` binds an EntityManager to the thread
  instead of opening a transaction, so the tenant filter still applies but a single read
  no longer pays a COMMIT round trip. Writes are unaffected -- Spring Data's own
  `@Transactional` starts a transaction on the bound EntityManager.
- The brief feed is **cached per tenant** for 30s (`pulse.brief.cache-ttl`, 0 disables).
  An expired entry is served anyway and refreshed on a background thread, because a plain
  expire-and-fetch cache put the whole 850ms-1s miss on whoever clicked first after an
  idle moment -- exactly the person watching the demo.

What still costs a round trip: the first request per tenant after a restart (~1.2s, pool
and TLS included). Everything after that is served warm.

Queries over 500ms log at WARN with their SQL, and every controller method logs its own
duration and tenant.

Every request to `/api/**` except `/api/health` requires an `X-Tenant-Id` header:

```bash
curl -H 'X-Tenant-Id: catalyst' 'http://localhost:8080/api/brief?persona=ops'
```

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
| `backend/.env`                          | `PULSE_DB_URL`       | — (required, JDBC form)  |
| `backend/.env`                          | `PULSE_DB_USER`      | — (required)            |
| `backend/.env`                          | `PULSE_DB_PASSWORD`  | — (required)            |
| `backend/.env`                          | `AGENT_BASE_URL`     | `http://localhost:8000` |
| `backend/src/main/resources/application.yml` | `server.port`   | `8080`                  |
| `backend/src/main/resources/application.yml` | `pulse.warehouse.path` | `data/warehouse.duckdb` |
| `backend/src/main/resources/application.yml` | `pulse.latency.slow-query-ms` | `500` |
| `backend/src/main/resources/application.yml` | `pulse.brief.cache-ttl` | `30s` (`0` disables) |
| `frontend/proxy.conf.json`              | `/api` target        | `http://localhost:8080` |

Agent paths in `.env` are relative to the repo root. `backend/.env` is read at startup
and sits below the process environment in precedence, so a real environment variable or
a `-D` flag always wins — which is what CI and container deployments use.

Nothing in the repo contains a password. `backend/.env` is gitignored;
`backend/.env.example` is committed and holds placeholders only.

## Tests

```bash
cd agent   && .venv/bin/pytest
cd backend && mvn test
cd frontend && npm test
```

The backend tests need a real Postgres — the schema uses JSONB, TIMESTAMPTZ and
BIGSERIAL, and an in-memory stand-in would prove nothing about what runs on Neon. They
read `backend/.env` like the application does, so point it at a scratch database (a Neon
branch, or a local `pulse_test`) before running them. Everything they write is rolled
back.

Two of them are worth knowing about:

- `TenantIsolationTest` inserts rows for `catalyst` and `vanta` through plain JDBC, then
  queries with no tenant predicate at all and asserts the other tenant's rows are absent
  — including through `findById`, `count()` and the brief projection. It also asserts
  that a repository call with no tenant in context throws rather than returning
  everything.
- `BriefQueryShapeTest` counts the statements the brief actually issues and fails if it
  is not exactly one. That is a latency guard, not a style rule: every extra statement is
  another round trip to `us-east-2`.

## Data

Two stores, deliberately:

- **Neon Postgres** — the platform database. Insights, action drafts, approvals. Schema
  owned by Flyway (`backend/src/main/resources/db/migration`); Hibernate only validates
  against it (`ddl-auto: validate`).
- **DuckDB** (`data/warehouse.duckdb`) — the analytical warehouse, read by the Python
  agent. Unchanged. The backend only checks that the file is present and readable, and
  never opens it: two processes holding a DuckDB file is how you corrupt one.

### Tenancy

Every table carries a non-null `tenant_id`, every index leads with it, and child rows use
a composite foreign key `(tenant_id, insight_id)` so a child physically cannot reference
another tenant's insight. On top of that, a Hibernate `@Filter` named `tenantFilter` is
enabled per session by an `@Around` aspect on the repository layer, from the tenant in
`TenantContextHolder`. A repository call with no tenant in context throws
`MissingTenantException` — there is no unscoped mode to fall back to.

Drop the hackathon CSVs into `data/raw/`. That directory and `*.duckdb` are gitignored.
