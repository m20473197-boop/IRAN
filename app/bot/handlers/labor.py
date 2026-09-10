"""Labor handler — receives 'کارگری' message and delegates to LaborService.

Business logic stays inside service; handler only translates Telegram -> service.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.context import get_services
from app.bot.messages import labor as labor_messages
from app.game.shared.errors import PlayerNotFoundError

logger = logging.getLogger(__name__)

# The exact text users type
LABOR_TRIGGER = "کارگری"


async def labor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'کارگری' text message."""
    if update.message is None or update.effective_user is None:
        return

    # Only respond to exact match (strip spaces)
    text = (update.message.text or "").strip()
    if text != LABOR_TRIGGER:
        return

    services = get_services(context)
    telegram_user_id = update.effective_user.id

    try:
        # Find player_id by telegram_user_id
        # Use PlayerRepository via PlayerService's session_factory
        from app.database.repositories.player_repository import PlayerRepository

        async with services.players._session_factory() as session:
            repo = PlayerRepository(session)
            player = await repo.get_by_telegram_user_id(telegram_user_id)
            if player is None:
                await update.message.reply_text(labor_messages.labor_not_registered_text())
                return
            player_id = player.id

        # Call LaborService
        result = await services.labor.perform_labor(player_id)

        if result.success:
            await update.message.reply_text(
                labor_messages.labor_success_text(result.reward, result.balance_after)
            )
        else:
            await update.message.reply_text(
                labor_messages.labor_cooldown_text(result.remaining_seconds)
            )

    except PlayerNotFoundError:
        await update.message.reply_text(labor_messages.labor_not_registered_text())
    except Exception as exc:
        logger.error("Labor handler failed for user %s", telegram_user_id, exc_info=exc)
        await update.message.reply_text(labor_messages.labor_error_text())
