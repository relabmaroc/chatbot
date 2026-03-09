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
    url = "https://graph.facebook.com/v21.0/me/messages"
    
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
    Extract all relevant message data from webhook payload.
    Handles: DMs, ad click-to-DM replies, story replies, postbacks.
    Returns list of dicts with 'sender_id', 'text', 'metadata'
    """
    extracted_messages = []
    try:
        entries = payload.get('entry', [])
        for entry in entries:
            messaging_events = entry.get('messaging', [])
            for messaging in messaging_events:
                sender_id = messaging.get('sender', {}).get('id')
                recipient_id = messaging.get('recipient', {}).get('id')

                if not sender_id or sender_id == recipient_id:
                    continue  # Skip self-messages / no sender

                logger.info(f"📍 Instagram event from {sender_id} — keys: {list(messaging.keys())}")

                # ── 1. Regular DM or Ad click-to-DM ──────────────────────────
                if 'message' in messaging:
                    message_obj = messaging['message']
                    mid = message_obj.get('mid', '')

                    # Skip echoes (bot's own messages)
                    if message_obj.get('is_echo') or message_obj.get('is_deleted'):
                        logger.info(f"📍 Ignoring echo/deleted message {mid}")
                        continue

                    message_text = message_obj.get('text', '')
                    attachments  = message_obj.get('attachments', [])

                    # Story reply: attachment with type 'story_mention' or 'story_reply'
                    if not message_text and attachments:
                        for att in attachments:
                            att_type = att.get('type', '')
                            if att_type in ('story_mention', 'story_reply', 'share'):
                                message_text = "Bonjour ! J'ai vu votre story / publication Relab 👋"
                                logger.info(f"📖 Story reply detected from {sender_id}")
                                break
                        if not message_text:
                            # Other attachment (image, sticker…) — still engage
                            message_text = "Bonjour ! (message avec pièce jointe)"

                    # Ad click-to-DM: referral present but possibly no text yet
                    referral = messaging.get('referral') or message_obj.get('referral', {})
                    is_ad = referral.get('source') in ('ADS', 'SHORTLINK', 'CUSTOMER_CHAT_PLUGIN')

                    if is_ad and not message_text:
                        ad_title = referral.get('headline', 'votre publicité Relab')
                        message_text = f"Bonjour ! Je vous contacte suite à la pub : {ad_title} 👋"
                        logger.info(f"📢 Ad referral (no text) auto-greeted for {sender_id}")

                    if message_text and sender_id:
                        extracted_messages.append({
                            'sender_id': sender_id,
                            'recipient_id': recipient_id,
                            'text': message_text,
                            'message_id': mid,
                            'metadata': {
                                'mid': mid,
                                'platform': 'instagram',
                                'is_ad_reply': is_ad,
                                'timestamp': messaging.get('timestamp')
                            }
                        })
                        logger.info(f"✅ Extracted Instagram message: '{message_text[:40]}...' from {sender_id}")
                    else:
                        logger.info(f"📍 Message has no usable text: {message_obj}")

                # ── 2. Postback (button tap) ──────────────────────────────────
                elif 'postback' in messaging:
                    pb = messaging['postback']
                    message_text = pb.get('title') or pb.get('payload') or 'Bonjour !'
                    logger.info(f"🔘 Postback from {sender_id}: {message_text}")
                    extracted_messages.append({
                        'sender_id': sender_id,
                        'recipient_id': recipient_id,
                        'text': message_text,
                        'message_id': f"pb_{sender_id}_{messaging.get('timestamp')}",
                        'metadata': {
                            'platform': 'instagram',
                            'is_postback': True,
                            'timestamp': messaging.get('timestamp')
                        }
                    })

                # ── 3. Standalone Ad referral (no message body at all) ────────
                elif 'referral' in messaging:
                    referral = messaging['referral']
                    if referral.get('source') in ('ADS', 'SHORTLINK'):
                        ad_title = referral.get('headline', 'votre publicité Relab')
                        message_text = f"Bonjour ! Je vous contacte suite à la pub : {ad_title} 👋"
                        logger.info(f"📢 Standalone ad referral from {sender_id}")
                        extracted_messages.append({
                            'sender_id': sender_id,
                            'recipient_id': recipient_id,
                            'text': message_text,
                            'message_id': f"ref_{sender_id}_{messaging.get('timestamp')}",
                            'metadata': {
                                'platform': 'instagram',
                                'is_ad_reply': True,
                                'timestamp': messaging.get('timestamp')
                            }
                        })
                else:
                    logger.info(f"📍 Unhandled Instagram event type: {list(messaging.keys())}")

    except Exception as e:
        logger.error(f"❌ Error extracting Instagram messages: {e}", exc_info=True)

    return extracted_messages
