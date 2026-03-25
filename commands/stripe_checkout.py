# commands/stripe_checkout.py
"""
Stripe checkout commands with credit system integration
"""

import asyncio
import random
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.proxy_utils import check_access
from functions.stripe_checkout import (
    parse_card_line,
    format_card_display,
    process_single_card
)
from database.repositories import UserRepository
from config_bot.credit_costs import CREDIT_COSTS, PER_CARD_COST
from config import OWNER_ID

router = Router()
user_repo = UserRepository()

@router.message(Command("st"))
async def single_card_command(msg: Message):
    """Handle /st command for single card"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "[🔗] Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = msg.text or ""
    args = text.split(maxsplit=1)
    
    if len(args) < 2:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] Please provide card details!\n\n"
            "<b>Usage:</b> <code>/st 4342561106277239|10|2029|204</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    card_text = args[1].strip()
    
    # Parse first card only
    card_data = parse_card_line(card_text.split('\n')[0])
    
    if not card_data:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] Invalid card format!\n\n"
            "<b>Supported formats:</b>\n"
            "• <code>card|month|year|cvc</code>\n"
            "• <code>card/month/year/cvc</code>\n\n"
            "<b>Example:</b> <code>4342561106277239|10|2029|204</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_id = msg.from_user.id
    
    # Skip credit check for owner
    if user_id != OWNER_ID:
        cost = CREDIT_COSTS.get("/st", 1)
        
        # Check and deduct credits
        success, before, after = user_repo.use_credits(
            user_id, 
            cost, 
            "/st",
            {"card": card_text[:20] + "..." if len(card_text) > 20 else card_text}
        )
        
        if not success:
            await msg.answer(
                "[❌] <b>Insufficient Credits</b>\n\n"
                f"You need {cost} credit(s) to use this command.\n"
                f"Your balance: {before}\n"
                "Use /buy to purchase credits.",
                parse_mode=ParseMode.HTML
            )
            return
    
    # Send cooking message
    cooking_msg = await msg.answer(
        f"[🔮] <b>Cooking something big...</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Process card
    status, result_msg, _ = await process_single_card(card_data, silent_declined=False)
    
    # Update cooking message with result
    try:
        await cooking_msg.edit_text(result_msg, parse_mode=ParseMode.HTML)
    except Exception:
        await msg.answer(result_msg, parse_mode=ParseMode.HTML)

@router.message(Command("mst"))
async def multi_card_command(msg: Message):
    """Handle /mst command for multiple cards"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "[🔗] Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = msg.text or ""
    args = text.split(maxsplit=1)
    
    if len(args) < 2:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] Please provide card details!\n\n"
            "<b>Usage:</b>\n"
            "<code>/mst 4342561106277239|10|2029|204\n"
            "4342561102086590|12|2027|890</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    full_text = args[1].strip()
    lines = full_text.split('\n')
    
    # Parse all cards
    cards = []
    invalid_lines = []
    
    for i, line in enumerate(lines, 1):
        if line.strip():
            card_data = parse_card_line(line)
            if card_data:
                cards.append(card_data)
            else:
                invalid_lines.append(i)
    
    if not cards:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] No valid cards found!\n\n"
            "<b>Supported formats:</b>\n"
            "• <code>card|month|year|cvc</code>\n"
            "• <code>card/month/year/cvc</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if invalid_lines:
        await msg.answer(
            f"[⚠️] <b>Warning</b>\n\n"
            f"[📝] {len(invalid_lines)} invalid line(s) skipped (lines: {', '.join(map(str, invalid_lines))})",
            parse_mode=ParseMode.HTML
        )
    
    user_id = msg.from_user.id
    
    # Skip credit check for owner
    if user_id != OWNER_ID:
        total_cost = len(cards) * PER_CARD_COST
        
        # Check and deduct credits
        success, before, after = user_repo.use_credits(
            user_id, 
            total_cost, 
            "/mst",
            {"card_count": len(cards)}
        )
        
        if not success:
            await msg.answer(
                "[❌] <b>Insufficient Credits</b>\n\n"
                f"You need {total_cost} credits for {len(cards)} cards.\n"
                f"Your balance: {before}\n"
                "Use /buy to purchase credits.",
                parse_mode=ParseMode.HTML
            )
            return
    
    # Send cooking message
    cooking_msg = await msg.answer(
        f"[🔮] <b>Cooking something big...</b>\n\n"
        f"[📊] <b>Total Cards:</b> {len(cards)}\n"
        f"[⏳] <b>Estimated Time:</b> ~{len(cards) * 8} seconds",
        parse_mode=ParseMode.HTML
    )
    
    # Process each card
    approved_count = 0
    declined_count = 0
    otp_count = 0
    
    for i, card_data in enumerate(cards, 1):
        card_display = format_card_display(card_data)
        
        # Update cooking message
        try:
            await cooking_msg.edit_text(
                f"[🔮] <b>Cooking something big...</b>\n\n"
                f"[📊] <b>Progress:</b> {i}/{len(cards)}\n"
                f"[💳] <b>Current:</b> <code>{card_display}</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        
        # Process card
        status, result_msg, _ = await process_single_card(card_data, silent_declined=True)
        
        # Only send message for approved cards
        if status == "APPROVED":
            await msg.answer(result_msg, parse_mode=ParseMode.HTML)
            approved_count += 1
        elif status == "DECLINED":
            declined_count += 1
        elif status == "OTP":
            otp_count += 1
        
        # Delay between cards
        if i < len(cards):
            await asyncio.sleep(random.uniform(6.0, 9.0))
    
    # Update cooking message with completion summary
    try:
        await cooking_msg.edit_text(
            f"[✅] <b>All Cards Processed!</b>\n\n"
            f"[📊] <b>Total:</b> {len(cards)}\n"
            f"[✅] <b>Approved:</b> {approved_count}\n"
            f"[❌] <b>Declined:</b> {declined_count}\n"
            f"[⚠️] <b>3DS:</b> {otp_count}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

@router.message(Command("txt"))
async def txt_command(msg: Message):
    """Handle /txt command for file processing"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "[🔗] Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check if replying to a message
    if not msg.reply_to_message:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] Please reply to a text file with this command!\n\n"
            "<b>Usage:</b>\n"
            "1. Send a .txt file with cards\n"
            "2. Reply to that file with <code>/txt</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check if replied message has document
    replied = msg.reply_to_message
    if not replied.document:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] Replied message is not a file!\n\n"
            "Please reply to a .txt file containing cards.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Download file
    try:
        file = await msg.bot.get_file(replied.document.file_id)
        file_content = await msg.bot.download_file(file.file_path)
        content = file_content.read().decode('utf-8')
    except Exception as e:
        await msg.answer(
            f"[❌] <b>Error reading file</b>\n\n"
            f"[📝] {str(e)}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Parse cards from file content
    lines = content.split('\n')
    cards = []
    invalid_lines = []
    
    for i, line in enumerate(lines, 1):
        if line.strip():
            card_data = parse_card_line(line)
            if card_data:
                cards.append(card_data)
            else:
                invalid_lines.append(i)
    
    if not cards:
        await msg.answer(
            "[❌] <b>Error</b>\n\n"
            "[📝] No valid cards found in file!\n\n"
            "<b>Supported formats:</b>\n"
            "• <code>card|month|year|cvc</code>\n"
            "• <code>card/month/year/cvc</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if invalid_lines:
        await msg.answer(
            f"[⚠️] <b>Warning</b>\n\n"
            f"[📝] {len(invalid_lines)} invalid line(s) skipped (lines: {', '.join(map(str, invalid_lines))})",
            parse_mode=ParseMode.HTML
        )
    
    user_id = msg.from_user.id
    
    # Skip credit check for owner
    if user_id != OWNER_ID:
        total_cost = len(cards) * PER_CARD_COST
        
        # Check and deduct credits
        success, before, after = user_repo.use_credits(
            user_id, 
            total_cost, 
            "/txt",
            {"card_count": len(cards)}
        )
        
        if not success:
            await msg.answer(
                "[❌] <b>Insufficient Credits</b>\n\n"
                f"You need {total_cost} credits for {len(cards)} cards.\n"
                f"Your balance: {before}\n"
                "Use /buy to purchase credits.",
                parse_mode=ParseMode.HTML
            )
            return
    
    # Send cooking message
    cooking_msg = await msg.answer(
        f"[📁] <b>File Processing Started</b>\n\n"
        f"[🔮] <b>Cooking something big...</b>\n\n"
        f"[📊] <b>Total Cards:</b> {len(cards)}\n"
        f"[⏳] <b>Estimated Time:</b> ~{len(cards) * 8} seconds",
        parse_mode=ParseMode.HTML
    )
    
    # Process each card
    approved_count = 0
    declined_count = 0
    otp_count = 0
    
    for i, card_data in enumerate(cards, 1):
        card_display = format_card_display(card_data)
        
        # Update cooking message
        try:
            await cooking_msg.edit_text(
                f"[📁] <b>File Processing</b>\n\n"
                f"[🔮] <b>Cooking something big...</b>\n\n"
                f"[📊] <b>Progress:</b> {i}/{len(cards)}\n"
                f"[💳] <b>Current:</b> <code>{card_display}</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        
        # Process card
        status, result_msg, _ = await process_single_card(card_data, silent_declined=True)
        
        # Only send message for approved cards
        if status == "APPROVED":
            await msg.answer(result_msg, parse_mode=ParseMode.HTML)
            approved_count += 1
        elif status == "DECLINED":
            declined_count += 1
        elif status == "OTP":
            otp_count += 1
        
        # Delay between cards
        if i < len(cards):
            await asyncio.sleep(random.uniform(6.0, 9.0))
    
    # Update cooking message with completion summary
    try:
        await cooking_msg.edit_text(
            f"[📁] <b>File Processing Complete!</b>\n\n"
            f"[✅] <b>All Cards Processed!</b>\n\n"
            f"[📊] <b>Total:</b> {len(cards)}\n"
            f"[✅] <b>Approved:</b> {approved_count}\n"
            f"[❌] <b>Declined:</b> {declined_count}\n"
            f"[⚠️] <b>3DS:</b> {otp_count}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass