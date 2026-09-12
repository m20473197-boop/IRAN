from __future__ import annotations
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.bot.context import get_services
TRIGGER='دیوار ایران'
def kb(): return InlineKeyboardMarkup([[InlineKeyboardButton('🏠 خانه‌ها',callback_data='divar:list:house'),InlineKeyboardButton('🌍 زمین‌ها',callback_data='divar:list:land')],[InlineKeyboardButton('📋 آگهی‌های من',callback_data='divar:mine')]])
async def divar_text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE): await update.message.reply_text('🧱 دیوار ایران\n\nاز دسته‌بندی‌ها انتخاب کن:',reply_markup=kb())
async def callback(update,context):
 q=update.callback_query; await q.answer(); svc=get_services(context); parts=q.data.split(':')
 try:
  if parts[1]=='mine': rows=await svc.divar.mine(update.effective_user.id); text='📋 آگهی‌های من\n\n'+'\n'.join(f'#{r.id} {r.asset_type} • {r.price:,} تومان' for r in rows) or 'آگهی فعالی نداری.'
  else:
   rows,total=await svc.divar.search(typ=parts[2]); text='🧱 آگهی‌ها\n\n'+'\n'.join(f'#{r.id} {r.asset_type} • {r.price:,} تومان' for r in rows) or 'برای این دسته آگهی‌ای پیدا نشد.'
  await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 دیوار ایران',callback_data='divar:menu')]]))
 except Exception: await q.edit_message_text('فعلاً نمایش آگهی‌ها ممکن نیست.')
