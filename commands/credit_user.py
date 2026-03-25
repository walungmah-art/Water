# commands/credit_user.py
"""
User commands for credit and redeem system
"""

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config_bot.credit_costs import CREDIT_COSTS, PER_CARD_COST
from functions.proxy_utils import check_access
from database.repositories import UserRepository, RedeemCodeRepository, TransactionRepository

router = Router()
user_repo = UserRepository()
code_repo = RedeemCodeRepository()
tx_repo = TransactionRepository()

@router.message(Command("redeem"))
async def redeem_handler(msg: Message):
    """Redeem a code - /redeem {code}"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "[🔗] Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer(
            "[❌] <b>Usage</b>\n\n"
            "<code>/redeem CODE</code>\n\n"
            "Example: <code>/redeem ABC123XYZ7</code>\n\n"
            "[💡] Get codes from @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    code = args[1].strip().upper()
    user_id = msg.from_user.id
    
    # Ensure user exists in database
    user_repo.add_user(
        user_id,
        msg.from_user.username,
        msg.from_user.first_name,
        msg.from_user.last_name
    )
    
    success, credits, message = code_repo.redeem_code(code, user_id)
    
    if success:
        await msg.answer(
            f"[✅] <b>Redeem Successful!</b>\n\n"
            f"[💰] <b>Credits Added:</b> {credits}\n"
            f"[📝] {message}\n\n"
            f"[💡] You can now use all bot commands",
            parse_mode=ParseMode.HTML
        )
    else:
        await msg.answer(
            f"[❌] <b>Redeem Failed</b>\n\n"
            f"[📝] {message}",
            parse_mode=ParseMode.HTML
        )

@router.message(Command("balance"))
async def balance_handler(msg: Message):
    """Check your credit balance"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_id = msg.from_user.id
    user = user_repo.get_user(user_id)
    
    if not user:
        credits = 0
        is_active = False
    else:
        credits = user.get("credits", 0)
        is_active = user.get("is_active", False)
    
    # Get recent transactions
    transactions = tx_repo.get_user_transactions(user_id, 5)
    
    tx_text = ""
    if transactions:
        tx_list = []
        for tx in transactions[:3]:
            emoji = "✅" if tx["credits_change"] > 0 else "➖"
            tx_list.append(f"{emoji} {tx['credits_change']} credits - {tx.get('description', '')[:30]}")
        tx_text = "\n" + "\n".join(tx_list)
    
    status = "✅ Active" if is_active else "❌ Inactive"
    
    await msg.answer(
        f"[💰] <b>Your Balance</b>\n\n"
        f"[👤] User: @{msg.from_user.username or 'N/A'}\n"
        f"[📊] Status: {status}\n"
        f"[💳] Credits: <code>{credits}</code>\n\n"
        f"[📋] <b>Recent Activity:</b>{tx_text}\n\n"
        f"[💡] Use <code>/redeem CODE</code> to add credits",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("buy"))
async def buy_handler(msg: Message):
    """Information about buying credits"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    await msg.answer(
        "[🛒] <b>Get Credits</b>\n\n"
        "To purchase credits or get redeem codes, contact:\n"
        "• Owner: @XMANSPEAK\n\n"
        "After receiving a code, use:\n"
        "<code>/redeem YOUR_CODE</code>\n\n"
        "Each command costs 1 credit except:\n"
        "• <code>/start</code>, <code>/help</code>, <code>/gen</code>, <code>.gen</code>, <code>/genhelp</code> - Free\n"
        "• Admin commands - Free",
        parse_mode=ParseMode.HTML
    )