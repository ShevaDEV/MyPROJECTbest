import asyncio
import logging
import time
from typing import Callable, Any
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance
from aiogram import types

class TelegramQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False

    async def process_queue(self, bot: Bot):
        """Обрабатывает очередь запросов к Telegram API."""
        while self.is_running:
            try:
                request = await self.queue.get()
                if request:
                    try:
                        logging.info(f"⏳ Начало обработки запроса: {request}")
                        result = await asyncio.wait_for(request(), timeout=10.0)
                        logging.info(f"✅ Запрос выполнен успешно: {request}")
                        if isinstance(result, types.Message):
                            chat_id = result.chat.id
                            message_id = result.message_id
                            db = await db_instance.get_connection()  # ✅ Ждём соединение
                            try:
                                async with db.execute(
                                    "SELECT purge_period FROM chat_settings WHERE chat_id = ?",
                                    (chat_id,)
                                ) as cursor:
                                    result_db = await cursor.fetchone()
                                if result_db and result_db["purge_period"] > 0:
                                    await db.execute("""
                                        INSERT OR IGNORE INTO messages (message_id, chat_id, user_id, timestamp)
                                        VALUES (?, ?, ?, ?)
                                    """, (message_id, chat_id, bot.id, int(time.time())))
                                    await db.commit()
                                    logging.info(f"📩 Сообщение бота {message_id} записано для чата {chat_id}")
                            finally:
                                await db.close()  # ✅ Закрываем соединение вручную
                        self.queue.task_done()
                    except asyncio.TimeoutError:
                        logging.error(f"❌ Таймаут при выполнении запроса {request}")
                        self.queue.task_done()
                    except TelegramAPIError as e:
                        logging.error(f"❌ Ошибка Telegram API при выполнении запроса {request}: {e}")
                        self.queue.task_done()
                    except Exception as e:
                        logging.error(f"❌ Неизвестная ошибка при выполнении запроса {request}: {e}")
                        self.queue.task_done()
                    finally:
                        await asyncio.sleep(0.05)  # Задержка для соблюдения лимитов Telegram
            except Exception as e:
                logging.error(f"❌ Ошибка в обработке очереди: {e}")
                self.queue.task_done()

    async def add_request(self, request: Callable[[], Any]) -> Any:
        """Добавляет запрос в очередь и возвращает результат."""
        future = asyncio.Future()
        async def wrapped_request():
            try:
                result = await request()
                future.set_result(result)
                return result
            except Exception as e:
                future.set_exception(e)
                raise
        await self.queue.put(wrapped_request)
        return await future

    async def start(self, bot: Bot):
        """Запускает обработку очереди."""
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self.process_queue(bot))
            logging.info("✅ Очередь Telegram запущена")

    def stop(self):
        """Останавливает обработку очереди."""
        self.is_running = False
        logging.info("⏹ Очередь Telegram остановлена")

telegram_queue = TelegramQueue()