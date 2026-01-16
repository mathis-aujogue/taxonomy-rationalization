#!/bin/bash
# Run the FastAPI backend server

cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
