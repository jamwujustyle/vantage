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
from utils import format_number, parse_compare_args, split_text
from plotting import generate_comparison_chart

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

    def test_split_text(self):
        text = "a" * 10
        chunks = split_text(text, limit=4)
        self.assertEqual(len(chunks), 3) # aaaa, aaaa, aa
        self.assertEqual(chunks[0], "aaaa")

    def test_time_ago(self):
        res = time_ago(datetime.now())
        self.assertIn("now", res)

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_bot_data_v7.db"
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

    async def test_cache_ttl(self):
        # Set cache with timestamp 0
        await self.db.set_cache("key", {})
        # Manually update timestamp to 2 hours ago
        await self.db.db.execute(
            'UPDATE cache SET timestamp = ? WHERE key = ?',
            (time.time() - 7200, "key")
        )
        await self.db.db.commit()

        # Should exist with 3h TTL
        res = await self.db.get_cache("key", ttl=3*3600)
        self.assertIsNotNone(res)

        # Should not exist with 1h TTL
        res = await self.db.get_cache("key", ttl=3600)
        self.assertIsNone(res)

class TestPlotting(unittest.TestCase):
    def test_generate_chart(self):
        video = Video(
            title="Test", view_count=100, like_count=10, comment_count=5,
            url="url", video_id="vid", type="VOD", published_at=datetime.now()
        )
        data = [{'title': 'Test Channel', 'videos': [video]}]

        img_bytes = generate_comparison_chart(data)
        self.assertIsNotNone(img_bytes)
        self.assertTrue(len(img_bytes) > 0)
        # Check if PNG signature is present
        self.assertEqual(img_bytes[:8], b'\x89PNG\r\n\x1a\n')

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
