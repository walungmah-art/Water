# commands/co.py
"""
Checkout command handler for Stripe operations with modern UI and credit system
"""

import time
import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

# Import functions from functions package
from functions.proxy_utils import (
    get_user_proxy,
    get_proxy_info,
    check_access
)
from functions.co_functions import (
    extract_checkout_url,
    get_checkout_info,
    get_currency_symbol,
    check_checkout_active
)
from functions.card_utils import parse_cards, mask_card
from functions.charge_functions import charge_card, ChargeStatus

# Import database and credit modules
from database.repositories import UserRepository
from config_bot.credit_costs import CREDIT_COSTS, PER_CARD_COST
from config import OWNER_ID

router = Router()
user_repo = UserRepository()

# Response templates with modern UI
RESPONSES = {
    "access_denied": (
        "❌ <b>Access Denied</b>\n\n"
        "[🔗] Join to use: @XMANSPEAK"
    ),
    "usage": (
        "[⚡] <b>STRIPE CHECKOUT</b>\n\n"
        "[📦] <b>Usage:</b>\n"
        "• <code>/co url</code> – Parse checkout\n"
        "• <code>/co url cc|mm|yy|cvv</code> – Charge card\n"
        "• <code>/co url yes cc|mm|yy|cvv</code> – Charge with bypass\n"
        "• <code>/co url (reply to .txt)</code> – Bulk charge"
    ),
    "no_proxy": (
        "❌ <b>No Proxy</b>\n\n"
        "[🔒] You must set a proxy first\n"
        "• <code>/addproxy host:port:user:pass</code>"
    ),
    "proxy_dead": (
        "❌ <b>Proxy Dead</b>\n\n"
        "[⚠️] Your proxy is not responding\n"
        "• Check <code>/proxy</code>\n"
        "• <code>/removeproxy all</code> to remove"
    ),
    "no_cards": (
        "❌ <b>No Cards</b>\n\n"
        "[💳] No valid cards found\n"
        "• Format: <code>cc|mm|yy|cvv</code>"
    ),
    "too_many_cards": (
        "❌ <b>Too Many Cards</b>\n\n"
        "[⚠️] Maximum 100 cards per batch"
    ),
    "insufficient_credits": (
        "[❌] <b>Insufficient Credits</b>\n\n"
        "You need {cost} credit(s) for this operation.\n"
        "Your balance: {balance}\n"
        "Use /buy to purchase credits."
    ),
}

