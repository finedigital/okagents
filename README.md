# OKAgents

A Telegram bot that channels Arthur Hayes' macro-first worldview. Ask it about markets, get sharp macro analysis. Want to trade? It executes on OKX — no friction.

## What it does

- **Macro signal** — @mention the bot in a group chat and it responds in Arthur Hayes' voice, connecting every market move back to liquidity, the TGA, RRP, and central bank policy
- **Live trading** — say "buy $200 BTC" or "sell $50 AVAX" and it places the order on OKX after confirmation
- **Deep research** — asks about Arthur's latest thesis trigger a pull of recent essays (Substack + Medium) and social signal to ground the response in what he's actually said
- **Conversation memory** — keeps the last 5 turns per user per chat for coherent back-and-forth

## Supported tokens

BTC, ETH, AVAX, SOL, XRP, ADA, DOGE, BNB, BCH, LTC, LINK, UNI, AAVE, MATIC, DOT, SHIB, TRX, FIL, ATOM

## Setup

### Environment variables

```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### Run locally

```bash
pip install -r requirements.txt
python bot.py
```

### Run with Docker

```bash
docker build -t okagents .
docker run -e TELEGRAM_BOT_TOKEN=... -e ANTHROPIC_API_KEY=... okagents
```

## Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Introduction message |
| `/connect KEY SECRET PASSPHRASE` | Link your OKX API credentials (DM only) |

## How it works

- `bot.py` — Telegram handler, trade detection, confirmation flow
- `agent.py` — Builds prompts with market context, calls Claude for responses
- `ingestion.py` — Fetches Arthur Hayes essays from Substack/Medium RSS, plus social signal
- `okx.py` — OKX API client for price data and order execution
- `db.py` — SQLite store for user OKX credentials
- `SOUL.md` — The persona definition that drives OKArthur's voice and behavior

## Trading flow

1. User says "buy $100 BTC"
2. Bot fetches live price, shows confirmation with inline buttons
3. User clicks "Yes, execute"
4. Bot places market order on OKX using the user's linked API credentials
5. Confirms execution

## Notes

- Trade amounts are capped at $1–$1,000
- OKX credentials are stored locally in SQLite — keep the database secure
- The bot only responds when @mentioned in groups, or in DMs
