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

def extract_instagram_messages(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Extract all relevant message data from webhook payload (handles multiple messages)
    Returns list of dicts with 'sender_id', 'text', 'metadata'
    """
    extracted_messages = []
    try:
        # Debug log for the full raw payload (truncated for safety)
        # item_str = str(payload)[:500]
        # logger.info(f"DEBUG RAW WEBHOOK: {item_str}")
        
        entries = payload.get('entry', [])
        for entry in entries:
            messaging_events = entry.get('messaging', [])
            for messaging in messaging_events:
                sender_id = messaging.get('sender', {}).get('id')
                recipient_id = messaging.get('recipient', {}).get('id')
                
                logger.info(f"📍 Event received - From: {sender_id} To: {recipient_id}")
                
                if 'message' in messaging:
                    message_obj = messaging['message']
                    mid = message_obj.get('mid')
                    
                    # Ignore echoes (messages sent by the bot)
                    if message_obj.get('is_echo') or sender_id == recipient_id:
                        logger.info(f"📍 Ignoring echo message {mid}")
                        continue
                        
                    # Ignore deleted
                    if message_obj.get('is_deleted'):
                        logger.info(f"📍 Ignoring deleted message {mid}")
                        continue
                        
                    message_text = message_obj.get('text', '')
                    
                    if message_text and sender_id:
                        logger.info(f"✅ Extracted Instagram text: '{message_text[:20]}...' from {sender_id}")
                        extracted_messages.append({
                            'sender_id': sender_id,
                            'recipient_id': recipient_id,
                            'text': message_text,
                            'metadata': {
                                'mid': mid,
                                'platform': 'instagram',
                                'timestamp': messaging.get('timestamp')
                            }
                        })
                    else:
                        logger.info(f"📍 Event has no text or sender: {messaging}")
                else:
                    logger.info(f"📍 Event is not a 'message': {list(messaging.keys())}")
            
    except Exception as e:
        logger.error(f"❌ Error extracting Instagram messages: {e}", exc_info=True)
        
    return extracted_messages
