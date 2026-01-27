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
        self.last_warnings = {}

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
                    last_warning = self.last_warnings.get(user.id, 0)
                    if now - last_warning > 5.0: # Warn max once every 5 seconds
                        try:
                            await event.answer("⚠️ You are sending commands too fast. Please slow down.")
                            self.last_warnings[user.id] = now
                        except Exception:
                            pass
                return

            self.last_requests[user.id] = now

        return await handler(event, data)
