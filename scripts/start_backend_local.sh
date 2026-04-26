#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"
exec env -u DEBUG .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
