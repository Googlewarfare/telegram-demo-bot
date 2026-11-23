# Demo Assistant Bot

A Telegram bot that shows what a custom bot can do for a business or group.
Try it live: **[@GarvDemoAssistant_bot](https://t.me/GarvDemoAssistant_bot)**

## Features

| Feature | Command | What it does |
|---|---|---|
| Menu with buttons | `/start` | Welcome message with tappable buttons |
| Reminders | `/remind 10 call the supplier` | Sends you a message after the time you set (`30m`, `2h` also work) |
| Website alerts | `/watch https://site.com` | Checks the page every 5 minutes and alerts you when it changes |
| Watch list | `/watching` and `/unwatch <url>` | Shows or removes the pages you're watching |
| Saved data | (automatic) | Watched pages are saved, so they survive a restart |

## What this could look like for your business

The same building blocks can be adapted to many jobs, for example:
- **Appointment reminders** for a barber shop, salon, or clinic
- **Price or stock alerts** when a supplier's or competitor's page changes
- **FAQ bot** with buttons for hours, location, prices, and contact info
- **Daily or weekly reports** sent to you or your team automatically
- **Members-only bot** with invite codes for a paid group or community

## How it's built

- **Language:** Python 3
- **Library:** [python-telegram-bot](https://python-telegram-bot.org/) (async, with a built-in scheduler)
- **Storage:** a JSON file for this demo. Client bots use a SQLite database.
- **Hosting:** runs on any computer, or 24/7 on a cloud server (AWS, DigitalOcean, etc.)

The code is short, commented, and organized so it's easy to change later.

## Running it yourself

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Copy `.env.example` to `.env` and paste the token in.
3. Install and run:
   ```
   python -m venv .venv
   .venv\Scripts\activate        (Windows)   |   source .venv/bin/activate   (Mac/Linux)
   pip install -r requirements.txt
   python bot.py
   ```

## Want one built for you?

Message me on Fiverr with what you want your bot to do. I'll tell you which package fits and how long it will take.
