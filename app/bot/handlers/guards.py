"""Cross-cutting handler guards (feature flags).

The admin panel can switch whole game systems off from ⚙️ Bot Settings.
Every jobs/housing/real-estate handler is wrapped with
:func:`requires_feature`, so a disabled system politely refuses access
instead of running — and the main menu hides its button as well.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.messages import errors as message_errors
from app.game.admin import runtime as admin_runtime

P = ParamSpec("P")
T = TypeVar("T")


def requires_feature(
    feature: str,
) -> Callable[
    [Callable[P, Awaitable[T]]], Callable[P, Awaitable[T | None]]
]:
    """Deny access (politely) when the admin disabled ``feature``."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
        @wraps(func)
        async def wrapper(
            update: Update, context: ContextTypes.DEFAULT_TYPE, *args: P.args, **kwargs: P.kwargs
        ) -> T | None:
            if not admin_runtime.feature_enabled(feature):
                query = update.callback_query
                if query is not None:
                    await query.answer(
                        text=message_errors.FEATURE_DISABLED, show_alert=True
                    )
                    return None
                if update.message is not None:
                    await update.message.reply_text(message_errors.FEATURE_DISABLED)
                    return None
                return None
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator


async def player_id_for(services, tg_id: int) -> int | None:
    """Map a Telegram user id to the internal player id (None if unregistered).

    Shared by the command-only systems (jobs, family) so no handler ever
    touches the database layer directly beyond this tiny lookup.
    """
    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:  # type: ignore[attr-defined]
        player = await PlayerRepository(session).get_by_telegram_user_id(tg_id)
        return player.id if player is not None else None

