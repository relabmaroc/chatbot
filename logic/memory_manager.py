
from typing import Dict, Any, List, Optional
import logging
from models.schemas import ContactMemory, QualificationData, IntentType

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages long-term user memory and LLM injection"""
    
    def format_memory_for_llm(self, memory_json: Dict[str, Any]) -> str:
        """
        Format long-term memory for injection into system prompt.
        This tells the LLM what we already know to avoid repetitive questions.
        """
        if not memory_json:
            return ""
        
        try:
            memory = ContactMemory(**memory_json)
        except Exception as e:
            logger.error(f"Error parsing memory_json: {e}")
            return ""
            
        parts = ["\n[MÉMOIRE LONG TERME UTILISATEUR]"]
        
        if memory.product_preferences:
            parts.append(f"- Produits consultés: {', '.join(memory.product_preferences)}")
            
        if memory.budget_range:
            parts.append(f"- Budget connu: {memory.budget_range}")
            
        if memory.city:
            parts.append(f"- Ville: {memory.city}")
            
        if memory.credit_interest is not None:
            interest = "Intéressé par le crédit" if memory.credit_interest else "Préfère payer comptant"
            parts.append(f"- Option paiement: {interest}")
            
        if memory.objections:
            parts.append(f"- Préoccupations notées: {', '.join(memory.objections)}")
            
        if memory.lead_stage:
            parts.append(f"- Étape du tunnel: {memory.lead_stage}")
            
        parts.append("IMPORTANT: Ne redemande JAMAIS une information listée ci-dessus.")
        
        return "\n".join(parts) if len(parts) > 1 else ""

    def update_memory(self, current_memory: Dict[str, Any], intent_type: IntentType, 
                      qualification_data: QualificationData, message: str) -> Dict[str, Any]:
        """
        Analyze current interaction to update long-term user profile.
        """
        try:
            memory = ContactMemory(**current_memory)
        except Exception:
            memory = ContactMemory()
            
        # 1. Update Intent History
        if intent_type.value not in memory.intent_history:
            memory.intent_history.append(intent_type.value)
            
        # 2. Update Product Preferences
        if qualification_data.product_interest:
            p = qualification_data.product_interest.strip()
            if p not in memory.product_preferences:
                memory.product_preferences.append(p)
                
        # 3. Update Budget
        if qualification_data.budget:
            memory.budget_range = f"{qualification_data.budget} MAD"
            
        # 4. Detect City (Simple heuristic, can be improved)
        cities = ['casablanca', 'rabat', 'marrakech', 'tanger', 'agadir', 'fes', 'meknes', 'oujda', 'el jadida']
        msg_lower = message.lower()
        for city in cities:
            if city in msg_lower:
                memory.city = city.capitalize()
                
        # 5. Detect Credit Interest
        credit_keywords = ['crédit', 'credit', 'facilité', 'mensualité', 'plusieurs fois']
        if any(kw in msg_lower for kw in credit_keywords):
            memory.credit_interest = True
            
        # 6. Update Lead Stage
        if qualification_data.completion_percentage >= 100:
            memory.lead_stage = "qualified"
        elif qualification_data.completion_percentage > 50:
            memory.lead_stage = "interested"
        elif memory.product_preferences:
            memory.lead_stage = "prospect"
            
        # 7. Last Action
        memory.last_action = f"Last intent: {intent_type.value}"
        
        return memory.dict()
