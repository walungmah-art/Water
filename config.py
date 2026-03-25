# config.py
"""
Main configuration file for the bot
Imports everything from config_bot for backward compatibility
Enhanced 2026 version with all settings
"""

import os
import sys
import logging
from pathlib import Path

# Add config_bot to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import everything from config_bot
from config_bot import *
from config_bot import __all__ as config_bot_all

# Print confirmation
logger.info("✅ Loaded configuration from config_bot (v2.5)")

# Re-export everything
__all__ = config_bot_all + ['__version__']

# Version
__version__ = "2.5.0"
