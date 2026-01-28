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
        self.db_path = "test_bot_data_v9.db"
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
        await self.db.set_cache("key", {})
        await self.db.db.execute(
            'UPDATE cache SET timestamp = ? WHERE key = ?',
            (time.time() - 7200, "key")
        )
        await self.db.db.commit()

        res = await self.db.get_cache("key", ttl=3*3600)
        self.assertIsNotNone(res)

        res = await self.db.get_cache("key", ttl=3600)
        self.assertIsNone(res)

    async def test_favorites(self):
        user_id = 123
        await self.db.add_favorite(user_id, "id1", "Title 1")

        favs = await self.db.get_favorites(user_id)
        self.assertEqual(len(favs), 1)
        self.assertEqual(favs[0], ("id1", "Title 1"))

        is_fav = await self.db.is_favorite(user_id, "id1")
        self.assertTrue(is_fav)

        await self.db.remove_favorite(user_id, "id1")
        is_fav = await self.db.is_favorite(user_id, "id1")
        self.assertFalse(is_fav)

    async def test_last_updated_migration(self):
        # Check if column exists by querying it
        res = await self.db.get_channel_id("nonexistent")
        self.assertIsNone(res)

        await self.db.set_channel_id("test", "id", "title")
        res = await self.db.get_channel_id("test")
        self.assertEqual(len(res), 3) # id, title, last_updated
        self.assertIsNotNone(res[2])

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

    async def test_get_vods_error(self):
        # Test error handling returns None
        async def mock_runner(func, *args, **kwargs):
            from googleapiclient.errors import HttpError
            resp = MagicMock()
            resp.status = 500
            raise HttpError(resp, b'Error')

        self.client._run_in_executor = mock_runner

        # Override decorator for this test instance? The decorator wraps the method.
        # We need to mock the underlying method or just let the decorator catch the error.
        # Since we mocked _run_in_executor to raise error, the decorator will retry and then raise.
        # Wait, the decorator catches specific status codes and retries, then raises.
        # The method `get_vods` has a try/except block that catches HttpError and returns None.
        # So it should return None.

        result = await self.client.get_vods("UC123")
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
