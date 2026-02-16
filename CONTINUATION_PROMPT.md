# WhatsApp Bridge + Frappe CRM Integration — Continuation Prompt

## Architecture

```
WhatsApp ←→ Baileys Bridge (:3100) ←→ HTTP/Webhooks ←→ Frappe CRM (:8000)
```

- **WhatsApp Bridge**: Node.js + TypeScript using `@whiskeysockets/baileys` (reverse-engineered WhatsApp Web). Stores in SQLite (`store/messages.db`). Port 3100.
  - Location: `/home/omegaui/Projects/whatsapp-bridge/`
  - Start: `cd /home/omegaui/Projects/whatsapp-bridge && WEBHOOK_URL=http://localhost:8000/api/method/crm.integrations.whatsapp.handler.webhook WEBHOOK_SECRET=4321 npm run server`
  - Compile: `cd /home/omegaui/Projects/whatsapp-bridge && npx tsc`

- **Frappe CRM**: Python/Vue CRM on Frappe framework.
  - Source (working dir): `/home/omegaui/Projects/crm/`
  - Bench (deployed): `/home/omegaui/Projects/crm/frappe-bench/apps/crm/`
  - Bench binary: `/home/omegaui/Projects/crm/.venv/bin/bench`
  - Site: `crm.localhost`

## Deployment Workflow (CRITICAL)

Changes in working dir must be synced to bench:

```bash
# 1. Sync Python + frontend
rsync -a /home/omegaui/Projects/crm/crm/ /home/omegaui/Projects/crm/frappe-bench/apps/crm/crm/ --exclude='*.pyc' --exclude='__pycache__'
rsync -a /home/omegaui/Projects/crm/frontend/src/ /home/omegaui/Projects/crm/frappe-bench/apps/crm/frontend/src/

# 2. Clear caches (from bench dir!)
find /home/omegaui/Projects/crm/frappe-bench/apps/crm/crm/api -name '__pycache__' -exec rm -rf {} + 2>/dev/null
cd /home/omegaui/Projects/crm/frappe-bench && /home/omegaui/Projects/crm/.venv/bin/bench --site crm.localhost clear-cache

# 3. Build frontend (--force to bust cache)
cd /home/omegaui/Projects/crm/frappe-bench && /home/omegaui/Projects/crm/.venv/bin/bench build --app crm --force

# 4. User restarts bench + bridge manually
```

## Files Modified

### Bridge (TypeScript) — `/home/omegaui/Projects/whatsapp-bridge/src/`

| File | Key Changes |
|------|-------------|
| `types.ts` | Added `media_path` to StoredMessage, `last_message` to Chat interface |
| `db.ts` | `media_path` column + migration, `storeMessage` ON CONFLICT upsert, backfill chat names from sender_name, `getAllChats` with COALESCE name fallback + `last_message` subquery |
| `index.ts` | `extractMessageContent` for unwrapping ephemeral/viewOnce/edited msgs, `downloadMediaMessage` for media, `contacts.upsert`/`contacts.update` for name sync, `knownGroupNumbers` set for group detection, enhanced `translateJid` that fixes @lid→@g.us and @s.whatsapp.net→@g.us for groups |
| `server.ts` | CORS media at `/media`, `buildAliasMap()` deduplicates: (1) individual chats by name across @lid/@s.whatsapp.net, (2) group chats by numeric prefix across @lid/@s.whatsapp.net/@g.us. `/chats` and `/chats/:jid/messages` use alias map |

### CRM Backend (Python) — `/home/omegaui/Projects/crm/crm/`

| File | Key Changes |
|------|-------------|
| `crm/api/whatsapp.py` | **Bug fixes**: `on_update` phone in realtime, `notify_agent` guard, `get_from_name` fallback. **Bridge mode in get_whatsapp_messages**: calls `_get_bridge_messages_for_doc` (resolves lead phone → JID → bridge messages). **New APIs**: `get_chat_list` (all conversations + groups + last_message), `get_chat_messages(jid)` (messages with media URLs), `send_chat_message(phone, jid)` (sends using JID directly), `get_chat_lead(phone)`, `convert_chat_to_lead(phone, contact_name)` (creates CRM Lead with WhatsApp source). **Helpers**: `_jid_to_phone`, `_phone_to_jid`, `_resolve_contact_name`, `_get_bridge_messages_for_doc` |

### CRM Frontend (Vue) — `/home/omegaui/Projects/crm/frontend/src/`

