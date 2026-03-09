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
        Delegates message processing exclusively to n8n.
        """
        try:
            logger.info(f"Processing message (n8n mode): {request.message[:50]}...")

            # 1. Get or Create Conversation (for local history/dashboard)
            conversation, is_new = self._get_or_create_conversation(
                db, request.conversation_id, request.identifier, request.channel
            )
            
            # 2. Save User Message
            self._save_message(db, conversation.id, "user", request.message, None)
            
            # 3. Whitelist check (optional, but kept for safety)
            if settings.test_mode_enabled:
                allowed_users = [u.strip() for u in settings.allowed_test_users.split(",") if u.strip()]
                if request.identifier not in allowed_users:
                    logger.warning(f"User {request.identifier} not in whitelist. Ignoring.")
                    return ChatResponse(message=None, conversation_id="ignored", should_handoff=False)

            # 4. Delegate to n8n
            response = await n8n_service.send_to_n8n(
                message=request.message,
                identifier=request.identifier,
                channel=request.channel,
                metadata=request.metadata,
                conversation_id=conversation.id
            )
            
            # 5. Save Assistant Message
            self._save_message(db, conversation.id, "assistant", response.message, response.intent)
            
            # 6. Update conversation metadata if possible
            if response.should_handoff:
                conversation.status = ConversationStatus.HANDED_OFF.value
            
            conversation.last_message_at = datetime.utcnow()
            db.commit()
            
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
