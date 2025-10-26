from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from utils.custom_filters import IsUserExistFilter
from handlers.user.autobuy import filter_details, create_callback_autobuy
from language import LanguageService
from services.filter import FilterService

max_price_router = Router()

class MaxPriceCallback(CallbackData, prefix="max_price"):
  session_id: int
  filter_id: int
  max_price: int

def create_callback_max_price(session_id: int, filter_id: int, max_price: int):
  return MaxPriceCallback(session_id=session_id, filter_id=filter_id, max_price=max_price).pack()

@max_price_router.callback_query(MaxPriceCallback.filter(), IsUserExistFilter())
async def max_price(callback: CallbackQuery, state: FSMContext, callback_data: MaxPriceCallback):
  await FilterService.set_max_price(callback_data.filter_id, callback_data.max_price)
  data_str = create_callback_autobuy(2, session_id=callback_data.session_id, filter_id=callback_data.filter_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await filter_details(new_callback, state)