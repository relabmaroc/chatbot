"""
WhatsApp Integration Module
Handles webhook verification and message processing for WhatsApp Cloud API
"""
import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import PlainTextResponse
from config import settings

logger = logging.getLogger(__name__)

async def verify_whatsapp_webhook(request: Request):
    """
    Verify the webhook verification request from Meta (WhatsApp)
    """
    params = dict(request.query_params)
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    mode = params.get("hub.mode")

    if mode and verify_token:
        if mode == "subscribe" and verify_token == settings.whatsapp_verify_token:
            logger.info("✅ WhatsApp webhook verified successfully")
            return PlainTextResponse(content=challenge)
        else:
            logger.warning("❌ WhatsApp webhook verification failed: Invalid token")
            raise HTTPException(status_code=403, detail="Verification failed")
    
    raise HTTPException(status_code=400, detail="Missing parameters")

async def send_whatsapp_message(recipient_id: str, text: str):
    """
    Send a message to a WhatsApp user via Cloud API
    """
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        logger.error("❌ WhatsApp configuration incomplete")
        return

    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text}
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"📤 Sent WhatsApp message to {recipient_id}")
        except Exception as e:
            logger.error(f"❌ Error sending WhatsApp message: {e}")
            if 'response' in locals():
                logger.error(f"Response: {response.text}")

def extract_whatsapp_message(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract relevant message data from WhatsApp webhook payload
    """
    try:
        value = payload.get('entry', [])[0].get('changes', [])[0].get('value', {})
        
        # VERY IMPORTANT: Ignore status messages (sent, delivered, read) to prevent echo loops
        if 'statuses' in value:
            logger.info(f"📍 Ignoring WhatsApp status update: {value['statuses'][0].get('status')}")
            return None
            
        messages = value.get('messages', [])
        
        if not messages:
            return None
            
        message = messages[0]
        sender_id = message.get('from') # Phone number
        
        # Handle text messages
        if message.get('type') == 'text':
            text = message.get('text', {}).get('body')
            
            logger.info(f"📍 WhatsApp IDs - Sender: {sender_id}, Recipient Phone: {value.get('metadata', {}).get('display_phone_number')}")
            
            if sender_id and text:
                return {
                    "sender_id": sender_id,
                    "text": text,
                    "metadata": {
                        "message_id": message.get('id'),
                        "timestamp": message.get('timestamp'),
                        "display_phone_number": value.get('metadata', {}).get('display_phone_number')
                    }
                }
            
    except (IndexError, AttributeError) as e:
        logger.debug(f"Could not extract WhatsApp message: {e}")
        
    return None
