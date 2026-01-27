import unittest
import os
import asyncio
import json
import time
from unittest.mock import MagicMock, patch
from database import Database
from youtube_client import YoutubeClient, Video
from services import ChannelService

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_bot_data_v3.db"
        self.db = Database(self.db_path)
        await self.db.init_db()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_channel_mapping(self):
        await self.db.set_channel_id("PewDiePie", "UC-lHJZR3Gqxm24_Vd_AJ5Yw", "PewDiePie")
        result = await self.db.get_channel_id("pewdiepie")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "UC-lHJZR3Gqxm24_Vd_AJ5Yw")
        self.assertEqual(result[1], "PewDiePie")

    async def test_cache(self):
        data = [{"title": "Test", "view_count": 100}]
        await self.db.set_cache("test:key", data)

        cached = await self.db.get_cache("test:key")
        self.assertEqual(cached, data)

    async def test_message_state(self):
        chat_id = 123
        msg_id = 456
        data = [{"id": "UC1", "title": "T1"}, {"id": "UC2", "title": "T2"}]

        await self.db.save_message_state(chat_id, msg_id, data)
        retrieved = await self.db.get_message_state(chat_id, msg_id)

        self.assertEqual(retrieved, data)

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

    async def test_get_vods(self):
        # Mocking _run_in_executor
        async def mock_runner(func, *args, **kwargs):
            return func(*args, **kwargs)
        self.client._run_in_executor = mock_runner

        # Mock playlistItems response
        mock_pl = MagicMock(return_value={
            "items": [
                {"contentDetails": {"videoId": "v1"}},
                {"contentDetails": {"videoId": "v2"}}
            ]
        })
        self.client.service.playlistItems().list().execute = mock_pl

        # Mock videos response
        mock_vid = MagicMock(return_value={
            "items": [
                {"id": "v1", "snippet": {"title": "Video 1"}, "statistics": {"viewCount": "100"}},
                {"id": "v2", "snippet": {"title": "Video 2"}, "statistics": {"viewCount": "200"}}
            ]
        })
        self.client.service.videos().list().execute = mock_vid

        result = await self.client.get_vods("UC123")

        # Should be sorted by view count desc
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].title, "Video 2")
        self.assertEqual(result[0].view_count, 200)

class TestChannelService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_service_db.db"
        self.db = Database(self.db_path)
        await self.db.init_db()
        self.client = MagicMock()
        self.service = ChannelService(self.db, self.client)

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_resolve_channel_cached(self):
        await self.db.set_channel_id("exists", "UC1", "Exists")
        res = await self.service.resolve_channel("exists")
        self.assertEqual(res, ("UC1", "Exists", "exists"))
        self.client.search_channel.assert_not_called()

if __name__ == "__main__":
    unittest.main()
