from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from handlers.common.common import get_back_to_menu_button, send_message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.custom_filters import IsUserExistFilter, UserSubscriptionValidFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter
from utils.session import hide_session_string
from services.session import SessionService
from models.session import Session
from language import LanguageService
from services.user import UserService
from services.filter import FilterService
from bot import bot
import traceback
import logging
import inspect
import asyncio

logger = logging.getLogger(__name__)

autobuy_router = Router()

class AutobuyCallback(CallbackData, prefix="autobuy"):
  level: int
  session_id: int
  filter_id: int

class AutobuyStates(StatesGroup):
  min_price = State()
  max_price = State()
  min_supply = State()
  max_supply = State()
  amount_stars = State()
  recipient = State()

def create_callback_autobuy(level: int, session_id: int = -1, filter_id: int = -1):
  return AutobuyCallback(level=level, session_id=session_id, filter_id=filter_id).pack()

async def autobuy(message: Union[Message, CallbackQuery]):
  telegram_id = message.chat.id if isinstance(message, Message) else message.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  is_valid = await UserService.is_subscription_valid(telegram_id)
  if not is_valid:
    from handlers.user.subscription import create_callback_subscription
    msg = LanguageService.get_translation(language_code, "not_subscribed")
    subscription_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "subscribe"), callback_data=create_callback_subscription(0))
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[subscription_button], [get_back_to_menu_button(language_code)]])
    await send_message(message, msg, reply_markup=markup)
    return
  session_count = await UserService.sessions_amount(telegram_id)
  if session_count <= 0:
    msg = LanguageService.get_translation(language_code, "not_enought_accounts")
    markup = await get_accounts_markup(telegram_id, language_code)
    await send_message(message, msg, reply_markup=markup)
    return
  msg = LanguageService.get_translation(language_code, "autobuy_description")
  markup = await get_accounts_markup(telegram_id, language_code)
  
  await send_message(message, msg, reply_markup=markup)

async def get_accounts_markup(telegram_id: int, language_code: str):
  keyboard_builder = InlineKeyboardBuilder()
  session_buttons = []

  user = await UserService.get_by_tgid(telegram_id)
  for session in user.sessions:
    status = "🟢" if await SessionService.is_active(session.id) else "🔴"
    display = f"{status} {hide_session_string(session.session_string)}"
    session_buttons.append(types.InlineKeyboardButton(text=display, callback_data=create_callback_autobuy(1, session_id=session.id)))

  keyboard_builder.add(*session_buttons)
  keyboard_builder.add(get_back_to_menu_button(language_code))
  adj = len(session_buttons) * [1] + [1]
  keyboard_builder.adjust(*adj)
  
  return keyboard_builder.as_markup()

async def session_details(callback: CallbackQuery):
  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  session = await SessionService.get_by_id(unpacked_callback.session_id)
  if session is None:
    return
  
  msg = LanguageService.get_translation(language_code, "autobuy_description")
  markup = await get_session_details_markup(telegram_id, session, language_code)
  await send_message(callback, msg, reply_markup=markup)

async def get_session_details_markup(telegram_id: int, session: Session, language_code: str):
  keyboard_builder = InlineKeyboardBuilder()
  filter_buttons = []
  for filter in session.filters:
    status = "🟢" if filter.active else "🔴"
    max_price = "∞" if filter.max_price < 0 else f"{filter.max_price}"
    price_range = f"{filter.min_price} -> {max_price}"
    max_supply = "∞" if filter.max_supply < 0 else f"{filter.max_supply}"
    supply_range = f"{filter.min_supply} -> {max_supply}"
    display = f"{status} | {price_range} | {supply_range}"

    filter_buttons.append(types.InlineKeyboardButton(text=display, callback_data=create_callback_autobuy(2, session_id=session.id, filter_id=filter.id)))

  keyboard_builder.add(*filter_buttons)
  if await SessionService.new_filter_available(session.id):
    add_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "add"), callback_data=create_callback_autobuy(3, session_id=session.id))
    back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(0))
    keyboard_builder.add(add_button, back_button)
    adj = len(filter_buttons) * [1] + [2]
    keyboard_builder.adjust(*adj)
  else:
    back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(0))
    keyboard_builder.add(back_button)
    adj = len(filter_buttons) * [1] + [1]
    keyboard_builder.adjust(*adj)
  
  return keyboard_builder.as_markup()

