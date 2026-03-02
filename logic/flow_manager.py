"""
Flow Manager & State Machine
Explicitly manages conversation state and transitions.
Refactored for strict separation of PRODUCT_INFO and COMMANDE.
"""
from enum import Enum
from typing import Optional, Dict, List, Any
from models.schemas import QualificationData, IntentType, Language
from logic.business_rules import business_rules
import re

class ConversationState(str, Enum):
    """Explicit Conversation States"""
    DISCOVERY = "discovery"      # User explains needs or asks for generic list
    SELECTION = "selection"      # User narrowed down but needs to pick specific variant
    CONFIRMATION = "confirmation" # Choice made, validating or verifying
    LOGISTICS = "logistics"      # Gathering contact/delivery info
    HANDOFF = "handoff"          # Ready for human

class FlowAction(str, Enum):
    """What the bot should do next"""
    SHOW_PRODUCT_LIST = "show_product_list"
    ASK_QUESTION = "ask_question" 
    CONFIRM_AND_ASK = "confirm_and_ask"
    HANDOFF = "handoff"
    COMPLETE = "complete"
    PRESENT_INFO = "present_info" # New: Present information without asking a question

class FlowStep(str, Enum):
    """Mapping to steps for QualificationData"""
    INIT = "init"
    ASK_PRODUCT = "ask_product"
    ASK_SPECIFIC_MODEL = "ask_specific_model" # New: pick from list
    ASK_BUDGET = "ask_budget" 
    ASK_PAYMENT = "ask_payment"
    ASK_FULFILLMENT = "ask_fulfillment"
    ASK_NAME = "ask_name"
    ASK_PHONE = "ask_phone"
    ASK_ADDRESS = "ask_address"
    CONFIRM_ORDER = "confirm_order"
    ASK_DEVICE_MODEL = "ask_device_model"
    ASK_DEVICE_CONDITION = "ask_device_condition"
    ASK_ACCESSORIES = "ask_accessories"
    ASK_ISSUE = "ask_issue"
    ASK_URGENCY = "ask_urgency" 
    ASK_LOGISTICS = "ask_logistics" # New step for general logistics
    ASK_ORDER_ID = "ask_order_id" # New step for order tracking
    VERIFY_AUTH = "verify_auth" # New step for order tracking authentication
    PRESENT_STATUS = "present_status" # New step for presenting order status
    ASK_REPRISE_DETAILS = "ask_reprise_details" # New step for trade-in details
    COMPLETE = "complete"

def is_generic_product_interest(text: str) -> bool:
    """
    Checks if the product interest is generic (family) or specific.
    Specific contains: Pro, Max, Plus, Storage (Go/GB/TB), or Color.
    """
    if not text:
        return True
    
    text_lower = text.lower()
    
    # Specificity signals
    specific_tokens = [r"\bpro\b", r"\bmax\b", r"\bplus\b", r"\bmini\b", r"\bultra\b", r"\bse\b"]
    storage_pattern = r"\b\d+\s*(go|gb|g|tb|to|to)\b"
    
    # Known colors from business logic (simplified)
    colors = ['noir', 'blanc', 'bleu', 'rouge', 'vert', 'or', 'argent', 'gris', 'violet', 'rose', 'gold', 'silver', 'black', 'white', 'midnight', 'starlight']
    
    if any(re.search(token, text_lower) for token in specific_tokens):
        return False
    if re.search(storage_pattern, text_lower):
        return False
    if any(color in text_lower for color in colors):
        return False
        
    return True

