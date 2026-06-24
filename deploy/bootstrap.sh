#!/bin/bash
# Ethical Panel — VPS bootstrap script
# Provisions a fresh Ubuntu 24.04 VPS from zero to running production app.
# Tested on Alibaba Cloud Ubuntu 24.04, but should work on any fresh Ubuntu.
#
# Usage: run as a sudo-enabled user (NOT root). The script will sudo as needed.
# Estimated runtime: 5-10 minutes.
#
# Prerequisites:
#   1. A fresh Ubuntu 24.04 VPS reachable via SSH
#   2. This script + a copy of the repo on the VPS (rsync or git clone)
#   3. A .env file with DEEPSEEK_API_KEY at /opt/ethical-panel/.env (chmod 600)
#   4. A Cloudflare tunnel token (from CF dashboard) - will be passed as $1
#   5. A GitHub deploy key for the repo added to the GitHub repo settings
#
# Analytics: handled by Cloudflare Web Analytics (no server-side install needed).
# Enable in CF dashboard → ethicalpanel.com → Analytics → Web Analytics.

set -euo pipefail

if [ "$(id -u)" = "0" ]; then
    echo "ERROR: do not run as root. Run as a sudo-enabled user (e.g. 'admin' on Alibaba)."
    exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <cloudflared-tunnel-token>"
    echo "  Get the token from Cloudflare dashboard → Zero Trust → Tunnels → your tunnel → token"
    exit 1
fi

TUNNEL_TOKEN="$1"
APP_DIR="/opt/ethical-panel"

echo "==================================================="
echo "  Ethical Panel — VPS bootstrap"
echo "  Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "==================================================="

# --- 1. apt update + install runtime + security packages ---
echo "[1/8] Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
sudo apt update && sudo apt upgrade -y
sudo apt install -y unattended-upgrades fail2ban ufw python3 python3-venv \
    python3-pip curl wget vim htop auditd rsync jq

# --- 2. Install uv (Python package manager) ---
echo "[2/8] Installing uv..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    sudo install -m 0755 "$HOME/.local/bin/uv" /usr/local/bin/uv
fi

# --- 3. Install Caddy ---
echo "[3/8] Installing Caddy..."
if ! command -v caddy &>/dev/null; then
    sudo apt install -y debian-keyring debian-archive-keyring
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
        sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
        sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt update && sudo apt install -y caddy
fi

# --- 4. Install cloudflared ---
echo "[4/8] Installing cloudflared..."
if ! command -v cloudflared &>/dev/null; then
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
        sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared noble main" | \
        sudo tee /etc/apt/sources.list.d/cloudflared.list
    sudo apt update && sudo apt install -y cloudflared
fi

# --- 5. Security: UFW, fail2ban, sshd hardening, unattended-upgrades ---
echo "[5/8] Hardening server..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment "SSH"
sudo ufw allow 80/tcp comment "HTTP"
sudo ufw allow 443/tcp comment "HTTPS"
sudo ufw --force enable

sudo tee /etc/fail2ban/jail.local > /dev/null << 'F2B'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
banaction = ufw

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
F2B
sudo systemctl enable --now fail2ban

sudo tee /etc/apt/apt.conf.d/20auto-upgrades > /dev/null << 'AUU'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Download-Upgradeable-Packages "1";
AUU
sudo dpkg-reconfigure -f noninteractive unattended-upgrades
sudo systemctl enable --now unattended-upgrades

# SSH hardening
sudo mkdir -p /etc/ssh/sshd_config.d
sudo tee /etc/ssh/sshd_config.d/99-ethical-panel-hardening.conf > /dev/null << 'SSHD'
PasswordAuthentication no
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
PermitEmptyPasswords no
UsePAM yes
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitUserEnvironment no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
Protocol 2
SSHD
sudo sshd -t && sudo systemctl restart ssh

# --- 6. Deploy the app (assumes repo is already at $APP_DIR) ---
echo "[6/8] Deploying app..."
[ -d "$APP_DIR" ] || { echo "ERROR: $APP_DIR not found. Clone the repo first."; exit 1; }
cd "$APP_DIR"
[ -f .env ] || { echo "ERROR: $APP_DIR/.env not found. Create it with DEEPSEEK_API_KEY=..."; exit 1; }
chmod 600 .env

# Set up Python venv with Python 3.13 (managed by uv)
export PATH="/root/.local/bin:$PATH"
uv python install 3.13
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -e '.[dev]'

# Install systemd unit
sudo install -m 0644 deploy/ethical-panel.service /etc/systemd/system/ethical-panel.service
sudo systemctl daemon-reload
sudo systemctl enable --now ethical-panel

# --- 7. Set up Caddy ---
echo "[7/8] Setting up Caddy..."
# Generate self-signed cert for caddy <-> cloudflared (cloudflared is noTLSVerify)
sudo mkdir -p /etc/caddy/ssl
sudo openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout /etc/caddy/ssl/key.pem \
    -out /etc/caddy/ssl/cert.pem -days 365 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:ethicalpanel.com,DNS:www.ethicalpanel.com,IP:127.0.0.1"
sudo chmod 600 /etc/caddy/ssl/key.pem
sudo chmod 644 /etc/caddy/ssl/cert.pem
sudo install -m 0644 deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy

# --- 8. Set up cloudflared ---
echo "[8/8] Setting up cloudflared tunnel..."
sudo cloudflared service install "$TUNNEL_TOKEN"
sudo systemctl enable --now cloudflared

echo ""
echo "==================================================="
echo "  ✓ Bootstrap complete"
echo "  Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "==================================================="
echo ""
echo "Status checks:"
echo "  systemctl status ethical-panel caddy cloudflared"
echo "  curl -k https://127.0.0.1:443/api/health"
echo ""
echo "After DNS nameserver switch propagates, test:"
echo "  curl https://ethicalpanel.com/api/health"
echo "  open https://ethicalpanel.com in a browser"
echo ""
echo "Analytics: enable Cloudflare Web Analytics in the CF dashboard"
echo "(Site → ethicalpanel.com → Analytics → Web Analytics). The beacon"
echo "script is already in static/index.html. No server-side install needed."
