from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from handlers.common.common import get_back_to_menu_button, send_message
from utils.custom_filters import IsUserExistFilter
from language import LanguageService
from services.user import UserService

my_profile_router = Router()

class MyProfileCallback(CallbackData, prefix="my_profile"):
  level: int

def create_callback_profile(level: int):
  return MyProfileCallback(level=level).pack()

async def get_my_profile_message(telegram_id: int, language_code: str):
  id_str = LanguageService.get_translation(language_code, "id")
  referrals_str = LanguageService.get_translation(language_code, "referrals")
  msg = f'⬜ <b>{id_str}</b>: <code>{telegram_id}</code>'

  valid_subscription = await UserService.is_subscription_valid(telegram_id)
  if valid_subscription:
    ex = await UserService.subscription_expiration_date(telegram_id)
    formated_ex = ex.strftime("%m.%d.%Y")
    subscription_expires_str = LanguageService.get_translation(language_code, "subscription_expires")
    msg += f"\n⬜ <b>{subscription_expires_str}</b>: {formated_ex}"

  msg += f'\n⬜ <b>{referrals_str}</b>: 0'
  return msg

async def my_profile(message: Union[Message, CallbackQuery]):
  from handlers.user.subscription import create_callback_subscription
  telegram_id = message.chat.id if isinstance(message, Message) else message.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  
  content = await get_my_profile_message(telegram_id, language_code)
  referrals_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "referrals_button"), callback_data=create_callback_profile(2))
  language_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "language"), callback_data=create_callback_profile(1))
  if await UserService.is_subscription_valid(telegram_id):
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[referrals_button, language_button], [get_back_to_menu_button(language_code)]])
  else:
    subscription_button = types.InlineKeyboardButton(text=LanguageService.get_translation(language_code, "subscribe"), callback_data=create_callback_subscription(0))
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[subscription_button], [referrals_button, language_button], [get_back_to_menu_button(language_code)]])
  
  await send_message(message, content, reply_markup=markup)

async def language(callback: types.CallbackQuery):
  telegram_id = callback.from_user.id
  language_code = await UserService.get_language_code(telegram_id)
  new_language = LanguageService.get_next_code(language_code)
  await UserService.update_language(telegram_id, new_language)
  await my_profile(callback)

@my_profile_router.callback_query(MyProfileCallback.filter(), IsUserExistFilter())
async def navigate(callback: CallbackQuery, callback_data: MyProfileCallback):
  current_level = callback_data.level

  levels = {
    0: my_profile,
    1: language
  }

  current_level_function = levels[current_level]

  await current_level_function(callback)
