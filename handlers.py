import asyncio
import re
from aiogram import Router, F, html
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender
from database import Database
from youtube_client import YoutubeClient, Video

router = Router()

def format_number(num: int) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def generate_report(channel_title: str, channel_id: str, videos: list[Video], mode: str) -> str:
    header = html.bold(html.link(channel_title, f"https://www.youtube.com/channel/{channel_id}"))
    lines = [header]
    if not videos:
        lines.append(f"No {mode}s found or accessible.")
    else:
        for i, video in enumerate(videos, 1):
            lines.append(f"{i}. {html.link(video.title, video.url)} ({format_number(video.view_count)})")
    return "\n".join(lines)

def get_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    target_mode = "Shorts" if current_mode == "VODs" else "VODs"
    callback_data = "mode:short" if current_mode == "VODs" else "mode:vod"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Switch to {target_mode}", callback_data=callback_data)]
    ])

async def fetch_data_for_channel(db: Database, client: YoutubeClient, channel_id: str, channel_title: str, mode: str) -> str:
    cache_key = f"{'shorts' if mode == 'Shorts' else 'vods'}:{channel_id}"

    # Try cache
    cached_data = await db.get_cache(cache_key)
    if cached_data:
        videos = [Video(**v) for v in cached_data]
        return generate_report(channel_title, channel_id, videos, mode)

    # Fetch from API
    if mode == "Shorts":
        videos = await client.get_shorts(channel_id)
    else:
        videos = await client.get_vods(channel_id)

    # Save to cache
    await db.set_cache(cache_key, [v.model_dump() for v in videos])

    return generate_report(channel_title, channel_id, videos, mode)

async def resolve_channel(name: str, db: Database, client: YoutubeClient) -> tuple[str, str, str] | None:
    """Returns (channel_id, title, original_name) or None."""
    channel_info = await db.get_channel_id(name)
    if channel_info:
        return channel_info[0], channel_info[1], name

    found = await client.search_channel(name)
    if found:
        channel_id, title = found
        await db.set_channel_id(name, channel_id, title)
        return channel_id, title, name
    return None

@router.message(Command("compare"))
async def cmd_compare(message: Message, db: Database, client: YoutubeClient):
    args = message.text.split()[1:]
    if not args:
        await message.answer("Usage: /compare [blogger1] [blogger2] ...")
        return

    # Send initial status
    status_msg = await message.answer(f"🔍 Searching for {len(args)} channels...")

    # Show typing action
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        # 1. Resolve all channels concurrently
        resolve_tasks = [resolve_channel(name, db, client) for name in args]
        resolved_results = await asyncio.gather(*resolve_tasks)

        valid_channels = [r for r in resolved_results if r is not None]
        missing_channels = [args[i] for i, r in enumerate(resolved_results) if r is None]

        if not valid_channels:
            await status_msg.edit_text("❌ No valid channels found.")
            return

        # 2. Fetch data for valid channels concurrently (Default VODs)
        fetch_tasks = [
            fetch_data_for_channel(db, client, c_id, c_title, "VODs")
            for c_id, c_title, _ in valid_channels
        ]
        reports = await asyncio.gather(*fetch_tasks)

        # Save state for this message
        state_data = [{'id': c_id, 'title': c_title} for c_id, c_title, _ in valid_channels]
        await db.save_message_state(message.chat.id, status_msg.message_id, state_data)

        # Construct response
        full_response_parts = reports
        if missing_channels:
            full_response_parts.append("\n⚠️ " + html.bold("Not found: ") + ", ".join(missing_channels))

        full_response = "\n\n".join(full_response_parts)

        # Edit the status message with result
        await status_msg.edit_text(full_response, reply_markup=get_keyboard("VODs"))

@router.callback_query(F.data.startswith("mode:"))
async def on_mode_switch(callback: CallbackQuery, db: Database, client: YoutubeClient):
    target_mode = "Shorts" if callback.data == "mode:short" else "VODs"
    message = callback.message

    # Retrieve state from DB
    channel_ids = await db.get_message_state(message.chat.id, message.message_id)

    if not channel_ids:
        # Fallback to old parsing method if DB entry missing (e.g. old messages after bot restart/db wipe)
        # Or simply error out gracefully.
        await callback.answer("Session expired or invalid.", show_alert=True)
        return

    await callback.answer(f"Switching to {target_mode}...")

    # We need titles again. We can get them from DB/Cache or just re-fetch mapping?
    # Actually fetch_data_for_channel needs title for the report header.
    # The DB `channel_map` stores name->id. But we have id.
    # We didn't store id->title mapping explicitly except in channel_map which is keyed by input name.
    # However, `fetch_data_for_channel` uses title to generate report.
    # Optimization: cache id->title or just fetch it.
    # But wait, `channel_map` has (name, id, title). We can't query by ID easily without index or full scan.
    # Let's fix this: `fetch_data_for_channel` takes title.
    # We can store (id, title) in `message_state` or just rely on the API/Cache to get title?
    # No, API calls for title are wasteful.
    # Let's check `database.py`. It has `get_channel_id(name)`.
    # Let's add `get_channel_title(id)` or similar. Or just store title in `message_state`.
    # Modifying `save_message_state` to store `{'id': ..., 'title': ...}` is better.

    # RE-PLAN: I need to update `save_message_state` logic in `cmd_compare` to save `[{id:..., title:...}]`.
    # And update `database.py` schema or just the JSON content. The schema is `channel_ids TEXT` which is JSON.
    # So I can store whatever JSON I want.

    # Let's assume I update `cmd_compare` to save `[{'id': c_id, 'title': c_title}]`.
    # Then here in callback:

    # Wait, I can't change `database.py` schema now without migration or drop.
    # The schema is `channel_ids TEXT`. The name implies IDs but it's just text.
    # I will store a list of dicts: `[{"id": "...", "title": "..."}]`.

    channels_data = channel_ids # It returns the JSON object directly from `get_message_state`

    # If it was a list of strings (old version compat? No, this is new code), handle it.
    # But for safety, let's assume it's the new format.

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        tasks = []
        for c_data in channels_data:
            # Handle both string (legacy/error) and dict
            if isinstance(c_data, str):
                c_id = c_data
                c_title = "Channel" # Fallback
            else:
                c_id = c_data['id']
                c_title = c_data['title']

            tasks.append(fetch_data_for_channel(db, client, c_id, c_title, target_mode))

        reports = await asyncio.gather(*tasks)

        full_response = "\n\n".join(reports)

        try:
            await message.edit_text(full_response, reply_markup=get_keyboard(target_mode))
        except Exception:
            pass
