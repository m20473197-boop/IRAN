"""Data transfer objects returned by services to the Telegram layer.

DTOs keep the bot layer decoupled from ORM models: handlers never touch
database objects directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProfileData:
    """Everything the profile screen needs."""

    display_name: str
    level: int
    xp: int
    money: int


@dataclass(frozen=True, slots=True)
class StatusData:
    """The basic game state shown on the status screen."""

    level: int
    xp: int
    money: int


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    """Outcome of ``/start`` registration (new or existing player)."""

    player_id: int
    created: bool
    profile: ProfileData


@dataclass(frozen=True, slots=True)
class AddXpResult:
    """Outcome of adding XP, including level-up detection."""

    player_id: int
    xp_before: int
    xp_after: int
    old_level: int
    new_level: int
    leveled_up: bool


@dataclass(frozen=True, slots=True)
class MoneyChangeResult:
    """Outcome of a balance change."""

    player_id: int
    amount: int
    balance_after: int
