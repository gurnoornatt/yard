"""
Shared Stagehand client factory.

Production: Browserbase (cloud, handles concurrency, works on any server).
Dev fallback: local Chrome when BROWSERBASE_API_KEY is not set.
"""

import os
from pathlib import Path

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
MODEL_KEY = os.environ.get("MODEL_API_KEY", "")

_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
]


def _local_chrome() -> str | None:
    for path in _CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def make_client():
    """Return AsyncStagehand. Browserbase for production; local Chrome for dev."""
    from stagehand import AsyncStagehand

    if BB_KEY:
        # Production: Browserbase handles concurrency natively
        return AsyncStagehand(browserbase_api_key=BB_KEY, model_api_key=MODEL_KEY)

    # Dev fallback: local Chrome (macOS only, not for production servers)
    chrome = _local_chrome()
    if chrome:
        return AsyncStagehand(server="local", local_headless=True)

    raise RuntimeError(
        "No browser backend available. Set BROWSERBASE_API_KEY for production "
        "or run on macOS with Chrome installed for local dev."
    )


def session_kwargs(model: str) -> dict:
    """Return kwargs for client.sessions.start() matching the client mode."""
    if BB_KEY:
        return {"model_name": model}

    chrome = _local_chrome()
    if chrome:
        return {
            "model_name": model,
            "browser": {
                "type": "local",
                "launchOptions": {"executablePath": chrome, "headless": True},
            },
        }
    return {"model_name": model}
