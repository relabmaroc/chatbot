"""
Facebook Messenger Integration Module
Handles webhook verification and message processing for Messenger.
Supports: DMs, Ad click-to-DM replies, postbacks, story replies, message requests.
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

    url = f"https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {settings.messenger_access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE"  # Required for message requests
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"📤 Sent Messenger message to {recipient_id}")
        except Exception as e:
            logger.error(f"❌ Error sending Messenger message: {e}")
            if 'response' in locals():
                logger.error(f"Response: {response.text}")

def extract_messenger_messages(payload: Dict[str, Any]) -> list:
    """
    Extract messages from Messenger webhook.
    Handles: DMs, ad click-to-DM, postbacks, story replies,
             message requests (accepted via Meta settings), echo filtering.
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
                    continue

                logger.info(f"📍 Messenger event from {sender_id} — keys: {list(messaging.keys())}")

                # ── 1. Regular message (DM, message request, ad reply) ────────
                if 'message' in messaging:
                    message_obj = messaging['message']
                    mid = message_obj.get('mid', '')

                    # Skip echo (bot's own sent messages) and deleted
                    if message_obj.get('is_echo') or message_obj.get('is_deleted'):
                        logger.info(f"📍 Ignoring echo/deleted {mid}")
                        continue

                    text = message_obj.get('text', '')
                    attachments = message_obj.get('attachments', [])

                    # Story / media reply — no text but has attachment
                    if not text and attachments:
                        for att in attachments:
                            if att.get('type') in ('story_mention', 'story_reply', 'share'):
                                text = "Bonjour ! J'ai vu votre publication Relab 👋"
                                logger.info(f"📖 Story reply from {sender_id}")
                                break
                        if not text:
                            text = "Bonjour ! (message avec pièce jointe)"

                    # Ad click-to-DM referral (message comes with referral, possibly no text)
                    raw_referral = messaging.get('referral') or message_obj.get('referral')
                    referral = raw_referral if isinstance(raw_referral, dict) else {}
                    is_ad = referral.get('source') in ('ADS', 'SHORTLINK', 'CUSTOMER_CHAT_PLUGIN')
                    if is_ad and not text:
                        ad_title = referral.get('headline', 'votre publicité Relab')
                        text = f"Bonjour ! Je vous contacte suite à la pub : {ad_title} 👋"
                        logger.info(f"📢 Messenger ad referral auto-text for {sender_id}")

                    if text:
                        extracted_messages.append({
                            "sender_id": sender_id,
                            "text": text,
                            "message_id": mid,
                            "metadata": {
                                "message_id": mid,
                                "timestamp": messaging.get('timestamp'),
                                "platform": "messenger",
                                "is_ad_reply": is_ad,
                            }
                        })
                        logger.info(f"✅ Messenger message '{text[:60]}' from {sender_id}")
                    else:
                        logger.info(f"📍 No usable text in Messenger event: {message_obj}")

                # ── 2. Postback (button tap on template / Get Started) ─────────
                elif 'postback' in messaging:
                    pb = messaging['postback']
                    text = pb.get('title') or pb.get('payload') or 'Bonjour !'
                    extracted_messages.append({
                        "sender_id": sender_id,
                        "text": text,
                        "message_id": f"pb_{sender_id}_{messaging.get('timestamp')}",
                        "metadata": {
                            "timestamp": messaging.get('timestamp'),
                            "platform": "messenger",
                            "is_postback": True
                        }
                    })
                    logger.info(f"🔘 Messenger postback from {sender_id}: {text}")

                # ── 3. Standalone Ad referral (user clicked ad, no initial text) ─
                elif 'referral' in messaging:
                    referral = messaging['referral']
                    if referral.get('source') in ('ADS', 'SHORTLINK'):
                        ad_title = referral.get('headline', 'votre publicité Relab')
                        text = f"Bonjour ! Je vous contacte suite à la pub : {ad_title} 👋"
                        extracted_messages.append({
                            "sender_id": sender_id,
                            "text": text,
                            "message_id": f"ref_{sender_id}_{messaging.get('timestamp')}",
                            "metadata": {
                                "timestamp": messaging.get('timestamp'),
                                "platform": "messenger",
                                "is_ad_reply": True
                            }
                        })
                        logger.info(f"📢 Standalone Messenger ad referral from {sender_id}")

                # ── 4. Message request accepted (optin) ───────────────────────
                elif 'optin' in messaging:
                    optin = messaging['optin']
                    text = optin.get('ref') or "Bonjour ! Comment puis-je vous aider ?"
                    extracted_messages.append({
                        "sender_id": sender_id,
                        "text": text,
                        "message_id": f"optin_{sender_id}_{messaging.get('timestamp')}",
                        "metadata": {
                            "timestamp": messaging.get('timestamp'),
                            "platform": "messenger",
                            "is_optin": True
                        }
                    })
                    logger.info(f"🔓 Messenger optin from {sender_id}")

                else:
                    logger.info(f"📍 Unhandled Messenger event: {list(messaging.keys())}")

    except Exception as e:
        logger.error(f"❌ Error extracting Messenger messages: {e}", exc_info=True)

    return extracted_messages
