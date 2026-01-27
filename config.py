from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., description="Telegram Bot Token")
    YOUTUBE_API_KEY: str = Field(..., description="YouTube Data API Key")
    DB_PATH: str = Field("bot_data.db", description="Path to SQLite database")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
