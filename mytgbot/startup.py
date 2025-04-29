import logging
from aiogram import Bot
from dabase.database import db_instance
from scheduler_jobs import start_scheduler

async def on_startup(bot: Bot):
    """Функция, вызываемая при запуске бота."""
    print("⏳ Запускаем инициализацию БД...")
    await db_instance.init_db()  # ✅ Инициализация БД

    start_scheduler(bot)  # ✅ Запускаем планировщик с передачей bot

    print("✅ База данных готова, бот запущен!")

async def on_shutdown(bot: Bot):
    """Функция, вызываемая при остановке бота."""
    print("⚠️ Остановка бота...")
    try:
        await db_instance.close_db()
    except Exception as e:
        logging.error(f"❌ Ошибка при закрытии БД: {e}")

    try:
        if bot.session:
            logging.info(f"Сессия aiohttp: closed={bot.session.closed}")
            if not bot.session.closed:
                await bot.session.close()
                logging.info("Сессия aiohttp успешно закрыта.")
            else:
                logging.warning("Сессия aiohttp уже закрыта.")
        else:
            logging.warning("Сессия aiohttp отсутствует.")
    except Exception as e:
        logging.error(f"❌ Ошибка при закрытии сессии aiohttp: {e}")

    print("❌ Бот остановлен.")