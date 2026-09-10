"""Job system handlers — menu, apply, work, leave, history.

All business logic in JobService, handlers only translate Telegram -> service.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.context import get_services
from app.bot.keyboards import build_back_to_main, build_jobs_list, build_jobs_menu, callbacks
from app.bot.messages import job as job_messages
from app.bot.messages import errors as error_messages
from app.game.shared.errors import PlayerNotFoundError
from app.services.job_service import (
    AlreadyHasJobError,
    JobCooldownError,
    JobNotFoundError,
    JobRequirementError,
    NoJobError,
)

logger = logging.getLogger(__name__)

WORK_TEXT_TRIGGER = "کار"
JOBS_TEXT_TRIGGER = "مشاغل"
MY_JOB_TEXT_TRIGGER = "شغل من"
LEAVE_JOB_TEXT_TRIGGER = "ترک کار"
APPLY_JOB_TEXT_TRIGGER = "استخدام"


async def show_jobs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data != callbacks.JOBS_MENU:
        return
    await query.answer()

    await query.edit_message_text(
        text=job_messages.jobs_menu_text(), reply_markup=build_jobs_menu()
    )


async def show_jobs_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data != callbacks.JOBS_LIST:
        return
    await query.answer()

    services = get_services(context)
    jobs = await services.jobs.get_available_jobs()

    await query.edit_message_text(
        text=job_messages.jobs_list_text(jobs), reply_markup=build_jobs_list(jobs)
    )


async def show_my_job(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data != callbacks.JOBS_MY_JOB:
        return
    await query.answer()

    services = get_services(context)
    tg_id = query.from_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await query.edit_message_text(
                text=error_messages.NOT_REGISTERED, reply_markup=None
            )
            return
        player_id = player.id

    try:
        player_job = await services.jobs.get_player_job(player_id)
    except PlayerNotFoundError:
        await query.edit_message_text(
            text=error_messages.NOT_REGISTERED, reply_markup=None
        )
        return

    await query.edit_message_text(
        text=job_messages.my_job_text(player_job), reply_markup=build_jobs_menu()
    )


async def work_job_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Work via button."""
    query = update.callback_query
    if query is None or query.data != callbacks.JOBS_WORK:
        return
    await query.answer()

    services = get_services(context)
    tg_id = query.from_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await query.edit_message_text(
                text=error_messages.NOT_REGISTERED, reply_markup=None
            )
            return
        player_id = player.id

    try:
        result = await services.jobs.work_job(player_id)
        await query.edit_message_text(
            text=job_messages.job_work_success(result.income, result.balance_after),
            reply_markup=build_jobs_menu(),
        )
    except NoJobError:
        await query.edit_message_text(
            text=job_messages.job_no_job(), reply_markup=build_jobs_menu()
        )
    except JobCooldownError as exc:
        await query.edit_message_text(
            text=job_messages.job_work_cooldown(exc.remaining_seconds),
            reply_markup=build_jobs_menu(),
        )
    except Exception as exc:
        logger.error("work_job_callback failed for %s", tg_id, exc_info=exc)
        await query.edit_message_text(
            text=error_messages.GENERIC, reply_markup=build_jobs_menu()
        )


async def leave_job_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data != callbacks.JOBS_LEAVE:
        return
    await query.answer()

    services = get_services(context)
    tg_id = query.from_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await query.edit_message_text(
                text=error_messages.NOT_REGISTERED, reply_markup=None
            )
            return
        player_id = player.id

    try:
        result = await services.jobs.leave_job(player_id)
        await query.edit_message_text(
            text=job_messages.job_leave_success(result.job_name, result.total_earnings),
            reply_markup=build_jobs_menu(),
        )
    except NoJobError:
        await query.edit_message_text(
            text=job_messages.job_no_job(), reply_markup=build_jobs_menu()
        )
    except Exception as exc:
        logger.error("leave_job_callback failed for %s", tg_id, exc_info=exc)
        await query.edit_message_text(
            text=error_messages.GENERIC, reply_markup=build_jobs_menu()
        )