class BaseFlow:
    """Base class for all flows"""
    def __init__(self, intent: IntentType):
        self.intent = intent
        
    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        """Determine current state based on message and data"""
        raise NotImplementedError
    
    def get_next_action(self, message: str, data: QualificationData, language: Language) -> Dict[str, Any]:
        """Determine the next action"""
        state = self.determine_state(message, data)
        
        if state == ConversationState.HANDOFF:
             return {
                "state": state,
                "action": FlowAction.HANDOFF,
                "step": FlowStep.COMPLETE,
                "question": None
            }
            
        return self._get_action_for_state(state, data, language)

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        raise NotImplementedError

    def get_question(self, step: FlowStep, language: Language) -> str:
        key_map = {
            FlowStep.ASK_PRODUCT: 'product_interest',
            FlowStep.ASK_SPECIFIC_MODEL: 'product_interest', # Use same rule
            FlowStep.ASK_BUDGET: 'budget',
            FlowStep.ASK_PAYMENT: 'payment_method',
            FlowStep.ASK_FULFILLMENT: 'fulfillment_type',
            FlowStep.ASK_NAME: 'full_name',
            FlowStep.ASK_PHONE: 'phone_number',
            FlowStep.ASK_ADDRESS: 'delivery_address',
            FlowStep.ASK_DEVICE_MODEL: 'device_model',
            FlowStep.ASK_DEVICE_CONDITION: 'device_condition',
            FlowStep.ASK_ACCESSORIES: 'has_accessories',
            FlowStep.ASK_ISSUE: 'issue_description',
            FlowStep.ASK_URGENCY: 'urgency'
        }
        
        field_key = key_map.get(step)
        if field_key:
            return business_rules.get_question(self.intent, field_key, language.value)
        return ""

class ProductInfoFlow(BaseFlow):
    """Flow for Information Requests"""
    def __init__(self):
        super().__init__(IntentType.PRODUCT_INFO)

    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        if not data.product_interest:
            return ConversationState.DISCOVERY
        
        # If user asks for list/stock specifically, stay in discovery/selection to show list
        msg_lower = message.lower()
        list_keywords = ["disponible", "stock", "quels", "modèles", "quoi comme", "liste", "available"]
        if any(k in msg_lower for k in list_keywords):
             return ConversationState.SELECTION

        if is_generic_product_interest(data.product_interest):
            return ConversationState.SELECTION
            
        return ConversationState.CONFIRMATION # Found specific info, ready to suggest order

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        if state == ConversationState.DISCOVERY:
            return {
                "state": state,
                "action": FlowAction.SHOW_PRODUCT_LIST,
                "step": FlowStep.ASK_PRODUCT,
                "question": self.get_question(FlowStep.ASK_PRODUCT, language)
            }
        
        if state == ConversationState.SELECTION:
            # We have a generic interest, need to narrow down
            return {
                "state": state,
                "action": FlowAction.SHOW_PRODUCT_LIST,
                "step": FlowStep.ASK_SPECIFIC_MODEL,
                "question": "Lequel de ces modèles préférez-vous précisément ?" if language == Language.FRENCH else "Achmen wa7ed bghiti bdebt?"
            }
            
        return {
            "state": state,
            "action": FlowAction.COMPLETE, # Just provide info
            "step": FlowStep.COMPLETE,
            "question": None
        }

