import asyncio
from aiogram import html
from database import Database
from youtube_client import YoutubeClient, Video

def format_number(num: int) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

class ChannelService:
    def __init__(self, db: Database, client: YoutubeClient):
        self.db = db
        self.client = client

    async def resolve_channel(self, name: str) -> tuple[str, str, str] | None:
        """Returns (channel_id, title, original_name) or None."""
        channel_info = await self.db.get_channel_id(name)
        if channel_info:
            return channel_info[0], channel_info[1], name

        found = await self.client.search_channel(name)
        if found:
            channel_id, title = found
            await self.db.set_channel_id(name, channel_id, title)
            return channel_id, title, name
        return None

    async def fetch_data_for_channel(self, channel_id: str, channel_title: str, mode: str) -> str:
        cache_key = f"{'shorts' if mode == 'Shorts' else 'vods'}:{channel_id}"

        # Try cache
        cached_data = await self.db.get_cache(cache_key)
        if cached_data:
            videos = [Video(**v) for v in cached_data]
            return self.generate_report(channel_title, channel_id, videos, mode)

        # Fetch from API
        if mode == "Shorts":
            videos = await self.client.get_shorts(channel_id)
        else:
            videos = await self.client.get_vods(channel_id)

        # Save to cache
        await self.db.set_cache(cache_key, [v.model_dump() for v in videos])

        return self.generate_report(channel_title, channel_id, videos, mode)

    def generate_report(self, channel_title: str, channel_id: str, videos: list[Video], mode: str) -> str:
        # We must assume title might contain HTML chars, so we should rely on aiogram's builders or just ensure escaping if needed.
        # aiogram.utils.markdown/html builders usually handle escaping if used correctly, or use html.quote.
        # html.link and html.bold do NOT auto-escape content passed to them in older versions, but in v3 it often expects safe strings.
        # It's safer to escape explicitly if we are unsure, but let's check standard usage.
        # Ideally: html.bold(html.quote(title)).
        # However, checking aiogram 3 docs, html.bold(value) wraps value in tags. If value has <, it breaks.
        safe_title = html.quote(channel_title)
        header = html.bold(html.link(safe_title, f"https://www.youtube.com/channel/{channel_id}"))
        lines = [header]
        if not videos:
            lines.append(f"No {mode}s found or accessible.")
        else:
            for i, video in enumerate(videos, 1):
                safe_video_title = html.quote(video.title)
                lines.append(f"{i}. {html.link(safe_video_title, video.url)} ({format_number(video.view_count)})")
        return "\n".join(lines)
