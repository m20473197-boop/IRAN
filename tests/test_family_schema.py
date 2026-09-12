"""Family schema tests — new tables on old databases, model shapes, menus.

Guards the two promises of the update:

1. ``create_all`` adds the six family tables and the players mirror columns
   to an existing database, WITHOUT touching existing rows (no drops).
2. The feature adds **no menus and no buttons** — the main menu and the
   callback namespace stay exactly as they were; the family system is wired
   only through text-message handlers.
"""

from __future__ import annotations

import sqlite3

from sqlalchemy import BigInteger, Integer, String

from app.database.database import Database
from app.database.models.child import Child
from app.database.models.divorce_record import DivorceRecord
from app.database.models.family_history import FamilyHistory
from app.database.models.marriage import Marriage
from app.database.models.marriage_proposal import MarriageProposal
from app.database.models.player import Player
from app.database.models.relationship_event import RelationshipEvent

FAMILY_TABLES = (
    "marriages",
    "marriage_proposals",
    "divorce_records",
    "relationship_events",
    "children",
    "family_histories",
)


def _create_pre_family_schema(db_path: str) -> None:
    """A database from before the family update (only the players table)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE players (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            telegram_user_id BIGINT NOT NULL,
            username VARCHAR(32),
            display_name VARCHAR(64) NOT NULL,
            level INTEGER NOT NULL,
            xp INTEGER NOT NULL,
            money BIGINT NOT NULL,
            is_banned BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (telegram_user_id)
        )
        """
    )
    conn.execute(
        "INSERT INTO players (telegram_user_id, display_name, level, xp, money) "
        "VALUES (777000, 'قدیمی', 7, 1234, 999)"
    )
    conn.commit()
    conn.close()


