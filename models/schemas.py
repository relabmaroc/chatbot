"""
Pydantic schemas for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, TypedDict
from datetime import datetime
from enum import Enum
import hashlib


# =============================================================================
# CANONICAL STATE CONTRACT - TypedDict for strict variant format
# =============================================================================
class VariantDict(TypedDict, total=False):
    """Strict format for product variants. This is the ONLY allowed format."""
    id: str
    model: str
    price: int
    storage: str
    battery: int
    grade: str
    color: str


class HandoffReason(str, Enum):
    """Enum for handoff reasons - ensures traceability."""
    NONE = "none"
    EXPLICIT_REQUEST = "explicit_request"  # User asked for human
    COMPLEX_SAV = "complex_sav"  # SAV/Repair with low confidence
    RECOVERY_FAILURE = "recovery_failure"  # 3+ consecutive failures
    LOOP_DETECTED = "loop_detected"  # Repetition detected


class IntentType(str, Enum):
    """Possible intent types based on design artifacts"""
    PRODUCT_INFO = "product_info"
    INFO_CREDIT = "info_credit"
    CREDIT_DOCUMENTS = "credit_documents"
    CREDIT_ELIGIBILITY = "credit_eligibility"
    LOCATION_DELIVERY = "location_delivery"
    SALES_ACHAT = "sales_achat"
    COMMANDE = "commande"
    TRADEIN = "tradein"
    REPARATION = "reparation"
    SAV = "sav"
    HUMAIN = "humain"
    ORDER_TRACKING = "order_tracking"
    AUTRE = "autre"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"
    
    # Aliases for backward compatibility or coarse grouping if needed
    @property
    def is_purchase_related(self) -> bool:
        return self in [IntentType.SALES_ACHAT, IntentType.PRODUCT_INFO, IntentType.COMMANDE]
    
    @property
    def is_credit_related(self) -> bool:
        return self in [IntentType.INFO_CREDIT, IntentType.CREDIT_DOCUMENTS, IntentType.CREDIT_ELIGIBILITY]


class Language(str, Enum):
    """Supported languages"""
    FRENCH = "fr"
    DARIJA = "darija"
    ENGLISH = "en"


class ConversationStatus(str, Enum):
    """Conversation status"""
    ACTIVE = "active"
    QUALIFIED = "qualified"
    HANDED_OFF = "handed_off"
    CLOSED = "closed"


class FlowType(str, Enum):
    """Types of active flows"""
    ORDER = "order"
    TRADEIN = "tradein"
    REPARATION = "reparation"
    NONE = "none"


class ChatRequest(BaseModel):
    """Incoming chat message request"""
    message: str = Field(..., description="User message text")
    channel: str = Field(..., description="Channel: whatsapp, instagram, email, web")
    identifier: str = Field(..., alias="user_id", description="User identifier (phone, user_id, email) - accepts both 'identifier' and 'user_id'")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        # Pydantic V2: Allow both field name ('identifier') and alias ('user_id')
        populate_by_name = True


class ContactMemory(BaseModel):
    """Schema for persistent user memory"""
    intent_history: List[str] = []
    product_preferences: List[str] = []
    budget_range: Optional[str] = None
    city: Optional[str] = None
    credit_interest: Optional[bool] = None
    objections: List[str] = []
    lead_stage: str = "new"  # new, interested, qualified, lead, customer
    last_action: Optional[str] = None


class Intent(BaseModel):
    """Detected intent from user message"""
    type: IntentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    language: Language
    monetization_score: int = Field(..., ge=0, le=100)
    keywords: List[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Chatbot response"""
    message: Optional[str] = Field(None, description="Bot response text (None in TEST_MODE for whitelisted users)")
    conversation_id: str = Field(..., description="Conversation ID")
    intent: Optional[Intent] = Field(None, description="Detected intent")
    should_handoff: bool = Field(False, description="Whether to hand off to human")
    handoff_reason: Optional[str] = Field(None, description="Reason for handoff")
    next_action: Optional[str] = Field(None, description="Suggested next action")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QualificationData(BaseModel):
    """Data collected during qualification"""
    # Common fields
    intent_type: IntentType
    budget: Optional[int] = None
    urgency: Optional[str] = None  # "immediate", "this_week", "flexible"
    payment_method: Optional[str] = None  # "cash", "credit"
    professional_situation: Optional[str] = None
    fulfillment_type: Optional[str] = None  # "pickup", "delivery"
    full_name: Optional[str] = None
    delivery_address: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Achat specific
    product_interest: Optional[str] = None
    identified_price: Optional[int] = None
    grade_preference: Optional[str] = None  # "neuf", "excellent", "bon"
    color_preference: Optional[str] = None
    min_battery: Optional[int] = None
    preferred_criterion: Optional[str] = None  # "price", "quality", "capacity", "aesthetic"
    selected_variant: Optional[Dict[str, Any]] = None
    
    # Reprise specific
    device_model: Optional[str] = None
    device_condition: Optional[str] = None
    has_accessories: Optional[bool] = None
    
    # Réparation specific
    issue_description: Optional[str] = None
    
    # Progress tracking
    current_step: Optional[str] = None  # Track current step in flow
    completion_percentage: int = Field(0, ge=0, le=100)
    questions_asked: List[str] = Field(default_factory=list)
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    credit_confirmed: bool = False
    
    # Order Tracking
    order_name: Optional[str] = None
    email_search: Optional[str] = None
    tracking_data: Optional[Dict[str, Any]] = None
    
    # --- NEW: Robustness & Loop Prevention ---
    selection_locked: bool = Field(False, description="Prevents relisting once a variant is confirmed")
    last_question_asked: Optional[str] = Field(None, description="Used to detect repetitions")
    consecutive_failures: int = Field(0, description="Count of repeated questions/failures")
    last_bot_message_hash: Optional[str] = Field(None, description="Hash of last bot message for repetition detection")
    repeat_count: int = Field(0, description="Count of identical responses")
    
    def compute_message_hash(self, message: str) -> str:
        """Compute a stable hash for a bot message."""
        # Normalize: lowercase, strip, remove extra spaces
        normalized = " ".join(message.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()[:16]


class LeadSummary(BaseModel):
    """Structured lead summary for human handoff"""
    conversation_id: str
    user_id: Optional[str]
    intent: IntentType
    language: Language
    qualification_data: QualificationData
    estimated_value: Optional[int] = None  # MAD
    conversation_summary: str
    key_points: List[str]
    recommended_action: str
    created_at: datetime
    channel: str
