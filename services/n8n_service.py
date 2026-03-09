"""
n8n Service
Handles communication with external n8n workflows.
"""
import httpx
import logging
from typing import Optional, Dict, Any
from config import settings
from models.schemas import ChatResponse, Intent, IntentType, Language

logger = logging.getLogger(__name__)

class N8NService:
    """Service to delegate chat logic to n8n"""
    
    async def send_to_n8n(
        self, 
        message: str, 
        identifier: str, 
        channel: str, 
        metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Sends a message to n8n and returns the response.
        """
        if not settings.n8n_webhook_url:
            logger.error("n8n_webhook_url is not configured")
            return self._fallback_error(conversation_id, "Configuration n8n manquante.")

        payload = {
            "message": message,
            "query": message,      # Standard for many n8n nodes
            "chatInput": message,  # Standard key for n8n AI templates
            "identifier": identifier,
            "channel": channel,
            "conversation_id": conversation_id,
            "sessionId": conversation_id,  # Standard key for n8n AI templates
            "metadata": metadata or {}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Sending message to n8n: {settings.n8n_webhook_url}")
                response = await client.post(
                    settings.n8n_webhook_url, 
                    json=payload,
                    timeout=120.0
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Received JSON response from n8n: {data}")
                
                # Extract response message - supporting multiple possible formats
                # format 1: {"response": "..."}
                # format 2: {"message": "..."}
                res_message = data.get("response") or data.get("message") or data.get("output") or "Pas de réponse de n8n."
                
                return ChatResponse(
                    message=res_message,
                    conversation_id=conversation_id or "n8n-session",
                    intent=Intent(
                        type=IntentType.UNKNOWN, 
                        confidence=1.0, 
                        language=Language.FRENCH, 
                        monetization_score=0
                    ),
                    should_handoff=data.get("should_handoff", False),
                    metadata=data.get("metadata", {})
                )
                
        except Exception as e:
            logger.error(f"Error communicating with n8n: {e}", exc_info=True)
            return self._fallback_error(conversation_id, f"Erreur de communication avec n8n: {str(e)}")

    def _fallback_error(self, conversation_id: Optional[str], error_msg: str) -> ChatResponse:
        return ChatResponse(
            message="Je rencontre une difficulté à joindre mon service externe. Un instant...",
            conversation_id=conversation_id or "error",
            intent=None,
            should_handoff=True,
            metadata={"error": error_msg}
        )

# Global instance
n8n_service = N8NService()