async def filter_details(callback: CallbackQuery | None, state: FSMContext, session_id: int | None = None, filter_id: int | None = None, username: str | None = None, chat_id: int | None = None, msg_id: int | None = None):
  await state.clear()  
  if all([session_id, filter_id, username, chat_id, msg_id]):
    telegram_id = chat_id
  else:
    telegram_id = callback.from_user.id
    unpacked_callback = AutobuyCallback.unpack(callback.data)
    filter_id = unpacked_callback.filter_id
    session_id = unpacked_callback.session_id
    username = callback.from_user.username

  language_code = await UserService.get_language_code(telegram_id)

  f = await FilterService.get_by_id(filter_id)
  if f is None:
    return

  filter_details = LanguageService.get_translation(language_code, "filter_details")
  status_text = LanguageService.get_translation(language_code, "status")
  min_price = LanguageService.get_translation(language_code, "min_price")
  max_price = LanguageService.get_translation(language_code, "max_price")
  min_supply = LanguageService.get_translation(language_code, "min_supply")
  max_supply = LanguageService.get_translation(language_code, "max_supply")
  amount_stars = LanguageService.get_translation(language_code, "amount_stars")
  filter_recipient = LanguageService.get_translation(language_code, "filter_recipient")
  status = "🟢" if f.active else "🔴"
  display_max_price = "∞" if f.max_price < 0 else f"{f.max_price}"
  display_max_supply = "∞" if f.max_supply < 0 else f"{f.max_supply}"
  display_amount_stars = "<code>unlimited</code>" if f.amount_stars < 0 else f"{f.amount_stars} ⭐"
  msg = (f"{filter_details}\n\n"
         f"{status_text}: {status}\n\n"
         f"{min_price}: {f.min_price} ⭐\n"
         f"{max_price}: {display_max_price} ⭐\n"
         f"{min_supply}: {f.min_supply}\n"
         f"{max_supply}: {display_max_supply}\n"
         f"{amount_stars}: {display_amount_stars}\n\n"
         f"{filter_recipient}: <code>{username if f.recipient_telegram_id == telegram_id else f.recipient_telegram_id}</code>")
 
  status_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_status"), callback_data=create_callback_autobuy(5, session_id=session_id, filter_id=filter_id))
  min_price_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_min_price"), callback_data=create_callback_autobuy(6, session_id=session_id, filter_id=filter_id))
  max_price_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_max_price"), callback_data=create_callback_autobuy(7, session_id=session_id, filter_id=filter_id))
  min_supply_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_min_supply"), callback_data=create_callback_autobuy(8, session_id=session_id, filter_id=filter_id))
  max_supply_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_max_supply"), callback_data=create_callback_autobuy(9, session_id=session_id, filter_id=filter_id))
  amount_stars_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_amount_stars"), callback_data=create_callback_autobuy(10, session_id=session_id, filter_id=filter_id))
  recipient_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "set_recipient"), callback_data=create_callback_autobuy(11, session_id=session_id, filter_id=filter_id))
  delete_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "delete"), callback_data=create_callback_autobuy(4, session_id=session_id, filter_id=filter_id))

  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(1, session_id=session_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[status_button], [min_price_button, max_price_button], [min_supply_button, max_supply_button], [amount_stars_button, recipient_button], [delete_button, back_button]])
  if all([session_id, filter_id, username, chat_id, msg_id]):
    try:
      await bot.edit_message_text(msg, message_id=msg_id, chat_id=chat_id, reply_markup=markup)
    except Exception:
      await bot.send_message(chat_id, msg, reply_markup=markup)
  else:
    await send_message(callback, msg, reply_markup=markup)

async def set_status(callback: CallbackQuery, state: FSMContext):
  unpacked_callback = AutobuyCallback.unpack(callback.data)

  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return
  
  await FilterService.set_status(f.id, not f.active)
  return await filter_details(callback, state)

