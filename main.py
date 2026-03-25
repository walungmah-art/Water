# main.py
"""
Main entry point for XMAN Stripe Bot
Enhanced 2026 version with all middleware and database connections
"""

import asyncio
import logging
import sys
import signal
import os
from pathlib import Path
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Import from config_bot
from config_bot import BOT_TOKEN, DEBUG, config, validate_config, print_config_summary
from config_bot.credit_costs import FREE_COMMANDS, ADMIN_COMMANDS
from commands import router

# Import functions for cleanup
from functions.charge_functions import close_session
from functions.co_functions import close_parser_session

# Import MongoDB client and repositories
from database.mongo_client import MongoDBClient
from database.repositories import StatsRepository, UserRepository

# Import middleware
from middleware import CreditCheckMiddleware, RateLimitMiddleware, LoggingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Global variables
bot = None
dp = None
shutdown_event = asyncio.Event()
stats_repo = None
user_repo = None
start_time = datetime.now()

async def health_check_server():
    """Simple health check server for Railway"""
    app = web.Application()
    
    async def health_check(request):
        return web.Response(text="OK")
    
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Get port from environment or use default
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Health check server running on port {port}")

async def on_startup():
    """Actions to perform on bot startup"""
    logger.info("=" * 60)
    logger.info("🚀 XMAN STRIPE BOT v2.5 starting up...")
    logger.info("=" * 60)
    
    # Print configuration summary
    print_config_summary()
    
    # Validate configuration
    if not validate_config():
        logger.error("❌ Configuration validation failed!")
        return
    
    # Initialize MongoDB connection
    try:
        mongo = MongoDBClient()
        logger.info("✅ MongoDB connected successfully")
        
        # Test connection by pinging
        mongo.db.command('ping')
        logger.info("✅ MongoDB ping successful")
        
        # Initialize repositories
        global stats_repo, user_repo
        stats_repo = StatsRepository()
        user_repo = UserRepository()
        
        # Initialize daily stats
        try:
            await stats_repo.update_daily_stats()
            logger.info("✅ Daily stats initialized")
        except Exception as e:
            logger.warning(f"⚠️ Could not update daily stats: {e}")
            
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        logger.warning("⚠️ Bot will continue but credit system may not work!")
    
    # Log bot info
    logger.info(f"✅ Bot token: {BOT_TOKEN[:10] if BOT_TOKEN else 'Not set'}...")
    logger.info(f"✅ Allowed group: {config.ALLOWED_GROUP}")
    logger.info(f"✅ Owner ID: {config.OWNER_ID}")
    logger.info(f"📊 Debug mode: {'ON' if DEBUG else 'OFF'}")
    logger.info(f"📊 Free commands: {len(FREE_COMMANDS)}")
    logger.info(f"📊 Admin commands: {len(ADMIN_COMMANDS)}")
    logger.info("=" * 60)
    logger.info("✅ Bot is ready to accept commands")
    logger.info("=" * 60)

async def on_shutdown():
    """Actions to perform on bot shutdown"""
    logger.info("=" * 60)
    logger.info("🛑 XMAN Bot is shutting down...")
    logger.info("=" * 60)
    
    # Calculate uptime
    uptime = datetime.now() - start_time
    logger.info(f"⏱️ Bot uptime: {uptime}")
    
    # Update final stats
    if stats_repo:
        try:
            await stats_repo.update_daily_stats()
            logger.info("✅ Final stats updated")
        except Exception as e:
            logger.error(f"❌ Error updating stats: {e}")
    
    # Cleanup charge functions session
    try:
        await close_session()
        logger.info("✅ Charge functions session closed")
    except Exception as e:
        logger.error(f"❌ Error closing charge session: {e}")
    
    # Cleanup co functions session
    try:
        await close_parser_session()
        logger.info("✅ Checkout parser session closed")
    except Exception as e:
        logger.error(f"❌ Error closing parser session: {e}")
    
    # Close MongoDB connection
    try:
        MongoDBClient().close()
        logger.info("✅ MongoDB connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing MongoDB: {e}")
    
    # Close bot session
    if bot and bot.session:
        await bot.session.close()
        logger.info("✅ Bot session closed")
    
    logger.info("✅ Shutdown complete")
    shutdown_event.set()

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info(f"📡 Received signal {sig}, initiating shutdown...")
    asyncio.create_task(on_shutdown())

async def main():
    """Main entry point"""
    global bot, dp, start_time
    
    try:
        # Validate bot token
        if not BOT_TOKEN or BOT_TOKEN == "DEV_TOKEN_PLACEHOLDER":
            logger.error("❌ BOT_TOKEN is not properly set in Railway environment variables!")
            logger.error("Please set BOT_TOKEN in Railway dashboard and redeploy.")
            return
        
        # Initialize bot with HTML parse mode
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Initialize dispatcher
        dp = Dispatcher()
        
        # Include router
        dp.include_router(router)
        
        # Add middleware in correct order
        dp.message.middleware(LoggingMiddleware())      # First - log everything
        dp.message.middleware(RateLimitMiddleware())    # Second - rate limit
        dp.message.middleware(CreditCheckMiddleware())  # Third - check credits
        
        # Register lifecycle hooks
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start health check server if on Railway
        if hasattr(config, 'IS_RAILWAY') and config.IS_RAILWAY:
            asyncio.create_task(health_check_server())
            logger.info("✅ Health check server started")
        elif os.getenv("RAILWAY_SERVICE_NAME"):  # Fallback check
            asyncio.create_task(health_check_server())
            logger.info("✅ Health check server started (fallback detection)")
        
        logger.info("🔄 Starting polling...")
        
        # Start polling with error handling
        await dp.start_polling(
            bot,
            skip_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard interrupt received")
        await on_shutdown()
        
    except Exception as e:
        logger.error(f"❌ Fatal error in main: {e}", exc_info=True)
        await on_shutdown()
        
    finally:
        # Wait for shutdown to complete
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Shutdown timed out")
        
        logger.info("👋 Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
