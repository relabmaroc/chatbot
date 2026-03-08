"""
Facebook Messenger Integration Module
Handles webhook verification and message processing for Messenger
"""
import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import PlainTextResponse
from config import settings

logger = logging.getLogger(__name__)

async def verify_messenger_webhook(request: Request):
    """
    Verify the webhook verification request from Meta (Messenger)
    """
    params = dict(request.query_params)
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    mode = params.get("hub.mode")

    if mode and verify_token:
        if mode == "subscribe" and verify_token == settings.messenger_verify_token:
            logger.info("✅ Messenger webhook verified successfully")
            return PlainTextResponse(content=challenge)
        else:
            logger.warning("❌ Messenger webhook verification failed: Invalid token")
            raise HTTPException(status_code=403, detail="Verification failed")
    
    raise HTTPException(status_code=400, detail="Missing parameters")

async def send_messenger_message(recipient_id: str, text: str):
    """
    Send a message to a Messenger user via Graph API
    """
    if not settings.messenger_access_token:
        logger.error("❌ Messenger access token not configured")
        return

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={settings.messenger_access_token}"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"📤 Sent Messenger message to {recipient_id}")
        except Exception as e:
            logger.error(f"❌ Error sending Messenger message: {e}")
            if 'response' in locals():
                logger.error(f"Response: {response.text}")

def extract_messenger_messages(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Extract all relevant messages from Messenger webhook payload
    Returns list of dicts with 'sender_id', 'text', 'metadata'
    """
    extracted_messages = []
    try:
        entries = payload.get('entry', [])
        for entry in entries:
            messaging_events = entry.get('messaging', [])
            for messaging in messaging_events:
                sender_id = messaging.get('sender', {}).get('id')
                message = messaging.get('message', {})
                text = message.get('text')
                
                if sender_id and text:
                    extracted_messages.append({
                        "sender_id": sender_id,
                        "text": text,
                        "metadata": {
                            "message_id": message.get('mid'),
                            "timestamp": messaging.get('timestamp'),
                            "platform": "messenger"
                        }
                    })
                            
    except Exception as e:
        logger.error(f"❌ Error extracting Messenger messages: {e}")
        
    return extracted_messages
