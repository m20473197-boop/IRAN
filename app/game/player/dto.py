"""Data transfer objects returned by services to the Telegram layer.

DTOs keep the bot layer decoupled from ORM models: handlers never touch
database objects directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ProfileData:
    """Everything the profile screen needs."""

    display_name: str
    level: int
    xp: int
    money: int
    # Extended progression fields — defaults keep old tests green
    xp_in_current_level: int = 0
    xp_needed_for_next: int = 0
    progress_percent: float = 0.0
    total_xp_for_next_level: int = 0


@dataclass(frozen=True, slots=True)
class StatusData:
    """The basic game state shown on the status screen."""

    level: int
    xp: int
    money: int
    # Extended progression fields — defaults keep old tests green
    xp_in_current_level: int = 0
    xp_needed_for_next: int = 0
    progress_percent: float = 0.0
    total_xp_for_next_level: int = 0


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
    # New optional fields for complete system
    reason: str = ""
    xp_needed_for_next: int = 0
    progress_percent: float = 0.0
    xp_in_current_level: int = 0
    transaction_id: int | None = None


@dataclass(frozen=True, slots=True)
class RemoveXpResult:
    """Outcome of removing XP."""

    player_id: int
    xp_before: int
    xp_after: int
    old_level: int
    new_level: int
    leveled_down: bool
    reason: str = ""
    xp_needed_for_next: int = 0
    progress_percent: float = 0.0
    xp_in_current_level: int = 0
    transaction_id: int | None = None


@dataclass(frozen=True, slots=True)
class MoneyChangeResult:
    """Outcome of a balance change."""

    player_id: int
    amount: int
    balance_after: int


@dataclass(frozen=True, slots=True)
class XPTransactionData:
    """DTO for a single XP history entry."""

    id: int
    player_id: int
    amount: int
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LevelUpData:
    """DTO for a level-up history entry."""

    id: int
    player_id: int
    old_level: int
    new_level: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LevelProgressData:
    """Complete progress snapshot used by Status/Profile and services."""

    level: int
    total_xp: int
    xp_in_current_level: int
    xp_needed_for_next: int
    total_xp_for_current_level: int
    total_xp_for_next_level: int
    progress_percent: float


@dataclass(frozen=True, slots=True)
class LaborResult:
    """Outcome of a labor attempt."""

    player_id: int
    success: bool
    reward: int
    balance_after: int
    remaining_seconds: int
    last_labor_at: datetime | None


@dataclass(frozen=True, slots=True)
class LaborStatus:
    """Current labor cooldown status without performing labor."""

    player_id: int
    can_work: bool
    remaining_seconds: int
    last_labor_at: datetime | None
    reward: int
    cooldown_seconds: int


@dataclass(frozen=True, slots=True)
class JobData:
    """DTO for a job definition."""

    id: int
    name: str
    description: str
    salary: int
    cooldown: int
    required_level: int
    required_skill: str | None
    is_active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlayerJobData:
    """DTO for player's current job."""

    id: int
    player_id: int
    job_id: int
    job_name: str
    job_description: str
    salary: int
    cooldown: int
    started_at: datetime
    last_work_time: datetime | None
    total_earnings: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class JobHistoryData:
    """DTO for job income history."""

    id: int
    player_id: int
    job_id: int
    job_name: str
    income: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobApplyResult:
    """Outcome of applying for a job."""

    player_id: int
    job_id: int
    job_name: str
    success: bool
    message: str


@dataclass(frozen=True, slots=True)
class JobWorkResult:
    """Outcome of working a job."""

    player_id: int
    job_id: int
    job_name: str
    success: bool
    income: int
    balance_after: int
    total_earnings: int
    remaining_seconds: int
    message: str


@dataclass(frozen=True, slots=True)
class JobLeaveResult:
    """Outcome of leaving a job."""

    player_id: int
    job_id: int
    job_name: str
    success: bool
    total_earnings: int
    message: str
