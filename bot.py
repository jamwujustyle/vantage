import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from database import Database
from youtube_client import YoutubeClient
from handlers import router

logging.basicConfig(level=logging.INFO)

async def main():
    # Initialize dependencies
    db = Database()
    await db.init_db()

    client = YoutubeClient(api_key=settings.YOUTUBE_API_KEY)

    # Initialize Bot and Dispatcher
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Inject dependencies into handlers
    dp["db"] = db
    dp["client"] = client

    # Register routers
    dp.include_router(router)

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
