# commands/gen.py
"""
Card generator command for aiogram bot - Preserves original UI
"""

from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.enums import ParseMode
import re

from functions.proxy_utils import check_access
from functions.card_generator import generator

router = Router()

OWNER = "@XMANSPEAK"

@router.message(Command("gen"))
async def gen_command(msg: Message):
    """Handle /gen command for card generation - Original UI preserved"""
    if not check_access(msg):
        await msg.answer("❌ Access Denied")
        return
    
    text = msg.text or ""
    args = text.split(maxsplit=1)
    
    if len(args) < 2:
        await msg.answer(
            "❌ Please provide BIN details!\n\n"
            "Example: `/gen 415464440` or `/gen 415464440|12|2035|123`",
            parse_mode='Markdown'
        )
        return
    
    input_pattern = args[1].strip()
    
    try:
        await msg.bot.send_chat_action(chat_id=msg.chat.id, action="typing")
        
        output_lines, original_pattern = generator.generate(input_pattern, 10)
        output_text = "\n".join(output_lines)
        
        # Original button format
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Generate Again", callback_data=f"gen_again:{original_pattern}")]
        ])
        
        await msg.answer(
            output_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
    except Exception as e:
        await msg.answer(f"❌ Error: {str(e)}")

@router.message(lambda message: message.text and message.text.startswith('.gen'))
async def dot_gen_handler(msg: Message):
    """Handle messages that start with .gen - Original UI preserved"""
    if not check_access(msg):
        await msg.answer("❌ Access Denied")
        return
    
    text = msg.text.strip()
    input_pattern = text[4:].strip()
    
    if not input_pattern:
        await msg.answer(
            "❌ Please provide BIN details!\n\n"
            "Example: `.gen 415464440` or `.gen 415464440|12|2035|123`"
        )
        return
    
    try:
        await msg.bot.send_chat_action(chat_id=msg.chat.id, action="typing")
        
        output_lines, original_pattern = generator.generate(input_pattern, 10)
        output_text = "\n".join(output_lines)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Generate Again", callback_data=f"gen_again:{original_pattern}")]
        ])
        
        await msg.answer(
            output_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
    except Exception as e:
        await msg.answer(f"❌ Error: {str(e)}")

@router.callback_query(lambda c: c.data and c.data.startswith("gen_again:"))
async def gen_again_callback(callback: CallbackQuery):
    """Handle Generate Again button clicks"""
    await callback.answer()
    
    pattern = callback.data.replace("gen_again:", "")
    
    try:
        await callback.message.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
        
        output_lines, original_pattern = generator.generate(pattern, 10)
        output_text = "\n".join(output_lines)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Generate Again", callback_data=f"gen_again:{original_pattern}")]
        ])
        
        await callback.message.answer(
            output_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
    except Exception as e:
        await callback.message.answer(f"❌ Error: {str(e)}")

@router.message(Command("genhelp"))
async def gen_help_command(msg: Message):
    """Help command for card generator - Original UI preserved"""
    if not check_access(msg):
        await msg.answer("❌ Access Denied")
        return
    
    help_text = (
        f"📚 *Help & Commands* 📚\n\n"
        f"👤 *Owner:* {OWNER}\n\n"
        f"Send `.gen` or `/gen` with your pattern:\n\n"
        f"1️⃣ *Just BIN:*\n"
        f"   `.gen 415464`\n"
        f"   `.gen 379363` \\(AmEx\\)\n"
        f"   `.gen 415464440` \\(Visa, shows full BIN\\)\n\n"
        f"2️⃣ *With expiry:*\n"
        f"   `.gen 415464|12|2035|`\n"
        f"   `.gen 415464/12/35/`\n\n"
        f"3️⃣ *With expiry and CVV:*\n"
        f"   `.gen 415464|12|2035|123`\n\n"
        f"4️⃣ *With X placeholders:*\n"
        f"   `.gen 415464xxxxxx`\n\n"
        f"🔹 *AmEx cards:* 15 digits, 4\\-digit CVV\n"
        f"🔹 *Other cards:* 16 digits, 3\\-digit CVV\n\n"
        f"✨ *Features:*\n"
        f"• Bold headings for easy reading\n"
        f"• Tap\\-to\\-copy cards \\(in code blocks\\)\n"
        f"• Shows *full BIN* you entered \\(not just first 6 digits\\)\n"
        f"• *Live BIN Info* from antipublic API\n"
        f"• Country flags in BIN info\n"
        f"• 🔄 *Generate Again* button below each result"
    )
    await msg.answer(help_text, parse_mode='MarkdownV2')