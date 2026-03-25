# commands/help.py
"""
Dynamic help command that shows different commands based on user role
"""

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.proxy_utils import check_access, is_allowed_user, OWNER_ID

router = Router()

def get_user_role(user_id: int) -> str:
    """Determine user role"""
    if user_id == OWNER_ID:
        return "admin"
    elif is_allowed_user(user_id):
        return "user"
    return "unauthorized"

@router.message(Command("help"))
async def help_handler(msg: Message):
    """Dynamic help command handler"""
    user_id = msg.from_user.id
    role = get_user_role(user_id)
    
    # Check basic access first
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "[🔗] Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    username = msg.from_user.username or "N/A"
    
    # Base help text with user info
    help_text = f"""
[📚] <b>COMMAND CENTER</b>

[👤] <b>User:</b> @{username}
[🆔] <b>ID:</b> <code>{user_id}</code>
[👑] <b>Role:</b> {'ADMIN' if role == 'admin' else 'USER'}
"""
    
    # Common commands for all users
    help_text += """

[💳] <b>CHECKOUT COMMANDS</b>
• <code>/co url</code> – Parse checkout info
• <code>/co url card</code> – Charge one card
• <code>/co url yes card</code> – Charge with bypass
• <code>/co url (reply to .txt)</code> – Bulk charge
• <code>/bco url BIN</code> – BIN-based checkout

[🎲] <b>CARD GENERATOR COMMANDS</b>
• <code>/gen BIN</code> – Generate 10 valid cards from BIN
• <code>.gen BIN</code> – Same as /gen (dot format)
• <code>/genhelp</code> – Detailed generator help

[🛒] <b>STRIPE AUTH COMMANDS</b>
• <code>/st card</code> – Check single card
• <code>/mst cards</code> – Check multiple cards
• <code>/txt</code> – Check cards from file (reply to .txt)
• DEVELOPER: @Vofuxk

[💰] <b>CREDIT SYSTEM COMMANDS</b>              # NEW SECTION
• <code>/redeem CODE</code> – Redeem a code for credits
• <code>/balance</code> – Check your credit balance
• <code>/buy</code> – Information about buying credits

[🔒] <b>PROXY COMMANDS</b>
• <code>/addproxy proxy</code> – Add proxy
• <code>/proxy</code> – List proxies
• <code>/proxy check</code> – Test proxies
• <code>/removeproxy proxy</code> – Remove proxy
• <code>/removeproxy all</code> – Remove all proxies
"""
    
    # Admin-only commands
    if role == "admin":
        help_text += """

[⚙️] <b>ADMIN COMMANDS</b>
• <code>/adduser id</code> – Add user
• <code>/removeuser id</code> – Remove user
• <code>/users</code> – List users
• <code>/stats</code> – Bot statistics
• <code>/broadcast msg</code> – Announce to all
• <code>/logs</code> – View logs
• <code>/restart</code> – Restart bot
• <code>/bininfo bin</code> – Check BIN info
• <code>/stopbco</code> – Stop BCO session

[💰] <b>CREDIT ADMIN COMMANDS</b>                # NEW SECTION
• <code>/generate CREDITS COUNT</code> – Generate redeem codes
• <code>/rmcode CODE</code> – Remove/deactivate a code
• <code>/codes</code> – List all redeem codes
• <code>/addcredits USER_ID AMOUNT</code> – Manually add credits
"""
    
    # Tips section
    help_text += """

[💡] <b>TIPS</b>
• Use <code>/co url</code> first to check checkout
• Test BINs with <code>/bininfo</code>
• Generate cards with <code>/gen 415464</code>
• Use <code>/st</code> for single card checks
• Check your credits with <code>/balance</code>
• Redeem codes with <code>/redeem CODE</code>
• Monitor stats with <code>/stats</code> (admin)

[⚡] <i>Type /help to see this menu</i>
"""
    
    await msg.answer(help_text.strip(), parse_mode=ParseMode.HTML)

@router.message(Command("help_admin"))
async def help_admin_handler(msg: Message):
    """Quick admin help (only for owner)"""
    if msg.from_user.id != OWNER_ID:
        await msg.answer("❌ This command is only for bot owner.")
        return
    
    help_text = """
[⚙️] <b>QUICK ADMIN HELP</b>

[👥] <b>User Management:</b>
• <code>/adduser 123456</code> – Add user
• <code>/removeuser 123456</code> – Remove user
• <code>/users</code> – List all users

[📊] <b>Bot Management:</b>
• <code>/stats</code> – Bot statistics
• <code>/broadcast Hello</code> – Message all
• <code>/logs 100</code> – Get logs
• <code>/restart</code> – Restart bot

[💰] <b>Credit Management:</b>                    # NEW SECTION
• <code>/generate 100 5</code> – Generate 5 codes of 100 credits
• <code>/rmcode ABC123</code> – Remove/deactivate a code
• <code>/codes</code> – List all codes
• <code>/addcredits 123456789 50</code> – Add credits to user

[🔍] <b>BIN Tools:</b>
• <code>/bininfo 374355</code> – Check BIN
• <code>/stopbco</code> – Stop BCO session

[🎲] <b>Card Generator:</b>
• <code>/gen 415464</code> – Generate cards
• <code>.gen 415464</code> – Dot format
• <code>/genhelp</code> – Generator help

[🛒] <b>Stripe Auth Commands:</b>
• <code>/st card</code> – Single card check
• <code>/mst cards</code> – Multi-card check
• <code>/txt</code> – File processing
"""
    await msg.answer(help_text.strip(), parse_mode=ParseMode.HTML)