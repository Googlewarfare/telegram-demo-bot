"""
Demo Telegram bot for the Fiverr portfolio.

What it shows off (each one matches a Fiverr package feature):
  1. Menu with buttons       -> /start         (Basic package)
  2. Reminders               -> /remind        (Standard: scheduled messages)
  3. Website-change alerts   -> /watch         (Standard: alerts)
  4. Saved data              -> watches.json   (Premium: stores data)

Run it:  python bot.py
Needs a .env file with TELEGRAM_TOKEN=... (get one from @BotFather).
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
load_dotenv()                                   # reads .env into os.environ
TOKEN = os.environ["TELEGRAM_TOKEN"]

CHECK_EVERY_SECONDS = 300                       # how often to check watched sites (5 min)
MAX_WATCHES_PER_USER = 5                        # keeps one user from overloading the bot
DATA_FILE = Path(__file__).with_name("watches.json")   # where watches are saved

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
# httpx logs every Telegram request; turn that down so the log stays readable
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("demo_bot")


# ---------------------------------------------------------------------------
# Saving / loading watches
# Format: {"<chat_id>": {"<url>": "<fingerprint of the page>"}}
# A JSON file is fine for a demo; a real client bot would use SQLite.
# ---------------------------------------------------------------------------
def load_watches() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}


def save_watches(watches: dict) -> None:
    DATA_FILE.write_text(json.dumps(watches, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Website fingerprinting
# We download the page, keep only the visible text, and hash it.
# If the hash changes later, the page changed.
# ---------------------------------------------------------------------------
def page_fingerprint(url: str) -> str:
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 demo-bot"})
    resp.raise_for_status()                     # error out on 404, 500, etc.
    html = resp.text
    # Remove <script> and <style> blocks - they change constantly and aren't visible
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)    # strip remaining tags
    text = " ".join(text.split())               # collapse whitespace
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# /start - menu with buttons
# ---------------------------------------------------------------------------
MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("⏰ Reminders", callback_data="help_remind")],
    [InlineKeyboardButton("🌐 Website alerts", callback_data="help_watch")],
    [InlineKeyboardButton("ℹ️ About this bot", callback_data="about")],
])

HELP_TEXT = {
    "help_remind": (
        "⏰ <b>Reminders</b>\n\n"
        "/remind 10 call the supplier\n"
        "→ I'll message you in 10 minutes.\n\n"
        "Use m or h too: /remind 2h check the oven"
    ),
    "help_watch": (
        "🌐 <b>Website alerts</b>\n\n"
        "/watch https://example.com → I check it every 5 min and alert you if it changes\n"
        "/watching → list what you're watching\n"
        "/unwatch https://example.com → stop watching"
    ),
    "about": (
        "ℹ️ <b>About</b>\n\n"
        "This is a demo bot showing what a custom Telegram bot can do: "
        "buttons, reminders, automatic alerts, and saved data.\n\n"
        "Want one for your business? Message me on Fiverr."
    ),
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hi {name}! I'm a demo assistant bot.\nPick something to try:",
        reply_markup=MENU,
    )


async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs when someone taps one of the menu buttons."""
    query = update.callback_query
    await query.answer()                        # stops the button's loading spinner
    await query.edit_message_text(
        HELP_TEXT[query.data], parse_mode="HTML", reply_markup=MENU
    )


# ---------------------------------------------------------------------------
# /remind <time> <text>
# ---------------------------------------------------------------------------
def parse_duration(raw: str) -> int | None:
    """Turn '10', '10m', or '2h' into seconds. Returns None if it can't."""
    match = re.fullmatch(r"(\d+)([mh]?)", raw.lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    seconds = amount * 3600 if unit == "h" else amount * 60
    # Limit to 1 minute .. 7 days
    return seconds if 60 <= seconds <= 7 * 24 * 3600 else None


async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called by the job queue when a reminder is due."""
    job = context.job
    await context.bot.send_message(job.chat_id, f"⏰ Reminder: {job.data}")


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args                         # words after /remind
    seconds = parse_duration(args[0]) if args else None
    if seconds is None or len(args) < 2:
        await update.message.reply_text(
            "Usage: /remind 10 call the supplier\n(time = minutes, or add m/h: 30m, 2h)"
        )
        return
    text = " ".join(args[1:])
    context.job_queue.run_once(
        send_reminder, seconds, chat_id=update.effective_chat.id, data=text
    )
    # Show the wait in friendly words, e.g. "10 min" or "2 hr"
    nice = f"{seconds // 3600} hr" if seconds % 3600 == 0 else f"{seconds // 60} min"
    await update.message.reply_text(f"✅ Got it. I'll remind you in {nice}.")


# ---------------------------------------------------------------------------
# /watch, /watching, /unwatch
# ---------------------------------------------------------------------------
async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].startswith(("http://", "https://")):
        await update.message.reply_text("Usage: /watch https://example.com")
        return

    url = context.args[0]
    chat_id = str(update.effective_chat.id)
    watches = load_watches()
    mine = watches.setdefault(chat_id, {})

    if url in mine:
        await update.message.reply_text("👀 Already watching that one.")
        return
    if len(mine) >= MAX_WATCHES_PER_USER:
        await update.message.reply_text(f"You can watch up to {MAX_WATCHES_PER_USER} sites.")
        return

    await update.message.reply_text("🔎 Checking the page...")
    try:
        # requests is blocking, so run it in a thread to keep the bot responsive
        fingerprint = await asyncio.to_thread(page_fingerprint, url)
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't load that page: {e}")
        return

    mine[url] = fingerprint
    save_watches(watches)
    await update.message.reply_text(
        f"✅ Watching {url}\nI'll message you when it changes."
    )


async def watching(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mine = load_watches().get(str(update.effective_chat.id), {})
    if not mine:
        await update.message.reply_text("You're not watching anything. Try /watch <url>")
        return
    lines = "\n".join(f"• {url}" for url in mine)
    await update.message.reply_text(f"👀 Watching:\n{lines}")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /unwatch https://example.com")
        return
    url = context.args[0]
    watches = load_watches()
    mine = watches.get(str(update.effective_chat.id), {})
    if mine.pop(url, None) is None:
        await update.message.reply_text("I wasn't watching that URL. See /watching")
        return
    save_watches(watches)
    await update.message.reply_text(f"🛑 Stopped watching {url}")


async def check_all_sites(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs every CHECK_EVERY_SECONDS. Alerts users whose pages changed."""
    watches = load_watches()
    changed_any = False

    for chat_id, sites in watches.items():
        for url, old_print in sites.items():
            try:
                new_print = await asyncio.to_thread(page_fingerprint, url)
            except Exception as e:
                log.warning("Check failed for %s: %s", url, e)
                continue                        # try again next round
            if new_print != old_print:
                sites[url] = new_print
                changed_any = True
                await context.bot.send_message(int(chat_id), f"🔔 This page changed:\n{url}")
                log.info("Change detected: %s", url)

    if changed_any:
        save_watches(watches)


# ---------------------------------------------------------------------------
# Start the bot
# ---------------------------------------------------------------------------
def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CallbackQueryHandler(menu_button))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("watching", watching))
    app.add_handler(CommandHandler("unwatch", unwatch))

    # Background job: check watched websites every few minutes
    app.job_queue.run_repeating(check_all_sites, interval=CHECK_EVERY_SECONDS, first=30)

    log.info("Demo bot running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
