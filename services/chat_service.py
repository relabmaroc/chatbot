"""
Chat Service (Pure n8n Proxy Mode)
Orchestrator that delegates all intelligence to n8n workflow.
"""
from typing import Optional, List, Dict, Any
from models.schemas import ChatRequest, ChatResponse, Intent, IntentType, Language, ConversationStatus
from models.database import get_db, Conversation, Message, Contact
from services.n8n_service import n8n_service
from services.notification_service import notification_service
from config import settings
from datetime import datetime
import uuid
import hashlib
import logging

logger = logging.getLogger(__name__)

# In-memory deduplication cache: message_hash -> timestamp
_recent_messages: dict = {}
DEDUP_WINDOW_SECONDS = 30

class ChatService:
    """Chat service acting as a proxy for n8n workflow"""
    
    def __init__(self):
        # We keep this instance simple
        pass
    
    async def process_message(self, request: ChatRequest, db) -> ChatResponse:
        """
        Delegates message processing exclusively to n8n FIRST.
        Saves locally only if successful (User's requirement).
        """
        try:
            logger.info(f"Processing message (n8n first mode): {request.message[:50]}...")

            # --- DEDUPLICATION: skip exact same message from same user within window ---
            dedup_key = hashlib.md5(f"{request.identifier}:{request.message}".encode()).hexdigest()
            now = datetime.utcnow().timestamp()
            # Clean old entries
            expired = [k for k, t in _recent_messages.items() if now - t > DEDUP_WINDOW_SECONDS]
            for k in expired:
                del _recent_messages[k]
            if dedup_key in _recent_messages:
                logger.warning(f"⚡ Duplicate message detected from {request.identifier}, skipping.")
                return ChatResponse(
                    message="",  # Silent: already processing
                    conversation_id=request.conversation_id or "dedup",
                    intent=None, should_handoff=False, metadata={"dedup": True}
                )
            _recent_messages[dedup_key] = now

            # 1. Use existing conversation_id or generate a temporary one for n8n
            n8n_session_id = request.conversation_id or str(uuid.uuid4())
            
            # 2. Delegate to n8n Webhook
            # n8n will process and return the response.
            response = await n8n_service.send_to_n8n(
                message=request.message,
                identifier=request.identifier,
                channel=request.channel,
                metadata=request.metadata,
                conversation_id=n8n_session_id
            )
            
            # 3. IF n8n succeeded, now we persist locally to provide history for the dashboard
            # We ONLY hit the database if n8n response doesn't contain a communication error
            is_n8n_error = response.metadata.get("error") and "communication avec n8n" in str(response.metadata.get("error"))
            
            if not is_n8n_error:
                try:
                    # Get or create conversation (writes to DB)
                    conversation, is_new = self._get_or_create_conversation(
                        db, n8n_session_id, request.identifier, request.channel
                    )
                    
                    # Save User & Assistant Messages
                    self._save_message(db, conversation.id, "user", request.message, None)
                    self._save_message(db, conversation.id, "assistant", response.message, response.intent)
                    
                    # Enrich conversation with n8n response data for dashboard
                    if response.intent and response.intent.type:
                        conversation.intent_type = response.intent.type.value if hasattr(response.intent.type, 'value') else str(response.intent.type)
                        conversation.monetization_score = max(
                            conversation.monetization_score or 0,
                            response.intent.monetization_score or 0
                        )
                    
                    # Track credit interest in extra_data
                    extra = conversation.extra_data or {}
                    if response.intent and hasattr(response.intent, 'type'):
                        intent_val = response.intent.type.value if hasattr(response.intent.type, 'value') else str(response.intent.type)
                        if "credit" in intent_val.lower():
                            extra["credit_interest"] = True
                    conversation.extra_data = extra
                    
                    # Update status
                    if response.should_handoff:
                        conversation.status = ConversationStatus.HANDED_OFF.value
                    
                    conversation.last_message_at = datetime.utcnow()
                    db.commit()

                    # --- AUTO SUMMARY every 8 messages ---
                    msg_count = db.query(Message).filter(
                        Message.conversation_id == conversation.id
                    ).count()
                    if msg_count > 0 and msg_count % 8 == 0:
                        try:
                            all_msgs = db.query(Message).filter(
                                Message.conversation_id == conversation.id
                            ).order_by(Message.created_at.asc()).all()
                            summary_lines = [
                                f"{m.sender.upper()}: {m.content[:120]}"
                                for m in all_msgs[-8:]
                            ]
                            summary = "\n".join(summary_lines)
                            extra = conversation.extra_data or {}
                            extra["conversation_summary"] = summary
                            conversation.extra_data = extra
                            db.commit()
                            logger.info(f"📝 Auto-summary saved for conversation {conversation.id}")
                        except Exception as summary_err:
                            logger.error(f"Summary error: {summary_err}")

                    # --- LEAD NOTIFICATION on handoff ---
                    if response.should_handoff:
                        try:
                            extra = conversation.extra_data or {}
                            await notification_service.notify_lead(
                                conversation_id=conversation.id,
                                identifier=request.identifier,
                                channel=request.channel,
                                last_message=request.message,
                                intent_type=conversation.intent_type or "N/A",
                                monetization_score=conversation.monetization_score or 0,
                                handoff_reason=response.handoff_reason,
                                conversation_summary=extra.get("conversation_summary"),
                            )
                        except Exception as notif_err:
                            logger.error(f"Notification error: {notif_err}")

                    # Ensure the response uses the actual CID from our DB
                    response.conversation_id = conversation.id
                except Exception as db_err:
                    logger.error(f"⚠️ Persistence error (n8n was OK): {db_err}")
            else:
                logger.warning("📍 Skipping DB persistence because n8n workflow failed.")
            
            return response

        except Exception as e:
            logger.error(f"Error in n8n proxy process_message: {e}", exc_info=True)
            return ChatResponse(
                message="Désolé, je rencontre une difficulté technique.",
                conversation_id=request.conversation_id or "error",
                intent=None,
                should_handoff=True,
                metadata={"error": str(e)}
            )

    # -------------------------------------------------------------------------
    # HELPER METHODS (Preserved for history)
    # -------------------------------------------------------------------------
    
    def _get_or_create_conversation(self, db, conversation_id: Optional[str], identifier: str, channel: str):
        contact_key = f"{channel}:{identifier}"
        contact = db.query(Contact).filter(Contact.contact_key == contact_key).first()
        if not contact:
            contact = Contact(contact_key=contact_key)
            db.add(contact)
            db.commit()
            db.refresh(contact)
        
        # Try finding by explicit ID
        if conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv: 
                contact.last_seen_at = datetime.utcnow()
                db.commit()
                return conv, False
        
        # Try finding active conversation for this contact
        latest_conv = db.query(Conversation).filter(
            Conversation.contact_id == contact.id, 
            Conversation.status.in_([ConversationStatus.ACTIVE.value, ConversationStatus.QUALIFIED.value])
        ).order_by(Conversation.created_at.desc()).first()
        
        if latest_conv: 
            return latest_conv, False

        # Create new if none found
        new_id = str(uuid.uuid4())
        conv = Conversation(
            id=new_id, 
            contact_id=contact.id, 
            channel=channel, 
            status=ConversationStatus.ACTIVE.value,
            last_message_at=datetime.utcnow()
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv, True

    def _save_message(self, db, conversation_id: str, sender: str, content: str, intent: Optional[Intent]):
        msg = Message(
            conversation_id=conversation_id, 
            sender=sender, 
            content=content, 
            intent_type=intent.type.value if intent else None, 
            intent_confidence=intent.confidence if intent else None,
            created_at=datetime.utcnow()
        )
        db.add(msg)
        db.commit()

# Global instance
chat_service = ChatService()
