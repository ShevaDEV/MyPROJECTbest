import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import find_dotenv, load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from dabase.database import init_db
from middleware.check_user import CheckUserMiddleware
from handlers.usershand.user_private import router
from handlers.cardshand.dobcards import dobcards_router
from handlers.cardshand.cardsall import cardsall_router
from handlers.cardshand.cardreceive import cardreceive_router
from handlers.usershand.referal import referal_router
from kbds.cardspagination import cardspagination_router
from promo.promocode import promocode_router
from handlers.usershand.admin import admin_router
from handlers.usershand.profil import profile_router
from cards.universe_choice import universechoice_router
from handlers.usershand.leaderboards import leaderboard_router
from handlers.usershand.dailyreward import dailyreward_router
from handlers.usershand.profile_callbacks import profile_callbacks_router
from cards.shop import shop_router, update_all_shops
from cards.admin_pagination import admin_pagination_router
from cards.shop_callbacks import shop_callbacks_router
from cards.admincards import admincards_router
from cards.admincardedit import admincardedit_router
from admin.universe_check import universecheck_router
from admin.adduniverse import adduniverse_router
from handlers.usershand.change_universe import change_universe_router


load_dotenv(find_dotenv())
init_db()

ALLOWED_UPDATES = ["message", "edited_message", "callback_query"]


bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Инициализация планировщика
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
scheduler.add_job(update_all_shops, 'cron', hour=0, minute=0, misfire_grace_time=60)

dp.update.middleware(CheckUserMiddleware())

# Регистрация всех роутеров
dp.include_router(router)
dp.include_router(dobcards_router)
dp.include_router(cardsall_router)
dp.include_router(cardreceive_router)
dp.include_router(cardspagination_router)
dp.include_router(admin_router)
dp.include_router(change_universe_router)
dp.include_router(universechoice_router)
dp.include_router(profile_router)
dp.include_router(leaderboard_router)
dp.include_router(promocode_router)
dp.include_router(dailyreward_router)
dp.include_router(profile_callbacks_router)
dp.include_router(shop_router)
dp.include_router(shop_callbacks_router)
dp.include_router(admincards_router)
dp.include_router(admin_pagination_router)
dp.include_router(admincardedit_router)
dp.include_router(universecheck_router)
dp.include_router(adduniverse_router)
dp.include_router(referal_router)

async def main():
    scheduler.start()  # Запуск планировщика внутри event loop
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)

if __name__ == "__main__":
    asyncio.run(main())
    