class CommandeFlow(BaseFlow):
    """Flow for Orders (Lead Collection)"""
    def __init__(self):
        super().__init__(IntentType.COMMANDE) 
        
    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        # Mandatory: we need a SPECIFIC product before logistics
        if not data.product_interest:
            return ConversationState.DISCOVERY
            
        if is_generic_product_interest(data.product_interest):
            return ConversationState.SELECTION
        
        # Mandatory: conscious confirmation of variant + price
        if not data.identified_price or not (data.extra_data or {}).get("confirmed_variant"):
            return ConversationState.CONFIRMATION

        # NEW: Handle Credit Flow if selected
        if data.payment_method == "credit" and not data.credit_confirmed:
             # Before logistics, we need professional situation and doc confirmation
             if not data.professional_situation:
                  return ConversationState.CONFIRMATION # Re-using state but will have credit-specific step
             return ConversationState.CONFIRMATION

        # Check logistics progression
        if not data.full_name or not data.phone_number or not data.fulfillment_type:
            return ConversationState.LOGISTICS
            
        return ConversationState.HANDOFF

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        if state == ConversationState.DISCOVERY:
            return {
                "state": state,
                "action": FlowAction.SHOW_PRODUCT_LIST,
                "step": FlowStep.ASK_PRODUCT,
                "question": self.get_question(FlowStep.ASK_PRODUCT, language)
            }
            
        if state == ConversationState.SELECTION:
            return {
                "state": state,
                "action": FlowAction.SHOW_PRODUCT_LIST,
                "step": FlowStep.ASK_SPECIFIC_MODEL,
                "question": "Lequel de ces modèles préférez-vous pour votre commande ?" if language == Language.FRENCH else "Achmen wa7ed bghiti tcommander?"
            }

        if state == ConversationState.CONFIRMATION:
            # The goal is to reformulate the choice and ask for price confirmation OR Credit info
            if data.payment_method == "credit" and not data.credit_confirmed:
                if not data.professional_situation:
                     return {
                        "state": state,
                        "action": FlowAction.ASK_QUESTION,
                        "step": FlowStep.ASK_SPECIFIC_MODEL, # Hack to keep flow moving or define new step
                        "question": business_rules.get_question(IntentType.SALES_ACHAT, 'professional_situation', language.value)
                    }
                else:
                    return {
                        "state": state,
                        "action": FlowAction.CONFIRM_AND_ASK,
                        "step": FlowStep.CONFIRM_ORDER,
                        "question": "Je vais vous lister les documents nécessaires. On valide ?" # ChatService handles details
                    }

            return {
                "state": state,
                "action": FlowAction.CONFIRM_AND_ASK,
                "step": FlowStep.CONFIRM_ORDER,
                "question": "Voulez-vous confirmer cette variante ?" # The ChatService will reformulate the details
            }
            
        if state == ConversationState.LOGISTICS:
            step = None
            if not data.full_name:
                step = FlowStep.ASK_NAME
            elif not data.phone_number:
                step = FlowStep.ASK_PHONE
            elif not data.fulfillment_type:
                step = FlowStep.ASK_FULFILLMENT
            elif data.fulfillment_type == 'delivery' and not data.delivery_address:
                step = FlowStep.ASK_ADDRESS
            
            if step:
                return {
                    "state": state,
                    "action": FlowAction.CONFIRM_AND_ASK, 
                    "step": step,
                    "question": self.get_question(step, language)
                }
        
        return {
            "state": ConversationState.HANDOFF,
            "action": FlowAction.HANDOFF,
            "step": FlowStep.COMPLETE,
            "question": None
        }

class TradeInFlow(BaseFlow):
    """Flow for Trade-In"""
    def __init__(self):
        super().__init__(IntentType.TRADEIN)
        
    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        if not data.device_model:
            return ConversationState.DISCOVERY
        if not data.device_condition or data.has_accessories is None:
            return ConversationState.SELECTION
        
        return ConversationState.HANDOFF

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        step = None
        if not data.device_model:
            step = FlowStep.ASK_DEVICE_MODEL
        elif not data.device_condition:
            step = FlowStep.ASK_DEVICE_CONDITION
        elif data.has_accessories is None:
            step = FlowStep.ASK_ACCESSORIES
            
        if step:
             return {
                "state": state,
                "action": FlowAction.CONFIRM_AND_ASK,
                "step": step,
                "question": self.get_question(step, language)
            }
            
        return {"state": state, "action": FlowAction.HANDOFF, "step": FlowStep.COMPLETE, "question": None}

class ReparationFlow(BaseFlow):
    """Flow for Reparation"""
    def __init__(self):
        super().__init__(IntentType.REPARATION)
        
    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        if not data.device_model:
            return ConversationState.DISCOVERY
        if not data.issue_description:
            return ConversationState.SELECTION
        return ConversationState.HANDOFF

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        step = None
        if not data.device_model:
            step = FlowStep.ASK_DEVICE_MODEL
        elif not data.issue_description:
            step = FlowStep.ASK_ISSUE
            
        if step:
             return {
                "state": state,
                "action": FlowAction.CONFIRM_AND_ASK,
                "step": step,
                "question": self.get_question(step, language)
            }
            
        return {"state": state, "action": FlowAction.HANDOFF, "step": FlowStep.COMPLETE, "question": None}

