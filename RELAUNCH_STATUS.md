# Frappe CRM + WhatsApp Bridge — Relaunch Status

**Last updated:** 2026-06-10
**Goal:** Relaunch a custom Frappe CRM (with a custom Baileys-based WhatsApp bridge) that
was rsync'd from a now-dead VM onto this Arch Linux machine.

> This bench was **copied via rsync from a dead Ubuntu VM** — so the OS-level pieces
> (MariaDB, build tools) were missing, and the original MariaDB database is **gone**
> (user confirmed they do NOT need the old data — a fresh site is fine).

## ⭐ CURRENT STATE (essentially live)

Everything is built, running, and reachable over HTTPS:
- ✅ Frappe CRM + WhatsApp bridge run as **systemd services** (`frappe-crm`, `whatsapp-bridge`) — reboot-safe.
- ✅ nginx vhost + **Let's Encrypt cert** live for **https://whatsapp.billingfast.com** (DNS A record added, certbot succeeded).
- ✅ WhatsApp paired & bridge connected; CRM bridge settings saved.
- ✅ Admin user `kumar@billingfast.com` created (System Manager); `Administrator` password hardened.

**THE ONE REMAINING ACTION:** run `sudo systemctl restart frappe-crm` once — needed so the web
worker reloads the fresh asset manifest (otherwise the login page CSS 404s / renders unstyled).
After that, log in at https://whatsapp.billingfast.com/login. Everything else is done.

---

## Key facts about this machine

- **OS:** Arch Linux (kernel 6.19.x). Original `instructions.md` assumes Ubuntu — paths differ.
- **Python:** 3.14 (system + the bench venv at `frappe-bench/env`).
- **Node:** **v26.2.0** (very new — broke native modules & Baileys; see below).
- **Frappe app version:** 17.0.0-dev (branch `develop`). CRM app on branch `bf`.
- **Project root:** `/home/omegaui/Projects/crm`
- **Bench dir:** `/home/omegaui/Projects/crm/frappe-bench`
- **Bridge dir:** `/home/omegaui/Projects/whatsapp-bridge`
- **bench CLI:** NOT global. Installed into the venv → run as
  `/home/omegaui/Projects/crm/frappe-bench/env/bin/bench` (from inside `frappe-bench/`).

## Credentials / config (dev box)

- **MariaDB root password:** `dev@bf0rex`
- **Site:** `crm.localhost`
- **Primary admin login (System Manager):** `kumar@billingfast.com` / `kumar@bfcrm1.1`
- **`Administrator` (fallback superuser):** password hardened from `admin` →
  `jSxRqdrKBdxo5f37xrM5_JeNGa@D` (store in a password manager; `Administrator` can't be
  deleted/disabled in Frappe, so a strong password is the protection).
- **Site DB password (actual):** `VhjX9dX6u9eUyXKl` (in `sites/crm.localhost/site_config.json`;
  Frappe regenerated it rather than honoring the `--db-password` flag — harmless, internally consistent).
- **WhatsApp webhook secret:** `9c06d62c9b8cce994d313d2788ef8f1566e2543d00227a4002cab64fb02c4304`
  (from `whatsapp-bridge/env.sh`)
- **Bridge URL (CRM setting):** `http://localhost:3100`

---

## What's DONE ✅

1. **Installed `bench` CLI into the venv** (`pip install frappe-bench` → v5.29.1).
   - It downgraded `click`, breaking frappe; fixed with `pip install 'click~=8.3.1'` (now 8.3.3).
2. **Installed MariaDB + yarn** (user ran, Arch):
   ```bash
   sudo pacman -S --needed --noconfirm mariadb yarn
   sudo cp /home/omegaui/Projects/crm/nano /etc/my.cnf.d/frappe.cnf   # utf8mb4 config
   sudo mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql
   sudo systemctl enable --now mariadb
   sudo mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'dev@bf0rex'; FLUSH PRIVILEGES;"
   ```
3. **Renamed old broken site dir:** `sites/crm.localhost` → `sites/crm.localhost.bak`
   (preserves old uploaded media `.jpg` files on disk; DB it pointed to is gone).
4. **Installed gcc + make** (user ran): `sudo pacman -S --needed --noconfirm gcc pkgconf make`
5. **Rebuilt `mysqlclient`** against Arch's MariaDB connector (the venv's copy was built on
   Ubuntu against `libmysqlclient.so.21`, which doesn't exist on Arch):
   ```bash
   /home/omegaui/Projects/crm/frappe-bench/env/bin/pip install --force-reinstall --no-binary mysqlclient mysqlclient==2.2.7
   ```
   Now links to `libmariadb.so.3`. ✅
