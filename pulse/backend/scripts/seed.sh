#!/usr/bin/env bash
# Loads backend/src/main/resources/db/seed/*.sql into whatever backend/.env
# points at, by starting the application with --seed.
#
# Idempotent: safe to run before every demo.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy backend/.env.example to backend/.env and fill it in." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo ">> seeding ${PULSE_DB_URL%%\?*}"
exec mvn -f "$BACKEND_DIR/pom.xml" --no-transfer-progress spring-boot:run \
  -Dspring-boot.run.arguments=--seed