async def set_min_price(callback: CallbackQuery, state: FSMContext):
  from handlers.user.min_price import create_callback_min_price

  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return

  set_min_price_title = LanguageService.get_translation(language_code, "set_min_price_title")
  set_min_price_details = LanguageService.get_translation(language_code, "set_min_price_details")
  msg = (f"{set_min_price_title}: {f.min_price} ⭐\n\n"
         f"<i>{set_min_price_details}</i>")
  
  button_100 = types.InlineKeyboardButton(text="100", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 100))
  button_200 = types.InlineKeyboardButton(text="200", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 200))
  button_500 = types.InlineKeyboardButton(text="500", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 500))
  button_1000 = types.InlineKeyboardButton(text="1000", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 1000))
  button_2000 = types.InlineKeyboardButton(text="2000", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 2000))
  button_5000 = types.InlineKeyboardButton(text="5000", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 5000))
  button_10000 = types.InlineKeyboardButton(text="10000", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 10000))
  button_20000 = types.InlineKeyboardButton(text="20000", callback_data=create_callback_min_price(unpacked_callback.session_id, unpacked_callback.filter_id, 20000))
  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(2, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[button_100, button_200], [button_500, button_1000], [button_2000, button_5000], [button_10000, button_20000], [back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await state.update_data(msg_id=callback.message.message_id, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id)
  await state.set_state(AutobuyStates.min_price)

@autobuy_router.message(IsUserExistFilter(), UserSubscriptionValidFilter(), StateFilter(AutobuyStates.min_price))
async def get_min_price(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  session_id = data.get("session_id")
  filter_id = data.get("filter_id")
  telegram_id = message.chat.id

  if not all([msg_id, session_id, filter_id]):
    logger.warning(f"[{telegram_id}] invalid min_price data: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  min_price_unsafe = message.text or ""

  try:
    min_price = int(min_price_unsafe)
  except ValueError:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.min_price), bot.delete_message(message.chat.id, message.message_id))
    return
  
  if min_price < 0:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.min_price), bot.delete_message(message.chat.id, message.message_id))
    return

  await FilterService.set_min_price(filter_id, min_price)
  await bot.delete_message(message.chat.id, message.message_id)
  return await filter_details(None, state, session_id=session_id, filter_id=filter_id, username=message.from_user.username, chat_id=message.chat.id, msg_id=msg_id)

async def set_max_price(callback: CallbackQuery, state: FSMContext):
  from handlers.user.max_price import create_callback_max_price

  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return

  display_max_price = "∞" if f.max_price < 0 else f"{f.max_price}"
  set_max_price_title = LanguageService.get_translation(language_code, "set_max_price_title")
  set_max_price_details = LanguageService.get_translation(language_code, "set_max_price_details")
  msg = (f"{set_max_price_title}: {display_max_price} ⭐\n\n"
         f"<i>{set_max_price_details}</i>")
  
  button_100 = types.InlineKeyboardButton(text="100", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 100))
  button_200 = types.InlineKeyboardButton(text="200", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 200))
  button_500 = types.InlineKeyboardButton(text="500", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 500))
  button_1000 = types.InlineKeyboardButton(text="1000", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 1000))
  button_2000 = types.InlineKeyboardButton(text="2000", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 2000))
  button_5000 = types.InlineKeyboardButton(text="5000", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 5000))
  button_10000 = types.InlineKeyboardButton(text="10000", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 10000))
  button_20000 = types.InlineKeyboardButton(text="20000", callback_data=create_callback_max_price(unpacked_callback.session_id, unpacked_callback.filter_id, 20000))
  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(2, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[button_100, button_200], [button_500, button_1000], [button_2000, button_5000], [button_10000, button_20000], [back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await state.update_data(msg_id=callback.message.message_id, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id)
  await state.set_state(AutobuyStates.max_price)

@autobuy_router.message(IsUserExistFilter(), UserSubscriptionValidFilter(), StateFilter(AutobuyStates.max_price))
async def get_max_price(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  session_id = data.get("session_id")
  filter_id = data.get("filter_id")
  telegram_id = message.chat.id

  if not all([msg_id, session_id, filter_id]):
    logger.warning(f"[{telegram_id}] invalid max_price data: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  max_price_unsafe = message.text or ""

  try:
    max_price = int(max_price_unsafe)
  except ValueError:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.max_price), bot.delete_message(message.chat.id, message.message_id))
    return
  
  if max_price < -1:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.max_price), bot.delete_message(message.chat.id, message.message_id))
    return

  await FilterService.set_max_price(filter_id, max_price)
  await bot.delete_message(message.chat.id, message.message_id)
  return await filter_details(None, state, session_id=session_id, filter_id=filter_id, username=message.from_user.username, chat_id=message.chat.id, msg_id=msg_id)

