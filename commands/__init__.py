# commands/__init__.py
from aiogram import Router

router = Router()

from .start import router as start_router
from .help import router as help_router
from .co import router as co_router
from .bco import router as bco_router
from .proxy_handlers import router as proxy_router
from .admin import router as admin_router
from .stripe_checkout import router as stripe_router
from .gen import router as gen_router
from .credit_user import router as credit_user_router      # NEW - Credit user commands
from .credit_admin import router as credit_admin_router    # NEW - Credit admin commands

router.include_router(start_router)
router.include_router(help_router)
router.include_router(co_router)
router.include_router(bco_router)
router.include_router(proxy_router)
router.include_router(admin_router)
router.include_router(stripe_router)
router.include_router(gen_router)
router.include_router(credit_user_router)      # Add this
router.include_router(credit_admin_router)     # Add this