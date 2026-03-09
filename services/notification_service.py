"""
Notification Service
Sends real-time lead alerts to the Relab admin team when a handoff is triggered.
"""
import logging
import httpx
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service to notify admin about leads and handoffs."""

    async def notify_lead(
        self,
        conversation_id: str,
        identifier: str,
        channel: str,
        last_message: str,
        intent_type: str = "N/A",
        monetization_score: int = 0,
        handoff_reason: str = None,
        conversation_summary: str = None,
    ):
        """
        Sends a WhatsApp alert to admin when a lead triggers handoff.
        Does NOT block the main chat flow.
        """
        try:
            admin_number = settings.admin_whatsapp_number
            if not admin_number:
                logger.warning("⚠️ No admin WhatsApp number configured - skipping lead notification")
                return

            score_bar = "🟢" if monetization_score >= 70 else ("🟡" if monetization_score >= 40 else "🔴")
            channel_icon = {"instagram": "📸", "whatsapp": "💬", "web": "🌐", "email": "📧"}.get(channel, "📲")

            msg = (
                f"🚨 *NOUVEAU LEAD RELAB* 🚨\n\n"
                f"{channel_icon} *Canal:* {channel.capitalize()}\n"
                f"👤 *Contact:* {identifier}\n"
                f"🎯 *Intent:* {intent_type}\n"
                f"{score_bar} *Score:* {monetization_score}/100\n"
                f"⚡ *Raison:* {handoff_reason or 'Handoff déclenché'}\n\n"
                f"💬 *Dernier message:*\n_{last_message[:200]}_\n\n"
            )
            if conversation_summary:
                msg += f"📝 *Résumé:*\n{conversation_summary[:300]}\n\n"

            msg += (
                f"🔗 https://chatbot-production-9a92.up.railway.app/dashboard.html\n"
                f"🕐 {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC"
            )

            await self._send_whatsapp(admin_number, msg)
            logger.info(f"✅ Lead notification sent to admin for {conversation_id}")

        except Exception as e:
            logger.error(f"❌ Failed to send lead notification: {e}")

    # Backward compatibility alias
    async def notify_handoff(self, conversation_id, contact_name, reason, channel,
                              intent_type="Inconnu", summary=""):
        await self.notify_lead(
            conversation_id=conversation_id,
            identifier=contact_name,
            channel=channel,
            last_message=summary,
            intent_type=intent_type,
            handoff_reason=reason,
            conversation_summary=summary
        )

    async def _send_whatsapp(self, to_number: str, message: str):
        """Send WhatsApp message via Meta Cloud API, fallback to log."""
        if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
            logger.info(f"[LEAD NOTIFICATION - Log fallback]\n{message}")
            return

        url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number.replace("+", ""),
            "type": "text",
            "text": {"body": message}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=15.0)
            if resp.status_code not in (200, 201):
                logger.error(f"WhatsApp API error {resp.status_code}: {resp.text}")
            else:
                logger.info(f"📨 Lead alert sent to admin {to_number}")


# Global instance
notification_service = NotificationService()
