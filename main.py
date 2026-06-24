"""Ethics Filter Canvas — uvicorn entrypoint.

Loads settings (will exit with a clear error if `DEEPSEEK_API_KEY` is
missing), configures logging, and starts the FastAPI app on port 8001.
"""
from __future__ import annotations
import uvicorn

from ethics_canvas.config import Settings
from ethics_canvas.logging import setup_logging


def main() -> None:
    settings = Settings()  # raises if DEEPSEEK_API_KEY is missing
    setup_logging(settings.log_level)
    uvicorn.run(
        "ethics_canvas.api:app",
        host="0.0.0.0",
        port=8001,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
