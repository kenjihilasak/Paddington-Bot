#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_PATH="$PROJECT_DIR/../postgres-apptainer/postgres16.sif"
RUN_DIR="$PROJECT_DIR/.postgres-run"

exec apptainer exec \
  --bind "$RUN_DIR:/var/run/postgresql" \
  "$IMAGE_PATH" \
  psql -h 127.0.0.1 -U postgres -d luke_bot -c 'select current_database(), current_user;'