6. **Created fresh site + installed CRM app:**
   ```bash
   cd /home/omegaui/Projects/crm/frappe-bench
   env/bin/bench new-site crm.localhost --force --db-root-username root \
     --mariadb-root-password 'dev@bf0rex' --admin-password admin --db-password 'crmdbpass123'
   env/bin/bench --site crm.localhost install-app crm
   env/bin/bench use crm.localhost
   ```
   - NOTE: do **NOT** pass `--mariadb-user-host-login-scope='%'` — it creates the DB user at
     `@'%'`, but Frappe's bootstrap restore connects over the local socket as `@'localhost'`
     and fails with "Access denied". Default (localhost scope) works.
   - MariaDB is v12.3.2 — newer than Frappe officially tests (warns, but works).
7. **Built frontend assets:**
   ```bash
   cd apps/crm && yarn install && cd ../..
   env/bin/bench build --app crm
   ```
   SPA built to `apps/crm/crm/public/frontend/` ✅
8. **WhatsApp bridge native module fix:** `better-sqlite3@11.10.0` couldn't compile on Node 26
   (uses removed V8 APIs). Upgraded:
   ```bash
   cd /home/omegaui/Projects/whatsapp-bridge && npm install better-sqlite3@12.10.0
   ```
   Loads under Node 26 and reads existing `store/messages.db` (9 tables intact). ✅

## WhatsApp re-pairing (QR) — RESOLVED ✅ (historical context below)

The Feb `store/auth/` session was **expired** (WhatsApp returned `loggedOut`/401). Backed up to
`store/auth.expired`. Re-paired via QR scan (`npm run auth`). Kept for context — the Baileys
version saga below is the useful part if the bridge ever needs re-pairing or upgrading.

### The Baileys version saga (important context)
- Bridge pins `@whiskeysockets/baileys@^7.0.0-rc.9`.
- 1st `npm run auth` (rc.9, no version fix) → **405 stream error before QR** (WA rejected handshake).
- Tried upgrading to **rc13** → broke with `ERR_PACKAGE_PATH_NOT_EXPORTED` for
  `whatsapp-rust-bridge` (rc13 dep only defines an ESM `import` export condition, but Baileys'
  CJS code `require()`s it → fails on Node 26). **rc13 is unusable here.**
- **Reverted to rc.9** (no rust-bridge dep, loads clean) and **added a `fetchLatestBaileysVersion()`
  patch** so it advertises the current WA Web version.

### Source patches applied (already built into `dist/`)
- `src/auth.ts`: import `fetchLatestBaileysVersion`; fetch `{version}` and pass `version` to
  `makeWASocket(...)`; logs `Using WhatsApp Web version ...`.
- `src/index.ts`: same — import + `const { version } = await fetchLatestBaileysVersion();` +
  `version` in the `makeWASocket({...})` options.
- Rebuilt with `npm run build` (tsc, exit 0).

### NEXT ACTION (user runs, in their own terminal so they can scan):
```bash
cd ~/Projects/whatsapp-bridge
npm run auth          # expect: "Using WhatsApp Web version 2.xxxx.x (latest: true)" then a QR
# Phone: WhatsApp > Settings > Linked Devices > Link a Device > scan
# Wait for "Successfully authenticated with WhatsApp!" (it syncs then exits)
```
**If still 405:** version wasn't the cause. Other angles to try: an intermediate rc
(rc10/rc11/rc12) that has a current bundled version but no rust-bridge; check system clock/ntp;
ensure not rate-limited (wait a few min between attempts). The previously-linked WA number was
`919326904804`.

> **Alternative if user wants CRM up without WhatsApp now:** skip the bridge entirely, just run
> `bench start`. CRM runs fine; set bridge settings later once paired.

---

