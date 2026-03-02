"""
Business Router
Routes intents to appropriate flows and manages context switches.
"""
from typing import Optional, Tuple
from models.schemas import IntentType, QualificationData
from logic.flow_manager import flow_manager, BaseFlow, FlowStep

class Router:
    """Core routing logic"""
    
    def route(self, intent: IntentType, current_flow: Optional[str] = None) -> Tuple[IntentType, bool]:
        """
        Determines the effective intent and whether to switch flows.
        Returns: (Effective Intent, Should Switch Flow)
        """
        
        # 1. Critical Intents Check (Always interrupt)
        critical_intents = [IntentType.HUMAIN, IntentType.SAV]
        if intent in critical_intents:
            return intent, True
            
        # 2. Context Check: If we are in the middle of a flow, decide if we STICK or SWITCH
        if current_flow:
            # CONFIRMATION intent never triggers a switch, simply indicates agreement
            if intent == IntentType.CONFIRMATION:
                return IntentType(current_flow), False

            # UNKNOWN intent usually means the user is answering a question
            if intent == IntentType.UNKNOWN:
                return IntentType(current_flow), False

            # Allow switching from INFO to COMMANDE
            if current_flow == IntentType.PRODUCT_INFO.value and intent in [IntentType.COMMANDE, IntentType.SALES_ACHAT]:
                return IntentType.COMMANDE, True

            # For other cases, we generally stick to the flow if it's active
            # UNLESS the user explicitly expresses a new top-level intent (TradeIn, Reparation)
            if intent in [IntentType.TRADEIN, IntentType.REPARATION]:
                 return intent, True

            return IntentType(current_flow), False 
            
        # 3. Default Routing (No active flow)
        if intent == IntentType.CONFIRMATION:
             return IntentType.UNKNOWN, False
             
        # Normalize SALES_ACHAT to COMMANDE
        if intent == IntentType.SALES_ACHAT:
            return IntentType.COMMANDE, True

        return intent, True

    def should_skip_intent_detection(self, current_flow: Optional[str], current_step: Optional[str]) -> bool:
        """
        Heuristic: detection skip.
        If we are in an active flow awaiting specific input (like name, address),
        we generally assume the answer is for that field, UNLESS it looks like a command.
        """
        if current_flow and current_step and current_step != FlowStep.COMPLETE.value:
            # We are in an active flow. 
            # Ideally we skip LLM intent detection to save latency/cost 
            # and avoid "over-thinking" simple answers like "Oui" or "Casa"
            return True
            
        return False

# Global instance
router = Router()
