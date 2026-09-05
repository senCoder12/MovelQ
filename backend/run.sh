#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Check or create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment at backend/.venv..."
    python3 -m venv .venv
fi

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Check if uvicorn is installed
if ! command -v uvicorn &> /dev/null; then
    echo "Dependencies not found. Installing backend dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# 4. Check for .env file
if [ ! -f ".env" ] && [ -f "../.env" ]; then
    echo "Linking root .env to backend/.env..."
    ln -sf ../.env .env
elif [ ! -f ".env" ] && [ -f "../.env.example" ]; then
    echo "Creating backend/.env from .env.example..."
    cp ../.env.example .env
fi

echo "Starting MoveIQ Backend on http://localhost:8000..."
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
