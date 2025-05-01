import aiohttp
import asyncio
import logging
from asyncio import Lock

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logging.getLogger('aiohttp').setLevel(logging.DEBUG)

# Создаем блокировку для предотвращения параллельных запросов
telegram_lock = Lock()


async def safe_telegram_request(request_func):
    """
    Выполняет запрос Telegram API с использованием новой сессии aiohttp.
    
    Args:
        request_func: Функция, выполняющая запрос Telegram API (например, bot.get_chat_member).
    
    Returns:
        Результат выполнения запроса.
    
    Raises:
        Exception: Если запрос завершился с ошибкой.
    """
    async with telegram_lock:  # Используем блокировку для последовательного выполнения
        async with aiohttp.ClientSession() as session:
            try:
                logging.info("🚀 Выполняется безопасный запрос Telegram API")
                result = await request_func()
                logging.info("✅ Безопасный запрос Telegram API успешно выполнен")
                return result
            except Exception as e:
                logging.error(f"❌ Ошибка при выполнении безопасного запроса Telegram API: {e}")
                raise
            finally:
                # Задержка для соблюдения лимитов Telegram API
                await asyncio.sleep(0.1)