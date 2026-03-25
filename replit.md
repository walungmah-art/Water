# XMAN Stripe Bot

A Telegram bot for processing Stripe payments, card checking, and managing a credit-based system for users.

## Tech Stack
- **Language**: Python 3.12
- **Telegram Framework**: aiogram 3.4.1 (async)
- **Database**: MongoDB (pymongo with SRV support)
- **HTTP Client**: aiohttp

## Project Structure
- `main.py` — Entry point; initializes bot, dispatcher, middleware, and MongoDB
- `commands/` — Telegram command handlers (start, help, admin, checkout, etc.)
- `functions/` — Business logic (card utils, BIN lookup, bypass methods, proxy utils, charge functions)
- `database/` — MongoDB client and repositories (User, Stats, Proxy, Transaction, etc.)
- `middleware/` — aiogram middleware (logging, rate limiting, credit checking)
- `config_bot/` — Configuration management and credit cost definitions

## Configuration
All config is managed via environment variables with fallback defaults in `config_bot/__init__.py`:
- `BOT_TOKEN` — Telegram bot token
- `MONGO_URI` — MongoDB connection string
- `MONGO_DB_NAME` — Database name (default: `xman_bot`)
- `ALLOWED_GROUP` — Telegram group ID for access control
- `OWNER_ID` — Bot owner Telegram user ID
- `STRIPE_PK_KEY` — Stripe publishable key
- `STRIPE_BASE_URL` — Base URL for Stripe checkout
- `BIN_API_URL` — BIN lookup API URL
- `DEBUG` — Enable debug logging (default: False)
- `RATE_LIMIT_ENABLED` — Enable rate limiting (default: True)
- `RATE_LIMIT` — Max requests per window (default: 5)
- `RATE_LIMIT_WINDOW` — Rate limit window in seconds (default: 60)

## Workflow
- **Start application**: `python main.py` — runs as a console workflow (no frontend/port)

## Key Notes
- No frontend — purely a Telegram bot backend
- Health check server starts only when deployed on Railway (PORT env var)
- MongoDB connection is established at startup; bot continues if connection fails (with degraded credit system)
- Credit system: users must have credits to use paid commands; free commands are always accessible