| File | Key Changes |
|------|-------------|
| `pages/WhatsAppChats.vue` | WhatsApp-like split panel. Left: search, conversation list (last message preview, unread green dot). Right: chat header with Convert to Lead / View Lead button, messages (image fullscreen overlay, inline audio, video, docs), WhatsApp formatting, ChatComposer. UTC→local timezone. Socket + 5s poll. New Chat dialog. |
| `components/ChatComposer.vue` | Composer with `phone` + `jid` props. File upload, emoji picker. Calls `send_chat_message` with JID. |
| `components/Icons/WhatsAppIcon.vue` | SVG icon |
| `components/Icons/CheckIcon.vue` | SVG checkmark |
| `router.js` | Added `/chats` route |
| `components/Layouts/AppSidebar.vue` | "Chats" sidebar link (conditional on `whatsappBridgeMode`) |

## JID Format Gotchas (Source of Most Bugs)

- `919876543210@s.whatsapp.net` — Phone-based individual (preferred)
- `215414101512439@lid` — Linked ID (newer WhatsApp, same person)
- `120363144853448591@g.us` — Group JID
- Same person has messages under BOTH @lid and @s.whatsapp.net → `buildAliasMap` deduplicates by name
- Group messages sometimes arrive as @s.whatsapp.net or @lid → `translateJid` + `buildAliasMap` fix this by matching numeric prefix to known @g.us JIDs
- Sending to @lid must preserve the JID (not convert to phone) → `send_chat_message` accepts `jid` param, bridge's `toJid()` passes JIDs through

## What's Working

1. Chats page with WhatsApp-like split panel UI
2. All conversations (individual + group) from bridge
3. Sending/receiving text messages (with correct JID routing)
4. Media: images (fullscreen), video (inline), audio (inline player), documents (download)
5. WhatsApp text formatting (bold, italic, strikethrough, code)
6. Contact name resolution (pushName → bridge DB → CRM contact)
7. JID deduplication (all three formats for individuals and groups)
8. Convert chat to CRM Lead (WhatsApp source auto-created)
9. View Lead/Deal link when chat is already linked
10. Lead's WhatsApp tab shows bridge messages
11. Unread green dot indicators
12. Last message preview in chat list
13. UTC → IST timezone conversion
14. Realtime updates (socket + polling)
15. New Chat dialog
16. Search/filter chats

## Known Issues / Not Done

- **Calls**: Baileys does NOT support voice/video calls
- **Read receipts**: Not implemented
- **Typing indicators**: Not implemented
- **Message reactions**: Skipped in bridge (filtered out)
- **Reply-to threading**: Bridge doesn't track reply_to from WhatsApp
- **Status broadcasts**: Filtered out

## Bridge SQLite Schema

```sql
CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TEXT);
CREATE TABLE messages (
  id TEXT, chat_jid TEXT, sender TEXT, sender_name TEXT, content TEXT,
  timestamp TEXT, is_from_me INTEGER, content_type TEXT DEFAULT 'text',
  media_mimetype TEXT, media_path TEXT,
  PRIMARY KEY (id, chat_jid), FOREIGN KEY (chat_jid) REFERENCES chats(jid)
);
```

## Key API Endpoints

### Bridge (port 3100)
- `GET /chats` — All chats with aliases, last_message
- `GET /chats/:jid/messages?limit=200` — Messages (merges aliases)
- `POST /send` — `{phone, message}` (phone can be JID with @)
- `POST /send-file-url` — `{phone, file_url, filename, caption}`
- `GET /media/:filename` — Downloaded media files (CORS enabled)

### CRM (Frappe whitelisted)
- `crm.api.whatsapp.get_chat_list` — Proxies bridge /chats, resolves CRM names
- `crm.api.whatsapp.get_chat_messages(jid)` — Proxies bridge, adds full media URLs
- `crm.api.whatsapp.send_chat_message(phone, message, attach, content_type, jid)` — Sends via bridge using JID
- `crm.api.whatsapp.get_chat_lead(phone)` — Check if linked to Lead/Deal
- `crm.api.whatsapp.convert_chat_to_lead(phone, contact_name)` — Creates CRM Lead
- `crm.api.whatsapp.get_whatsapp_messages(reference_doctype, reference_name)` — Lead/Deal WhatsApp tab, fetches from bridge in bridge mode

## Important Notes

1. **`bench` must run from bench dir**: `cd /home/omegaui/Projects/crm/frappe-bench` first
2. **New @frappe.whitelist functions**: Must clear `__pycache__` + `bench clear-cache` + restart bench
3. **`_use_bridge()`**: Returns True when frappe_whatsapp NOT installed AND `CRM WhatsApp Bridge Settings` exists AND enabled=True
4. **CRM WhatsApp Bridge Settings** doctype: `enabled` (Check), `bridge_url` (Data, default http://localhost:3100), `webhook_secret` (Password, set to 4321)
5. **WhatsApp Message** hooks in `hooks.py`: `validate` and `on_update` point to `crm.api.whatsapp`
