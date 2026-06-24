#!/bin/bash
# Ethics Filter Canvas — Start Script
# Launches the FastAPI app via `uv run`, using the project's local venv.

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧬 Ethics Filter Canvas"
echo "========================"
echo ""
echo "Starting server on http://localhost:8001"
echo "Open that in your browser."
echo ""
echo "Press Ctrl+C to stop."
echo ""

cd "$DIR"
exec uv run python main.py
