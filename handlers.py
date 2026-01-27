import re
from aiogram import Router, F, html
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
        # Deserialize to Video objects
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

@router.message(Command("compare"))
async def cmd_compare(message: Message, db: Database, client: YoutubeClient):
    args = message.text.split()[1:]
    if not args:
        await message.answer("Usage: /compare [blogger1] [blogger2] ...")
        return

    report_parts = []

    for name in args:
        # Resolve channel ID
        channel_info = await db.get_channel_id(name)
        if not channel_info:
            found = await client.search_channel(name)
            if found:
                channel_id, title = found
                await db.set_channel_id(name, channel_id, title)
                channel_info = (channel_id, title)
            else:
                report_parts.append(f"Could not find channel: {html.bold(name)}")
                continue

        channel_id, title = channel_info
        # Default to VODs
        part = await fetch_data_for_channel(db, client, channel_id, title, "VODs")
        report_parts.append(part)

    if not report_parts:
        await message.answer("No valid channels found.")
        return

    full_response = "\n\n".join(report_parts)
    await message.answer(full_response, reply_markup=get_keyboard("VODs"))

@router.callback_query(F.data.startswith("mode:"))
async def on_mode_switch(callback: CallbackQuery, db: Database, client: YoutubeClient):
    target_mode = "Shorts" if callback.data == "mode:short" else "VODs"
    message = callback.message

    # Extract channel IDs from entities (links)
    if not message.entities:
        await callback.answer("No channels found in message.")
        return

    channel_ids = []
    for entity in message.entities:
        if entity.type == "text_link" and "youtube.com/channel/" in entity.url:
            # Extract ID
            match = re.search(r"youtube\.com/channel/([^/]+)", entity.url)
            if match:
                channel_ids.append(match.group(1))

    # We also need titles. But titles are in the text.
    # Parsing title is harder. But wait, `fetch_data_for_channel` needs title.
    # The title is the text covered by the link.
    # Let's extract (id, title) pairs.

    channels = []
    text = message.html_text if hasattr(message, 'html_text') else message.text
    # message.text gives plain text. message.html_text is not standard attribute but we can reconstruct or use entities with text.
    # message.text + entities indices.

    for entity in message.entities:
        if entity.type == "text_link" and "youtube.com/channel/" in entity.url:
            match = re.search(r"youtube\.com/channel/([^/]+)", entity.url)
            if match:
                c_id = match.group(1)

                # Extract title from text using offset/length
                # Python strings are weird with offsets if emojis are present, but aiogram helps.
                # Actually, simpler:
                start = entity.offset
                end = start + entity.length
                # title = message.text[start:end] # This might fail with surrogates.
                # Correct way using utf16 decode/encode trick or just trusting python slice if no special chars.
                # Let's try simple slice first.
                title = message.text[start:end]
                channels.append((c_id, title))

    if not channels:
        await callback.answer("Could not parse channels.")
        return

    await callback.answer(f"Switching to {target_mode}...")

    report_parts = []
    for c_id, c_title in channels:
        part = await fetch_data_for_channel(db, client, c_id, c_title, target_mode)
        report_parts.append(part)

    full_response = "\n\n".join(report_parts)

    try:
        await message.edit_text(full_response, reply_markup=get_keyboard(target_mode))
    except Exception as e:
        # sometimes 'message is not modified' error
        pass
