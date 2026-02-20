import json

import frappe
import requests
from frappe import _
from frappe.permissions import add_permission, update_permission_property

from crm.api.doc import get_assigned_users
from crm.fcrm.doctype.crm_notification.crm_notification import notify_user
from crm.integrations.api import get_contact_lead_or_deal_from_number

ALLOWED_WHATSAPP_ROLES = ["System Manager", "Sales Manager", "Sales User"]


def _use_bridge():
	"""Return True if we should use the WhatsApp bridge instead of frappe_whatsapp."""
	if "frappe_whatsapp" in frappe.get_installed_apps():
		return False
	if not frappe.db.exists("DocType", "CRM WhatsApp Bridge Settings"):
		return False
	return bool(frappe.db.get_single_value("CRM WhatsApp Bridge Settings", "enabled"))


def validate_access(reference_doctype=None, reference_name=None, permtype="read"):
	if not any(role in ALLOWED_WHATSAPP_ROLES for role in frappe.get_roles()):
		frappe.throw(_("Only sales users can access WhatsApp features."), frappe.PermissionError)

	if reference_doctype and reference_name:
		if not frappe.db.exists(reference_doctype, reference_name):
			frappe.throw(
				_("Reference document {0} {1} does not exist.").format(reference_doctype, reference_name),
				frappe.DoesNotExistError,
			)
		reference_doc = frappe.get_doc(reference_doctype, reference_name)
		if not reference_doc.has_permission(permtype):
			frappe.throw(
				_("Not permitted to access reference document {0} {1}.").format(
					reference_doctype, reference_name
				),
				frappe.PermissionError,
			)
		return reference_doc

	return None


def validate(doc, method):
	phone_number = doc.get("from") if doc.type == "Incoming" else doc.get("to")
	if phone_number:
		name, doctype = get_contact_lead_or_deal_from_number(phone_number)
		if doctype and name is not None:
			doc.reference_doctype = doctype
			doc.reference_name = name


def on_update(doc, method):
	phone = doc.get("from") if doc.type == "Incoming" else doc.get("to")
	frappe.publish_realtime(
		"whatsapp_message",
		{
			"reference_doctype": doc.reference_doctype,
			"reference_name": doc.reference_name,
			"phone": phone,
		},
	)

	notify_agent(doc)


def notify_agent(doc):
	if not doc.reference_doctype or not doc.reference_name:
		return
	if doc.type == "Incoming":
		doctype = doc.reference_doctype
		if doctype and doctype.startswith("CRM "):
			doctype = doctype[4:].lower()
		notification_text = f"""
            <div class="mb-2 leading-5 text-ink-gray-5">
                <span class="font-medium text-ink-gray-9">{_("You")}</span>
                <span>{_("received a whatsapp message in {0}").format(doctype)}</span>
                <span class="font-medium text-ink-gray-9">{doc.reference_name}</span>
            </div>
        """
		assigned_users = get_assigned_users(doc.reference_doctype, doc.reference_name)
		for user in assigned_users:
			notify_user(
				{
					"owner": doc.owner,
					"assigned_to": user,
					"notification_type": "WhatsApp",
					"message": doc.message,
					"notification_text": notification_text,
					"reference_doctype": "WhatsApp Message",
					"reference_docname": doc.name,
					"redirect_to_doctype": doc.reference_doctype,
					"redirect_to_docname": doc.reference_name,
				}
			)


@frappe.whitelist()
def is_whatsapp_enabled():
	if _use_bridge():
		return True
	if not frappe.db.exists("DocType", "WhatsApp Settings"):
		return False
	default_outgoing = frappe.get_cached_value(
		"WhatsApp Settings", "WhatsApp Settings", "default_outgoing_account"
	)
	if not default_outgoing:
		return False
	status = frappe.get_cached_value("WhatsApp Account", default_outgoing, "status")
	return status == "Active"


@frappe.whitelist()
def is_whatsapp_installed():
	if _use_bridge():
		return True
	# Show settings page if bridge settings doctype exists (so user can enable it)
	if frappe.db.exists("DocType", "CRM WhatsApp Bridge Settings"):
		return True
	if not frappe.db.exists("DocType", "WhatsApp Settings"):
		return False
	return True


