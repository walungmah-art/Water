# commands/credit_admin.py
"""
Admin commands for credit and redeem code management
"""

import time
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config_bot.credit_costs import CREDIT_COSTS, PER_CARD_COST
from functions.proxy_utils import check_access
from database.repositories import UserRepository, RedeemCodeRepository
from config import OWNER_ID

router = Router()
user_repo = UserRepository()
code_repo = RedeemCodeRepository()

def is_owner_or_admin(user_id: int) -> bool:
    """Check if user is owner or admin"""
    if user_id == OWNER_ID:
        return True
    return user_repo.is_admin(user_id)

@router.message(Command("generate"))
async def generate_codes_handler(msg: Message):
    """Generate redeem codes - /generate {credits} {count}"""
    if not is_owner_or_admin(msg.from_user.id):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "This command is only for admins.",
            parse_mode=ParseMode.HTML
        )
        return
    
    args = msg.text.split()
    if len(args) < 3:
        await msg.answer(
            "[❌] <b>Usage</b>\n\n"
            "<code>/generate {credits} {count}</code>\n\n"
            "Example: <code>/generate 100 5</code> - Creates 5 codes with 100 credits each",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        credits = int(args[1])
        count = int(args[2])
        
        if credits <= 0 or count <= 0 or count > 50:
            await msg.answer(
                "[❌] <b>Invalid Values</b>\n\n"
                "Credits must be positive\n"
                "Count must be between 1 and 50",
                parse_mode=ParseMode.HTML
            )
            return
        
        codes = code_repo.create_codes(
            admin_id=msg.from_user.id,
            credits=credits,
            count=count
        )
        
        # Format codes for display
        codes_text = "\n".join([f"<code>{code}</code>" for code in codes])
        
        await msg.answer(
            f"[✅] <b>Codes Generated Successfully</b>\n\n"
            f"[💰] <b>Credits each:</b> {credits}\n"
            f"[🔢] <b>Count:</b> {count}\n\n"
            f"[📋] <b>Codes:</b>\n{codes_text}\n\n"
            f"[💡] Users can redeem with <code>/redeem CODE</code>",
            parse_mode=ParseMode.HTML
        )
        
    except ValueError:
        await msg.answer(
            "[❌] <b>Invalid Numbers</b>\n\n"
            "Please provide valid numbers for credits and count",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.answer(
            f"[❌] <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )

@router.message(Command("rmcode"))
async def remove_code_handler(msg: Message):
    """Remove a redeem code - /rmcode {code}"""
    if not is_owner_or_admin(msg.from_user.id):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "This command is only for admins.",
            parse_mode=ParseMode.HTML
        )
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer(
            "[❌] <b>Usage</b>\n\n"
            "<code>/rmcode CODE</code>\n\n"
            "Example: <code>/rmcode ABC123XYZ7</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    code = args[1].strip().upper()
    
    try:
        success, message = code_repo.deactivate_code(code)
        if success:
            await msg.answer(
                f"[✅] <b>Code Removed</b>\n\n"
                f"[📋] Code: <code>{code}</code>\n"
                f"[📝] {message}",
                parse_mode=ParseMode.HTML
            )
        else:
            await msg.answer(
                f"[❌] <b>Error</b>\n\n{message}",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await msg.answer(
            f"[❌] <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )

@router.message(Command("codes"))
async def list_codes_handler(msg: Message):
    """List all redeem codes - /codes"""
    if not is_owner_or_admin(msg.from_user.id):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "This command is only for admins.",
            parse_mode=ParseMode.HTML
        )
        return
    
    codes = code_repo.get_all_codes(include_used=True)
    stats = code_repo.get_stats()
    
    if not codes:
        await msg.answer(
            "[📋] <b>No Codes Found</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Show first 20 codes
    codes_text = []
    for code in codes[:20]:
        status = "✅ Used" if code.get("is_used") else "🆕 Available"
        if not code.get("is_active"):
            status = "❌ Deactivated"
        codes_text.append(f"<code>{code['code']}</code> - {code['credits']} credits - {status}")
    
    if len(codes) > 20:
        codes_text.append(f"... and {len(codes) - 20} more")
    
    await msg.answer(
        f"[📊] <b>Code Statistics</b>\n\n"
        f"[📦] Total: {stats['total']}\n"
        f"[✅] Used: {stats['used']}\n"
        f"[🆕] Available: {stats['active']}\n"
        f"[💰] Total Credits: {stats['total_credits']}\n"
        f"[💸] Redeemed: {stats['redeemed_credits']}\n\n"
        f"[📋] <b>Recent Codes:</b>\n" + "\n".join(codes_text),
        parse_mode=ParseMode.HTML
    )

@router.message(Command("addcredits"))
async def add_credits_handler(msg: Message):
    """Manually add credits to user - /addcredits {user_id} {amount}"""
    if not is_owner_or_admin(msg.from_user.id):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "This command is only for admins.",
            parse_mode=ParseMode.HTML
        )
        return
    
    args = msg.text.split()
    if len(args) < 3:
        await msg.answer(
            "[❌] <b>Usage</b>\n\n"
            "<code>/addcredits USER_ID AMOUNT</code>\n\n"
            "Example: <code>/addcredits 123456789 100</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_user = int(args[1])
        amount = int(args[2])
        
        if amount <= 0:
            await msg.answer(
                "[❌] <b>Invalid Amount</b>\n\n"
                "Amount must be positive",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Ensure user exists
        user_repo.add_user(target_user)
        
        success, before, after = user_repo.add_credits(
            target_user,
            amount,
            f"Manual add by admin {msg.from_user.id}"
        )
        
        if success:
            # Activate user
            user_repo.set_active(target_user, True)
            
            await msg.answer(
                f"[✅] <b>Credits Added</b>\n\n"
                f"[👤] User: <code>{target_user}</code>\n"
                f"[💰] Before: {before}\n"
                f"[➕] Added: +{amount}\n"
                f"[💰] After: {after}",
                parse_mode=ParseMode.HTML
            )
        else:
            await msg.answer(
                "[❌] <b>Failed to add credits</b>",
                parse_mode=ParseMode.HTML
            )
            
    except ValueError:
        await msg.answer(
            "[❌] <b>Invalid Numbers</b>\n\n"
            "Please provide valid user ID and amount",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.answer(
            f"[❌] <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )