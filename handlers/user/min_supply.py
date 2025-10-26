from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from utils.custom_filters import IsUserExistFilter
from handlers.user.autobuy import filter_details, create_callback_autobuy
from language import LanguageService
from services.filter import FilterService

min_supply_router = Router()

class MinSupplyCallback(CallbackData, prefix="min_supply"):
  session_id: int
  filter_id: int
  min_supply: int

def create_callback_min_supply(session_id: int, filter_id: int, min_supply: int):
  return MinSupplyCallback(session_id=session_id, filter_id=filter_id, min_supply=min_supply).pack()

@min_supply_router.callback_query(MinSupplyCallback.filter(), IsUserExistFilter())
async def min_supply(callback: CallbackQuery, state: FSMContext, callback_data: MinSupplyCallback):
  await FilterService.set_min_supply(callback_data.filter_id, callback_data.min_supply)
  data_str = create_callback_autobuy(2, session_id=callback_data.session_id, filter_id=callback_data.filter_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await filter_details(new_callback, state)