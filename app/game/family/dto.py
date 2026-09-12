"""DTOs handed from ``FamilyService`` to the Telegram layer (and profiles).

Handlers never touch ORM rows — these frozen dataclasses are the whole
contract of the family system's outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MARRIED: str = "married"
SINGLE: str = "single"
DIVORCED: str = "divorced"


@dataclass(frozen=True, slots=True)
class FamilySnapshot:
    """The tiny slice of family state the profile screen shows."""

    marriage_status: str = SINGLE
    spouse_player_id: int | None = None
    spouse_display_name: str | None = None
    married_at: datetime | None = None
    children_count: int = 0


@dataclass(frozen=True, slots=True)
class FamilyInfoData:
    """The «خانواده» screen: the complete family picture of one player."""

    player_id: int
    display_name: str
    marriage_status: str
    spouse_player_id: int | None = None
    spouse_display_name: str | None = None
    spouse_telegram_user_id: int | None = None
    marriage_id: int | None = None
    married_at: datetime | None = None
    mahr: int = 0
    relationship_points: int = 100
    cheating_count: int = 0
    children_count: int = 0
    divorce_pending_by_me: bool = False
    divorce_requested_by_spouse: bool = False
    divorce_request_age_seconds: int | None = None
    children: tuple[ChildData, ...] = ()


@dataclass(frozen=True, slots=True)
class ProposalData:
    """One pending marriage proposal («ازدواج»)."""

    id: int
    sender_player_id: int
    receiver_player_id: int
    mahr: int
    created_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProposalResult:
    """Outcome of creating a proposal (shown to the proposer + the target)."""

    proposal: ProposalData
    target_telegram_user_id: int
    target_display_name: str
    proposer_display_name: str


@dataclass(frozen=True, slots=True)
class MarriageResult:
    """Outcome of an accepted proposal — the marriage record."""

    marriage_id: int
    partner_a_id: int
    partner_b_id: int
    mahr: int
    married_at: datetime
    relationship_points: int
    proposer_display_name: str
    target_display_name: str
    proposer_telegram_user_id: int
    target_telegram_user_id: int
    xp_granted: bool = False


@dataclass(frozen=True, slots=True)
class DivorceResult:
    """Outcome of a finalized divorce («طلاق»)."""

    marriage_id: int
    initiator_player_id: int
    other_player_id: int
    mahr: int
    payer_player_id: int
    payee_player_id: int
    paid_amount: int
    unpaid_debt: int
    mahr_waived: bool
    cheater_liable: bool
    divorce_record_id: int
    initiator_telegram_user_id: int
    other_telegram_user_id: int
    initiator_display_name: str
    other_display_name: str


@dataclass(frozen=True, slots=True)
class DivorceRequestResult:
    """Outcome of *filing* a divorce request (the spouse may forgive)."""

    marriage_id: int
    requester_player_id: int
    expires_at: datetime | None
    final: bool
    mahr_required: int
    spouse_telegram_user_id: int
    spouse_display_name: str


@dataclass(frozen=True, slots=True)
class ForgiveResult:
    """Outcome of «بخشش» — the spouse forgave and the divorce is off."""

    marriage_id: int
    forgiver_player_id: int
    requester_player_id: int
    relationship_points_before: int
    relationship_points_after: int
    requester_telegram_user_id: int


@dataclass(frozen=True, slots=True)
class CheatResult:
    """Outcome of a secret «خیانت» attempt (only ever shown to its author).

    ``succeeded``/``discovered`` are the two independent rolls; the exact
    dice values are kept so the (hidden) result can be re-audited from the
    family history. ``spouse_telegram_user_id`` is set only when the affair
    was discovered — the handler uses it to deliver the spouse notification.
    """

    succeeded: bool
    discovered: bool
    relationship_points_before: int
    relationship_points_after: int
    penalty_money: int
    penalty_xp: int
    divorce_possible: bool
    marriage_id: int
    cheater_player_id: int
    success_roll: int = 0
    discovery_roll: int = 0
    spouse_player_id: int | None = None
    spouse_telegram_user_id: int | None = None
    spouse_display_name: str | None = None
    cheater_display_name: str | None = None


@dataclass(frozen=True, slots=True)
class ChildData:
    """One child row (future growth/education/expenses attach to it)."""

    id: int
    marriage_id: int
    father_player_id: int
    mother_player_id: int
    name: str
    gender: str
    birth_date: datetime
    age_years: int = 0
    growth_stage: int = 0
    education_level: int = 0
    expense_total: int = 0


@dataclass(frozen=True, slots=True)
class RelationshipResult:
    """Outcome of «رابطه» — the event plus a possible pregnancy/child."""

    event_id: int
    marriage_id: int
    partner_player_id: int
    partner_telegram_user_id: int
    partner_display_name: str
    satisfaction: int
    pregnancy_chance_percent: int
    pregnant: bool
    child: ChildData | None = None


@dataclass(frozen=True, slots=True)
class FamilyHistoryEntry:
    """One line of the persistent family history log."""

    id: int
    player_id: int
    marriage_id: int | None
    event_type: str
    details: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DivorceRecordData:
    """One stored divorce record (history of ended marriages)."""

    id: int
    marriage_id: int
    initiator_player_id: int
    partner_a_id: int
    partner_b_id: int
    mahr: int
    paid_amount: int
    unpaid_debt: int
    reason: str
    created_at: datetime
    initiator_display_name: str = ""
    other_display_name: str = ""
