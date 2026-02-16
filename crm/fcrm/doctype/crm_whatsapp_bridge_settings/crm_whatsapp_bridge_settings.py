import frappe
import requests
from frappe import _
from frappe.model.document import Document


class CRMWhatsAppBridgeSettings(Document):
	def validate(self):
		if self.enabled:
			self.check_bridge_connection()

	def check_bridge_connection(self):
		try:
			resp = requests.get(
				f"{self.bridge_url.rstrip('/')}/status",
				timeout=5,
			)
			resp.raise_for_status()
		except Exception:
			frappe.throw(
				_(
					"Cannot reach WhatsApp Bridge at {0}. "
					"Please verify the URL and that the bridge server is running."
				).format(self.bridge_url)
			)
