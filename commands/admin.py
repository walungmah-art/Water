# commands/admin.py
"""
Admin-only commands for bot management with modern UI and MongoDB integration
"""

import os
import time
import json
import asyncio
import logging
from datetime import datetime
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import OWNER_ID, USER_FILE
from functions.proxy_utils import load_users, save_users, add_allowed_user, remove_allowed_user
from database.repositories import UserRepository, TransactionRepository, RedeemCodeRepository, ProxyRepository

router = Router()
logger = logging.getLogger(__name__)

# Initialize repositories
user_repo = UserRepository()
tx_repo = TransactionRepository()
code_repo = RedeemCodeRepository()
proxy_repo = ProxyRepository()

# Statistics tracking (keep for uptime)
bot_stats = {
    "start_time": datetime.now(),
    "commands_processed": 0,
    "cards_charged": 0,
    "successful_charges": 0,
    "failed_charges": 0,
    "proxies_added": 0,
    "users_count": 0
}

def is_owner(func):
    """Decorator to check if user is owner - accepts any kwargs"""
    async def wrapper(msg: Message, *args, **kwargs):
        if msg.from_user.id != OWNER_ID:
            await msg.answer("❌ This command is only for bot owner.")
            return
        return await func(msg, *args, **kwargs)
    return wrapper

