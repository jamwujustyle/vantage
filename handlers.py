import asyncio
from aiogram import Router, F, html
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender
from database import Database
from youtube_client import YoutubeClient
from services import ChannelService
from utils import parse_compare_args, split_text
from plotting import generate_comparison_chart
from aiogram.types import BufferedInputFile

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

@router.message(Command("favorites"))
async def cmd_favorites(message: Message, db: Database):
    favs = await db.get_favorites(message.from_user.id)
    if not favs:
        await message.answer("You have no favorites yet. Use /add [channel] to add one!")
        return

    text = "<b>⭐ Your Favorites:</b>\n\n"
    for _, title in favs:
        text += f"• {html.quote(title)}\n"

    # Quick compare all button
    names = [f'"{title}"' for _, title in favs] # Quote names
    compare_cmd = f"/compare {' '.join(names)}"

    text += f"\nCompare all: <code>{compare_cmd}</code>"

    await message.answer(text)

@router.message(Command("add"))
async def cmd_add_fav(message: Message, db: Database, client: YoutubeClient):
    args = parse_compare_args(message.text)
    if not args:
        await message.answer("Usage: /add [channel]")
        return

    name = args[0]
    service = ChannelService(db, client)
    res = await service.resolve_channel(name)

    if not res:
        await message.answer(f"Could not find channel: {name}")
        return

    c_id, title, _ = res
    await db.add_favorite(message.from_user.id, c_id, title)
    await message.answer(f"✅ Added <b>{html.quote(title)}</b> to favorites!")

@router.message(Command("remove"))
async def cmd_remove_fav(message: Message, db: Database, client: YoutubeClient):
    args = parse_compare_args(message.text)
    if not args:
        await message.answer("Usage: /remove [channel]")
        return

    name = args[0]
    service = ChannelService(db, client)
    res = await service.resolve_channel(name)
    if not res:
        await message.answer(f"Could not find channel: {name}")
        return

    c_id, title, _ = res
    await db.remove_favorite(message.from_user.id, c_id)
    await message.answer(f"🗑 Removed <b>{html.quote(title)}</b> from favorites.")

@router.callback_query(F.data.startswith("fav:"))
async def on_fav_action(callback: CallbackQuery, db: Database):
    action, _, channel_id = callback.data.split(":")

    if action == "add":
        # Need title. Check channel_map
        async with db.db.execute("SELECT title FROM channel_map WHERE channel_id = ?", (channel_id,)) as cursor:
            row = await cursor.fetchone()
            title = row[0] if row else "Channel"

        await db.add_favorite(callback.from_user.id, channel_id, title)
        await callback.answer("Added to favorites!")

    elif action == "remove":
        await db.remove_favorite(callback.from_user.id, channel_id)
        await callback.answer("Removed from favorites!")

    # Update keyboard
    is_fav = await db.is_favorite(callback.from_user.id, channel_id)

    # Identify current mode from existing buttons
    current_mode = "VODs" # default fallback
    if callback.message.reply_markup:
        for row in callback.message.reply_markup.inline_keyboard:
            for btn in row:
                if "Switch to Shorts" in btn.text:
                    current_mode = "VODs"
                elif "Switch to VODs" in btn.text:
                    current_mode = "Shorts"

    new_kb = get_report_keyboard(current_mode, channel_id, is_fav)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass

