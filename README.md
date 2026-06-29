# Kraken Profit Guard v1

A suggest-first crypto account-defense bot for Kraken.

## Mission

Read your Kraken account, detect unrealized profit, protect gains, prevent reckless buys, defend only worthy positions, and keep USDC/USD ready.

This v1 is designed to run in **suggest-only** mode first. Do not start full-auto with real money.

## What it does

- Reads balances from Kraken
- Reads ticker prices
- Calculates approximate portfolio value
- Tracks position state locally
- Scores positions with Position Advocacy
- Runs Position Court
- Runs Portfolio Profit Guard
- Runs Position Profit Guard
- Blocks chase buys
- Protects USDC reserve
- Outputs:
  - 3 profit moves
  - 3 buy/rebuy moves
  - final account mode: protect / attack / wait

## Install

```bash
cd kraken_profit_guard_v1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your Kraken API key/secret to `.env`.

## API key safety

For v1, create a Kraken API key with the lowest permissions possible.

Recommended for suggest-only:
- Query funds
- Query open orders/trades if you add that later

Do **not** enable trading until the bot has proven itself.

## Run

```bash
python -m kpg.main --config config.example.yaml
```

The bot will print a JSON report.

## Important

This is not financial advice. This is a trading-risk automation framework. Test with small size and dry-run mode first.
