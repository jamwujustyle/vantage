import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from database import Database
from youtube_client import YoutubeClient
from handlers import router
from middlewares import LoggingMiddleware, ThrottlingMiddleware

logging.basicConfig(level=logging.INFO)

async def cache_pruner(db: Database):
    while True:
        await asyncio.sleep(3600)  # Run every hour
        try:
            await db.prune_cache()
            logging.info("Cache pruned.")
        except Exception as e:
            logging.error(f"Error pruning cache: {e}")

async def main():
    # Initialize dependencies
    db = Database()
    await db.init_db()

    client = YoutubeClient(api_key=settings.YOUTUBE_API_KEY)

    # Initialize Bot and Dispatcher
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Inject dependencies via workflow_data
    dp.workflow_data.update({"db": db, "client": client})

    # Register middlewares
    dp.update.middleware(LoggingMiddleware())
    dp.message.middleware(ThrottlingMiddleware())

    # Register routers
    dp.include_router(router)

    # Start background tasks
    asyncio.create_task(cache_pruner(db))

    logging.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
