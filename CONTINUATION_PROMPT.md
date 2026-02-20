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
  - Bench binary: `/home/omegaui/.local/bin/bench`
  - Site: `crm.localhost`

## Deployment Workflow (CRITICAL)

Changes in working dir must be synced to bench:

```bash
# 1. Sync Python + frontend
rsync -a /home/omegaui/Projects/crm/crm/ /home/omegaui/Projects/crm/frappe-bench/apps/crm/crm/
rsync -a /home/omegaui/Projects/crm/frontend/src/ /home/omegaui/Projects/crm/frappe-bench/apps/crm/frontend/src/

# 2. Clear cache
cd /home/omegaui/Projects/crm/frappe-bench && /home/omegaui/.local/bin/bench --site crm.localhost clear-cache

# 3. Build frontend (--force to bust cache)
/home/omegaui/.local/bin/bench build --app crm --force

# 4. User restarts bench + bridge manually
```

## Files Modified

### Bridge (TypeScript) — `/home/omegaui/Projects/whatsapp-bridge/src/`

| File | Key Changes |
|------|-------------|
| `types.ts` | Added `media_path` to StoredMessage, `last_message` + `assigned_to` to Chat interface |
| `db.ts` | `media_path` column + migration, `assigned_to TEXT` column + migration, `storeMessage` ON CONFLICT upsert, backfill chat names, `getAllChats` with last_message subquery + `c.assigned_to`, `assignChat(jid, assignedTo)` function, `contacts` table with `upsertContact` + `resolvePhoneForLid` |
| `index.ts` | `extractMessageContent` for unwrapping ephemeral/viewOnce/edited msgs, `downloadMediaMessage` for media, `contacts.upsert`/`contacts.update` for name sync, `knownGroupNumbers` set for group detection, enhanced `translateJid`, **`pendingSenderNames` Map** stores CRM user's name keyed by msg ID for outgoing messages, `sendMessage(phone, text, senderName?)` + `sendFile(phone, filePath, caption, senderName?)` store pending sender names, `assignChat(jid, assignedTo)` method |
| `server.ts` | CORS media at `/media`, `buildAliasMap()` deduplicates JIDs. `/send` + `/send-file-url` accept `sender_name` in body. **`POST /chats/:jid/assign`** endpoint. `/chats` and `/chats/:jid/messages` use alias map |

### CRM Backend (Python) — `/home/omegaui/Projects/crm/crm/`

| File | Key Changes |
|------|-------------|
| `crm/api/whatsapp.py` | **Bridge APIs**: `get_chat_list` (includes `assigned_to`), `get_chat_messages(jid)` (outgoing messages show `sender_name` or "You"), `send_chat_message` (passes `frappe.utils.get_fullname` as `sender_name`), `assign_chat(jid, user)` (admin/manager only — proxies to bridge), `get_chat_lead(phone)`, `convert_chat_to_lead(phone, contact_name, assigned_to)` (uses `assigned_to` as `lead_owner` if provided). **Helpers**: `_jid_to_phone`, `_phone_to_jid`, `_resolve_contact_name`, `_get_bridge_messages_for_doc` |
| `crm/api/user.py` | **`create_crm_user(email, first_name, last_name, password, role)`** — creates Frappe User with password (no email verification), assigns CRM role. Admin/manager only. |
| `crm/integrations/whatsapp/handler.py` | `send_message_via_bridge(phone, message, sender_name=None)` + `send_file_via_bridge(phone, file_url, filename, caption, sender_name=None)` forward `sender_name` to bridge |

### CRM Frontend (Vue) — `/home/omegaui/Projects/crm/frontend/src/`

