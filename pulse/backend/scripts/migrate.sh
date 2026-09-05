#!/usr/bin/env bash
# Applies the Flyway migrations to whatever backend/.env points at.
#
# The Flyway Maven plugin reads the process environment, not .env, so this
# sources the file first. Credentials never appear on the command line.
#
#   ./backend/scripts/migrate.sh            # migrate
#   ./backend/scripts/migrate.sh info       # show what is applied
#   ./backend/scripts/migrate.sh validate   # check checksums against the database

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
GOAL="${1:-migrate}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy backend/.env.example to backend/.env and fill it in." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# The Flyway plugin wants the three properties separately. If .env only carries
# NEON_DATABASE_URL (the postgres:// URI Neon issues), split it the same way the
# application does -- credentials as properties, never inside the URL.
if [[ -z "${PULSE_DB_URL:-}" && -n "${NEON_DATABASE_URL:-}" ]]; then
  eval "$(
    NEON_DATABASE_URL="$NEON_DATABASE_URL" python3 - <<'PYEOF'
import os, shlex, urllib.parse as up
u = up.urlparse(os.environ["NEON_DATABASE_URL"])
kept = [(k, v) for k, v in up.parse_qsl(u.query) if k != "channel_binding"]
if not any(k == "sslmode" for k, _ in kept):
    kept.append(("sslmode", "require"))
port = f":{u.port}" if u.port else ""
url = f"jdbc:postgresql://{u.hostname}{port}/{u.path.lstrip('/')}?{up.urlencode(kept)}"
print("export PULSE_DB_URL=" + shlex.quote(url))
print("export PULSE_DB_USER=" + shlex.quote(up.unquote(u.username or "")))
print("export PULSE_DB_PASSWORD=" + shlex.quote(up.unquote(u.password or "")))
PYEOF
  )"
fi

for var in PULSE_DB_URL PULSE_DB_USER PULSE_DB_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set, and $ENV_FILE has no usable NEON_DATABASE_URL either" >&2
    exit 1
  fi
done

# Print the target without the credentials.
echo ">> flyway:$GOAL against ${PULSE_DB_URL%%\?*} as $PULSE_DB_USER"
exec mvn -f "$BACKEND_DIR/pom.xml" --no-transfer-progress "flyway:$GOAL"
