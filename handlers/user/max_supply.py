from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from utils.custom_filters import IsUserExistFilter
from handlers.user.autobuy import filter_details, create_callback_autobuy
from language import LanguageService
from services.filter import FilterService

max_supply_router = Router()

class MaxSupplyCallback(CallbackData, prefix="max_supply"):
  session_id: int
  filter_id: int
  max_supply: int

def create_callback_max_supply(session_id: int, filter_id: int, max_supply: int):
  return MaxSupplyCallback(session_id=session_id, filter_id=filter_id, max_supply=max_supply).pack()

@max_supply_router.callback_query(MaxSupplyCallback.filter(), IsUserExistFilter())
async def max_supply(callback: CallbackQuery, state: FSMContext, callback_data: MaxSupplyCallback):
  await FilterService.set_max_supply(callback_data.filter_id, callback_data.max_supply)
  data_str = create_callback_autobuy(2, session_id=callback_data.session_id, filter_id=callback_data.filter_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await filter_details(new_callback, state)