async def apply_job_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data.startswith(callbacks.JOBS_APPLY_PREFIX):
        return
    await query.answer()

    services = get_services(context)
    tg_id = query.from_user.id

    # Extract job_id
    try:
        job_id_str = query.data[len(callbacks.JOBS_APPLY_PREFIX) :]
        job_id = int(job_id_str)
    except ValueError:
        await query.answer(text="شناسه شغل نامعتبر است.", show_alert=True)
        return

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await query.edit_message_text(
                text=error_messages.NOT_REGISTERED, reply_markup=None
            )
            return
        player_id = player.id

    try:
        result = await services.jobs.apply_job(player_id, job_id)
        await query.edit_message_text(
            text=job_messages.job_applied_success(result.job_name),
            reply_markup=build_jobs_menu(),
        )
    except JobNotFoundError:
        await query.edit_message_text(
            text=job_messages.job_not_found(), reply_markup=build_jobs_menu()
        )
    except JobRequirementError as exc:
        await query.edit_message_text(
            text=job_messages.job_apply_error(str(exc)), reply_markup=build_jobs_menu()
        )
    except AlreadyHasJobError as exc:
        await query.edit_message_text(
            text=job_messages.job_apply_error(str(exc)), reply_markup=build_jobs_menu()
        )
    except Exception as exc:
        logger.error("apply_job_callback failed for %s", tg_id, exc_info=exc)
        await query.edit_message_text(
            text=error_messages.GENERIC, reply_markup=build_jobs_menu()
        )


async def show_job_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data != callbacks.JOBS_HISTORY:
        return
    await query.answer()

    services = get_services(context)
    tg_id = query.from_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await query.edit_message_text(
                text=error_messages.NOT_REGISTERED, reply_markup=None
            )
            return
        player_id = player.id

    try:
        histories = await services.jobs.get_job_history(player_id, limit=10)
        await query.edit_message_text(
            text=job_messages.job_history_text(histories),
            reply_markup=build_jobs_menu(),
        )
    except Exception as exc:
        logger.error("show_job_history failed for %s", tg_id, exc_info=exc)
        await query.edit_message_text(
            text=error_messages.GENERIC, reply_markup=build_jobs_menu()
        )


async def work_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text message 'کار' for working."""
    if update.message is None or update.effective_user is None:
        return

    text = (update.message.text or "").strip()
    if text != "کار":
        return

    services = get_services(context)
    tg_id = update.effective_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await update.message.reply_text(error_messages.NOT_REGISTERED)
            return
        player_id = player.id

    try:
        result = await services.jobs.work_job(player_id)
        await update.message.reply_text(
            job_messages.job_work_success(result.income, result.balance_after)
        )
    except NoJobError:
        await update.message.reply_text(job_messages.job_no_job())
    except JobCooldownError as exc:
        await update.message.reply_text(
            job_messages.job_work_cooldown(exc.remaining_seconds)
        )
    except Exception as exc:
        logger.error("work_text_handler failed for %s", tg_id, exc_info=exc)
        await update.message.reply_text(error_messages.GENERIC)


# --- New Persian command handlers ----------------------------------------


async def jobs_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'مشاغل' — show available jobs."""
    if update.message is None or update.effective_user is None:
        return
    if (update.message.text or "").strip() != JOBS_TEXT_TRIGGER:
        return

    services = get_services(context)
    tg_id = update.effective_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await update.message.reply_text(error_messages.NOT_REGISTERED)
            return

    try:
        jobs = await services.jobs.get_available_jobs()
        await update.message.reply_text(
            text=job_messages.jobs_list_text(jobs),
            reply_markup=build_jobs_list(jobs),
        )
    except Exception as exc:
        logger.error("jobs_text_handler failed for %s", tg_id, exc_info=exc)
        await update.message.reply_text(error_messages.GENERIC)


