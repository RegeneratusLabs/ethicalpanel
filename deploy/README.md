# Deploy

VPS deployment artifacts for Ethical Panel.

## Architecture

```
public user → Cloudflare edge (real cert) → cloudflared tunnel (QUIC) →
caddy (:443, self-signed) → uvicorn (:8001, systemd)
```

The origin (VPS) has no public DNS for its IP — `ethicalpanel.com` only resolves via Cloudflare. SSH + 22/80/443 are open in UFW, but 80/443 are unreachable from the public internet (no DNS points here).

## Files

| File | Purpose | Lives on VPS at |
|---|---|---|
| `Caddyfile` | Reverse proxy, TLS termination, security headers | `/etc/caddy/Caddyfile` |
| `ethical-panel.service` | systemd unit (hardened) | `/etc/systemd/system/ethical-panel.service` |
| `cloudflared-config.yml` | Tunnel config template | `/etc/cloudflared/config.yml` |
| `bootstrap.sh` | One-shot VPS provisioning script | (run once) |

## First-time deploy on a fresh Ubuntu 24.04 VPS

### 1. Pre-flight (locally)

1. Create a **GitHub deploy key** (read-only) at the repo's Settings → Deploy keys. Save the private key as `~/.ssh/ethical-panel-deploy`.
2. Get a **Cloudflare tunnel token** from the CF dashboard → Zero Trust → Networks → Tunnels → create tunnel → copy token.

### 2. Pre-flight (VPS web console)

1. Create a non-root user with `sudo` access.
2. Add your SSH public key to that user's `~/.ssh/authorized_keys`.
3. Verify you can `ssh <your-user>@<vps-ip>` without a password.

### 3. Pre-flight (Cloudflare dashboard)

1. Add your domain to Cloudflare (free plan works).
2. Copy the 2 nameservers; set them at your domain registrar.
3. Create a tunnel, add a public hostname:
   - `yourdomain.com` (and `www.yourdomain.com`) → `https://localhost:443`
4. Copy the tunnel token.

### 4. Run bootstrap.sh

```bash
# On the VPS, as your non-root user:
git clone https://github.com/RegeneratusLabs/ethicalpanel.git
cd ethicalpanel

# Create .env with your DeepSeek API key
cp .env.example .env
$EDITOR .env   # add DEEPSEEK_API_KEY=sk-...
chmod 600 .env

# Run the bootstrap (one argument: tunnel token)
./deploy/bootstrap.sh "eyJhIjoi..."
```

The script will:
- Install all system + runtime packages
- Harden SSH, UFW, fail2ban, unattended-upgrades
- Deploy the app via systemd
- Configure Caddy with a self-signed cert (cloudflared is `noTLSVerify`)
- Install + start the cloudflared tunnel

Estimated runtime: 5–10 minutes.

### 5. After DNS propagates (5–30 min)

```bash
curl https://yourdomain.com/api/health
# → {"status":"ok"}
```

Open `https://yourdomain.com` in a browser.

## Updates / redeployment

```bash
# As your deploy user on the VPS:
cd /opt/ethical-panel
git pull
sudo systemctl restart ethical-panel
```

Caddy picks up static files immediately (no restart needed). cloudflared auto-reconnects.

## Configuration (placeholders)

The deploy artifacts use these placeholders — replace them in your fork if you change the defaults:

- `$DEPLOY_USER` — the non-root user that runs the app (also owns `/opt/ethical-panel`)
- `/opt/ethical-panel` — the install directory (change in all 4 files if you relocate)

## Secrets and rotations

- **DeepSeek API key**: `/opt/ethical-panel/.env` (chmod 600, owner `$DEPLOY_USER`). Rotate in the DeepSeek dashboard, edit `.env`, `sudo systemctl restart ethical-panel`.
- **Cloudflare tunnel token**: embedded in `/etc/systemd/system/cloudflared.service` ExecStart. To rotate: create a new tunnel in CF, `cloudflared service install <new-token>`, disable old tunnel.

## Analytics

Enable Cloudflare Web Analytics in the CF dashboard (Site → your domain → Analytics → Web Analytics). The beacon script is already in `static/index.html`; no server-side install needed.

## Self-signed cert rotation

The self-signed cert on `:443` (used only between cloudflared and Caddy) is valid for 365 days. To rotate:

```bash
sudo openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /etc/caddy/ssl/key.pem \
  -out /etc/caddy/ssl/cert.pem -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:yourdomain.com,DNS:www.yourdomain.com,IP:127.0.0.1"
sudo systemctl restart caddy
```

For a longer-term solution, replace the self-signed cert with a Cloudflare-issued origin cert (free, 15-year validity). Set `noTLSVerify: false` in `cloudflared-config.yml` after switching.

## Monitoring

```bash
# Live tail of all services
journalctl -u ethical-panel -u caddy -u cloudflared -f

# Service security score
systemd-analyze security ethical-panel   # expect around 5.0 MEDIUM
```

## HA / multi-VPS

This is a single-VPS deploy. For HA, add a second VPS, run the same bootstrap, and put a Cloudflare Load Balancer in front of the two tunnel origins.
