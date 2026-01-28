import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from aiogram.types import BotCommand
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

async def on_startup(bot: Bot, db: Database, client: YoutubeClient):
    await db.init_db()
    # Start background tasks
    asyncio.create_task(cache_pruner(db))

    # Set bot commands
    commands = [
        BotCommand(command="compare", description="Compare top videos (VODs/Shorts)"),
        BotCommand(command="favorites", description="List your saved channels"),
        BotCommand(command="add", description="Add channel to favorites"),
        BotCommand(command="remove", description="Remove channel from favorites"),
        BotCommand(command="help", description="Show help message"),
        BotCommand(command="start", description="Welcome message"),
    ]
    await bot.set_my_commands(commands)
    logging.info("Bot started.")

async def on_shutdown(bot: Bot, db: Database, client: YoutubeClient):
    await db.close()
    client.close()
    logging.info("Bot stopped.")

async def main():
    # Initialize dependencies
    db = Database()
    client = YoutubeClient(api_key=settings.YOUTUBE_API_KEY)

    # Initialize Bot and Dispatcher
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Inject dependencies via workflow_data
    dp.workflow_data.update({"db": db, "client": client})

    # Register events
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register middlewares
    dp.update.middleware(LoggingMiddleware())
    dp.message.middleware(ThrottlingMiddleware())

    # Register routers
    dp.include_router(router)

    logging.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