async def set_min_supply(callback: CallbackQuery, state: FSMContext):
  from handlers.user.min_supply import create_callback_min_supply

  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return

  set_min_supply_title = LanguageService.get_translation(language_code, "set_min_supply_title")
  set_min_supply_details = LanguageService.get_translation(language_code, "set_min_supply_details")
  msg = (f"{set_min_supply_title}: {f.min_supply}\n\n"
         f"<i>{set_min_supply_details}</i>")
  
  button_500000 = types.InlineKeyboardButton(text="500000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 500000))
  button_200000 = types.InlineKeyboardButton(text="200000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 200000))
  button_100000 = types.InlineKeyboardButton(text="100000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 100000))
  button_50000 = types.InlineKeyboardButton(text="50000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 50000))
  button_20000 = types.InlineKeyboardButton(text="20000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 20000))
  button_10000 = types.InlineKeyboardButton(text="10000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 10000))
  button_5000 = types.InlineKeyboardButton(text="5000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 5000))
  button_2000 = types.InlineKeyboardButton(text="2000", callback_data=create_callback_min_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 2000))
  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(2, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[button_500000, button_200000], [button_100000, button_50000], [button_20000, button_10000], [button_5000, button_2000], [back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await state.update_data(msg_id=callback.message.message_id, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id)
  await state.set_state(AutobuyStates.min_supply)

@autobuy_router.message(IsUserExistFilter(), UserSubscriptionValidFilter(), StateFilter(AutobuyStates.min_supply))
async def get_min_supply(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  session_id = data.get("session_id")
  filter_id = data.get("filter_id")
  telegram_id = message.chat.id

  if not all([msg_id, session_id, filter_id]):
    logger.warning(f"[{telegram_id}] invalid min_supply data: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  min_supply_unsafe = message.text or ""

  try:
    min_supply = int(min_supply_unsafe)
  except ValueError:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.min_supply), bot.delete_message(message.chat.id, message.message_id))
    return
  
  if min_supply < 0:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.min_supply), bot.delete_message(message.chat.id, message.message_id))
    return

  await FilterService.set_min_supply(filter_id, min_supply)
  await bot.delete_message(message.chat.id, message.message_id)
  return await filter_details(None, state, session_id=session_id, filter_id=filter_id, username=message.from_user.username, chat_id=message.chat.id, msg_id=msg_id)

async def set_max_supply(callback: CallbackQuery, state: FSMContext):
  from handlers.user.max_supply import create_callback_max_supply

  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return

  display_max_supply = "∞" if f.max_supply < 0 else f"{f.max_supply}"
  set_max_supply_title = LanguageService.get_translation(language_code, "set_max_supply_title")
  set_max_supply_details = LanguageService.get_translation(language_code, "set_max_supply_details")
  msg = (f"{set_max_supply_title}: {display_max_supply} ⭐\n\n"
         f"<i>{set_max_supply_details}</i>")
  
  button_500000 = types.InlineKeyboardButton(text="500000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 500000))
  button_200000 = types.InlineKeyboardButton(text="200000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 200000))
  button_100000 = types.InlineKeyboardButton(text="100000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 100000))
  button_50000 = types.InlineKeyboardButton(text="50000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 50000))
  button_20000 = types.InlineKeyboardButton(text="20000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 20000))
  button_10000 = types.InlineKeyboardButton(text="10000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 10000))
  button_5000 = types.InlineKeyboardButton(text="5000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 5000))
  button_2000 = types.InlineKeyboardButton(text="2000", callback_data=create_callback_max_supply(unpacked_callback.session_id, unpacked_callback.filter_id, 2000))
  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(2, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[button_500000, button_200000], [button_100000, button_50000], [button_20000, button_10000], [button_5000, button_2000], [back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await state.update_data(msg_id=callback.message.message_id, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id)
  await state.set_state(AutobuyStates.max_supply)

@autobuy_router.message(IsUserExistFilter(), UserSubscriptionValidFilter(), StateFilter(AutobuyStates.max_supply))
async def get_max_supply(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  session_id = data.get("session_id")
  filter_id = data.get("filter_id")
  telegram_id = message.chat.id

  if not all([msg_id, session_id, filter_id]):
    logger.warning(f"[{telegram_id}] invalid max_supply data: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  max_supply_unsafe = message.text or ""

  try:
    max_supply = int(max_supply_unsafe)
  except ValueError:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.max_supply), bot.delete_message(message.chat.id, message.message_id))
    return
  
  if max_supply < -1:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.max_supply), bot.delete_message(message.chat.id, message.message_id))
    return

  await FilterService.set_max_supply(filter_id, max_supply)
  await bot.delete_message(message.chat.id, message.message_id)
  return await filter_details(None, state, session_id=session_id, filter_id=filter_id, username=message.from_user.username, chat_id=message.chat.id, msg_id=msg_id)

async def set_amount_stars(callback: CallbackQuery, state: FSMContext):
  from handlers.user.amount_stars import create_callback_amount_stars

  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return

  display_amount_stars = "unlimited" if f.amount_stars < 0 else f"{f.amount_stars}"
  set_amount_stars_title = LanguageService.get_translation(language_code, "set_amount_stars_title")
  set_amount_stars_details = LanguageService.get_translation(language_code, "set_amount_stars_details")
  msg = (f"{set_amount_stars_title}: {display_amount_stars} ⭐\n\n"
         f"<i>{set_amount_stars_details}</i>")
  
  button_100 = types.InlineKeyboardButton(text="100", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 100))
  button_200 = types.InlineKeyboardButton(text="200", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 200))
  button_500 = types.InlineKeyboardButton(text="500", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 500))
  button_1000 = types.InlineKeyboardButton(text="1000", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 1000))
  button_2000 = types.InlineKeyboardButton(text="2000", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 2000))
  button_5000 = types.InlineKeyboardButton(text="5000", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 5000))
  button_10000 = types.InlineKeyboardButton(text="10000", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 10000))
  button_20000 = types.InlineKeyboardButton(text="20000", callback_data=create_callback_amount_stars(unpacked_callback.session_id, unpacked_callback.filter_id, 20000))
  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(2, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[button_100, button_200], [button_500, button_1000], [button_2000, button_5000], [button_10000, button_20000], [back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await state.update_data(msg_id=callback.message.message_id, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id)
  await state.set_state(AutobuyStates.amount_stars)

@autobuy_router.message(IsUserExistFilter(), UserSubscriptionValidFilter(), StateFilter(AutobuyStates.amount_stars))
async def get_amount_stars(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  session_id = data.get("session_id")
  filter_id = data.get("filter_id")
  telegram_id = message.chat.id

  if not all([msg_id, session_id, filter_id]):
    logger.warning(f"[{telegram_id}] invalid amount_stars data: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  amount_stars_unsafe = message.text or ""

  try:
    amount_stars = int(amount_stars_unsafe)
  except ValueError:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.amount_stars), bot.delete_message(message.chat.id, message.message_id))
    return
  
  if amount_stars < -1:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.amount_stars), bot.delete_message(message.chat.id, message.message_id))
    return

  await FilterService.set_amount_stars(filter_id, amount_stars)
  await bot.delete_message(message.chat.id, message.message_id)
  return await filter_details(None, state, session_id=session_id, filter_id=filter_id, username=message.from_user.username, chat_id=message.chat.id, msg_id=msg_id)

async def set_recipient_telegram_id(callback: CallbackQuery, state: FSMContext):
  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  f = await FilterService.get_by_id(unpacked_callback.filter_id)
  if f is None:
    return

  display_recipient_telegram_id = callback.from_user.username if f.recipient_telegram_id == telegram_id else f.recipient_telegram_id
  set_recipient_telegram_id_title = LanguageService.get_translation(language_code, "set_recipient_telegram_id_title")
  set_recipient_telegram_id_details = LanguageService.get_translation(language_code, "set_recipient_telegram_id_details")
  link_details = LanguageService.get_translation(language_code, "link_details")
  msg = (f"{set_recipient_telegram_id_title}: <code>{display_recipient_telegram_id}</code>\n\n"
         f"<i>{set_recipient_telegram_id_details}</i>\n\n"
         f"{link_details}")
  
  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_autobuy(2, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await state.update_data(msg_id=callback.message.message_id, session_id=unpacked_callback.session_id, filter_id=unpacked_callback.filter_id)
  await state.set_state(AutobuyStates.recipient)

@autobuy_router.message(IsUserExistFilter(), UserSubscriptionValidFilter(), StateFilter(AutobuyStates.recipient))
async def get_recipient_telegram_id(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  session_id = data.get("session_id")
  filter_id = data.get("filter_id")
  telegram_id = message.chat.id

  if not all([msg_id, session_id, filter_id]):
    logger.warning(f"[{telegram_id}] invalid recipient_telegram_id data: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  session = await SessionService.get_by_id(session_id)
  if session is None:
    logger.warning(f"[{telegram_id}] invalid recipient_telegram_id session: {data}")
    await bot.delete_message(message.chat.id, message.message_id)
    return
  
  recipient_telegram_id_unsafe = message.text or ""

  try:
    recipient_telegram_id = int(recipient_telegram_id_unsafe)
  except ValueError:
    await asyncio.gather(state.update_data(msg_id=msg_id, session_id=session_id, filter_id=filter_id), state.set_state(AutobuyStates.recipient), bot.delete_message(message.chat.id, message.message_id))
    return

  await FilterService.set_recipient_telegram_id(filter_id, recipient_telegram_id)
  await bot.delete_message(message.chat.id, message.message_id)
  return await filter_details(None, state, session_id=session_id, filter_id=filter_id, username=message.from_user.username, chat_id=message.chat.id, msg_id=msg_id)
  
async def add_filter(callback: CallbackQuery, state: FSMContext):
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  session = await SessionService.get_by_id(unpacked_callback.session_id)
  if session is None:
    return
  
  user = await UserService.get_by_id(session.user_id)
  if await SessionService.new_filter_available(session.id):
    f_id = await SessionService.add_filter(session.id, user.telegram_id)
  data_str = create_callback_autobuy(2, session_id=session.id, filter_id=f_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await filter_details(new_callback, state)

async def delete_filter(callback: CallbackQuery, state: FSMContext):
  unpacked_callback = AutobuyCallback.unpack(callback.data)
  
  await SessionService.remove_filter(unpacked_callback.session_id, unpacked_callback.filter_id)
  data_str = create_callback_autobuy(1, session_id=unpacked_callback.session_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await session_details(new_callback)

@autobuy_router.callback_query(AutobuyCallback.filter(), IsUserExistFilter())
async def navigate(callback: CallbackQuery, state: FSMContext, callback_data: AutobuyCallback):
  current_level = callback_data.level

  levels = {
    0: autobuy,
    1: session_details,
    2: filter_details,
    3: add_filter,
    4: delete_filter,
    5: set_status,
    6: set_min_price,
    7: set_max_price,
    8: set_min_supply,
    9: set_max_supply,
    10: set_amount_stars,
    11: set_recipient_telegram_id
  }
  is_valid = await UserService.is_subscription_valid(callback.from_user.id)
  if current_level != 0 and not is_valid:
    return

  current_level_function = levels[current_level]
  if inspect.getfullargspec(current_level_function).annotations.get("state") == FSMContext:
    await current_level_function(callback, state)
  else:
    await current_level_function(callback)