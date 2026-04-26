#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_PATH="$PROJECT_DIR/../postgres-apptainer/postgres16.sif"
DATA_DIR="$PROJECT_DIR/.postgres-data"
RUN_DIR="$PROJECT_DIR/.postgres-run"

mkdir -p "$DATA_DIR" "$RUN_DIR"

exec apptainer run \
  --bind "$DATA_DIR:/var/lib/postgresql/data,$RUN_DIR:/var/run/postgresql" \
  --env POSTGRES_PASSWORD=postgres \
  --env POSTGRES_USER=postgres \
  --env POSTGRES_DB=luke_bot \
  "$IMAGE_PATH"
