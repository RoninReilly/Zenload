#!/bin/bash

# Make script executable on copy-paste
chmod +x "$0"

# Function to prompt for environment variables
prompt_env_vars() {
    echo "Please enter your Telegram Bot Token:"
    read -r telegram_token
    echo "Please enter your Yandex Music Token (press Enter to skip):"
    read -r yandex_token

    # Create .env file
    echo "TELEGRAM_BOT_TOKEN=$telegram_token" > .env
    if [ ! -z "$yandex_token" ]; then
        echo "YANDEX_MUSIC_TOKEN=$yandex_token" >> .env
    fi
}

# Check for Python and Git
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required. Install it with: sudo apt update && sudo apt install python3 python3-venv"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "Git is required. Install it with: sudo apt install git"; exit 1; }

# Clone or update repository
if [ ! -d ".git" ]; then
    echo "Cloning Zenload repository..."
    git clone https://github.com/RoninReilly/Zenload.git .
else
    echo "Updating repository..."
    git pull
fi

# Setup virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create systemd service file
create_service() {
    echo "Creating systemd service..."
    sudo tee /etc/systemd/system/zenload.service > /dev/null << EOL
[Unit]
Description=Zenload Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin:$PATH
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable zenload
}

# Main installation
echo "=== Zenload Bot Installation ==="

# Get environment variables if not exist
if [ ! -f ".env" ]; then
    prompt_env_vars
fi

# Create service and start bot
if [ ! -f "/etc/systemd/system/zenload.service" ]; then
    create_service
fi

# If service exists and we're updating, restart it
if systemctl is-active --quiet zenload; then
    echo "Restarting service after update..."
    sudo systemctl restart zenload
fi

echo "
=== Installation Complete ===

Your bot has been installed as a system service!

Commands:
- Start bot:   sudo systemctl start zenload
- Stop bot:    sudo systemctl stop zenload
- Check logs:  sudo journalctl -u zenload -f
- Status:      sudo systemctl status zenload
- Update:      Just run this script again: ./deploy.sh

The bot will automatically:
- Start on system boot
- Restart if it crashes
- Log all output to system journal

To update environment variables:
1. Edit .env file
2. Restart service: sudo systemctl restart zenload
"

# Start the service if not already running
if ! systemctl is-active --quiet zenload; then
    read -p "Start the bot now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl start zenload
        echo "Bot started! Check status with: sudo systemctl status zenload"
    fi
fi