async def my_job_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'شغل من' — show current job."""
    if update.message is None or update.effective_user is None:
        return
    if (update.message.text or "").strip() != MY_JOB_TEXT_TRIGGER:
        return

    services = get_services(context)
    tg_id = update.effective_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await update.message.reply_text(error_messages.NOT_REGISTERED)
            return
        player_id = player.id

    try:
        pj = await services.jobs.get_player_job(player_id)
        await update.message.reply_text(
            text=job_messages.my_job_text(pj), reply_markup=build_jobs_menu()
        )
    except Exception as exc:
        logger.error("my_job_text_handler failed for %s", tg_id, exc_info=exc)
        await update.message.reply_text(error_messages.GENERIC)


async def leave_job_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'ترک کار' — leave current job."""
    if update.message is None or update.effective_user is None:
        return
    if (update.message.text or "").strip() != LEAVE_JOB_TEXT_TRIGGER:
        return

    services = get_services(context)
    tg_id = update.effective_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await update.message.reply_text(error_messages.NOT_REGISTERED)
            return
        player_id = player.id

    try:
        result = await services.jobs.leave_job(player_id)
        await update.message.reply_text(
            text=job_messages.job_leave_success(result.job_name, result.total_earnings),
            reply_markup=build_jobs_menu(),
        )
    except NoJobError:
        await update.message.reply_text(job_messages.job_no_job())
    except Exception as exc:
        logger.error("leave_job_text_handler failed for %s", tg_id, exc_info=exc)
        await update.message.reply_text(error_messages.GENERIC)


async def apply_job_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'استخدام' — apply for a job.

    Supports:
    - 'استخدام' alone -> shows jobs list
    - 'استخدام <job_name>' or 'استخدام <job_id>' -> tries to apply directly
    """
    if update.message is None or update.effective_user is None:
        return

    raw_text = (update.message.text or "").strip()
    if not raw_text.startswith(APPLY_JOB_TEXT_TRIGGER):
        return

    services = get_services(context)
    tg_id = update.effective_user.id

    from app.database.repositories.player_repository import PlayerRepository

    async with services.players._session_factory() as session:
        repo = PlayerRepository(session)
        player = await repo.get_by_telegram_user_id(tg_id)
        if player is None:
            await update.message.reply_text(error_messages.NOT_REGISTERED)
            return
        player_id = player.id

    # Parse argument after 'استخدام'
    arg = raw_text[len(APPLY_JOB_TEXT_TRIGGER) :].strip()

    if not arg:
        # No arg — show jobs list
        try:
            jobs = await services.jobs.get_available_jobs()
            await update.message.reply_text(
                text=job_messages.jobs_list_text(jobs),
                reply_markup=build_jobs_list(jobs),
            )
        except Exception as exc:
            logger.error("apply_job_text_handler list failed for %s", tg_id, exc_info=exc)
            await update.message.reply_text(error_messages.GENERIC)
        return

    # Try to find job by id or name
    try:
        jobs = await services.jobs.get_available_jobs()
        target_job = None

        # Try by id
        try:
            job_id = int(arg)
            target_job = next((j for j in jobs if j.id == job_id), None)
        except ValueError:
            pass

        # Try by exact name
        if target_job is None:
            target_job = next((j for j in jobs if j.name == arg), None)

        # Try by contains
        if target_job is None:
            # Allow partial match
            for j in jobs:
                if arg in j.name:
                    target_job = j
                    break

        if target_job is None:
            await update.message.reply_text(job_messages.job_not_found())
            return

        result = await services.jobs.apply_job(player_id, target_job.id)
        await update.message.reply_text(
            text=job_messages.job_applied_success(result.job_name),
            reply_markup=build_jobs_menu(),
        )
    except JobNotFoundError:
        await update.message.reply_text(job_messages.job_not_found())
    except JobRequirementError as exc:
        await update.message.reply_text(job_messages.job_apply_error(str(exc)))
    except AlreadyHasJobError as exc:
        await update.message.reply_text(job_messages.job_apply_error(str(exc)))
    except Exception as exc:
        logger.error("apply_job_text_handler failed for %s", tg_id, exc_info=exc)
        await update.message.reply_text(error_messages.GENERIC)
