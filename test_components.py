import unittest
import os
import asyncio
import json
import time
from unittest.mock import MagicMock, patch
from datetime import datetime
from database import Database
from youtube_client import YoutubeClient, Video
from services import ChannelService, time_ago
from utils import format_number, parse_compare_args

class TestUtils(unittest.TestCase):
    def test_format_number(self):
        self.assertEqual(format_number(500), "500")
        self.assertEqual(format_number(1500), "1.5K")
        self.assertEqual(format_number(1500000), "1.5M")

    def test_parse_args(self):
        self.assertEqual(parse_compare_args("/compare a b"), ["a", "b"])
        self.assertEqual(parse_compare_args('/compare "Channel One" b'), ["Channel One", "b"])
        self.assertEqual(parse_compare_args("/compare"), [])
        # Unbalanced quote fallback
        self.assertEqual(parse_compare_args('/compare "Channel One'), ['"Channel', 'One'])

    def test_time_ago(self):
        # We can't easily test time_ago relative to now without freezing time,
        # but we can check basic behavior if we mock datetime or pass a specific delta if refactored.
        # Here we just ensure it doesn't crash.
        res = time_ago(datetime.now())
        self.assertIn("now", res)

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_bot_data_v5.db"
        self.db = Database(self.db_path)
        await self.db.init_db()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_cache_prune(self):
        await self.db.db.execute(
            'INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)',
            ("old_key", json.dumps({}), 0)
        )
        await self.db.db.commit()

        await self.db.prune_cache(ttl=3600)

        cached = await self.db.get_cache("old_key")
        self.assertIsNone(cached)

class TestYoutubeClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = YoutubeClient(api_key="TEST_KEY")
        self.client.service = MagicMock()

    def tearDown(self):
        self.client.close()

    async def test_search_channel(self):
        mock_execute = MagicMock(return_value={
            "items": [{"snippet": {"channelId": "UC123", "channelTitle": "Test Channel"}}]
        })
        self.client.service.search().list().execute = mock_execute

        async def mock_runner(func, *args, **kwargs):
            return func(*args, **kwargs)
        self.client._run_in_executor = mock_runner

        result = await self.client.search_channel("Test")
        self.assertEqual(result, ("UC123", "Test Channel"))

if __name__ == "__main__":
    unittest.main()