## WhatsApp pairing — DONE ✅ (2026-06-10)
- Re-paired via `npm run auth` (rc.9 + version fix worked — QR shown, scanned, "Successfully authenticated").
- Bridge connects ("Connected to WhatsApp", number `919326904804`) and listens on **:3100**.
- **CRM WhatsApp Bridge Settings saved** (enabled=1, bridge_url=http://localhost:3100, webhook_secret set).
  Doctype `crm/fcrm/doctype/crm_whatsapp_bridge_settings`; handler `crm/integrations/whatsapp/handler.py`
  (`...handler.webhook`). NOTE: settings `save()` validates by pinging the bridge — bridge must be UP first.

---

## PRODUCTION HOSTING — `whatsapp.billingfast.com` — DONE ✅ (one restart pending)

User wants this served at **https://whatsapp.billingfast.com** (NOT localhost). Decisions:
**systemd services** (reboot-safe) + **certbot --nginx** for TLS.

### Machine / hosting facts
- This is a **public server**, public IP **187.127.139.31**.
- nginx + certbot already installed; nginx is active serving other billingfast subdomains.
- Existing vhosts in `/etc/nginx/sites-enabled/` (bollo, fastlane, store, salefast .billingfast.com).
  Pattern: per-domain 443 server block, Let's Encrypt cert under `/etc/letsencrypt/live/<domain>/`,
  reverse-proxy to a local app port. `nginx.conf` does `include /etc/nginx/sites-enabled/*;`.
- Routing: `common_site_config.json` has `default_site: crm.localhost` + `serve_default_site: true`,
  so requests for `whatsapp.billingfast.com` are served by the crm.localhost site automatically —
  **no site rename / add-domain needed.**
- Set `host_name: "https://whatsapp.billingfast.com"` in `sites/crm.localhost/site_config.json`.

### Deploy artifacts (version-controlled in `deploy/`)
- `deploy/frappe-crm.service` → runs `env/bin/bench start` (web 8000, socketio 9000, redis 11000/13000,
  workers, scheduler). PATH includes venv bin so Procfile's bare `bench` cmds resolve.
- `deploy/whatsapp-bridge.service` → runs `node dist/server.js` with the PORT/WEBHOOK_*/STORE_DIR env.
- `deploy/whatsapp.billingfast.conf` → nginx vhost (HTTP); proxies `/socket.io/`→9000, everything
  else→8000. certbot has since added the 443 block + http→https redirect (now in the installed copy
  at `/etc/nginx/sites-enabled/whatsapp.billingfast.conf`).

### Install steps — ALL DONE ✅ (USER ran these; sudo prompts for password)
```bash
# 1. systemd services  [DONE]
sudo cp /home/omegaui/Projects/crm/deploy/frappe-crm.service /etc/systemd/system/
sudo cp /home/omegaui/Projects/crm/deploy/whatsapp-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now frappe-crm.service whatsapp-bridge.service

# 2. nginx vhost  [DONE]
sudo cp /home/omegaui/Projects/crm/deploy/whatsapp.billingfast.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 3. DNS A record whatsapp.billingfast.com -> 187.127.139.31  [DONE]
# 4. TLS  [DONE]
sudo certbot --nginx -d whatsapp.billingfast.com
```

### Issues hit during go-live (and fixes)
- **redis_queue crash-loop:** the rsync'd `config/pids/redis_queue.rdb` was RDB **format v12** (newer
  Redis), but Arch's `redis-server` is **Valkey** which can't load it → `# Can't handle RDB format
  version 12` → service kept restarting. **Fix:** deleted the stale `*.rdb` (queue data is ephemeral).
  If it recurs after a redis upgrade, delete `config/pids/*.rdb` again.
- **Login CSS 404 / unstyled:** `bench watch` (dev live-reload, part of `bench start`) kept rebuilding
  assets with new content-hashes, so the page referenced an old hash while disk had a new one. **Fix:**
  removed the `watch:` line from `frappe-bench/Procfile` (no live-reload on a prod box). **Requires one
  `sudo systemctl restart frappe-crm`** so the web worker reloads the current `sites/assets/assets.json`.

### Verify (no sudo needed)
- `systemctl is-active frappe-crm whatsapp-bridge nginx` → all `active`
- `curl --resolve whatsapp.billingfast.com:443:127.0.0.1 -s https://whatsapp.billingfast.com/api/method/ping` → `{"message":"pong"}`
- `ss -ltn | grep -E ':(8000|9000|3100|11000|13000)'`
- After the pending restart: the login CSS asset returns 200 and the page renders styled.

> Login when live: **https://whatsapp.billingfast.com/login** → `kumar@billingfast.com` / `kumar@bfcrm1.1`
> (CRM UI at `/crm`). `/crm` returns 403 for guests by design — that's the SPA's permission check, not a bug.

---

## WhatsApp hardening + features (2026-06-17)

Big round of anti-ban + feature work after WhatsApp logged the device out (`device_removed`,
caused by bulk cold-sending). All in the bridge (`~/Projects/whatsapp-bridge`, its own repo) +
the CRM app.

