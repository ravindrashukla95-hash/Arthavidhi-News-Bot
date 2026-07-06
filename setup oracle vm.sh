#!/usr/bin/env bash
# One-time setup for the Arthavidhi News Bot on a fresh Oracle Cloud
# Always-Free VM (Ubuntu). Run this FROM inside the project folder,
# after uploading all the .py/.txt/.md/.env.example files there.
set -e

echo "=== Arthavidhi News Bot: Oracle VM setup ==="

echo "--> Installing system packages (python3-venv, pip, git)..."
sudo apt update
sudo apt install -y python3-pip python3-venv git

CURRENT_DIR=$(cd "$(dirname "$0")" && pwd)
CURRENT_USER=$(whoami)
cd "$CURRENT_DIR"

echo "--> Creating virtualenv + installing requirements..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo ">>> Created .env from template. You MUST edit it before starting:"
  echo ">>>   nano .env"
  echo ">>> (fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID)"
fi

echo "--> Writing systemd service (arthavidhi-news-bot)..."
sudo tee /etc/systemd/system/arthavidhi-news-bot.service > /dev/null <<EOF
[Unit]
Description=Arthavidhi Market News Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo ""
echo "=== Setup complete. Next: ==="
echo "  1. nano .env                                   # fill in Telegram token + channel"
echo "  2. sudo systemctl enable --now arthavidhi-news-bot"
echo "  3. sudo journalctl -u arthavidhi-news-bot -f    # watch it running live"