| File | Key Changes |
|------|-------------|
| `pages/WhatsAppChats.vue` | WhatsApp-like split panel. Left: search, conversation list (last message preview, unread green dot, small UserAvatar for assigned staff). Right: chat header with **assignment UI** (Autocomplete dropdown for managers, UserAvatar + name when assigned, unassign X button — all gated by `isManager()`), Convert to Lead / View Lead buttons (passes `assigned_to` to lead creation), messages with sender name in blue for outgoing. Socket + 5s poll. |
| `components/ChatComposer.vue` | Composer with `phone` + `jid` props. File upload, emoji picker. Calls `send_chat_message` with JID. |
| `components/Modals/CreateNewUserModal.vue` | **NEW** — Dialog to create users with email, first/last name, password, role selection. Calls `crm.api.user.create_crm_user`. |
| `components/Settings/Users.vue` | Added "Create new user" option in dropdown (alongside "Add existing user" and "Invite new user"). Imports + renders `CreateNewUserModal`. |
| `components/Layouts/AppSidebar.vue` | Sidebar order: **Chats** (top, conditional on `whatsappBridgeMode`), Dashboard, Leads, Deals, Notes, Tasks, Calendar. **Removed**: Organizations, Contacts, Call Logs. |
| `components/Icons/WhatsAppIcon.vue` | SVG icon |
| `components/Icons/CheckIcon.vue` | SVG checkmark |
| `router.js` | Added `/chats` route |

## Staff Management Features

### Chat Assignment (Admin/Manager Only)
- Bridge stores `assigned_to` TEXT column in `chats` table
- `POST /chats/:jid/assign` bridge endpoint sets/clears assignment
- CRM `assign_chat(jid, user)` API proxies to bridge, gated to System Manager + Sales Manager roles
- Frontend: Autocomplete dropdown in chat header, UserAvatar in chat list. Hidden for Sales Users (view-only).

### Outgoing Message Sender Name
- CRM passes `frappe.utils.get_fullname(frappe.session.user)` as `sender_name` when sending
- Bridge stores in `pendingSenderNames` Map keyed by message ID
- On `messages.upsert`, checks map for outgoing messages and uses stored name
- Frontend shows sender name in blue above outgoing messages (when not "You")

### Convert to Lead with Correct Owner
- `convert_chat_to_lead(phone, contact_name, assigned_to)` uses `assigned_to` as `lead_owner` if provided
- Frontend passes `selectedChat.assigned_to` when converting
- CRM Lead's `after_insert` hook auto-assigns `lead_owner` to `_assign` field
- This ensures the "Assigned to" column in Leads list shows the staff, not Administrator

### Create User with Password
- Backend: `crm.api.user.create_crm_user` — creates Frappe User with `send_welcome_email=0`, `flags.no_welcome_mail=True`, then calls `update_user_role`
- Frontend: `CreateNewUserModal.vue` — form dialog in Settings > Users > "Create new user" dropdown option

## JID Format Gotchas (Source of Most Bugs)

- `919876543210@s.whatsapp.net` — Phone-based individual (preferred)
- `215414101512439@lid` — Linked ID (newer WhatsApp, same person)
- `120363144853448591@g.us` — Group JID
- Same person has messages under BOTH @lid and @s.whatsapp.net → `buildAliasMap` deduplicates by name
- Group messages sometimes arrive as @s.whatsapp.net or @lid → `translateJid` + `buildAliasMap` fix this
- Sending to @lid must preserve the JID → `send_chat_message` accepts `jid` param, bridge's `toJid()` passes JIDs through

## What's Working

1. Chats page with WhatsApp-like split panel UI (moved to top of sidebar)
2. All conversations (individual + group) from bridge
3. Sending/receiving text messages (with correct JID routing)
4. Media: images (fullscreen), video (inline), audio (inline player), documents (download)
5. WhatsApp text formatting (bold, italic, strikethrough, code)
6. Contact name resolution (pushName → bridge DB → CRM contact)
7. JID deduplication (all three formats for individuals and groups)
8. Convert chat to CRM Lead (WhatsApp source auto-created, respects chat assignment)
9. View Lead/Deal link when chat is already linked
10. Lead's WhatsApp tab shows bridge messages
11. Unread green dot indicators
12. Last message preview in chat list
13. UTC → local timezone conversion
14. Realtime updates (socket + polling)
15. New Chat dialog
16. Search/filter chats
17. **Staff assignment to WhatsApp chats** (admin/manager only)
18. **Logged-in user's name on outgoing messages** (sender name tracking)
19. **Create new user with password** (bypasses email invitation)
20. **Lead assignment inherits chat assignment** (not "Administrator")

