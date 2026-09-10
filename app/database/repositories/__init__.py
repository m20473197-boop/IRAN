"""Repositories package — the only layer that talks to the database."""

from app.database.repositories.player_repository import PlayerRepository

__all__ = ["PlayerRepository"]
