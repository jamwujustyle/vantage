import asyncio
from typing import List, Optional
import time
import functools
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

class Video(BaseModel):
    title: str
    view_count: int
    url: str
    video_id: str
    type: str  # 'VOD' or 'Short'

def retry_async(max_retries=3, delay=1.0, backoff=2.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except HttpError as e:
                    if e.resp.status in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                        # Log warning here if logger available
                        print(f"Retrying {func.__name__} due to {e.resp.status} (attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise e
            return await func(*args, **kwargs) # Should not reach here
        return wrapper
    return decorator

class YoutubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.service = build('youtube', 'v3', developerKey=self.api_key)
        self.executor = ThreadPoolExecutor(max_workers=5)

    def close(self):
        self.executor.shutdown(wait=False)

    async def _run_in_executor(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))

    @retry_async()
    async def search_channel(self, name: str) -> Optional[tuple[str, str]]:
        """
        Searches for a channel by name.
        Returns (channel_id, title) or None if not found.
        """
        try:
            response = await self._run_in_executor(
                self.service.search().list(
                    q=name,
                    type='channel',
                    part='snippet',
                    maxResults=1
                ).execute
            )
            items = response.get('items', [])
            if not items:
                return None
            snippet = items[0]['snippet']
            return snippet['channelId'], snippet['channelTitle']
        except HttpError as e:
            print(f"Error searching channel {name}: {e}")
            # Raise or let caller handle None? None is fine for "not found".
            # For API errors, logging is key.
            return None

    @retry_async()
    async def get_vods(self, channel_id: str) -> List[Video]:
        """
        Fetches top 3 most watched VODs from the last 50 uploads.
        Returns empty list on API error or no videos.
        """
        # Convert UC to UU
        if channel_id.startswith('UC'):
            uploads_playlist_id = 'UU' + channel_id[2:]
        else:
            uploads_playlist_id = channel_id # Should not happen usually

        try:
            # Fetch top 50 uploads
            pl_response = await self._run_in_executor(
                self.service.playlistItems().list(
                    playlistId=uploads_playlist_id,
                    part='contentDetails',
                    maxResults=50
                ).execute
            )

            video_ids = [item['contentDetails']['videoId'] for item in pl_response.get('items', [])]
            if not video_ids:
                return []

            # Fetch details (statistics) for these videos
            vid_response = await self._run_in_executor(
                self.service.videos().list(
                    id=','.join(video_ids),
                    part='snippet,statistics'
                ).execute
            )

            videos = []
            for item in vid_response.get('items', []):
                stats = item.get('statistics', {})
                snippet = item.get('snippet', {})
                view_count = int(stats.get('viewCount', 0))
                videos.append(Video(
                    title=snippet.get('title', 'Unknown'),
                    view_count=view_count,
                    url=f"https://www.youtube.com/watch?v={item['id']}",
                    video_id=item['id'],
                    type='VOD'
                ))

            # Sort by view count desc and take top 3
            videos.sort(key=lambda x: x.view_count, reverse=True)
            return videos[:3]

        except HttpError as e:
            print(f"Error fetching VODs for {channel_id}: {e}")
            # In a production bot, we might want to signal this error to the user.
            # But adhering to the interface returning List[Video], empty list is safest fallback.
            return []

    @retry_async()
    async def get_shorts(self, channel_id: str) -> List[Video]:
        """
        Fetches top 3 most watched Shorts.
        """
        try:
            # Search for shorts ordered by viewCount
            search_response = await self._run_in_executor(
                self.service.search().list(
                    channelId=channel_id,
                    type='video',
                    videoDuration='short',
                    order='viewCount',
                    part='id',
                    maxResults=3
                ).execute
            )

            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            if not video_ids:
                return []

            # Fetch details to get exact view count and title
            vid_response = await self._run_in_executor(
                self.service.videos().list(
                    id=','.join(video_ids),
                    part='snippet,statistics'
                ).execute
            )

            videos = []
            for item in vid_response.get('items', []):
                stats = item.get('statistics', {})
                snippet = item.get('snippet', {})
                view_count = int(stats.get('viewCount', 0))
                videos.append(Video(
                    title=snippet.get('title', 'Unknown'),
                    view_count=view_count,
                    url=f"https://www.youtube.com/shorts/{item['id']}",
                    video_id=item['id'],
                    type='Short'
                ))

            # Sort again just in case (though API should have sorted it)
            videos.sort(key=lambda x: x.view_count, reverse=True)
            return videos

        except HttpError as e:
            print(f"Error fetching Shorts for {channel_id}: {e}")
            return []