@frappe.whitelist()
def get_whatsapp_messages(reference_doctype, reference_name):
	reference_doc = validate_access(reference_doctype, reference_name)

	# In bridge mode, fetch messages directly from the bridge using the lead/deal's phone
	if _use_bridge():
		return _get_bridge_messages_for_doc(reference_doctype, reference_name, reference_doc)

	# twilio integration app is not compatible with crm app
	# crm has its own twilio integration in built
	if "twilio_integration" in frappe.get_installed_apps():
		return []
	if not frappe.db.exists("DocType", "WhatsApp Message"):
		return []
	messages = []

	if reference_doctype == "CRM Deal":
		lead = reference_doc.get("lead")
		if lead:
			validate_access("CRM Lead", lead)
			messages = frappe.get_all(
				"WhatsApp Message",
				filters={
					"reference_doctype": "CRM Lead",
					"reference_name": lead,
				},
				fields=WHATSAPP_MESSAGE_FIELDS,
			)

	messages += frappe.get_all(
		"WhatsApp Message",
		filters={
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		},
		fields=WHATSAPP_MESSAGE_FIELDS,
	)

	template_messages = [message for message in messages if message["message_type"] == "Template"]

	# Iterate through template messages
	for template_message in template_messages:
		# Find the template that this message is using
		template = frappe.get_doc("WhatsApp Templates", template_message["template"])

		# If the template is found, add the template details to the template message
		if template:
			template_message["template_name"] = template.template_name
			if template_message["template_parameters"]:
				parameters = json.loads(template_message["template_parameters"])
				template.template = parse_template_parameters(template.template, parameters)

			template_message["template"] = template.template
			if template_message["template_header_parameters"]:
				header_parameters = json.loads(template_message["template_header_parameters"])
				template.header = parse_template_parameters(template.header, header_parameters)
			template_message["header"] = template.header
			template_message["footer"] = template.footer

	return _process_messages(messages)


def _get_bridge_messages_for_doc(reference_doctype, reference_name, reference_doc):
	"""Fetch messages from the bridge for a Lead or Deal's phone number."""
	# Extract phone number from the document
	phone = ""
	if reference_doctype == "CRM Lead":
		phone = reference_doc.get("mobile_no") or reference_doc.get("phone") or ""
	elif reference_doctype == "CRM Deal":
		# Try the deal's lead first
		lead_name = reference_doc.get("lead")
		if lead_name and frappe.db.exists("CRM Lead", lead_name):
			lead_doc = frappe.get_doc("CRM Lead", lead_name)
			phone = lead_doc.get("mobile_no") or lead_doc.get("phone") or ""
		# Try contacts on the deal
		if not phone and reference_doc.get("contacts"):
			for c in reference_doc.get("contacts"):
				if c.mobile_no:
					phone = c.mobile_no
					break

	if not phone:
		return []

	# Find the JID for this phone number from the bridge chat list
	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	try:
		resp = requests.get(f"{bridge_url}/chats", timeout=10)
		resp.raise_for_status()
		bridge_chats = resp.json()
	except Exception:
		return []

	# Normalize phone for matching
	clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
	matched_jid = None
	for bc in bridge_chats:
		jid = bc.get("jid", "")
		jid_num = jid.split("@")[0].split(":")[0] if "@" in jid else ""
		if jid_num == clean_phone:
			matched_jid = jid
			break

	if not matched_jid:
		# Try with the phone as JID directly
		matched_jid = f"{clean_phone}@s.whatsapp.net"

	# Fetch messages from the bridge
	return get_chat_messages(matched_jid)


