# Frappe CRM + WhatsApp Bridge — VM Setup Instructions

This guide gets you from a fresh Ubuntu/Debian VM to a working Frappe CRM with WhatsApp Bridge integration, ready to `bench start`.

---

## 1. System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

# Core build tools
sudo apt install -y git python3 python3-dev python3-pip python3-venv \
  build-essential libssl-dev libffi-dev libmysqlclient-dev \
  redis-server curl wget

# MariaDB
sudo apt install -y mariadb-server mariadb-client

# wkhtmltopdf (required by Frappe for PDF generation)
sudo apt install -y xvfb libfontconfig wkhtmltopdf

# Node.js 20+ (via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Yarn
sudo npm install -g yarn
```

### Configure MariaDB

```bash
sudo mysql_secure_installation
# Set a root password, answer Y to all prompts
```

Edit MariaDB config for Frappe compatibility:

```bash
sudo nano /etc/mysql/mariadb.conf.d/50-server.cnf
```

Add under `[mysqld]`:

```ini
[mysqld]
innodb-file-format=barracuda
innodb-file-per-table=1
innodb-large-prefix=1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
```

```bash
sudo systemctl restart mariadb
```

---

## 2. Install Bench CLI

```bash
pip3 install frappe-bench
```

Make sure `~/.local/bin` is in your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## 3. Initialize Frappe Bench

```bash
cd ~
bench init frappe-bench --frappe-branch version-16
cd frappe-bench
```

---

## 4. Get the CRM App

Copy (or clone) the CRM app into the bench:

```bash
# Option A: rsync from your dev machine
rsync -avz your-dev-machine:/path/to/crm/ apps/crm/

# Option B: if you have it in a git repo
bench get-app <your-crm-repo-url>
```

Make sure the app is properly linked:

```bash
ls apps/crm/crm/hooks.py  # should exist
```

---

## 5. Create Site & Install CRM

```bash
bench new-site crm.localhost \
  --mariadb-root-password <your-mariadb-root-password> \
  --admin-password admin

bench --site crm.localhost install-app crm
bench --site crm.localhost set-config developer_mode 0
bench use crm.localhost
```

This runs `after_install` which creates default lead/deal statuses, field layouts, industries, lead sources, etc.

---

## 6. Build Frontend Assets

```bash
cd apps/crm
yarn install
cd ../..
bench build --app crm
```

---

## 7. WhatsApp Bridge Setup

The bridge is a separate Node.js service that connects to WhatsApp via Baileys.

### Install & Build

```bash
cd ~
# Copy (or clone) the bridge
rsync -avz your-dev-machine:/path/to/whatsapp-bridge/ whatsapp-bridge/

cd whatsapp-bridge
npm install
npm run build
```

### Authenticate WhatsApp

Run the auth script and scan the QR code with your WhatsApp phone:

```bash
npm run auth
# A QR code appears in the terminal — scan it with WhatsApp > Linked Devices
# Once authenticated, credentials are saved in ./store/auth/
# Press Ctrl+C after "Connected to WhatsApp" appears
```

### Create a Webhook Secret

Generate a random secret string:

```bash
openssl rand -hex 32
```

Save this — you'll use it in both the bridge and CRM config.

### Start the Bridge

```bash
PORT=3100 \
WEBHOOK_URL="http://localhost:8000/api/method/crm.integrations.whatsapp.handler.webhook" \
WEBHOOK_SECRET="<your-generated-secret>" \
STORE_DIR="./store" \
node dist/server.js
```

For production, use a process manager like `pm2`:

```bash
npm install -g pm2

pm2 start dist/server.js --name wa-bridge \
  --env PORT=3100 \
  --env WEBHOOK_URL="http://localhost:8000/api/method/crm.integrations.whatsapp.handler.webhook" \
  --env WEBHOOK_SECRET="<your-generated-secret>" \
  --env STORE_DIR="./store"

pm2 save
pm2 startup  # follow its instructions to enable on boot
```

---

## 8. Configure CRM WhatsApp Bridge Settings

Open CRM in browser and go to:

```
http://crm.localhost:8000/app/crm-whatsapp-bridge-settings
```

Or via bench console:

```bash
bench --site crm.localhost console
```

```python
settings = frappe.get_doc("CRM WhatsApp Bridge Settings")
settings.enabled = 1
settings.bridge_url = "http://localhost:3100"
settings.webhook_secret = "<your-generated-secret>"  # same secret as above
settings.save()
frappe.db.commit()
exit()
```

---

## 9. Start Everything

```bash
cd ~/frappe-bench
bench start
```

This starts:
- **Web server** on port 8000 (Gunicorn)
- **Socket.IO** on port 9000 (realtime events)
- **Redis** cache (13000) and queue (11000)
- **Background workers** (scheduled tasks, async jobs)
- **File watcher** (for development)

Access CRM at: `http://crm.localhost:8000`

Login: `Administrator` / `admin` (or whatever you set as admin-password)

---

## Production Notes

### Nginx Reverse Proxy

For a real domain, set up Nginx:

```bash
sudo bench setup nginx
sudo ln -s ~/frappe-bench/config/nginx.conf /etc/nginx/conf.d/frappe-bench.conf
sudo nginx -t && sudo systemctl reload nginx
```

### SSL with Let's Encrypt

```bash
sudo bench setup lets-encrypt crm.yourdomain.com
```

### Supervisor (process manager)

```bash
sudo bench setup supervisor
sudo ln -s ~/frappe-bench/config/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf
sudo supervisorctl reread
sudo supervisorctl update
```

### Bridge WEBHOOK_URL for production

If using Nginx, update the bridge's `WEBHOOK_URL` to use the public URL:

```
WEBHOOK_URL="https://crm.yourdomain.com/api/method/crm.integrations.whatsapp.handler.webhook"
```

---

## Quick Reference

| Service        | Port  | Purpose                    |
|----------------|-------|----------------------------|
| Frappe Web     | 8000  | CRM application            |
| Socket.IO      | 9000  | Realtime events (WebSocket)|
| Redis Cache    | 13000 | Caching                    |
| Redis Queue    | 11000 | Background job queue       |
| WhatsApp Bridge| 3100  | WhatsApp ↔ CRM connector  |
