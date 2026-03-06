"""
Instagram Integration Module
Handles webhook verification and message processing for Instagram Direct
"""
import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import PlainTextResponse
from config import settings

logger = logging.getLogger(__name__)

async def verify_instagram_webhook(request: Request):
    """
    Verify the webhook verification request from Meta
    """
    params = dict(request.query_params)
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    mode = params.get("hub.mode")

    if mode and verify_token:
        if mode == "subscribe" and verify_token == settings.instagram_verify_token:
            logger.info("✅ Instagram webhook verified successfully")
            return PlainTextResponse(content=challenge)
        else:
            logger.warning("❌ Instagram webhook verification failed: Invalid token")
            raise HTTPException(status_code=403, detail="Verification failed")
    
    raise HTTPException(status_code=400, detail="Missing parameters")

async def send_instagram_message(recipient_id: str, text: str):
    """
    Send a message to an Instagram user via Graph API
    """
    if not settings.instagram_access_token:
        logger.error("❌ Instagram access token not configured")
        return

    # Use the standard Graph API endpoint for messages
    url = "https://graph.facebook.com/v18.0/me/messages"
    
    headers = {
        "Authorization": f"Bearer {settings.instagram_access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"❌ Error sending Instagram message: {response.status_code} {response.text}")
            else:
                logger.info(f"📤 Sent Instagram message to {recipient_id}")
            response.raise_for_status()
        except Exception as e:
            logger.error(f"❌ Exception in send_instagram_message: {e}")

def extract_instagram_message(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract relevant message data from webhook payload
    Returns dict with 'sender_id', 'text', 'metadata' or None
    """
    try:
        entry = payload.get('entry', [])[0]
        messaging = entry.get('messaging', [])[0]
        
        sender_id = messaging.get('sender', {}).get('id')
        message = messaging.get('message', {})
        text = message.get('text')
        
        if sender_id and text:
            return {
                "sender_id": sender_id,
                "text": text,
                "metadata": {
                    "message_id": message.get('mid'),
                    "timestamp": messaging.get('timestamp')
                }
            }
            
    except (IndexError, AttributeError) as e:
        logger.debug(f"Could not extract message from payload: {e}")
        
    return None
