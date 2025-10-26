from typing import Union
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from utils.custom_filters import IsUserExistFilter
from handlers.user.autobuy import filter_details, create_callback_autobuy
from language import LanguageService
from services.filter import FilterService

amount_stars_router = Router()

class AmountStarsCallback(CallbackData, prefix="amount_stars"):
  session_id: int
  filter_id: int
  amount_stars: int

def create_callback_amount_stars(session_id: int, filter_id: int, amount_stars: int):
  return AmountStarsCallback(session_id=session_id, filter_id=filter_id, amount_stars=amount_stars).pack()

@amount_stars_router.callback_query(AmountStarsCallback.filter(), IsUserExistFilter())
async def amount_stars(callback: CallbackQuery, state: FSMContext, callback_data: AmountStarsCallback):
  await FilterService.set_amount_stars(callback_data.filter_id, callback_data.amount_stars)
  data_str = create_callback_autobuy(2, session_id=callback_data.session_id, filter_id=callback_data.filter_id)

  new_callback = callback.model_copy(update={"data": data_str})
  return await filter_details(new_callback, state)