async def test_old_database_gains_all_family_tables(tmp_path):
    db_path = tmp_path / "old.db"
    _create_pre_family_schema(db_path.as_posix())

    database = Database(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await database.create_all()

    async with database.engine.begin() as connection:
        tables = {
            row[0]
            for row in (
                await connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            ).fetchall()
        }
        assert set(FAMILY_TABLES) <= tables

        # the old player row survives untouched
        players = await connection.exec_driver_sql(
            "SELECT telegram_user_id, level, xp, money FROM players"
        )
        row = players.fetchone()
        assert row == (777000, 7, 1234, 999)

    # and is readable through the (now-extended) model
    from app.services import ServiceRegistry

    registry = ServiceRegistry(database.session_factory)
    profile = await registry.players.get_profile(777000)
    assert profile is not None
    assert profile.marriage_status == "single"
    assert profile.spouse_display_name is None
    assert profile.children_count == 0

    # family service works on the migrated database
    info = await registry.family.get_family_info(1)
    assert info is not None and info.marriage_status == "single"
    await database.dispose()


async def test_old_database_gains_players_family_columns(tmp_path):
    db_path = tmp_path / "old.db"
    _create_pre_family_schema(db_path.as_posix())

    database = Database(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await database.create_all()

    async with database.engine.begin() as connection:
        columns = {
            row[1]
            for row in (
                await connection.exec_driver_sql("PRAGMA table_info(players)")
            ).fetchall()
        }
    assert {"marriage_status", "spouse_player_id", "married_at", "children_count"} <= columns
    await database.dispose()


async def test_migration_is_idempotent(tmp_path):
    """Running create_all repeatedly (bot restarts) changes nothing."""
    db_path = tmp_path / "old.db"
    _create_pre_family_schema(db_path.as_posix())
    url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    database = Database(url)
    await database.create_all()
    await database.create_all()
    await database.dispose()

    database = Database(url)
    await database.create_all()
    async with database.engine.begin() as connection:
        row = (
            await connection.exec_driver_sql(
                "SELECT telegram_user_id, level, marriage_status, children_count FROM players"
            )
        ).fetchone()
    assert row == (777000, 7, "single", 0)
    await database.dispose()


# --- Model shapes ----------------------------------------------------------------


def test_marriage_columns_and_constraints():
    cols = Marriage.__table__.columns
    assert isinstance(cols["mahr"].type, BigInteger)  # exact integer money
    assert isinstance(cols["children_count"].type, Integer)
    names = {idx.name for idx in Marriage.__table__.indexes}
    assert "ux_marriages_partner_a_active" in names
    assert "ux_marriages_partner_b_active" in names
    from sqlalchemy import CheckConstraint

    check_names = {
        c.name
        for c in Marriage.__table__.constraints
        if isinstance(c, CheckConstraint)
    }
    assert "ck_marriages_partners_differ" in check_names
    assert "ck_marriages_points_in_band" in check_names


def test_proposal_columns():
    cols = MarriageProposal.__table__.columns
    assert cols["status"].default.arg == "pending"
    assert cols["mahr"].nullable is False
    assert cols["expires_at"].nullable is True
    assert any(
        idx.name == "ux_proposals_pending_receiver"
        for idx in MarriageProposal.__table__.indexes
    )


def test_divorce_record_columns():
    cols = DivorceRecord.__table__.columns
    for name in ("mahr", "paid_amount", "unpaid_debt"):
        assert isinstance(cols[name].type, BigInteger)
    assert cols["marriage_id"].foreign_keys  # links back to the marriage
    assert cols["reason"].type.length >= 16


def test_child_columns_cover_the_required_data():
    cols = Child.__table__.columns
    assert {"marriage_id", "father_player_id", "mother_player_id", "birth_date"} <= set(
        cols.keys()
    )
    # prepared structure for future growth / education / expenses
    assert cols["growth_stage"].default.arg == 0
    assert cols["education_level"].default.arg == 0
    assert isinstance(cols["expense_total"].type, BigInteger)


def test_relationship_event_and_history_shapes():
    cols = RelationshipEvent.__table__.columns
    assert {"marriage_id", "initiator_player_id", "pregnancy_chance_percent", "outcome"} <= set(
        cols.keys()
    )
    hist_cols = FamilyHistory.__table__.columns
    assert hist_cols["event_type"].type.length >= 20
    assert isinstance(hist_cols["details"].type, String)


def test_player_family_mirror_defaults():
    cols = Player.__table__.columns
    assert cols["marriage_status"].default.arg == "single"
    assert cols["spouse_player_id"].nullable is True
    assert cols["married_at"].nullable is True
    assert cols["children_count"].default.arg == 0


# --- No menus / no buttons promise -------------------------------------------------


def test_main_menu_untouched_by_family_system():
    """The family system must NOT add any menu button."""
    from app.bot.keyboards import callbacks
    from app.bot.keyboards.main_menu import build_main_menu

    data = {b.callback_data for row in build_main_menu().inline_keyboard for b in row}
    assert data <= {
        callbacks.PROFILE,
        callbacks.STATUS,
        callbacks.JOBS_MENU,
        callbacks.HOUSING_MENU,
        callbacks.BACK_TO_MAIN,
    }
    assert not any(str(d).startswith(("fam_", "marry", "divorce")) for d in data)


def test_no_new_keyboard_builders_exported():
    """The keyboards package must not grow family builders."""
    import app.bot.keyboards as keyboards

    for name in dir(keyboards):
        assert not name.lower().startswith(("build_family", "build_marriage", "build_divorce"))


def test_family_routes_are_message_handlers_only():
    """All family commands are registered as TEXT message handlers."""
    from telegram.ext import ApplicationBuilder, MessageHandler

    from app.bot.handlers import register_handlers

    application = ApplicationBuilder().token("123456:ABC-test").build()
    register_handlers(application)

    wired = {
        h.callback
        for h in application.handlers[0]
        if isinstance(h, MessageHandler)
        and getattr(h, "callback", None) in family_handlers()
    }
    assert wired == set(family_handlers())


def family_handlers():
    from app.bot.handlers import family

    return [
        family.marry_text_handler,
        family.accept_proposal_text_handler,
        family.reject_proposal_text_handler,
        family.divorce_text_handler,
        family.forgive_text_handler,
        family.cheat_text_handler,
        family.relationship_text_handler,
        family.family_info_text_handler,
        family.divorce_history_text_handler,
        family.family_history_text_handler,
    ]


def test_family_triggers_do_not_collide_with_other_text_triggers():
    from app.bot.handlers import family, housing, job, realestate

    family_triggers = {
        family.MARRY_TEXT_TRIGGER,
        family.ACCEPT_TEXT_TRIGGER,
        family.REJECT_TEXT_TRIGGER,
        family.DIVORCE_TEXT_TRIGGER,
        family.FORGIVE_TEXT_TRIGGER,
        family.CHEAT_TEXT_TRIGGER,
        family.RELATIONSHIP_TEXT_TRIGGER,
        family.FAMILY_INFO_TEXT_TRIGGER,
        family.DIVORCE_HISTORY_TEXT_TRIGGER,
        family.FAMILY_HISTORY_TEXT_TRIGGER,
    }
    other_triggers = {
        job.JOBS_TEXT_TRIGGER,
        job.MY_JOB_TEXT_TRIGGER,
        job.LEAVE_JOB_TEXT_TRIGGER,
        job.APPLY_JOB_TEXT_TRIGGER,
        housing.HOUSING_TEXT_TRIGGER,
        housing.HOUSING_MENU_TEXT_TRIGGER,
        realestate.LANDS_MY_TEXT_TRIGGER,
        realestate.LANDS_MARKET_TEXT_TRIGGER,
        realestate.BUILD_TEXT_TRIGGER,
        realestate.STATUS_TEXT_TRIGGER,
        realestate.RENOVATE_TEXT_TRIGGER,
    }
    assert family_triggers & other_triggers == set()
