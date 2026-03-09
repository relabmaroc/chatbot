"""
Chat Service (Pure n8n Proxy Mode)
Orchestrator that delegates all intelligence to n8n workflow.
"""
from typing import Optional, List, Dict, Any
from models.schemas import ChatRequest, ChatResponse, Intent, IntentType, Language
from models.database import get_db, Conversation, Message, Contact, ConversationStatus
from services.n8n_service import n8n_service
from config import settings
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

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

            # 1. Use existing conversation_id or generate a temporary one for n8n
            # We don't save to DB yet.
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
                    
                    # Update status
                    if response.should_handoff:
                        conversation.status = ConversationStatus.HANDED_OFF.value
                    
                    conversation.last_message_at = datetime.utcnow()
                    db.commit()
                    
                    # Ensure the response uses the actual CID from our DB for consistency
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