@frappe.whitelist()
def create_whatsapp_message(
	reference_doctype,
	reference_name,
	message,
	to,
	attach,
	reply_to,
	content_type="text",
):
	validate_access(reference_doctype, reference_name)

	if _use_bridge():
		return _create_bridge_message(
			reference_doctype, reference_name, message, to, attach, reply_to, content_type
		)

	doc = frappe.new_doc("WhatsApp Message")

	if reply_to:
		reply_doc = frappe.get_doc("WhatsApp Message", reply_to)
		if not reply_doc.has_permission("read"):
			frappe.throw(
				_("Not permitted to access the referenced WhatsApp message."), frappe.PermissionError
			)
		validate_access(reply_doc.reference_doctype, reply_doc.reference_name)
		doc.update(
			{
				"is_reply": True,
				"reply_to_message_id": reply_doc.message_id,
			}
		)

	doc.update(
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"message": message or attach,
			"to": to,
			"attach": attach,
			"content_type": content_type,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _create_bridge_message(
	reference_doctype, reference_name, message, to, attach, reply_to, content_type
):
	"""Send via bridge API and create local WhatsApp Message doc."""
	from crm.integrations.whatsapp.handler import send_file_via_bridge, send_message_via_bridge

	message_id = ""
	status = "sent"

	try:
		if attach and content_type in ("image", "document", "video", "audio"):
			result = send_file_via_bridge(to, attach, attach.split("/")[-1], message or "")
			message_id = result.get("message_id", "")
		elif message:
			result = send_message_via_bridge(to, message)
			message_id = result.get("message_id", "")
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge Send Error", message=str(e))
		status = "failed"

	doc = frappe.new_doc("WhatsApp Message")

	if reply_to:
		reply_doc = frappe.get_doc("WhatsApp Message", reply_to)
		if not reply_doc.has_permission("read"):
			frappe.throw(
				_("Not permitted to access the referenced WhatsApp message."), frappe.PermissionError
			)
		validate_access(reply_doc.reference_doctype, reply_doc.reference_name)
		doc.update(
			{
				"is_reply": True,
				"reply_to_message_id": reply_doc.message_id,
			}
		)

	doc.update(
		{
			"type": "Outgoing",
			"to": to,
			"message": message or attach,
			"message_id": message_id,
			"content_type": content_type,
			"status": status,
			"attach": attach if content_type != "text" else "",
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def send_whatsapp_template(reference_doctype, reference_name, template, to):
	if _use_bridge():
		frappe.throw(_("WhatsApp templates are not supported with the WhatsApp Bridge integration."))
	validate_access(reference_doctype, reference_name)
	doc = frappe.new_doc("WhatsApp Message")
	doc.update(
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"message_type": "Template",
			"message": "Template message",
			"content_type": "text",
			"use_template": True,
			"template": template,
			"to": to,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def react_on_whatsapp_message(emoji, reply_to_name):
	if _use_bridge():
		frappe.throw(_("Reactions are not supported with the WhatsApp Bridge integration."))
	validate_access()
	reply_to_doc = frappe.get_doc("WhatsApp Message", reply_to_name)

	if not reply_to_doc.has_permission("read"):
		frappe.throw(_("Not permitted to access the referenced WhatsApp message."), frappe.PermissionError)

	validate_access(reply_to_doc.reference_doctype, reply_to_doc.reference_name)

	to = (reply_to_doc.type == "Incoming" and reply_to_doc.get("from")) or reply_to_doc.to
	doc = frappe.new_doc("WhatsApp Message")
	doc.update(
		{
			"reference_doctype": reply_to_doc.reference_doctype,
			"reference_name": reply_to_doc.reference_name,
			"message": emoji,
			"to": to,
			"reply_to_message_id": reply_to_doc.message_id,
			"content_type": "reaction",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


WHATSAPP_MESSAGE_FIELDS = [
	"name", "type", "to", "from", "content_type", "message_type", "attach",
	"template", "use_template", "message_id", "is_reply", "reply_to_message_id",
	"creation", "message", "status", "reference_doctype", "reference_name",
	"template_parameters", "template_header_parameters",
]


def _process_messages(messages):
	"""Shared processing for WhatsApp messages: reactions, replies, from_name."""
	# Process reactions
	reaction_messages = [m for m in messages if m["content_type"] == "reaction"]
	reaction_messages.reverse()
	for reaction_message in reaction_messages:
		reacted_message = next(
			(m for m in messages if m["message_id"] == reaction_message["reply_to_message_id"]),
			None,
		)
		if reacted_message:
			reacted_message["reaction"] = reaction_message["message"]

	# Process from_name
	for message in messages:
		from_name = get_from_name(message) if message["from"] else _("You")
		message["from_name"] = from_name

	# Process replies
	reply_messages = [m for m in messages if m["is_reply"]]
	for reply_message in reply_messages:
		replied_message = next(
			(m for m in messages if m["message_id"] == reply_message["reply_to_message_id"]),
			None,
		)
		if replied_message:
			from_name = get_from_name(reply_message) if replied_message["from"] else _("You")
			msg = replied_message["message"]
			if replied_message["message_type"] == "Template":
				msg = replied_message["template"]
			reply_message["reply_message"] = msg
			reply_message["header"] = replied_message.get("header") or ""
			reply_message["footer"] = replied_message.get("footer") or ""
			reply_message["reply_to"] = replied_message["name"]
			reply_message["reply_to_type"] = replied_message["type"]
			reply_message["reply_to_from"] = from_name

	return [m for m in messages if m["content_type"] != "reaction"]


@frappe.whitelist()
def get_chat_list(search=None):
	"""Return all WhatsApp conversations from the bridge server."""
	validate_access()

	if not _use_bridge():
		return []

	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	try:
		resp = requests.get(f"{bridge_url}/chats", timeout=10)
		resp.raise_for_status()
		bridge_chats = resp.json()
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge: Failed to fetch chats", message=str(e))
		return []

	chats = []
	for bc in bridge_chats:
		jid = bc.get("jid", "")
		if not jid or jid == "status@broadcast":
			continue

		is_group = jid.endswith("@g.us")
		display_name = bc.get("name") or ""
		phone = ""

		if is_group:
			# Groups use their subject/name directly, no phone number
			phone = jid
		else:
			# Use the resolved phone from the bridge (handles LID→phone resolution)
			bridge_phone = bc.get("phone") or ""
			if bridge_phone:
				phone = bridge_phone
			else:
				# Fallback: only derive phone from @s.whatsapp.net JIDs (not @lid)
				if jid.endswith("@s.whatsapp.net"):
					phone = _jid_to_phone(jid)
				else:
					# @lid with no resolved phone — use the display name or JID as identifier
					phone = ""

			# Try to resolve CRM contact name for individual chats
			if phone:
				crm_name = _resolve_contact_name(phone)
				if crm_name:
					display_name = crm_name

		# Apply search filter
		if search:
			search_lower = search.lower()
			if (
				search_lower not in phone.lower()
				and search_lower not in display_name.lower()
			):
				continue

		chats.append({
			"jid": jid,
			"phone": phone,
			"contact_name": display_name,
			"is_group": is_group,
			"last_message_time": bc.get("last_message_time") or "",
			"last_message": bc.get("last_message") or "",
			"last_message_is_from_me": bool(bc.get("last_message_is_from_me")),
			"last_message_sender_name": bc.get("last_message_sender_name") or "",
			"assigned_to": bc.get("assigned_to") or "",
			"photo_url": bc.get("photo_url") or "",
		})

	return chats


def _jid_to_phone(jid):
	"""Convert WhatsApp JID to phone number: '919876543210@s.whatsapp.net' -> '+919876543210'"""
	if "@" in jid:
		return "+" + jid.split("@")[0].split(":")[0]
	return jid


def _phone_to_jid(phone):
	"""Convert phone number to WhatsApp JID: '+919876543210' -> '919876543210@s.whatsapp.net'"""
	cleaned = phone.replace("+", "").replace(" ", "").replace("-", "")
	return f"{cleaned}@s.whatsapp.net"


def _resolve_contact_name(phone):
	"""Try to resolve a phone number to a contact/lead name."""
	if not phone:
		return ""
	try:
		name, doctype = get_contact_lead_or_deal_from_number(phone)
		if not name or not doctype:
			return ""
		doc = frappe.get_doc(doctype, name)
		if doctype == "CRM Deal":
			if doc.get("contacts"):
				for c in doc.get("contacts"):
					if c.is_primary:
						return c.full_name or c.mobile_no or ""
			return doc.get("lead_name") or ""
		elif doctype == "CRM Lead":
			return " ".join(filter(None, [doc.get("first_name"), doc.get("last_name")])) or ""
		elif doctype == "Contact":
			return doc.get("full_name") or ""
	except Exception:
		pass
	return ""


@frappe.whitelist()
def get_chat_messages(jid):
	"""Return all WhatsApp messages for a given JID from the bridge server."""
	validate_access()

	if not jid or not _use_bridge():
		return []

	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	try:
		resp = requests.get(
			f"{bridge_url}/chats/{jid}/messages",
			params={"limit": 500},
			timeout=10,
		)
		resp.raise_for_status()
		bridge_messages = resp.json()
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge: Failed to fetch messages", message=str(e))
		return []

	# Transform bridge messages to CRM format
	messages = []
	for bm in bridge_messages:
		# Build media URL — proxy through Frappe so the client never needs direct bridge access
		attach = ""
		media_url = bm.get("media_url") or ""
		if media_url:
			from urllib.parse import quote as _quote
			filename = media_url.split("/")[-1]
			attach = f"/api/method/crm.api.whatsapp.get_media?filename={_quote(filename)}"

		messages.append({
			"name": bm.get("id", ""),
			"type": "Outgoing" if bm.get("is_from_me") else "Incoming",
			"from": _jid_to_phone(bm["sender"]) if not bm.get("is_from_me") else "",
			"to": _jid_to_phone(bm["chat_jid"]) if bm.get("is_from_me") else "",
			"message": bm.get("content", ""),
			"message_id": bm.get("id", ""),
			"content_type": bm.get("content_type", "text"),
			"message_type": "",
			"status": "sent" if bm.get("is_from_me") else "received",
			"creation": bm.get("timestamp", ""),
			"attach": attach,
			"is_reply": False,
			"reply_to_message_id": "",
			"from_name": bm.get("sender_name", "") if not bm.get("is_from_me") else (bm.get("sender_name") or _("You")),
		})

	return messages


@frappe.whitelist()
def get_media(filename):
	"""Proxy a media file from the WhatsApp bridge server so clients don't need direct bridge access."""
	validate_access()
	if not filename or not _use_bridge():
		frappe.throw(_("Not found"), frappe.DoesNotExistError)

	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	from urllib.parse import quote as _quote
	try:
		resp = requests.get(f"{bridge_url}/media/{_quote(str(filename))}", timeout=30)
		resp.raise_for_status()
	except Exception:
		frappe.throw(_("Media file not found"), frappe.DoesNotExistError)

	content_type = resp.headers.get("Content-Type", "application/octet-stream")
	frappe.response.type = "download"
	frappe.response.filename = filename
	frappe.response.filecontent = resp.content
	frappe.response.content_type = content_type
	# Serve inline so images/video/audio display directly in the browser
	frappe.response.display_content_as = "inline"


@frappe.whitelist()
def send_chat_message(phone, message="", attach="", content_type="text", jid="", reply_to=""):
	"""Send a WhatsApp message from the Chats page."""
	validate_access()

	if not _use_bridge():
		frappe.throw(_("Chat messaging is only supported with the WhatsApp Bridge integration."))

	from crm.integrations.whatsapp.handler import send_file_via_bridge, send_message_via_bridge

	# Use the JID directly if provided (preserves @lid, @g.us, etc.)
	# Fall back to phone number if no JID given
	send_to = jid if jid else phone

	# Pass the current user's full name so it appears on outgoing messages
	sender_name = frappe.utils.get_fullname(frappe.session.user) or frappe.session.user

	status = "sent"
	message_id = ""
	chat_jid = jid or _phone_to_jid(phone)

	try:
		if attach and content_type in ("image", "document", "video", "audio"):
			result = send_file_via_bridge(send_to, attach, attach.split("/")[-1], message or "", sender_name=sender_name)
			message_id = (result or {}).get("message_id", "")
			chat_jid = (result or {}).get("chat_jid", "") or chat_jid
		elif message:
			result = send_message_via_bridge(send_to, message, sender_name=sender_name)
			message_id = (result or {}).get("message_id", "")
			chat_jid = (result or {}).get("chat_jid", "") or chat_jid
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge Send Error", message=str(e))
		status = "failed"

	# Rich realtime event so Chats page can append instead of reload
	now_iso = frappe.utils.now_datetime().isoformat()
	frappe.publish_realtime("whatsapp_chat_update", {
		"event_type": "new_message",
		"chat_jid": chat_jid,
		"phone": phone,
		"message": {
			"name": message_id or frappe.generate_hash(length=10),
			"type": "Outgoing",
			"from": "",
			"to": phone,
			"message": message or "",
			"message_id": message_id,
			"content_type": content_type,
			"message_type": "",
			"status": status,
			"creation": now_iso,
			"attach": attach if content_type != "text" else "",
			"is_reply": False,
			"reply_to_message_id": "",
			"from_name": sender_name,
		},
		"chat_update": {
			"last_message": (message or "")[:100],
			"last_message_time": now_iso,
			"last_message_is_from_me": True,
			"last_message_sender_name": sender_name,
		},
	})

	# Legacy event for Activities component backward compatibility
	frappe.publish_realtime("whatsapp_message", {"phone": phone})

	return {"ok": True, "status": status, "message_id": message_id, "chat_jid": chat_jid}


@frappe.whitelist()
def assign_chat(jid, user=""):
	"""Assign a CRM user to a WhatsApp chat. Only admins and managers can assign."""
	validate_access()
	if not any(role in ["System Manager", "Sales Manager"] for role in frappe.get_roles()):
		frappe.throw(_("Only admins and managers can assign staff to chats."), frappe.PermissionError)

	if not _use_bridge() or not jid:
		return {"ok": False}

	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	try:
		resp = requests.post(
			f"{bridge_url}/chats/{jid}/assign",
			json={"assigned_to": user or None},
			timeout=10,
		)
		resp.raise_for_status()
		return resp.json()
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge: Failed to assign chat", message=str(e))
		return {"ok": False}


@frappe.whitelist()
def get_chat_lead(phone):
	"""Check if a phone number is already linked to a CRM Lead or Deal."""
	validate_access()
	if not phone:
		return None
	try:
		name, doctype = get_contact_lead_or_deal_from_number(phone)
		if name and doctype:
			return {"doctype": doctype, "name": name}
	except Exception:
		pass
	return None


@frappe.whitelist()
def convert_chat_to_lead(phone, contact_name="", assigned_to=""):
	"""Create a CRM Lead from a WhatsApp chat phone number."""
	validate_access()

	# Check if already linked (only if we have a valid phone)
	if phone:
		try:
			name, doctype = get_contact_lead_or_deal_from_number(phone)
			if name and doctype:
				return {"doctype": doctype, "name": name, "already_exists": True}
		except Exception:
			pass

	# Parse contact_name into first/last name
	parts = (contact_name or "").strip().split(" ", 1)
	first_name = parts[0] if parts[0] else (phone or "Unknown")
	last_name = parts[1] if len(parts) > 1 else ""

	# Ensure WhatsApp lead source exists
	source = ""
	if frappe.db.exists("DocType", "CRM Lead Source"):
		if not frappe.db.exists("CRM Lead Source", "WhatsApp"):
			frappe.get_doc({"doctype": "CRM Lead Source", "source_name": "WhatsApp"}).insert(
				ignore_permissions=True
			)
		source = "WhatsApp"

	# Use the assigned staff as lead_owner if provided, otherwise current user
	owner = assigned_to if assigned_to and frappe.db.exists("User", assigned_to) else frappe.session.user

	lead_data = {
		"first_name": first_name,
		"last_name": last_name,
		"lead_owner": owner,
		"source": source,
	}

	# Only set mobile_no if we have a real phone number (not a LID)
	if phone:
		lead_data["mobile_no"] = phone

	lead = frappe.new_doc("CRM Lead")
	lead.update(lead_data)
	lead.insert(ignore_permissions=True)

	return {"doctype": "CRM Lead", "name": lead.name, "already_exists": False}


@frappe.whitelist()
def get_profile_photo(jid):
	"""Fetch WhatsApp profile photo URL for a given JID via the bridge."""
	validate_access()
	if not jid or not _use_bridge():
		return {"url": None}
	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")
	try:
		from urllib.parse import quote
		resp = requests.get(f"{bridge_url}/chats/{quote(jid, safe='')}/photo", timeout=10)
		resp.raise_for_status()
		return resp.json()
	except Exception:
		return {"url": None}


@frappe.whitelist()
def delete_chat(jid):
	"""Delete an entire chat and all its messages from the bridge."""
	validate_access()
	if not any(role in ["System Manager", "Sales Manager"] for role in frappe.get_roles()):
		frappe.throw(_("Only admins and managers can delete chats."), frappe.PermissionError)

	if not jid or not _use_bridge():
		return {"ok": False}

	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	try:
		from urllib.parse import quote
		resp = requests.delete(
			f"{bridge_url}/chats/{quote(jid, safe='')}",
			timeout=10,
		)
		resp.raise_for_status()
		return resp.json()
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge: Failed to delete chat", message=str(e))
		return {"ok": False}


@frappe.whitelist()
def delete_chat_message(jid, message_id):
	"""Delete a message from the bridge's local store."""
	validate_access()
	if not jid or not message_id or not _use_bridge():
		return {"ok": False}
	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")
	try:
		from urllib.parse import quote
		resp = requests.delete(
			f"{bridge_url}/chats/{quote(jid, safe='')}/messages/{quote(message_id, safe='')}",
			timeout=10,
		)
		resp.raise_for_status()
		return resp.json()
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge: Failed to delete message", message=str(e))
		return {"ok": False}


@frappe.whitelist()
def merge_duplicate_chats():
	"""Merge duplicate WhatsApp chats that share the same phone number."""
	validate_access()
	if not any(role in ["System Manager", "Sales Manager"] for role in frappe.get_roles()):
		frappe.throw(_("Only admins and managers can merge chats."), frappe.PermissionError)

	if not _use_bridge():
		return {"ok": False, "merged": 0}

	settings = frappe.get_single("CRM WhatsApp Bridge Settings")
	bridge_url = (settings.bridge_url or "").rstrip("/")

	try:
		resp = requests.post(f"{bridge_url}/chats/merge-duplicates", timeout=30)
		resp.raise_for_status()
		return resp.json()
	except Exception as e:
		frappe.log_error(title="WhatsApp Bridge: Failed to merge duplicate chats", message=str(e))
		return {"ok": False, "merged": 0}


def parse_template_parameters(string, parameters):
	for i, parameter in enumerate(parameters, start=1):
		placeholder = "{{" + str(i) + "}}"
		string = string.replace(placeholder, parameter)

	return string


def get_from_name(message):
	if not message.get("reference_doctype") or not message.get("reference_name"):
		return message.get("from") or ""
	doc = frappe.get_doc(message["reference_doctype"], message["reference_name"])
	from_name = ""
	if message["reference_doctype"] == "CRM Deal":
		if doc.get("contacts"):
			for c in doc.get("contacts"):
				if c.is_primary:
					from_name = c.full_name or c.mobile_no
					break
		else:
			from_name = doc.get("lead_name")
	else:
		from_name = " ".join(filter(None, [doc.get("first_name"), doc.get("last_name")]))
	return from_name


def add_roles():
	if _use_bridge():
		# Permissions are already set in the doctype JSON for bridge mode
		return

	if "frappe_whatsapp" not in frappe.get_installed_apps():
		return

	role_list = ["Sales Manager", "Sales User"]
	doctypes = ["WhatsApp Message", "WhatsApp Templates", "WhatsApp Settings"]
	for doctype in doctypes:
		for role in role_list:
			if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role}):
				continue
			add_permission(doctype, role, 0, "write")
			update_permission_property(doctype, role, 0, "create", 1)
			update_permission_property(doctype, role, 0, "delete", 1)
			update_permission_property(doctype, role, 0, "share", 1)
			update_permission_property(doctype, role, 0, "email", 1)
			update_permission_property(doctype, role, 0, "print", 1)
			update_permission_property(doctype, role, 0, "report", 1)
			update_permission_property(doctype, role, 0, "export", 1)
