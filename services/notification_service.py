"""
Notification Service
Handles notifying the admin when a conversation needs human intervention.
"""
import logging
from typing import Optional, Dict, Any
from config import settings
from integrations.whatsapp import send_whatsapp_message
from integrations.instagram import send_instagram_message

logger = logging.getLogger(__name__)

class NotificationService:
    """Service to notify admin about handoffs and important events"""

    async def notify_handoff(
        self, 
        conversation_id: str, 
        contact_name: str, 
        reason: str, 
        channel: str,
        intent_type: str = "Inconnu",
        summary: str = ""
    ):
        """
        Sends a notification to the admin when a bot hands off to a human.
        """
        admin_number = settings.admin_whatsapp_number
        if not admin_number:
            logger.warning("⚠️ No admin_whatsapp_number configured. Skipping notification.")
            return

        # Prepare message
        msg = (
            f"🚨 *ALERTE REPRISE MAIN (Handoff)* 🚨\n\n"
            f"👤 *Client* : {contact_name}\n"
            f"📍 *Canal* : {channel.capitalize()}\n"
            f"🎯 *Intention* : {intent_type}\n"
            f"📝 *Raison* : {reason}\n"
            f"🆔 *ID Convo* : {conversation_id}\n\n"
            f"--- Résumé ---\n"
            f"{summary[:150]}...\n\n"
            f"🔗 *Dashboard* : https://chatbot-production-9a92.up.railway.app/dashboard.html"
        )

        try:
            # We notify via WhatsApp primarily as requested
            logger.info(f"📤 Sending handoff notification to admin {admin_number}")
            await send_whatsapp_message(admin_number, msg)
            
            # Option: could also send to other channels if needed
        except Exception as e:
            logger.error(f"❌ Failed to notify admin: {e}")

# Global instance
notification_service = NotificationService()
