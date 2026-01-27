import time
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, Update

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        start_time = time.time()
        result = await handler(event, data)
        duration = time.time() - start_time

        user = data.get("event_from_user")
        user_id = user.id if user else "unknown"

        logging.info(f"Update {event.update_id} from {user_id} processed in {duration:.3f}s")
        return result

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 2.0):
        self.limit = limit
        self.last_requests = {}

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            now = time.time()
            last_request = self.last_requests.get(user.id, 0)
            if now - last_request < self.limit:
                # Throttled
                if isinstance(event, Message):
                    # Ideally we don't reply to every throttled message to avoid spam
                    pass
                # Stop processing
                return

            self.last_requests[user.id] = now

        return await handler(event, data)
