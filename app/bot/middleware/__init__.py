"""Cross-cutting middleware applied to every update."""

from app.bot.middleware.activity_logging import register_middleware

__all__ = ["register_middleware"]