## Known Issues / Not Done

- **Calls**: Baileys does NOT support voice/video calls
- **Read receipts**: Not implemented
- **Typing indicators**: Not implemented
- **Message reactions**: Skipped in bridge (filtered out)
- **Reply-to threading**: Bridge doesn't track reply_to from WhatsApp
- **Status broadcasts**: Filtered out

## Bridge SQLite Schema

```sql
CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TEXT, assigned_to TEXT);
CREATE TABLE messages (
  id TEXT, chat_jid TEXT, sender TEXT, sender_name TEXT, content TEXT,
  timestamp TEXT, is_from_me INTEGER, content_type TEXT DEFAULT 'text',
  media_mimetype TEXT, media_path TEXT,
  PRIMARY KEY (id, chat_jid), FOREIGN KEY (chat_jid) REFERENCES chats(jid)
);
CREATE TABLE contacts (
  jid TEXT PRIMARY KEY, name TEXT, phone TEXT,
  UNIQUE(phone)
);
```

## Key API Endpoints

### Bridge (port 3100)
- `GET /chats` — All chats with aliases, last_message, assigned_to
- `GET /chats/:jid/messages?limit=200` — Messages (merges aliases)
- `POST /send` — `{phone, message, sender_name?}`
- `POST /send-file-url` — `{phone, file_url, filename, caption, sender_name?}`
- `POST /chats/:jid/assign` — `{assigned_to}` (set/clear staff assignment)
- `GET /media/:filename` — Downloaded media files (CORS enabled)

### CRM (Frappe whitelisted)
- `crm.api.whatsapp.get_chat_list` — Proxies bridge /chats, resolves CRM names, includes assigned_to
- `crm.api.whatsapp.get_chat_messages(jid)` — Proxies bridge, adds full media URLs, sender names
- `crm.api.whatsapp.send_chat_message(phone, message, attach, content_type, jid)` — Sends via bridge with sender_name
- `crm.api.whatsapp.assign_chat(jid, user)` — Admin/manager only, proxies to bridge
- `crm.api.whatsapp.get_chat_lead(phone)` — Check if linked to Lead/Deal
- `crm.api.whatsapp.convert_chat_to_lead(phone, contact_name, assigned_to)` — Creates CRM Lead with correct owner
- `crm.api.whatsapp.get_whatsapp_messages(reference_doctype, reference_name)` — Lead/Deal WhatsApp tab
- `crm.api.user.create_crm_user(email, first_name, last_name, password, role)` — Create user with password

## Important Notes

1. **`bench` binary is at**: `/home/omegaui/Projects/crm/.venv/bin/bench` (not in PATH)
2. **`bench` must run from bench dir**: `cd /home/omegaui/Projects/crm/frappe-bench` first
3. **New @frappe.whitelist functions**: Must `bench clear-cache` + restart bench
4. **`_use_bridge()`**: Returns True when frappe_whatsapp NOT installed AND `CRM WhatsApp Bridge Settings` exists AND enabled=True
5. **CRM WhatsApp Bridge Settings** doctype: `enabled` (Check), `bridge_url` (Data, default http://localhost:3100), `webhook_secret` (Password, set to 4321)
6. **WhatsApp Message** hooks in `hooks.py`: `validate` and `on_update` point to `crm.api.whatsapp`
7. **User roles**: System Manager (Admin), Sales Manager (Manager), Sales User — `isManager()` from usersStore returns true for both System Manager and Sales Manager
8. **Sidebar customized**: Organizations, Contacts, Call Logs removed. Chats moved to top.
