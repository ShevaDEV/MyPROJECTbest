import pytz
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from cards.shop import update_all_shops
from handlers.satefy.event_users import update_all_users
from handlers.satefy.mute import check_and_remove_mute
from handlers.satefy.ban import check_and_remove_ban

# ✅ Создаём планировщик
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Moscow"))

def start_scheduler(bot):
    """Запуск планировщика (с защитой от повторного запуска)"""
    print("⚠️ Планировщик временно отключен для теста.")
    # if not scheduler.running:  # ✅ Проверяем, запущен ли он уже
    #     scheduler.start()

    #     scheduler.add_job(update_all_shops, "cron", hour=0, minute=0, misfire_grace_time=60)
    #     scheduler.add_job(check_and_remove_mute, "interval", minutes=10, args=[bot])
    #     scheduler.add_job(check_and_remove_ban, "interval", minutes=10, args=[bot])

    #     print("✅ Планировщик запущен!")
    # else:
    #     print("⚠️ Планировщик уже работает, повторный запуск не требуется.")