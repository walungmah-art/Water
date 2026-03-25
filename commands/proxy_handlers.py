# commands/proxy_handlers.py
"""
Proxy management commands for the bot with modern UI
"""

import time
import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.proxy_utils import (
    get_user_proxies,
    get_user_proxy,
    add_user_proxy,
    remove_user_proxy,
    check_proxy_alive,
    check_proxies_batch,
    get_proxy_info,
    check_access,
    format_proxy_list
)

router = Router()

# Response templates with modern UI
ACCESS_DENIED = (
    "❌ <b>Access Denied</b>\n\n"
    "[🔗] Join to use: @XMANSPEAK"
)

PROXY_HELP = """
[🔒] <b>PROXY MANAGER</b>

[📝] <b>Commands:</b>
• <code>/addproxy proxy</code> – Add proxy
• <code>/removeproxy proxy</code> – Remove proxy
• <code>/removeproxy all</code> – Remove all
• <code>/proxy</code> – List proxies
• <code>/proxy check</code> – Check all

[📦] <b>Formats:</b>
• <code>host:port:user:pass</code>
• <code>user:pass@host:port</code>
• <code>host:port</code>
"""

@router.message(Command("addproxy"))
async def addproxy_handler(msg: Message):
    """Add proxy command"""
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return
    
    args = msg.text.split(maxsplit=1)
    user_id = msg.from_user.id
    user_proxies = get_user_proxies(user_id)
    
    # Show help if no proxy provided
    if len(args) < 2:
        proxy_list = format_proxy_list(user_proxies)
        await msg.answer(
            f"[📋] <b>Your Proxies ({len(user_proxies)})</b>\n\n"
            f"{proxy_list}\n\n"
            f"{PROXY_HELP}",
            parse_mode=ParseMode.HTML
        )
        return
    
    proxy_input = args[1].strip()
    proxies_to_add = [p.strip() for p in proxy_input.split('\n') if p.strip()]
    
    if not proxies_to_add:
        await msg.answer(
            "❌ <b>Error</b>\n\n"
            "[⚠️] No valid proxies provided",
            parse_mode=ParseMode.HTML
        )
        return
    
    checking_msg = await msg.answer(
        f"[🔄] <b>Checking Proxies</b>\n\n"
        f"[📊] Total: {len(proxies_to_add)}\n"
        f"[⚡] Threads: 10\n"
        f"[⏳] Status: Testing...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Add timeout to prevent hanging
        results = await asyncio.wait_for(
            check_proxies_batch(proxies_to_add, max_concurrent=10),
            timeout=45  # 45 seconds timeout
        )
    except asyncio.TimeoutError:
        await checking_msg.edit_text(
            "❌ <b>Timeout Error</b>\n\n"
            "[⚠️] Proxy checking took too long.\n"
            "[📝] Please try again with fewer proxies or check your connection.",
            parse_mode=ParseMode.HTML
        )
        return
    except Exception as e:
        await checking_msg.edit_text(
            f"❌ <b>Error</b>\n\n"
            f"[⚠️] {str(e)[:100]}",
            parse_mode=ParseMode.HTML
        )
        return
    
    alive_proxies = []
    dead_proxies = []
    
    for r in results:
        if r["status"] == "alive":
            alive_proxies.append(r)
            # Add to database
            add_user_proxy(user_id, r["proxy"])
        else:
            dead_proxies.append(r)
    
    response = f"""
[✅] <b>Proxy Check Complete</b>

[📊] <b>Results:</b>
• Alive: {len(alive_proxies)}/{len(proxies_to_add)} ✅
• Dead: {len(dead_proxies)}/{len(proxies_to_add)} ❌
"""
    
    if alive_proxies:
        response += "\n[✅] <b>Added Proxies:</b>\n"
        for p in alive_proxies[:5]:
            response += f"• <code>{p['proxy']}</code> ({p['response_time']})\n"
        if len(alive_proxies) > 5:
            response += f"• ... and {len(alive_proxies) - 5} more\n"
    
    if dead_proxies and len(dead_proxies) <= 5:
        response += "\n[❌] <b>Failed Proxies:</b>\n"
        for p in dead_proxies[:5]:
            error = p.get('error', 'Unknown error')
            response += f"• <code>{p['proxy']}</code> - {error}\n"
    
    await checking_msg.edit_text(response.strip(), parse_mode=ParseMode.HTML)

@router.message(Command("removeproxy"))
async def removeproxy_handler(msg: Message):
    """Remove proxy command"""
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return
    
    args = msg.text.split(maxsplit=1)
    user_id = msg.from_user.id
    
    if len(args) < 2:
        await msg.answer(
            "[🗑️] <b>REMOVE PROXY</b>\n\n"
            "[📝] Usage:\n"
            "• <code>/removeproxy proxy</code> – Remove specific\n"
            "• <code>/removeproxy all</code> – Remove all",
            parse_mode=ParseMode.HTML
        )
        return
    
    proxy_input = args[1].strip()
    
    if proxy_input.lower() == "all":
        user_proxies = get_user_proxies(user_id)
        count = len(user_proxies)
        success = remove_user_proxy(user_id, "all")
        if success:
            await msg.answer(
                f"[✅] <b>All Proxies Removed</b>\n\n"
                f"[📊] Removed: {count} proxies",
                parse_mode=ParseMode.HTML
            )
        else:
            await msg.answer(
                "❌ <b>Error</b>\n\n"
                "[⚠️] No proxies found to remove",
                parse_mode=ParseMode.HTML
            )
        return
    
    if remove_user_proxy(user_id, proxy_input):
        await msg.answer(
            f"[✅] <b>Proxy Removed</b>\n\n"
            f"[🔌] Proxy: <code>{proxy_input}</code>",
            parse_mode=ParseMode.HTML
        )
    else:
        await msg.answer(
            "❌ <b>Error</b>\n\n"
            f"[⚠️] Proxy not found: <code>{proxy_input}</code>",
            parse_mode=ParseMode.HTML
        )

@router.message(Command("proxy"))
async def proxy_handler(msg: Message):
    """Proxy management command"""
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return
    
    args = msg.text.split(maxsplit=1)
    user_id = msg.from_user.id
    
    # Show proxy list if no arguments or not "check"
    if len(args) < 2 or args[1].strip().lower() != "check":
        user_proxies = get_user_proxies(user_id)
        
        if user_proxies:
            proxy_lines = []
            for i, proxy in enumerate(user_proxies[:10], 1):
                proxy_lines.append(f"{i}. <code>{proxy}</code>")
            
            if len(user_proxies) > 10:
                proxy_lines.append(f"• ... and {len(user_proxies) - 10} more")
            
            proxy_list = "\n".join(proxy_lines)
        else:
            proxy_list = "• None"
        
        await msg.answer(
            f"[📋] <b>Your Proxies ({len(user_proxies)})</b>\n\n"
            f"{proxy_list}\n\n"
            f"[🔍] <code>/proxy check</code> – Test all proxies",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check all proxies
    user_proxies = get_user_proxies(user_id)
    
    if not user_proxies:
        await msg.answer(
            "❌ <b>No Proxies</b>\n\n"
            "[⚠️] No proxies to check\n"
            "[📝] Add with: <code>/addproxy proxy</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    checking_msg = await msg.answer(
        f"[🔄] <b>Checking Proxies</b>\n\n"
        f"[📊] Total: {len(user_proxies)}\n"
        f"[⚡] Threads: 10\n"
        f"[⏳] Status: Testing...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Add timeout to prevent hanging
        results = await asyncio.wait_for(
            check_proxies_batch(user_proxies, max_concurrent=10),
            timeout=45
        )
    except asyncio.TimeoutError:
        await checking_msg.edit_text(
            "❌ <b>Timeout Error</b>\n\n"
            "[⚠️] Proxy checking took too long.\n"
            "[📝] Some proxies may be unresponsive.",
            parse_mode=ParseMode.HTML
        )
        return
    except Exception as e:
        await checking_msg.edit_text(
            f"❌ <b>Error</b>\n\n"
            f"[⚠️] {str(e)[:100]}",
            parse_mode=ParseMode.HTML
        )
        return
    
    alive = [r for r in results if r["status"] == "alive"]
    dead = [r for r in results if r["status"] == "dead"]
    
    response = f"""
[📊] <b>Proxy Check Results</b>

[📈] <b>Summary:</b>
• Alive: {len(alive)}/{len(user_proxies)} ✅
• Dead: {len(dead)}/{len(user_proxies)} ❌
"""
    
    if alive:
        response += "\n[✅] <b>Alive Proxies:</b>\n"
        for p in alive[:5]:
            ip_display = p['external_ip'] or 'Unknown'
            response += f"• <code>{p['proxy']}</code>\n  IP: {ip_display} | ⚡ {p['response_time']}\n"
        if len(alive) > 5:
            response += f"• ... and {len(alive) - 5} more\n"
    
    if dead:
        response += "\n[❌] <b>Dead Proxies:</b>\n"
        for p in dead[:3]:
            error = p.get('error', 'Unknown')
            response += f"• <code>{p['proxy']}</code> ({error})\n"
        if len(dead) > 3:
            response += f"• ... and {len(dead) - 3} more\n"
    
    await checking_msg.edit_text(response.strip(), parse_mode=ParseMode.HTML)

# Optional: Add a command to test a single proxy quickly
@router.message(Command("testproxy"))
async def test_proxy_handler(msg: Message):
    """Test a single proxy"""
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer(
            "[🔍] <b>TEST PROXY</b>\n\n"
            "[📝] Usage: <code>/testproxy proxy_string</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    proxy_str = args[1].strip()
    
    testing_msg = await msg.answer(
        f"[🔄] Testing proxy: <code>{proxy_str}</code>...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        result = await asyncio.wait_for(
            check_proxy_alive(proxy_str, timeout=15),
            timeout=20
        )
        
        if result["status"] == "alive":
            response = f"""
[✅] <b>Proxy is Alive</b>

[🔌] Proxy: <code>{proxy_str}</code>
[🌐] IP: {result.get('external_ip', 'Unknown')}
[⚡] Response: {result.get('response_time', 'N/A')}
"""
        else:
            response = f"""
[❌] <b>Proxy is Dead</b>

[🔌] Proxy: <code>{proxy_str}</code>
[⚠️] Error: {result.get('error', 'Unknown')}
"""
        await testing_msg.edit_text(response.strip(), parse_mode=ParseMode.HTML)
        
    except asyncio.TimeoutError:
        await testing_msg.edit_text(
            f"[❌] <b>Timeout</b>\n\n"
            f"[🔌] Proxy: <code>{proxy_str}</code>\n"
            f"[⚠️] Connection timed out",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await testing_msg.edit_text(
            f"[❌] <b>Error</b>\n\n"
            f"[🔌] Proxy: <code>{proxy_str}</code>\n"
            f"[⚠️] {str(e)[:100]}",
            parse_mode=ParseMode.HTML
        )