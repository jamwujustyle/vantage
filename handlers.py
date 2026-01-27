import asyncio
from aiogram import Router, F, html
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender
from database import Database
from youtube_client import YoutubeClient
from services import ChannelService
from utils import parse_compare_args

router = Router()

def get_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    target_mode = "Shorts" if current_mode == "VODs" else "VODs"
    callback_data = "mode:short" if current_mode == "VODs" else "mode:vod"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Switch to {target_mode}", callback_data=callback_data)]
    ])

@router.message(Command("start", "help"))
async def cmd_welcome(message: Message):
    text = (
        f"👋 <b>Welcome to YT-Vantage!</b>\n\n"
        f"I can help you compare the most popular videos of your favorite YouTubers.\n\n"
        f"<b>Commands:</b>\n"
        f"• /compare [channel1] [channel2] ... — Compare top 3 VODs/Shorts.\n"
        f"  <i>Example:</i> <code>/compare PewDiePie \"MrBeast Gaming\"</code>\n\n"
        f"I support quotes for names with spaces!"
    )
    await message.answer(text)

@router.message(Command("compare"))
async def cmd_compare(message: Message, db: Database, client: YoutubeClient):
    args = parse_compare_args(message.text)
    if not args:
        await message.answer("Usage: /compare [blogger1] [blogger2] ...")
        return

    service = ChannelService(db, client)

    # Send initial status
    status_msg = await message.answer(f"🔍 Searching for {len(args)} channels...")

    # Show typing action
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        # 1. Resolve all channels concurrently
        resolve_tasks = [service.resolve_channel(name) for name in args]
        resolved_results = await asyncio.gather(*resolve_tasks)

        valid_channels = [r for r in resolved_results if r is not None]
        missing_channels = [args[i] for i, r in enumerate(resolved_results) if r is None]

        if not valid_channels:
            await status_msg.edit_text("❌ No valid channels found.")
            return

        # 2. Fetch data for valid channels concurrently (Default VODs)
        fetch_tasks = [
            service.fetch_data_for_channel(c_id, c_title, "VODs")
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
        await callback.answer("Session expired or invalid.", show_alert=True)
        return

    await callback.answer(f"Switching to {target_mode}...")

    service = ChannelService(db, client)
    channels_data = channel_ids

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        tasks = []
        for c_data in channels_data:
            if isinstance(c_data, str):
                c_id = c_data
                c_title = "Channel"
            else:
                c_id = c_data['id']
                c_title = c_data['title']

            tasks.append(service.fetch_data_for_channel(c_id, c_title, target_mode))

        reports = await asyncio.gather(*tasks)

        full_response = "\n\n".join(reports)

        try:
            await message.edit_text(full_response, reply_markup=get_keyboard(target_mode))
        except Exception:
            pass
