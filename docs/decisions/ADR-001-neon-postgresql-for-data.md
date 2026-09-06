# ADR-001: Neon PostgreSQL for Data Storage

## Context
The application requires a robust data store to serve the API and perform analytics. The raw and transformed data (schemas `staging`, `core`, `analytics`) is already loaded and modeled as a star schema in a Neon PostgreSQL instance. 

## Decision
We will use the existing Neon PostgreSQL database directly via `asyncpg` for data access.

## Alternatives Considered
- **DuckDB:** Good for local analytics but adds complexity for syncing and concurrent writes from the Replay engine.
- **CSV:** Too slow and lacks relational integrity.

## Reason
The data is already normalized and loaded into Neon. Using it directly minimizes data movement, leverages the existing star schema, and provides robust concurrent access for the API and background processors. `asyncpg` provides high performance.

## Consequences
- **Positive:** Fast time-to-market, high performance, single source of truth.
- **Negative:** Hard dependency on network and Neon availability. Requires connection pooling configuration.
