"""HTTP API — FastAPI dashboard and chat lookup."""

from radar.api.app import app
from radar.api.chat import lookup as chat_lookup

__all__ = ["app", "chat_lookup"]