@router.message(Command("compare"))
async def cmd_compare(message: Message, db: Database, client: YoutubeClient):
    args = parse_compare_args(message.text)
    if not args:
        # Check if user typed arguments but parsing failed (e.g. weird spacing?)
        # parse_compare_args returns [] if len < 2 (command + 0 args).
        # If text has more words but args is empty, it means just command.

        await message.answer(
            "⚠️ <b>Usage:</b> <code>/compare [channel1] [channel2] ...</code>\n\n"
            "<i>Tip: Use quotes for names with spaces!</i>\n"
            "Example: <code>/compare PewDiePie \"MrBeast Gaming\"</code>"
        )
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
        results = await asyncio.gather(*fetch_tasks)

        reports = [r[0] for r in results]
        all_videos_data = []
        for i, (_, videos) in enumerate(results):
             all_videos_data.append({
                 'title': valid_channels[i][1],
                 'videos': videos
             })

        # Save state for this message
        state_data = [{'id': c_id, 'title': c_title} for c_id, c_title, _ in valid_channels]
        await db.save_message_state(message.chat.id, status_msg.message_id, state_data)

        # Construct response
        full_response_parts = reports
        if missing_channels:
            full_response_parts.append("\n⚠️ " + html.bold("Not found: ") + ", ".join(missing_channels))

        full_response = "\n\n".join(full_response_parts)

        # Generate chart if more than 1 channel
        chart_bytes = None
        if len(valid_channels) > 1:
            try:
                chart_bytes = generate_comparison_chart(all_videos_data)
            except Exception:
                pass

        # Edit the status message with result
        parts = split_text(full_response)

        if not parts:
            await status_msg.delete()
            return

        # Edit first part
        # Logic: If we have a chart, the chart gets the button.
        # But wait, if we edit text, the user can toggle on text.
        # If we send chart, user toggles on chart.
        # Problem: Callback query comes from chart message, but we saved state for status_msg.
        # Solution: Save state for chart message too if sent.
        # Also: Can't edit photo message to text on toggle.
        # Strategy:
        # 1. Always keep buttons on the TEXT message (status_msg).
        # 2. The chart is just an attachment. It shouldn't have the toggle button to avoid state confusion.
        # 3. If user toggles mode, we update text AND send a NEW chart (or edit existing chart if possible? No, can't easily link them).
        # Let's keep buttons ONLY on the last text message. Chart is supplementary.

        # Edit first part
        # If multipart, last part gets button. If chart exists, last part still gets button?
        # Yes, let's keep controls on text.

        await status_msg.edit_text(parts[0], reply_markup=get_keyboard("VODs") if len(parts) == 1 else None)

        # Send remaining parts
        for i, part in enumerate(parts[1:], 1):
            is_last = i == len(parts) - 1
            last_msg = await message.answer(part, reply_markup=get_keyboard("VODs") if is_last else None)
            if is_last:
                # We need to save state for this new message too if it has buttons
                await db.save_message_state(message.chat.id, last_msg.message_id, state_data)

        # Send chart (without buttons to avoid state issues for now)
        if chart_bytes:
            await message.answer_photo(
                BufferedInputFile(chart_bytes, filename="chart.png"),
                caption="📊 View Comparison"
            )

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
        titles = []
        for c_data in channels_data:
            if isinstance(c_data, str):
                c_id = c_data
                c_title = "Channel"
            else:
                c_id = c_data['id']
                c_title = c_data['title']

            titles.append(c_title)
            tasks.append(service.fetch_data_for_channel(c_id, c_title, target_mode))

        results = await asyncio.gather(*tasks)

        reports = [r[0] for r in results]

        # Prepare chart data
        all_videos_data = []
        for i, (_, videos) in enumerate(results):
             all_videos_data.append({
                 'title': titles[i],
                 'videos': videos
             })

        full_response = "\n\n".join(reports)

        chart_bytes = None
        if len(titles) > 1:
            try:
                chart_bytes = generate_comparison_chart(all_videos_data)
            except Exception:
                pass

        parts = split_text(full_response)
        if not parts:
            return

        try:
            # Edit first part
            await message.edit_text(parts[0], reply_markup=get_keyboard(target_mode) if len(parts) == 1 else None)

            # Send others
            for i, part in enumerate(parts[1:], 1):
                is_last = i == len(parts) - 1
                last_msg = await message.answer(part, reply_markup=get_keyboard(target_mode) if is_last else None)
                if is_last:
                    await db.save_message_state(message.chat.id, last_msg.message_id, channels_data)

            # Send chart if available
            if chart_bytes:
                 await message.answer_photo(
                    BufferedInputFile(chart_bytes, filename="chart.png"),
                    caption=f"📊 {target_mode} View Comparison"
                )

        except Exception:
            pass