@router.message(Command("adduser"))
@is_owner
async def adduser_handler(msg: Message, **kwargs):
    """Add user to allowed list"""
    args = (msg.text or "").split(maxsplit=1)
    
    if len(args) < 2:
        await msg.answer(
            "[👥] <b>ADD USER</b>\n\n"
            "[📝] Usage: <code>/adduser user_id</code>\n"
            "[💡] Example: <code>/adduser 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await msg.answer("❌ Invalid user ID. Must be a number.")
        return
    
    # Add user to MongoDB
    user_repo.add_user(user_id)
    user_repo.set_allowed(user_id, True)
    
    await msg.answer(
        f"[✅] <b>User Added</b>\n\n"
        f"[👤] User ID: <code>{user_id}</code>\n"
        f"[🔓] Status: Now has access to bot",
        parse_mode=ParseMode.HTML
    )
    
    # Update stats
    bot_stats["users_count"] = len(user_repo.get_all_users())

@router.message(Command("removeuser"))
@is_owner
async def removeuser_handler(msg: Message, **kwargs):
    """Remove user from allowed list"""
    args = (msg.text or "").split(maxsplit=1)
    
    if len(args) < 2:
        await msg.answer(
            "[👥] <b>REMOVE USER</b>\n\n"
            "[📝] Usage: <code>/removeuser user_id</code>\n"
            "[💡] Example: <code>/removeuser 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await msg.answer("❌ Invalid user ID. Must be a number.")
        return
    
    if user_id == OWNER_ID:
        await msg.answer("❌ Cannot remove owner.")
        return
    
    # Remove user from allowed list in MongoDB
    user_repo.set_allowed(user_id, False)
    
    await msg.answer(
        f"[✅] <b>User Removed</b>\n\n"
        f"[👤] User ID: <code>{user_id}</code>\n"
        f"[🔒] Status: Access revoked",
        parse_mode=ParseMode.HTML
    )
    
    # Update stats
    bot_stats["users_count"] = len(user_repo.get_all_users())

@router.message(Command("users"))
@is_owner
async def users_handler(msg: Message, **kwargs):
    """List all allowed users from MongoDB"""
    users = user_repo.get_all_users()
    allowed_users = [u for u in users if u.get("is_allowed", False)]
    
    if not allowed_users:
        await msg.answer(
            "[📋] <b>User List</b>\n\n"
            "[ℹ️] No users found",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Format user list with additional info
    user_lines = []
    for i, user in enumerate(allowed_users[:20], 1):  # Limit to 20 users
        user_id = user.get("user_id", "Unknown")
        credits = user.get("credits", 0)
        is_active = "✅" if user.get("is_active", False) else "❌"
        user_lines.append(f"{i}. <code>{user_id}</code> | Credits: {credits} | {is_active}")
    
    user_list = "\n".join(user_lines)
    
    if len(allowed_users) > 20:
        user_list += f"\n... and {len(allowed_users) - 20} more"
    
    await msg.answer(
        f"[📋] <b>User List [{len(allowed_users)}]</b>\n\n"
        f"{user_list}\n\n"
        f"[👑] Owner: <code>{OWNER_ID}</code>",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("stats"))
@is_owner
async def stats_handler(msg: Message, **kwargs):
    """Show bot statistics from MongoDB"""
    uptime = datetime.now() - bot_stats["start_time"]
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Get stats from MongoDB
    users = user_repo.get_all_users()
    active_users = [u for u in users if u.get("is_active", False)]
    allowed_users = [u for u in users if u.get("is_allowed", False)]
    
    # Get transaction stats
    tx_stats = {
        "total": 0,
        "charged": 0,
        "declined": 0,
        "total_amount": 0
    }
    
    try:
        # Aggregate transaction stats
        pipeline = [
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "charged": {"$sum": {"$cond": [{"$eq": ["$status", "CHARGED"]}, 1, 0]}},
                "declined": {"$sum": {"$cond": [{"$eq": ["$status", "DECLINED"]}, 1, 0]}},
                "total_amount": {"$sum": "$amount"}
            }}
        ]
        result = list(tx_repo.collection.aggregate(pipeline))
        if result:
            tx_stats = result[0]
    except:
        pass
    
    # Get proxy stats
    all_proxies = list(proxy_repo.collection.find({}))
    active_proxies = [p for p in all_proxies if p.get("is_active", False)]
    
    # Get redeem code stats
    code_stats = code_repo.get_stats()
    
    # Calculate success rate
    total_charges = bot_stats["successful_charges"] + bot_stats["failed_charges"]
    success_rate = (bot_stats["successful_charges"] / total_charges * 100) if total_charges > 0 else 0
    
    # Total credits in system
    total_credits = sum(u.get("credits", 0) for u in users)
    
    stats_text = f"""
[📊] <b>BOT STATISTICS</b>

[⏱️] <b>Uptime:</b> {hours}h {minutes}m {seconds}s
[📝] <b>Commands:</b> {bot_stats['commands_processed']}

[👥] <b>USER STATISTICS</b>
• Total Users: {len(users)}
• Active Users: {len(active_users)}
• Allowed Users: {len(allowed_users)}
• Total Credits: {total_credits}

[💳] <b>TRANSACTION STATISTICS</b>
• Total Charges: {tx_stats['total']}
• ✅ Successful: {tx_stats['charged']}
• ❌ Failed: {tx_stats['declined']}
• 📈 Success Rate: {(tx_stats['charged']/tx_stats['total']*100) if tx_stats['total'] > 0 else 0:.1f}%
• 💰 Total Amount: ${tx_stats['total_amount']/100:.2f}

[🔒] <b>PROXY STATISTICS</b>
• Total Proxies: {len(all_proxies)}
• 🟢 Active: {len(active_proxies)}
• 🔴 Inactive: {len(all_proxies) - len(active_proxies)}

[🎟️] <b>REDEEM CODE STATISTICS</b>
• Total Codes: {code_stats['total']}
• ✅ Used: {code_stats['used']}
• 🆕 Available: {code_stats['active']}
• 💰 Credits Generated: {code_stats['total_credits']}
• 💸 Credits Redeemed: {code_stats['redeemed_credits']}

[⚡] <b>PERFORMANCE</b>
• Success Rate: {success_rate:.1f}%
• Proxies Added: {bot_stats['proxies_added']}
"""
    await msg.answer(stats_text.strip(), parse_mode=ParseMode.HTML)

@router.message(Command("broadcast"))
@is_owner
async def broadcast_handler(msg: Message, **kwargs):
    """Broadcast message to all users"""
    args = (msg.text or "").split(maxsplit=1)
    
    if len(args) < 2:
        await msg.answer(
            "[📢] <b>BROADCAST</b>\n\n"
            "[📝] Usage: <code>/broadcast your message here</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    broadcast_text = args[1].strip()
    
    # Get all users from MongoDB
    users = user_repo.get_all_users()
    user_ids = [u["user_id"] for u in users if u.get("is_active", False)]
    
    if not user_ids:
        await msg.answer("❌ No active users to broadcast to.")
        return
    
    # Add owner to broadcast list
    all_recipients = list(set(user_ids + [OWNER_ID]))
    
    success_count = 0
    fail_count = 0
    
    status_msg = await msg.answer(f"[📢] Broadcasting to {len(all_recipients)} users...")
    
    for user_id in all_recipients:
        try:
            await msg.bot.send_message(
                user_id,
                f"[📢] <b>Broadcast Message</b>\n\n"
                f"{broadcast_text}\n\n"
                f"[👤] From: @{msg.from_user.username or 'Admin'}",
                parse_mode=ParseMode.HTML
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to broadcast to {user_id}: {e}")
            fail_count += 1
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.1)
    
    await status_msg.edit_text(
        f"[✅] <b>Broadcast Complete</b>\n\n"
        f"[✅] Success: {success_count}\n"
        f"[❌] Failed: {fail_count}\n"
        f"[📊] Total: {len(all_recipients)}",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("logs"))
@is_owner
async def logs_handler(msg: Message, **kwargs):
    """Get bot logs"""
    args = (msg.text or "").split(maxsplit=1)
    lines = 100  # Default
    
    if len(args) > 1:
        try:
            lines = int(args[1].strip())
            lines = min(max(lines, 10), 500)  # Limit between 10-500
        except ValueError:
            pass
    
    log_file = "bot.log"
    
    if not os.path.exists(log_file):
        await msg.answer("❌ Log file not found.")
        return
    
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:]
        
        log_text = "".join(last_lines)
        
        # Split if too long
        if len(log_text) > 4000:
            chunks = [log_text[i:i+4000] for i in range(0, len(log_text), 4000)]
            for i, chunk in enumerate(chunks, 1):
                await msg.answer(
                    f"[📋] <b>Logs [Part {i}/{len(chunks)}]</b>\n\n"
                    f"<code>{chunk}</code>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await msg.answer(
                f"[📋] <b>Logs [Last {len(last_lines)} lines]</b>\n\n"
                f"<code>{log_text}</code>",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await msg.answer(f"❌ Error reading logs: {e}")

@router.message(Command("restart"))
@is_owner
async def restart_handler(msg: Message, **kwargs):
    """Restart the bot"""
    await msg.answer(
        "[🔄] <b>Restarting...</b>\n\n"
        "[⏱️] Bot will be back in a few seconds",
        parse_mode=ParseMode.HTML
    )
    
    # Log restart
    logger.info(f"Bot restart initiated by {msg.from_user.id}")
    
    # Exit with code that supervisor can detect
    os._exit(0)

# Function to update stats (call from other handlers)
def update_stats(command: str = None, charge_success: bool = None, proxy_added: bool = None):
    """Update bot statistics"""
    if command:
        bot_stats["commands_processed"] += 1
    
    if charge_success is not None:
        bot_stats["cards_charged"] += 1
        if charge_success:
            bot_stats["successful_charges"] += 1
        else:
            bot_stats["failed_charges"] += 1
    
    if proxy_added:
        bot_stats["proxies_added"] += 1
    
    # Update users count from MongoDB
    bot_stats["users_count"] = len(user_repo.get_all_users())