- **Throttled send queue** (bridge `send_queue` table + paced worker). Every send is enqueued and
  dispatched under a **ceiling**: messages go out immediately until `RATE_MAX` have been sent in
  the last `RATE_WINDOW_MS`, then wait just enough to stay under the cap (NOT a per-message pacer).
  Defaults: **10 per 1 min** (strict). Env knobs (set in `deploy/whatsapp-bridge.service`):
  `WA_RATE_MAX`, `WA_RATE_WINDOW_MS`, `WA_DAILY_CAP` (0=off), `WA_VERIFY_ON_WHATSAPP` (1=on),
  `WA_PAUSE_ON_WARNING_MS`. API returns `{queued:true}` instantly; `GET /queue/status` for visibility.
- **Human-behaviour emulation**: before each send the bridge shows a "typing…" presence for a
  length-based, randomized duration (`WA_TYPING`=1 default; `WA_TYPING_MIN_MS`/`_MAX_MS`/`_PER_CHAR_MS`).
- **HTTP server starts before the WhatsApp connection** (`server.ts main()`), so `/status`, `/qr`,
  `/relink` are reachable even when logged out — required for QR pairing from the CRM.
- **Guards**: verify recipient is on WhatsApp before sending (skips dead numbers); auto-pause sending
  for a cooldown when WhatsApp returns rate/forbidden errors.
- **Image + caption = one message** (frontend `ChatComposer.vue` now stages the attachment instead
  of auto-sending it; bridge already supported caption).
- **Incoming URL rendering fixed** + **HTML-escaped** (XSS) in `formatMessage` (WhatsAppChats.vue).
- **WhatsApp login/auth from the CRM**: bridge `POST /relink` (clear dead session → new QR) and
  `POST /logout`; backend `handler.relink_bridge` / `handler.logout_bridge` (manager-only);
  `Settings → WhatsApp` shows status + QR (auto-polling) + **Connect/Re-link** + **Disconnect**.
  So no more terminal `npm run auth` needed for re-pairing.
- **Excel/CSV contact import** (`crm.api.whatsapp.parse_contacts_file`, ad-hoc, nothing saved):
  auto-detects a phone column (or scans cells), normalizes to E.164. Wired into the **New Chat**
  dialog (bulk-start chats: one message → many imported numbers) and the **Broadcast** dialog
  (adds parsed numbers to recipients). Needs `openpyxl` (present, 3.1.5).
- **Broadcast** (WhatsApp-broadcast style): `Broadcast` button in the Chats header → pick existing
  chats + paste numbers + message + optional image → `crm.api.whatsapp.send_broadcast` enqueues each
  recipient through the throttle (so a broadcast can't breach the rate limit). Each recipient gets a
  normal 1:1 message.

> After any of these changes: `sudo systemctl restart whatsapp-bridge frappe-crm`. The bridge keeps
> its session across restarts (no re-pair) **unless** WhatsApp removed the device — then use the
> Settings → WhatsApp → Connect/Re-link button (or `npm run auth`).
> ⚠️ The throttle massively lowers ban risk but is not a license to bulk-cold-message; that's what
> got the device removed in the first place.

## Service / port reference

| Service         | Port  | Notes |
|-----------------|-------|-------|
| Frappe Web      | 8000  | `bench serve` (Werkzeug). Fine for low traffic; swap to gunicorn later for scale. |
| Socket.IO       | 9000  | realtime |
| Redis cache     | 13000 | spawned by bench (Procfile), separate from system redis on 6379 |
| Redis queue     | 11000 | spawned by bench |
| MariaDB         | 3306  | system service (`systemctl status mariadb`) |
| WhatsApp Bridge | 3100  | `node dist/server.js` in whatsapp-bridge |

## Gotchas / notes

- Always run `bench` as `frappe-bench/env/bin/bench` from inside `frappe-bench/` (not on PATH).
- `redis` system service runs on 6379 but bench uses its OWN redis on 11000/13000 — no conflict.
- wkhtmltopdf: **skipped** (AUR-only on Arch; only needed for PDF export, not to run CRM).
- Node 26 is bleeding-edge: any other native npm module may need rebuild/upgrade (e.g. `sharp`).
- `instructions.md` (Ubuntu-oriented) is the original setup guide; this file supersedes it for Arch.
- **Service management:** `sudo systemctl {status,restart,stop} frappe-crm whatsapp-bridge`.
  Logs: `journalctl -u frappe-crm -f` / `journalctl -u whatsapp-bridge -f`.
- **`watch` was removed from `frappe-bench/Procfile`** (no dev live-reload in prod). After any
  `bench build`/asset change, run `sudo systemctl restart frappe-crm` so the worker reloads the manifest.
- **Admin login** is `kumar@billingfast.com` (System Manager); `Administrator` is the hardened fallback.
  Reset either via: `printf 'from frappe.utils.password import update_password; update_password("<user>","<pw>"); frappe.db.commit()\n' | env/bin/bench --site crm.localhost console`.
