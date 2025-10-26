from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from utils.custom_filters import IsUserExistFilter
from handlers.user.autobuy import filter_details, create_callback_autobuy
from language import LanguageService
from services.filter import FilterService

min_price_router = Router()

class MinPriceCallback(CallbackData, prefix="min_price"):
  session_id: int
  filter_id: int
  min_price: int

def create_callback_min_price(session_id: int, filter_id: int, min_price: int):
  return MinPriceCallback(session_id=session_id, filter_id=filter_id, min_price=min_price).pack()

@min_price_router.callback_query(MinPriceCallback.filter(), IsUserExistFilter())
async def min_price(callback: CallbackQuery, state: FSMContext, callback_data: MinPriceCallback):
  await FilterService.set_min_price(callback_data.filter_id, callback_data.min_price)
  data_str = create_callback_autobuy(2, session_id=callback_data.session_id, filter_id=callback_data.filter_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await filter_details(new_callback, state)