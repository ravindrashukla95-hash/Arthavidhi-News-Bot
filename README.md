# Arthavidhi Market News Bot

Polls BSE + NSE corporate announcements, splits them into **Results**,
**Corporate Action**, and **Stock News**, and pushes new ones to a
Telegram channel — a standalone Python replacement for the manual
Sheet → Telegram flow.

Built on two actively-maintained unofficial libraries (same author) instead
of raw scraping:
- [`bse`](https://pypi.org/project/bse/) — BSE announcements/actions/quotes
- [`nse`](https://pypi.org/project/nse/) — NSE announcements/board meetings/quotes

## 1. Create your Telegram bot (5 min, one-time)

1. In Telegram, open a chat with **@BotFather**.
2. Send `/newbot`, then give it a display name (e.g. `Arthavidhi Market News`)
   and a username ending in `bot` (e.g. `arthavidhi_news_bot`).
3. BotFather replies with a token like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxx`
   — copy it, this is your `TELEGRAM_BOT_TOKEN`.
4. Create (or pick) the channel you want alerts posted to.
5. Add your new bot to that channel **as an admin** (needs "Post Messages"
   permission at minimum).
6. Get the channel ID:
   - If the channel is public, just use its handle: `@your_channel_name`.
   - If it's private, post any message in the channel, then visit
     `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser — look
     for `"chat":{"id":-100xxxxxxxxxx` in the response and use that number.

## 2. Install

```bash
cd arthavidhi-news-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`: paste in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID`.
Leave the per-category channel vars blank unless you want Results /
Corporate Action / Stock News routed to separate channels or topics —
if so, repeat step 1.4–1.6 for each and fill those vars in instead.

## 3. Run

```bash
python main.py
```

First run **bootstraps silently** — it marks whatever's already on BSE/NSE
today as "seen" without alerting, so you don't get a flood of history.
From the second poll onward, only genuinely new announcements get sent.

Logs go to stdout and to `./data/news_bot.log` (rotated at 5MB).

## 4. Keep it running 24/7 (VPS / systemd)

```ini
# /etc/systemd/system/arthavidhi-news-bot.service
[Unit]
Description=Arthavidhi Market News Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/arthavidhi-news-bot
ExecStart=/path/to/arthavidhi-news-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now arthavidhi-news-bot
sudo journalctl -u arthavidhi-news-bot -f   # tail logs
```

## Notes / things to tune

- **I couldn't test the live BSE/NSE calls from this sandbox** — the dev
  environment's network allowlist doesn't include `bseindia.com` /
  `nseindia.com`. Everything except the actual HTTP round-trip (parsing,
  classification, dedup, Telegram formatting) is unit-tested and passing.
  Run `python main.py` on your own machine/VPS first and watch the logs
  for the first few cycles.
- **NSE is the fragile one.** It rate-limits to ~3 req/sec and is stricter
  about non-browser traffic than BSE. If you see repeated `NSE fetch
  failed` warnings, widen `POLL_INTERVAL_SECONDS` first before anything else.
- **Classification is keyword-based** on `classifier.py` — tune
  `RESULTS_TEXT_KEYWORDS` / `CORP_ACTION_TEXT_KEYWORDS` as you see
  mis-buckets in real traffic (e.g. add scrip codes/companies you know
  always file in a particular pattern).
- **Dedup** is a local SQLite file (`data/seen_announcements.db`) — back
  it up if you move servers, otherwise you'll get one bootstrap-style
  silent re-sync on first run at the new location.
