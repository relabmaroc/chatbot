"""
OpenAI LLM Client with strict controls
LLM is used ONLY for text generation, NEVER for decisions
"""
from openai import AsyncOpenAI
from config import settings
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """Controlled LLM client wrapper"""
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("⚠️ OPENAI_API_KEY non configurée. Les fonctionnalités LLM internes seront désactivées.")
        
        self.model = settings.openai_model
        self.max_tokens = 300  # Keep responses concise
        self.temperature = 0.7  # Balanced creativity
    
    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text response using LLM
        This is ONLY for formatting, not decision-making
        """
        try:
            if not self.client:
                logger.error("LLM Client not initialized (missing API key)")
                return ""
                
            # Guard clause: Empty prompts
            if not system_prompt or not user_message:
                logger.warning("Empty system_prompt or user_message provided to LLM")
                return ""

            messages = [{"role": "system", "content": system_prompt}]
            
            # Add context if provided
            if context:
                messages.extend(context)
            
            messages.append({"role": "user", "content": user_message})
            
            # Use instance default if not overridden
            temp = temperature if temperature is not None else self.temperature

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temp,
                timeout=15.0  # Explicit timeout
            )
            
            if not response or not response.choices or not response.choices[0].message:
                logger.error("Invalid or empty response structure from OpenAI")
                return ""
                
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            # Return empty string on error - caller should use fallback
            return ""
    
    async def classify_intent(
        self,
        message: str,
        conversation_history: List[str],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to classify intent when keyword detection is uncertain
        Returns: {intent: str, confidence: float}
        """
        if not self.client:
            logger.error("LLM Client not initialized (missing API key)")
            return {"intent": "unknown", "confidence": 0.0}

        if not system_prompt:
            system_prompt = """Tu es un classificateur d'intentions pour Relab, entreprise marocaine de vente/reprise/réparation de produits high-tech.

Classe l'intention du client parmi:
- achat: veut acheter un produit
- reprise: veut vendre/échanger son appareil
- reparation: veut faire réparer
- info: demande d'information générale
- sav: problème après-vente
- humain: veut parler à quelqu'un

Réponds UNIQUEMENT avec le format JSON:
{"intent": "achat", "confidence": 0.85}"""
        
        context_str = "\n".join(conversation_history[-3:]) if conversation_history else ""
        user_prompt = f"Historique:\n{context_str}\n\nMessage actuel: {message}"
        
        try:
            response = await self.generate_response(
                system_prompt=system_prompt,
                user_message=user_prompt,
                max_tokens=100,  # Increased slightly for safety
                temperature=0.0  # FORCE DETERMINISTIC OUTPUT
            )
            
            if not response:
                return {"intent": "unknown", "confidence": 0.0}

            # Robust JSON extraction
            result = self._extract_json(response)
            
            if result:
                return result
            
            logger.warning(f"Could not parse JSON from LLM response: {response}")
            return {"intent": "unknown", "confidence": 0.0}
        
        except Exception as e:
            logger.error(f"Intent classification error: {e}", exc_info=True)
            return {"intent": "unknown", "confidence": 0.0}

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON object from text, handling markdown blocks and extra text"""
        import json
        import re
        
        # 1. Clean markdown code blocks if present
        cleaned = re.sub(r'```json\s*(.*?)\s*```', r'\1', text, flags=re.DOTALL)
        cleaned = re.sub(r'```\s*(.*?)\s*```', r'\1', cleaned, flags=re.DOTALL)
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 2. Try to find the first { and last }
            try:
                match = re.search(r'(\{.*\})', cleaned, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    # Handle minor issues like trailing commas before closing braces
                    json_str = re.sub(r',\s*\}', '}', json_str)
                    json_str = re.sub(r',\s*\]', ']', json_str)
                    return json.loads(json_str)
            except Exception as e:
                logger.debug(f"Regex JSON extraction failed: {e}")
                
        return None


# Global instance
llm_client = LLMClient()
