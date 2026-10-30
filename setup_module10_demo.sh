#!/usr/bin/env bash
# Module 10 demo bootstrap — runs the API with the labelled dev mock.
# The mock (NOT AI) is used ONLY to demonstrate the pipeline; see
# docs/rhino-mvp/SECTION_10_DEMO.md. Real AI needs RECONSTRUCTION_PROVIDER=trellis.
set -euo pipefail
cd "$(dirname "$0")/backend"
mkdir -p ../storage
MARLIN_ENVIRONMENT=development \
RECONSTRUCTION_PROVIDER=mock \
MARLIN_STORAGE_DIR="$(pwd)/../storage" \
  ../.venv-m10/bin/python -m uvicorn app.mvp:create_app --factory \
    --host 127.0.0.1 --port 8123
