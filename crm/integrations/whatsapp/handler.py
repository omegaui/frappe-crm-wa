import base64
import hmac

import frappe
import requests
from frappe import _

from crm.integrations.api import get_contact_lead_or_deal_from_number


def get_bridge_settings():
	"""Return CRM WhatsApp Bridge Settings as a document."""
	return frappe.get_single("CRM WhatsApp Bridge Settings")


@frappe.whitelist()
def is_bridge_enabled():
	"""Check if the WhatsApp bridge integration is enabled."""
	if not frappe.db.exists("DocType", "CRM WhatsApp Bridge Settings"):
		return False
	return bool(frappe.db.get_single_value("CRM WhatsApp Bridge Settings", "enabled"))


def validate_webhook_secret():
	"""Validate the X-Webhook-Secret header matches our stored secret."""
	settings = get_bridge_settings()
	expected = settings.get_password("webhook_secret")
	received = frappe.request.headers.get("X-Webhook-Secret", "")
	if not expected or not received:
		frappe.throw(_("Missing webhook secret"), frappe.AuthenticationError)
	if not hmac.compare_digest(expected, received):
		frappe.throw(_("Invalid webhook secret"), frappe.AuthenticationError)


@frappe.whitelist(allow_guest=True)
def webhook(**kwargs):
	"""
	Webhook endpoint called by the WhatsApp bridge server when
	an incoming message arrives.

	URL: /api/method/crm.integrations.whatsapp.handler.webhook

	Expected JSON body (StoredMessage from bridge):
	{
	  "id": "ABCD1234",
	  "chat_jid": "919876543210@s.whatsapp.net",
	  "sender": "919876543210@s.whatsapp.net",
	  "sender_name": "John Doe",
	  "content": "Hello!",
	  "timestamp": "2026-02-12T10:30:00.000Z",
	  "is_from_me": false,
	  "content_type": "text",
	  "media_base64": null,
	  "media_filename": null
	}
	"""
	validate_webhook_secret()

	data = frappe.parse_json(frappe.request.data)

	# Skip messages sent by us (outgoing messages we already tracked)
	if data.get("is_from_me"):
		return {"ok": True, "skipped": True}

	# Skip if message_id already exists (dedup)
	msg_id = data.get("id", "")
	if msg_id and frappe.db.exists("WhatsApp Message", {"message_id": msg_id}):
		return {"ok": True, "skipped": True}

	# Extract phone number from JID: "919876543210@s.whatsapp.net" -> "+919876543210"
	sender_jid = data.get("sender") or data.get("chat_jid") or ""
	phone_number = sender_jid.split("@")[0] if "@" in sender_jid else sender_jid
	if phone_number:
		phone_number = "+" + phone_number

	# Resolve to Lead/Deal
	ref_name, ref_doctype = get_contact_lead_or_deal_from_number(phone_number)

	content_type = data.get("content_type", "text")
	attach = ""

	# If media was included as base64 in the webhook, save it as a file
	if data.get("media_base64") and data.get("media_filename"):
		file_doc = save_media_file(
			data["media_base64"],
			data["media_filename"],
			ref_doctype,
			ref_name,
		)
		if file_doc:
			attach = file_doc.file_url

	# Create WhatsApp Message document
	msg_doc = frappe.new_doc("WhatsApp Message")
	msg_doc.update(
		{
			"type": "Incoming",
			"from": phone_number,
			"to": "",
			"message": data.get("content", ""),
			"message_id": msg_id,
			"content_type": content_type if content_type != "text" or not attach else "text",
			"message_type": "",
			"status": "received",
			"attach": attach,
			"is_reply": 0,
			"reply_to_message_id": "",
			"reference_doctype": ref_doctype or "",
			"reference_name": ref_name or "",
		}
	)
	msg_doc.insert(ignore_permissions=True)
	frappe.db.commit()

	# Publish rich realtime event so Chats page can append instead of reload
	settings_rt = get_bridge_settings()
	bridge_url_rt = (settings_rt.bridge_url or "").rstrip("/")
	media_path = data.get("media_path") or ""
	attach_url = f"{bridge_url_rt}/media/{media_path}" if media_path else attach

	frappe.publish_realtime(
		"whatsapp_chat_update",
		{
			"event_type": "new_message",
			"chat_jid": data.get("chat_jid", ""),
			"phone": phone_number,
			"message": {
				"name": msg_doc.name,
				"type": "Incoming",
				"from": phone_number,
				"to": "",
				"message": data.get("content", ""),
				"message_id": msg_id,
				"content_type": content_type,
				"message_type": "",
				"status": "received",
				"creation": data.get("timestamp", ""),
				"attach": attach_url,
				"is_reply": False,
				"reply_to_message_id": "",
				"from_name": data.get("sender_name", ""),
			},
			"chat_update": {
				"last_message": (data.get("content", "") or "")[:100],
				"last_message_time": data.get("timestamp", ""),
			},
		},
		after_commit=False,
	)

	return {"ok": True, "name": msg_doc.name}


def save_media_file(base64_data, filename, doctype=None, docname=None):
	"""Save base64-encoded media as a Frappe File."""
	try:
		content = base64.b64decode(base64_data)
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"content": content,
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"is_private": 0,
			}
		)
		file_doc.save(ignore_permissions=True)
		return file_doc
	except Exception:
		frappe.log_error(title="WhatsApp Bridge: Failed to save media file")
		return None


def send_message_via_bridge(phone, message, sender_name=None):
	"""Send a text message through the WhatsApp bridge."""
	settings = get_bridge_settings()
	url = f"{settings.bridge_url.rstrip('/')}/send"
	payload = {"phone": phone, "message": message}
	if sender_name:
		payload["sender_name"] = sender_name
	resp = requests.post(url, json=payload, timeout=30)
	resp.raise_for_status()
	return resp.json()


def send_file_via_bridge(phone, file_url, filename, caption="", sender_name=None):
	"""Send a file through the WhatsApp bridge."""
	settings = get_bridge_settings()
	url = f"{settings.bridge_url.rstrip('/')}/send-file-url"
	site_url = frappe.utils.get_url()
	# Convert relative URLs to absolute
	if file_url.startswith("/"):
		file_url = site_url + file_url
	payload = {
		"phone": phone,
		"file_url": file_url,
		"filename": filename,
		"caption": caption,
	}
	if sender_name:
		payload["sender_name"] = sender_name
	resp = requests.post(url, json=payload, timeout=60)
	resp.raise_for_status()
	return resp.json()


@frappe.whitelist()
def get_bridge_status():
	"""Get connection status from bridge for the settings page."""
	settings = get_bridge_settings()
	if not settings.enabled:
		return {"connected": False, "reason": "disabled"}
	try:
		resp = requests.get(
			f"{settings.bridge_url.rstrip('/')}/status",
			timeout=5,
		)
		return resp.json()
	except Exception as e:
		return {"connected": False, "error": str(e)}


@frappe.whitelist()
def get_qr_code():
	"""Get QR code from bridge for WhatsApp authentication."""
	settings = get_bridge_settings()
	try:
		resp = requests.get(
			f"{settings.bridge_url.rstrip('/')}/qr",
			timeout=5,
		)
		return resp.json()
	except Exception as e:
		return {"error": str(e)}
