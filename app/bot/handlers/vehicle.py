from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from app.bot.context import get_services
TRIGGER='نمایشگاه ماشین حاج ممد'
def menu():return InlineKeyboardMarkup([[InlineKeyboardButton('🚘 خرید ماشین',callback_data='cars:catalog'),InlineKeyboardButton('🚗 ماشین‌های من',callback_data='cars:mine')]])
async def text(update,context):await update.message.reply_text('🚗 نمایشگاه ماشین حاج ممد\n\nچه کاری انجام بدیم؟',reply_markup=menu())
async def callback(update,context):
 q=update.callback_query;await q.answer();svc=get_services(context);p=q.data.split(':');
 try:
  if p[1]=='catalog':
   rows=await svc.vehicles.catalog();txt='🚘 ماشین‌های موجود:\n\n'; kb=[]
   for r in rows:kb.append([InlineKeyboardButton(f'{r.name} • {r.price:,} تومان',callback_data=f'cars:buy:{r.key}')])
   await q.edit_message_text(txt,reply_markup=InlineKeyboardMarkup(kb));return
  if p[1]=='mine':
   rows=await svc.vehicles.mine(update.effective_user.id);await q.edit_message_text('🚗 ماشین‌های من\n\n'+('\n'.join(f'🚗 خودرو #{r.id} • {r.purchase_price:,} تومان' for r in rows) or 'هنوز ماشینی نداری.'),reply_markup=menu());return
  if p[1]=='buy':
   m=next((x for x in await svc.vehicles.catalog() if x.key==p[2]),None)
   await q.edit_message_text(f'🚗 {m.name}\n\n💰 قیمت: {m.price:,} تومان\n\nمطمئنی می‌خوای بخری؟',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ خرید',callback_data=f'cars:confirm:{m.key}'),InlineKeyboardButton('❌ انصراف',callback_data='cars:catalog')]]));return
  if p[1]=='confirm':
   r,m=await svc.vehicles.purchase(update.effective_user.id,p[2]);await q.edit_message_text(f'مبارکه! 🚗 {m.name} به ماشین‌هات اضافه شد.');return
 except Exception: await q.edit_message_text('خرید انجام نشد؛ موجودی حسابت یا وضعیت خودرو را بررسی کن.')
