"""
Entry point for running the bot as a module.

Usage:
    python -m kalshi_bot run --mode paper
    python -m kalshi_bot run --mode live
"""

from kalshi_bot.cli import app

if __name__ == "__main__":
    app()
