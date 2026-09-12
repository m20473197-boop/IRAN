from __future__ import annotations
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.bot.context import get_services
from app.game.market import MARKET_ASSETS, direction
TRIGGER='بازار ایران'
def _fmt(v): return '—' if v is None else f'{int(v):,} تومان'
def _kb(): return InlineKeyboardMarkup([[InlineKeyboardButton(n,callback_data=f'market:{k}') for k,n in MARKET_ASSETS[:2]],[InlineKeyboardButton(n,callback_data=f'market:{k}') for k,n in MARKET_ASSETS[2:]]])
async def market_text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await _show(update,context)
async def _show(update,context):
    rows=await get_services(context).market.assets(); text='📈 بازار ایران\n\n'
    for r in rows:
        ch=(r.current_price or 0)-(r.previous_price or r.current_price or 0)
        text+=f'{r.display_name}: {_fmt(r.current_price)} {direction(ch)} {ch:+,}\n'
    if update.callback_query: await update.callback_query.edit_message_text(text,reply_markup=_kb())
    else: await update.message.reply_text(text,reply_markup=_kb())
async def market_callback(update,context):
    q=update.callback_query; await q.answer(); key=q.data.split(':',1)[1]
    if key=='menu': return await _show(update,context)
    row=await get_services(context).market.get(key)
    if row is None: return await q.edit_message_text('این دارایی پیدا نشد.')
    ch=(row.current_price or 0)-(row.previous_price or row.current_price or 0)
    text=f'{row.display_name}\n\nقیمت فعلی: {_fmt(row.current_price)}\nقیمت قبلی: {_fmt(row.previous_price)}\nتغییر: {direction(ch)} {ch:+,} تومان\nآخرین بروزرسانی: {row.last_successful_update or "هنوز ثبت نشده"}'
    await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 بازار ایران',callback_data='market:menu')]]))
