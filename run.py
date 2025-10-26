from aiogram import Router

from bot import dp, main
import logging

from handlers.user.start import start_router
from handlers.user.my_profile import my_profile_router
from handlers.user.accounts import accounts_router
from handlers.user.autobuy import autobuy_router
from handlers.user.min_price import min_price_router
from handlers.user.max_price import max_price_router
from handlers.user.min_supply import min_supply_router
from handlers.user.max_supply import max_supply_router
from handlers.user.subscription import subscription_router
from handlers.user.amount_stars import amount_stars_router

logging.basicConfig(level=logging.INFO)

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(my_profile_router)
main_router.include_router(accounts_router)
main_router.include_router(autobuy_router)
main_router.include_router(min_price_router)
main_router.include_router(max_price_router)
main_router.include_router(min_supply_router)
main_router.include_router(max_supply_router)
main_router.include_router(subscription_router)
main_router.include_router(amount_stars_router)
dp.include_router(main_router)

if __name__ == '__main__':
    main()