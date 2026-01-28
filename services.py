import asyncio
from aiogram import html
from database import Database
from youtube_client import YoutubeClient, Video
from utils import format_number, time_ago

class ChannelService:
    def __init__(self, db: Database, client: YoutubeClient):
        self.db = db
        self.client = client

    async def resolve_channel(self, name: str) -> tuple[str, str, str] | None:
        """Returns (channel_id, title, original_name) or None."""
        import time

        # Check negative cache (1 hour TTL)
        if await self.db.get_cache(f"not_found:{name.lower()}", ttl=3600):
            return None

        channel_info = await self.db.get_channel_id(name)
        if channel_info:
            # Check staleness (30 days = 2592000s)
            c_id, title, last_updated = channel_info
            # Handle migration where last_updated might be None
            if last_updated and (time.time() - last_updated < 2592000):
                return c_id, title, name
            # Else fall through to refresh

        found = await self.client.search_channel(name)
        if found:
            channel_id, title = found
            await self.db.set_channel_id(name, channel_id, title)
            return channel_id, title, name

        # Cache negative result
        await self.db.set_cache(f"not_found:{name.lower()}", {"found": False})
        return None

    async def fetch_data_for_channel(self, channel_id: str, channel_title: str, mode: str) -> tuple[str, list[Video]]:
        cache_key = f"{'shorts' if mode == 'Shorts' else 'vods'}:{channel_id}"

        # Try cache
        cached_data = await self.db.get_cache(cache_key)
        if cached_data:
            # Check if cached data is a valid list (it could be empty list for 'no videos')
            # Assuming cache stores lists.
            videos = [Video(**v) for v in cached_data]
            return self.generate_report(channel_title, channel_id, videos, mode), videos

        # Fetch from API
        if mode == "Shorts":
            videos = await self.client.get_shorts(channel_id)
        else:
            videos = await self.client.get_vods(channel_id)

        if videos is None:
            # API Error
            return f"⚠️ Could not fetch {mode} for <b>{html.quote(channel_title)}</b> (API Error).", []

        # Save to cache
        await self.db.set_cache(cache_key, [v.model_dump(mode='json') for v in videos])

        return self.generate_report(channel_title, channel_id, videos, mode), videos

    def generate_report(self, channel_title: str, channel_id: str, videos: list[Video], mode: str) -> str:
        safe_title = html.quote(channel_title)
        header = html.bold(html.link(safe_title, f"https://www.youtube.com/channel/{channel_id}"))
        lines = [header]

        if not videos:
            lines.append(f"<i>No {mode}s found or accessible.</i>")
        else:
            medals = ["🥇", "🥈", "🥉"]
            for i, video in enumerate(videos):
                rank_icon = medals[i] if i < 3 else f"{i+1}."
                safe_video_title = html.quote(video.title)

                # Format: 🥇 <Link>
                #         👁️ 1.5M • 👍 10K • 💬 500 • 2d ago
                line_1 = f"{rank_icon} {html.link(safe_video_title, video.url)}"
                stats_part = f"👁️ {format_number(video.view_count)}"
                if video.like_count > 0:
                    stats_part += f" • 👍 {format_number(video.like_count)}"
                if video.comment_count > 0:
                    stats_part += f" • 💬 {format_number(video.comment_count)}"

                line_2 = f"   {stats_part} • {time_ago(video.published_at)}"

                lines.append(line_1)
                lines.append(line_2)

        return "\n".join(lines)
