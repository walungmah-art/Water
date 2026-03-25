# commands/start.py
"""
Start command for the bot with modern UI
"""

import time
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.proxy_utils import check_access

router = Router()

# Bot start time for uptime tracking
BOT_START_TIME = time.time()

def get_uptime() -> str:
    """Calculate bot uptime in readable format"""
    seconds = int(time.time() - BOT_START_TIME)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

@router.message(Command("start"))
async def start_handler(msg: Message):
    """Start command handler - shows welcome message"""
    # Check access
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "[🔗] Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    uptime = get_uptime()
    
    welcome = f"""
[⚡] <b>XMAN STRIPE BOT</b>

[📦] <b>Checkout Parser & Charger</b>

[🚀] <b>Quick Start:</b>
• <code>/help</code> – Show all commands
• <code>/co url</code> – Parse checkout
• <code>/addproxy</code> – Add proxy

[🌐] <b>Supported URLs:</b>
• <code>checkout.stripe.com</code>
• <code>buy.stripe.com</code>
• <code>pay.stripe.com</code>

[⏱️] <b>Uptime:</b> {uptime}
[🔗] <b>Contact:</b> @XMANSPEAK
"""
    await msg.answer(welcome.strip(), parse_mode=ParseMode.HTML)