@router.message(Command("co"))
async def co_handler(msg: Message):
    """Main checkout command handler"""
    # Check access
    if not check_access(msg):
        await msg.answer(RESPONSES["access_denied"], parse_mode=ParseMode.HTML)
        return
    
    start_time = time.perf_counter()
    user_id = msg.from_user.id
    text = msg.text or ""
    lines = text.strip().split('\n')
    first_line_args = lines[0].split(maxsplit=3)
    
    # Show usage if no arguments
    if len(first_line_args) < 2:
        await msg.answer(RESPONSES["usage"], parse_mode=ParseMode.HTML)
        return
    
    # Extract URL
    url = extract_checkout_url(first_line_args[1])
    if not url:
        url = first_line_args[1].strip()
    
    # Parse arguments
    cards = []
    bypass_3ds = False
    
    if len(first_line_args) > 2:
        if first_line_args[2].lower() in ['yes', 'no']:
            bypass_3ds = first_line_args[2].lower() == 'yes'
            if len(first_line_args) > 3:
                cards = parse_cards(first_line_args[3])
        else:
            cards = parse_cards(first_line_args[2])
    
    # Check for multi-line cards
    if len(lines) > 1:
        remaining_text = '\n'.join(lines[1:])
        cards.extend(parse_cards(remaining_text))
    
    # Handle file attachment
    if msg.reply_to_message and msg.reply_to_message.document:
        doc = msg.reply_to_message.document
        if doc.file_name and doc.file_name.endswith('.txt'):
            try:
                file = await msg.bot.get_file(doc.file_id)
                file_content = await msg.bot.download_file(file.file_path)
                text_content = file_content.read().decode('utf-8')
                cards = parse_cards(text_content)
            except Exception as e:
                await msg.answer(
                    f"❌ <b>Error</b>\n\n"
                    f"[⚠️] Failed to read file: {str(e)}",
                    parse_mode=ParseMode.HTML
                )
                return
    
    # Validate cards if charging
    if cards and len(cards) == 0:
        await msg.answer(RESPONSES["no_cards"], parse_mode=ParseMode.HTML)
        return
    
    if len(cards) > 100:
        await msg.answer(RESPONSES["too_many_cards"], parse_mode=ParseMode.HTML)
        return
    
    # Get user proxy
    user_proxy = get_user_proxy(user_id)
    if not user_proxy:
        await msg.answer(RESPONSES["no_proxy"], parse_mode=ParseMode.HTML)
        return
    
    # Check proxy
    proxy_info = await get_proxy_info(user_proxy)
    if proxy_info["status"] == "dead":
        await msg.answer(RESPONSES["proxy_dead"], parse_mode=ParseMode.HTML)
        return
    
    proxy_display = f"LIVE ✅ | {proxy_info['ip_obfuscated']}"
    
    # Processing message
    processing_msg = await msg.answer(
        f"[⏳] <b>Processing</b>\n\n"
        f"[🌐] Proxy: <code>{proxy_display}</code>\n"
        f"[📊] Status: Parsing checkout...",
        parse_mode=ParseMode.HTML
    )
    
    # Get checkout info
    checkout_data = await get_checkout_info(url)
    
    if checkout_data.get("error"):
        await processing_msg.edit_text(
            f"❌ <b>Error</b>\n\n"
            f"[⚠️] {checkout_data['error']}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # If no cards, show checkout info (free)
    if not cards:
        await show_checkout_info(processing_msg, checkout_data, proxy_display, url, start_time)
        return
    
    # Check credits before processing
    if user_id != OWNER_ID:
        # Calculate total cost (1 credit per card for /co)
        total_cost = len(cards) * PER_CARD_COST
        
        # Check and deduct credits
        success, before, after = user_repo.use_credits(
            user_id, 
            total_cost, 
            "/co",
            {"card_count": len(cards), "url": url[:50] + "..." if len(url) > 50 else url}
        )
        
        if not success:
            await processing_msg.edit_text(
                RESPONSES["insufficient_credits"].format(cost=total_cost, balance=before),
                parse_mode=ParseMode.HTML
            )
            return
    
    # Charge cards
    await charge_cards_handler(
        processing_msg, cards, checkout_data, 
        user_proxy, proxy_display, url, 
        bypass_3ds, start_time
    )

async def show_checkout_info(msg: Message, checkout_data: dict, proxy_display: str, url: str, start_time: float):
    """Display checkout information with free trial detection"""
    
    # Check if it's a free trial
    if checkout_data.get("is_free_trial"):
        price_display = "🎁 FREE TRIAL"
    else:
        currency = checkout_data.get('currency', '')
        sym = get_currency_symbol(currency)
        price_display = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"
    
    total_time = round(time.perf_counter() - start_time, 2)
    
    response = f"""
[⚡] <b>CHECKOUT INFO</b>

[🏪] <b>Merchant:</b> {checkout_data.get('merchant', 'N/A')}
[📦] <b>Product:</b> {checkout_data.get('product', 'N/A')}
[💰] <b>Amount:</b> {price_display}
[🌍] <b>Country:</b> {checkout_data.get('country', 'N/A')}
[🔄] <b>Mode:</b> {checkout_data.get('mode', 'N/A')}

[🔑] <b>CS:</b> <code>{checkout_data.get('cs', 'N/A')}</code>
[🔐] <b>PK:</b> <code>{checkout_data.get('pk', 'N/A')}</code>

[⏱️] <b>Time:</b> {total_time}s
[🔗] <a href="{url}">Open Checkout</a>
"""
    await msg.edit_text(response.strip(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def charge_cards_handler(msg: Message, cards: list, checkout_data: dict, 
                               proxy: str, proxy_display: str, url: str,
                               bypass_3ds: bool, start_time: float):
    """Handle charging multiple cards with free trial support"""
    
    # Check if free trial
    if checkout_data.get("is_free_trial"):
        price_display = "🎁 FREE TRIAL"
    else:
        currency = checkout_data.get('currency', '')
        sym = get_currency_symbol(currency)
        price_display = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"
    
    bypass_str = "YES 🔓" if bypass_3ds else "NO 🔒"
    
    await msg.edit_text(
        f"[💳] <b>Charging {price_display}</b>\n\n"
        f"[🌐] Proxy: <code>{proxy_display}</code>\n"
        f"[🔓] Bypass: {bypass_str}\n"
        f"[📊] Cards: {len(cards)}\n"
        f"[⏳] Status: Starting...",
        parse_mode=ParseMode.HTML
    )
    
    results = []
    charged_card = None
    successful_card_data = None
    cancelled = False
    check_interval = 5
    last_update = time.perf_counter()
    
    for i, card in enumerate(cards):
        # Check if checkout still active for bulk operations
        if len(cards) > 1 and i > 0 and i % check_interval == 0:
            is_active = await check_checkout_active(checkout_data['pk'], checkout_data['cs'])
            if not is_active:
                cancelled = True
                break
        
        # Store card data before charging - handle both key formats (mm/yy and month/year)
        current_card_data = {
            'cc': card.get('cc', ''),
            'month': card.get('month', card.get('mm', '')),
            'year': card.get('year', card.get('yy', '')),
            'cvv': card.get('cvv', '')
        }
        
        # Charge card
        result = await charge_card(card, checkout_data, proxy, bypass_3ds)
        results.append(result)
        
        # Update progress for bulk operations
        if len(cards) > 1 and (time.perf_counter() - last_update) > 1.5:
            last_update = time.perf_counter()
            charged = sum(1 for r in results if r['status'] == 'CHARGED')
            declined = len(results) - charged
            
            try:
                await msg.edit_text(
                    f"[💳] <b>Charging {price_display}</b>\n\n"
                    f"[🌐] Proxy: <code>{proxy_display}</code>\n"
                    f"[🔓] Bypass: {bypass_str}\n"
                    f"[📊] Progress: {i+1}/{len(cards)}\n\n"
                    f"[✅] Charged: {charged}\n"
                    f"[❌] Declined: {declined}",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        
        # Check if successful (handle both string and enum comparison)
        if result['status'] == 'CHARGED' or result['status'] == ChargeStatus.CHARGED:
            charged_card = result
            successful_card_data = current_card_data
            break
    
    total_time = round(time.perf_counter() - start_time, 2)
    
    # Show final results (send new message instead of editing)
    await show_final_results(
        msg, results, cards, charged_card, successful_card_data, checkout_data,
        proxy_display, bypass_str, url, price_display, total_time, cancelled
    )
    
    # Try to delete the old processing message
    try:
        await msg.delete()
    except:
        pass  # Ignore if can't delete

async def update_progress(msg: Message, results: list, current: int, total: int, 
                         proxy_display: str, bypass_str: str, price_display: str):
    """Update progress for bulk charging"""
    charged = sum(1 for r in results if r['status'] == 'CHARGED')
    declined = len(results) - charged
    
    try:
        await msg.edit_text(
            f"[💳] <b>Charging {price_display}</b>\n\n"
            f"[🌐] Proxy: <code>{proxy_display}</code>\n"
            f"[🔓] Bypass: {bypass_str}\n"
            f"[📊] Progress: {current+1}/{total}\n\n"
            f"[✅] Charged: {charged}\n"
            f"[❌] Declined: {declined}",
            parse_mode=ParseMode.HTML
        )
    except:
        pass

async def show_final_results(msg: Message, results: list, cards: list, charged_card: dict,
                            successful_card_data: dict, checkout_data: dict, proxy_display: str, 
                            bypass_str: str, url: str, price_display: str, total_time: float, cancelled: bool):
    """Show final charging results - sends new message instead of editing old one"""
    
    if cancelled:
        response = f"""
[⏹️] <b>CHECKOUT CANCELLED</b>

[🏪] Merchant: {checkout_data.get('merchant', 'N/A')}
[💰] Amount: {price_display}

[📋] Reason: Checkout no longer active

[📊] Cards tried: {len(results)}
[✅] Charged: {sum(1 for r in results if r['status'] == 'CHARGED')}
[❌] Declined: {len(results) - sum(1 for r in results if r['status'] == 'CHARGED')}

[⏱️] Time: {total_time}s
"""
    elif charged_card and successful_card_data:
        # Format the successful card using month/year format
        card_str = f"{successful_card_data['cc']}|{successful_card_data['month']}|{successful_card_data['year']}|{successful_card_data['cvv']}"
        
        response = f"""
[✅] <b>PAYMENT SUCCESSFUL</b>

[🏪] Merchant: {checkout_data.get('merchant', 'N/A')}
[💰] Amount: {price_display}

[💳] <b>Card:</b>
<code>{card_str}</code>

[✅] Status: CHARGED
[⏱️] Time: {charged_card['time']}s

[📊] Tried before success: {len(results)}
[⏱️] Total time: {total_time}s

[🔗] <a href="{url}">Open Checkout</a>
"""
    elif len(results) == 1:
        r = results[0]
        status_emoji = {
            'CHARGED': '✅',
            'DECLINED': '❌',
            '3DS': '🔐',
            '3DS SKIP': '🔓',
            'NOT SUPPORTED': '🚫',
            'ERROR': '⚠️',
            'FAILED': '⚠️',
            'UNKNOWN': '❓'
        }.get(r['status'], '❓')
        
        response = f"""
[{status_emoji}] <b>{r['status']}</b>

[🏪] Merchant: {checkout_data.get('merchant', 'N/A')}
[💰] Amount: {price_display}

[💳] Card: <code>{mask_card(r['card'].split('|')[0])}</code>
[📝] Response: {r['response'][:100]}
[⏱️] Time: {r['time']}s

[🔗] <a href="{url}">Open Checkout</a>
"""
    else:
        charged = sum(1 for r in results if r['status'] == 'CHARGED')
        three_ds = sum(1 for r in results if r['status'] in ['3DS', '3DS SKIP'])
        errors = sum(1 for r in results if r['status'] in ['ERROR', 'FAILED', 'NOT SUPPORTED', 'UNKNOWN'])
        total = len(results)
        
        response = f"""
[📊] <b>BULK RESULTS</b>

[🏪] Merchant: {checkout_data.get('merchant', 'N/A')}
[💰] Amount: {price_display}

[✅] Charged: {charged}/{total}
[❌] Declined: {total - charged}/{total}
[🔐] 3DS: {three_ds}
[⚠️] Errors: {errors}

[⏱️] Total time: {total_time}s

[🔗] <a href="{url}">Open Checkout</a>
"""
    
    # Send as new message instead of editing old one
    await msg.answer(response.strip(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


# ========== USER MANAGEMENT FUNCTIONS (MongoDB Version) ==========

def load_users() -> list:
    """Load allowed users from MongoDB"""
    from database.repositories import UserRepository
    repo = UserRepository()
    users = repo.get_all_users()
    return [u["user_id"] for u in users if u.get("is_allowed", False)]

def save_users(users: list):
    """Save users to MongoDB - kept for compatibility"""
    from database.repositories import UserRepository
    repo = UserRepository()
    # This function is kept for backward compatibility
    # Actual user management should use the repositories directly
    pass

def is_allowed_user(user_id: int) -> bool:
    """Check if user is allowed using MongoDB"""
    from database.repositories import UserRepository
    repo = UserRepository()
    user = repo.get_user(user_id)
    return user.get("is_allowed", False) if user else False

def add_allowed_user(user_id: int):
    """Add user to allowed list in MongoDB"""
    from database.repositories import UserRepository
    repo = UserRepository()
    repo.add_user(user_id)
    repo.set_allowed(user_id, True)

def remove_allowed_user(user_id: int):
    """Remove user from allowed list in MongoDB"""
    from database.repositories import UserRepository
    repo = UserRepository()
    repo.set_allowed(user_id, False)


# ========== ADMIN COMMANDS ==========

@router.message(Command("adduser"))
async def adduser_handler(msg: Message):
    """Add user to allowed list (owner only) using MongoDB"""
    from config import OWNER_ID
    
    if not msg.from_user or msg.from_user.id != OWNER_ID:
        await msg.answer("❌ Only owner can use this command.")
        return

    args = (msg.text or "").split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("[👥] <b>ADD USER</b>\n\n[📝] Usage: <code>/adduser user_id</code>", parse_mode=ParseMode.HTML)
        return

    try:
        new_user_id = int(args[1].strip())
    except Exception:
        await msg.answer("❌ Invalid Telegram ID.")
        return

    add_allowed_user(new_user_id)
    await msg.answer(
        f"[✅] User <code>{new_user_id}</code> added successfully.",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("removeuser"))
async def removeuser_handler(msg: Message):
    """Remove user from allowed list (owner only) using MongoDB"""
    from config import OWNER_ID
    
    if not msg.from_user or msg.from_user.id != OWNER_ID:
        await msg.answer("❌ Only owner can use this command.")
        return

    args = (msg.text or "").split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("[👥] <b>REMOVE USER</b>\n\n[📝] Usage: <code>/removeuser user_id</code>", parse_mode=ParseMode.HTML)
        return

    try:
        user_id = int(args[1].strip())
    except Exception:
        await msg.answer("❌ Invalid Telegram ID.")
        return

    remove_allowed_user(user_id)
    await msg.answer(
        f"[✅] User <code>{user_id}</code> removed.",
        parse_mode=ParseMode.HTML
    )