class OrderTrackingFlow(BaseFlow):
    """Handles Shopify order tracking requests"""
    
    def __init__(self):
        super().__init__(IntentType.ORDER_TRACKING)

    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        if not data.order_name:
            return ConversationState.DISCOVERY
            
        # If we have order_name but no email/phone auth
        if not data.email_search and not data.phone_number:
            return ConversationState.DISCOVERY # Re-using discovery to trigger ASK_ORDER_ID or AUTH
            
        # We have both, let's process
        return ConversationState.HANDOFF # Tracking ends in presentation or handoff

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        if not data.order_name:
            return {
                "state": state,
                "action": FlowAction.ASK_QUESTION,
                "step": FlowStep.ASK_ORDER_ID,
                "question": business_rules.get_question(IntentType.ORDER_TRACKING, "order_name", language.value)
            }
            
        if not data.email_search and not data.phone_number:
            return {
                "state": state,
                "action": FlowAction.ASK_QUESTION,
                "step": FlowStep.VERIFY_AUTH,
                "question": business_rules.get_question(IntentType.ORDER_TRACKING, "email_search", language.value)
            }
            
        return {
            "state": state,
            "action": FlowAction.PRESENT_INFO,
            "step": FlowStep.PRESENT_STATUS,
            "question": "" # Managed by ChatService
        }


class CreditInfoFlow(BaseFlow):
    """Flow for Credit Information/Documents"""
    def __init__(self, intent: IntentType):
        super().__init__(intent)

    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        if not data.professional_situation:
            return ConversationState.DISCOVERY
        return ConversationState.SELECTION # Transition to showing docs

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        if state == ConversationState.DISCOVERY:
            return {
                "state": state,
                "action": FlowAction.ASK_QUESTION,
                "step": FlowStep.ASK_PAYMENT, 
                "question": business_rules.get_question(IntentType.INFO_CREDIT, 'professional_situation', language.value)
            }
        
        return {
            "state": state,
            "action": FlowAction.PRESENT_INFO,
            "step": FlowStep.COMPLETE,
            "question": "" 
        }


class GenericInfoFlow(BaseFlow):
    """Simple informational flow (Location, etc.)"""
    def __init__(self, intent: IntentType):
        super().__init__(intent)

    def determine_state(self, message: str, data: QualificationData) -> ConversationState:
        return ConversationState.CONFIRMATION 

    def _get_action_for_state(self, state: ConversationState, data: QualificationData, language: Language) -> Dict[str, Any]:
        return {
            "state": state,
            "action": FlowAction.PRESENT_INFO,
            "step": FlowStep.COMPLETE,
            "question": ""
        }


class FlowManager:
    """Manages active flows and state transitions"""
    
    def __init__(self):
        self.flows = {
            IntentType.SALES_ACHAT: CommandeFlow(),
            IntentType.COMMANDE: CommandeFlow(),
            IntentType.PRODUCT_INFO: ProductInfoFlow(),
            IntentType.TRADEIN: TradeInFlow(),
            IntentType.REPARATION: ReparationFlow(),
            IntentType.ORDER_TRACKING: OrderTrackingFlow(),
            IntentType.INFO_CREDIT: CreditInfoFlow(IntentType.INFO_CREDIT),
            IntentType.CREDIT_DOCUMENTS: CreditInfoFlow(IntentType.CREDIT_DOCUMENTS),
            IntentType.CREDIT_ELIGIBILITY: CreditInfoFlow(IntentType.CREDIT_ELIGIBILITY),
            IntentType.LOCATION_DELIVERY: GenericInfoFlow(IntentType.LOCATION_DELIVERY),
        }
    
    def get_flow(self, intent: IntentType) -> Optional[BaseFlow]:
        return self.flows.get(intent)
        
    def get_next_action(self, intent: IntentType, message: str, data: QualificationData, language: Language) -> Dict[str, Any]:
        """
        Determines the next action in the flow.
        """
        flow = self.get_flow(intent)
        if not flow:
            return {
                "state": ConversationState.DISCOVERY, 
                "action": FlowAction.SHOW_PRODUCT_LIST, 
                "step": FlowStep.ASK_PRODUCT, 
                "question": business_rules.get_question(IntentType.SALES_ACHAT, 'product_interest', language.value),
                "is_complete": False
            }
            
        result = flow.get_next_action(message, data, language)
        result["is_complete"] = (result.get("action") == FlowAction.HANDOFF or result.get("action") == FlowAction.COMPLETE)
        
        return result

# Global instance
flow_manager = FlowManager()
