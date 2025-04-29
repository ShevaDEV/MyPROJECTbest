import asyncio
from collections import deque

class TelegramQueue:
    def __init__(self):
        self.queue = deque()
        self.lock = asyncio.Lock()
        self.running = False

    async def add_request(self, request_func):
        """Добавляет запрос в очередь и возвращает результат."""
        future = asyncio.Future()
        self.queue.append((request_func, future))

        if not self.running:
            asyncio.create_task(self.process_queue())

        return await future

    async def process_queue(self):
        """Обрабатывает очередь запросов."""
        async with self.lock:
            self.running = True
            while self.queue:
                request_func, future = self.queue.popleft()
                try:
                    result = await request_func()
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                await asyncio.sleep(0.1)  # Задержка между запросами
            self.running = False

# Глобальная очередь
telegram_queue = TelegramQueue()