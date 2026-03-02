"""
Email Integration Module
Handles inbound webhooks (SendGrid/Postmark) and SMTP replies
"""
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)

async def send_email_message(recipient_email: str, text: str, subject: str = "Relab - Service Client"):
    """
    Send a reply email via SMTP
    """
    if not settings.smtp_user or not settings.smtp_password:
        logger.error("❌ SMTP configuration incomplete")
        return

    msg = MIMEText(text)
    msg['Subject'] = subject
    msg['From'] = settings.smtp_user
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
            logger.info(f"📤 Sent Email to {recipient_email}")
    except Exception as e:
        logger.error(f"❌ Error sending email: {e}")

def extract_email_message_sendgrid(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract email data from SendGrid Inbound Parse JSON
    Note: SendGrid usually sends multipart/form-data, but some adapters JSON-ify it.
    """
    try:
        from_email = payload.get('from')
        text = payload.get('text')
        subject = payload.get('subject', 'Sans titre')
        
        if from_email and text:
            return {
                "sender_id": from_email,
                "text": text,
                "metadata": {
                    "subject": subject,
                    "to": payload.get('to')
                }
            }
    except Exception as e:
        logger.debug(f"Could not extract Email data: {e}")
        
    return None

def extract_email_message_generic(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generic extraction for custom webhooks
    """
    sender = payload.get('sender') or payload.get('from')
    content = payload.get('content') or payload.get('text') or payload.get('body')
    
    if sender and content:
        return {
            "sender_id": sender,
            "text": content,
            "metadata": {"subject": payload.get('subject')}
        }
    return None
