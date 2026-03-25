# middleware/credit_check.py
"""
Credit check middleware for bot commands
Enhanced 2026 version with proper free command handling and dual access control
"""

from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
import logging

from database.repositories import UserRepository
from config_bot import OWNER_ID
from config_bot.credit_costs import FREE_COMMANDS, ADMIN_COMMANDS, get_command_cost
from functions.proxy_utils import check_access, check_paid_access

logger = logging.getLogger(__name__)

class CreditCheckMiddleware(BaseMiddleware):
    """Middleware to check if user has enough credits"""
    
    def __init__(self):
        self.user_repo = UserRepository()
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Skip if not a message or no text
        if not event.text:
            return await handler(event, data)
        
        # Get command (first word)
        command = event.text.split()[0].lower()
        full_text = event.text
        
        # DEBUG: Log the command and user
        print(f"[DEBUG] User {event.from_user.id} used command: {full_text[:50]}")
        
        # Always allow /start and /help for everyone
        if command in ["/start", "/help"]:
            print(f"[DEBUG] Allowing {command} for everyone")
            return await handler(event, data)
        
        # Check if user is owner (always allowed)
        if event.from_user.id == OWNER_ID:
            print(f"[DEBUG] Owner detected, allowing all commands")
            return await handler(event, data)
        
        # Check if it's a free command - these should work for ANY user
        if command in FREE_COMMANDS:
            print(f"[DEBUG] Free command detected: {command}")
            # For free commands, we just need to ensure user exists in DB
            # but don't check credits or active status
            user = self.user_repo.get_user(event.from_user.id)
            if not user:
                # Create user if they don't exist
                self.user_repo.add_user(
                    event.from_user.id,
                    event.from_user.username,
                    event.from_user.first_name,
                    event.from_user.last_name
                )
                print(f"[DEBUG] Created new user for free command")
            return await handler(event, data)
        
        # For paid commands, check if user has paid access (allowed users only)
        if not check_paid_access(event):
            await event.answer(
                "❌ <b>Access Denied for Paid Commands</b>\n\n"
                "You need to be added as an allowed user to use paid commands.\n"
                f"Free commands available: {', '.join(FREE_COMMANDS[:5])}...\n\n"
                "Contact @XMANSPEAK to get access.",
                parse_mode="HTML"
            )
            return
        
        # Check if user exists and has credits
        user = self.user_repo.get_user(event.from_user.id)
        
        if not user:
            # User exists in access control but not in MongoDB? Add them
            print(f"[DEBUG] User {event.from_user.id} not in MongoDB, adding...")
            self.user_repo.add_user(
                event.from_user.id,
                event.from_user.username,
                event.from_user.first_name,
                event.from_user.last_name
            )
            user = self.user_repo.get_user(event.from_user.id)
            
            if not user:
                await event.answer(
                    "[❌] <b>Error</b>\n\n"
                    "Could not create user account. Please contact support.",
                    parse_mode="HTML"
                )
                return
        
        # Check if user is admin (free)
        if user.get("is_admin", False):
            print(f"[DEBUG] Admin user detected, allowing all commands")
            return await handler(event, data)
        
        # Check if user is active
        if not user.get("is_active", False):
            print(f"[DEBUG] User {event.from_user.id} is inactive")
            await event.answer(
                "[❌] <b>Account Inactive</b>\n\n"
                "Your account is not active. Use /redeem to activate.\n\n"
                f"Free commands: {', '.join(FREE_COMMANDS[:5])}...",
                parse_mode="HTML"
            )
            return
        
        # Detect bypass strength from command
        bypass_strength = "none"
        if "yes" in full_text or "bypass" in full_text:
            bypass_strength = "maximum"
        elif "extreme" in full_text:
            bypass_strength = "extreme"
        elif "light" in full_text:
            bypass_strength = "light"
        elif "medium" in full_text:
            bypass_strength = "medium"
        
        # Detect card count for multi-card commands
        card_count = 1
        if command in ["/mst", "/txt"]:
            # Rough estimate - actual count will be checked in command handler
            lines = full_text.split('\n')
            card_count = max(1, len(lines) - 1) if len(lines) > 1 else 1
        
        # Calculate required credits
        required_credits = get_command_cost(command, bypass_strength, card_count)
        
        credits = user.get("credits", 0)
        print(f"[DEBUG] User {event.from_user.id} has {credits} credits, needs {required_credits}")
        
        if credits < required_credits:
            await event.answer(
                f"[❌] <b>Insufficient Credits</b>\n\n"
                f"You need {required_credits} credit(s) to use {command}\n"
                f"Your balance: {credits}\n"
                f"Use /buy to purchase credits or /redeem to redeem a code.\n\n"
                f"Free commands: {', '.join(FREE_COMMANDS[:5])}...",
                parse_mode="HTML"
            )
            return
        
        # User has enough credits, store info in data
        data["user_credits"] = credits
        data["required_credits"] = required_credits
        data["bypass_strength"] = bypass_strength
        
        print(f"[DEBUG] User {event.from_user.id} authorized to use {command}")
        return await handler(event, data)
