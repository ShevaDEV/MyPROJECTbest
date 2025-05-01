import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv, find_dotenv
from dabase.database import db_instance
from middleware.check_user import CheckUserMiddleware
from scheduler_jobs import start_scheduler
from startup import on_startup, on_shutdown

# 🔹 Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger('aiohttp').setLevel(logging.DEBUG)  # Отладка для aiohttp

# 🔹 Загрузка переменных окружения
load_dotenv(find_dotenv())

# 🔹 Инициализация бота и диспетчера
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# ✅ Добавляем middleware
dp.update.middleware(CheckUserMiddleware())
dp.chat_member.middleware(CheckUserMiddleware())

# 🔹 Подключаем и регистрируем роутеры
from handlers.usershand.user_private import router
from handlers.cardshand.dobcards import dobcards_router
from handlers.cardshand.cardsall import cardsall_router
from handlers.cardshand.cardreceive import cardreceive_router
from handlers.usershand.referal import referal_router
from handlers.satefy.warn import warn_router
from handlers.satefy.mute import mute_router
from handlers.satefy.ban import ban_router
from handlers.satefy.event_users import event_router
from handlers.usershand.list_users import list_router
from kbds.cardspagination import cardspagination_router
from promo.promocode import promocode_router
from handlers.usershand.promocode_add import admin_router
from handlers.usershand.profil import profile_router
from cards.universe_choice import universechoice_router
from handlers.usershand.leaderboards import leaderboard_router
from handlers.usershand.dailyreward import dailyreward_router
from handlers.usershand.profile_callbacks import profile_callbacks_router
from cards.shop import shop_router
from cards.admin_pagination import admin_pagination_router
from cards.shop_callbacks import shop_callbacks_router
from cards.admincards import admincards_router
from handlers.usershand.admintoggleuniverse import admin_universe_router
from cards.admincardedit import admincardedit_router
from admin.universe_check import universecheck_router
from admin.adduniverse import adduniverse_router
from handlers.usershand.change_universe import change_universe_router

# ✅ Регистрируем роутеры
dp.include_router(router)
dp.include_router(list_router)
dp.include_router(warn_router)
dp.include_router(mute_router)
dp.include_router(ban_router)
dp.include_router(event_router)
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
dp.include_router(admin_universe_router)
dp.include_router(admincards_router)
dp.include_router(admin_pagination_router)
dp.include_router(admincardedit_router)
dp.include_router(universecheck_router)
dp.include_router(adduniverse_router)
dp.include_router(referal_router)

async def main():
    """Основная асинхронная функция"""
    await on_startup(bot)

    # ✅ Запускаем планировщик (с передачей `bot`)
    start_scheduler(bot)

    # ✅ Удаление webhook (если был установлен)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(0.1)  # Задержка после запроса
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при удалении webhook: {e}")

    try:
        await dp.start_polling(bot, allowed_updates=["message", "edited_message", "callback_query"])
    finally:
        await on_shutdown(bot)

if __name__ == "__main__":
    print("🚀 Запуск бота...")

    try:
        asyncio.run(main())  # ✅ Безопасный запуск asyncio
    except KeyboardInterrupt:
        print("⛔ Бот остановлен вручную")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")