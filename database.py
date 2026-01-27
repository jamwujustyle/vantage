import aiosqlite
import json
import time
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS channel_map (
                    name TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    title TEXT NOT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS message_state (
                    chat_id INTEGER,
                    message_id INTEGER,
                    channel_ids TEXT,
                    PRIMARY KEY (chat_id, message_id)
                )
            ''')
            await db.commit()

    async def save_message_state(self, chat_id: int, message_id: int, channel_ids: list[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO message_state (chat_id, message_id, channel_ids) VALUES (?, ?, ?)',
                (chat_id, message_id, json.dumps(channel_ids))
            )
            await db.commit()

    async def get_message_state(self, chat_id: int, message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT channel_ids FROM message_state WHERE chat_id = ? AND message_id = ?',
                (chat_id, message_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
        return None

    async def get_channel_id(self, name: str):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT channel_id, title FROM channel_map WHERE name = ?', (name.lower(),)) as cursor:
                row = await cursor.fetchone()
                return row if row else None

    async def set_channel_id(self, name: str, channel_id: str, title: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO channel_map (name, channel_id, title) VALUES (?, ?, ?)',
                (name.lower(), channel_id, title)
            )
            await db.commit()

    async def get_cache(self, key: str):
        """Returns cached data if valid (less than 6 hours old), else None."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT data, timestamp FROM cache WHERE key = ?', (key,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    data_json, timestamp = row
                    if time.time() - timestamp < 6 * 3600:
                        return json.loads(data_json)
        return None

    async def set_cache(self, key: str, data: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)',
                (key, json.dumps(data), time.time())
            )
            await db.commit()
