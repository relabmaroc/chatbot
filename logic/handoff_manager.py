"""
Handoff Manager
Determines when to hand off conversation to human
"""
from typing import Tuple, Optional, List
from models.schemas import IntentType, QualificationData, LeadSummary, Language, HandoffReason
from logic.business_rules import business_rules
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class HandoffManager:
    """Manages human handoff decisions"""
    
    def __init__(self):
        self.rules = business_rules
    
    def should_handoff(
        self,
        intent: IntentType,
        message: str,
        qualification_data: QualificationData,
        message_count: int,
        conversation_history: List[str] = None,
        flow_action: str = None  # NEW: Pass the FlowAction if available
    ) -> Tuple[bool, HandoffReason]:
        """
        Determine if conversation should be handed off to human.
        Returns: (should_handoff, HandoffReason)
        
        STRICT RULES:
        - COMPLETE action NEVER triggers handoff
        - UNKNOWN intent NEVER triggers handoff
        - Only explicit user requests, SAV, complex repairs, or recovery failures trigger handoff
        """
        message_lower = message.lower()
        
        # =================================================================
        # GATE 0: COMPLETE action NEVER hands off
        # =================================================================
        if flow_action == "COMPLETE":
            logger.info(f"🚫 Handoff blocked: COMPLETE action does not trigger handoff")
            return False, HandoffReason.NONE
        
        # =================================================================
        # GATE 1: UNKNOWN intent NEVER hands off
        # =================================================================
        if intent == IntentType.UNKNOWN:
            logger.info(f"🚫 Handoff blocked: UNKNOWN intent does not trigger handoff")
            return False, HandoffReason.NONE
        
        # =================================================================
        # GATE 2: Payment/credit questions - ANSWER FIRST, NO HANDOFF
        # =================================================================
        payment_query_patterns = [r'combien.*mois', r'mensualité', r'payer.*mois', r'bach?7al.*chhar']
        if any(re.search(p, message_lower, re.IGNORECASE) for p in payment_query_patterns):
            logger.info(f"🚫 Handoff blocked: Payment query should be answered first")
            return False, HandoffReason.NONE

        # =================================================================
        # RULE 1: Explicit human request keywords
        # =================================================================
        human_keywords = [
            r'\b(humain|agent|conseiller|vendeur|quelqu\'un|personne|parler \u00e0 qqn)\b',
            r'\b(bnadm|wa7ed|chi wa7ed|3awenni)\b'  # Darija
        ]
        if intent == IntentType.HUMAIN or any(re.search(p, message_lower) for p in human_keywords):
            # Don't handoff on simple greetings
            greetings = [r'^(bonjour|salam|salut|hello|hi)$']
            if any(re.search(p, message_lower.strip()) for p in greetings):
                logger.info(f"🚫 Handoff blocked: Simple greeting, not explicit request")
                return False, HandoffReason.NONE
            logger.info(f"✅ Handoff triggered: EXPLICIT_REQUEST")
            return True, HandoffReason.EXPLICIT_REQUEST
        
        # =================================================================
        # RULE 2: SAV (after-sales) - always handoff (CRITICAL)
        # =================================================================
        if intent == IntentType.SAV:
            logger.info(f"✅ Handoff triggered: COMPLEX_SAV")
            return True, HandoffReason.COMPLEX_SAV
        
        # =================================================================
        # RULE 3: Complex repair (water damage, motherboard, etc.)
        # =================================================================
        if intent == IntentType.REPARATION:
            if qualification_data.issue_description:
                complex_keywords = ['eau', 'water', 'carte mère', 'motherboard', 'multiple', 'oxydation']
                if any(kw in message_lower for kw in complex_keywords):
                    logger.info(f"✅ Handoff triggered: COMPLEX_SAV (complex repair)")
                    return True, HandoffReason.COMPLEX_SAV
        
        # =================================================================
        # RULE 4: Recovery failure (3+ consecutive failures)
        # =================================================================
        if qualification_data.repeat_count >= 3:
            logger.info(f"✅ Handoff triggered: RECOVERY_FAILURE (repeat_count={qualification_data.repeat_count})")
            return True, HandoffReason.RECOVERY_FAILURE

        # =================================================================
        # DEFAULT: No handoff
        # =================================================================
        return False, HandoffReason.NONE

    
    def generate_lead_summary(
        self,
        conversation_id: str,
        user_id: Optional[str],
        intent: IntentType,
        language: Language,
        qualification_data: QualificationData,
        conversation_history: List[str],
        handoff_reason: str,
        channel: str = "web"
    ) -> LeadSummary:
        """Generate structured lead summary for human"""
        
        # Generate conversation summary
        summary = self._generate_conversation_summary(
            intent,
            qualification_data,
            conversation_history
        )
        
        # Extract key points
        key_points = self._extract_key_points(intent, qualification_data)
        
        # Generate recommended action
        recommended_action = self._generate_recommended_action(
            intent,
            qualification_data,
            handoff_reason
        )
        
        # Estimate value
        estimated_value = self._estimate_value(intent, qualification_data)
        
        return LeadSummary(
            conversation_id=conversation_id,
            user_id=user_id,
            intent=intent,
            language=language,
            qualification_data=qualification_data,
            estimated_value=estimated_value,
            conversation_summary=summary,
            key_points=key_points,
            recommended_action=recommended_action,
            created_at=datetime.utcnow(),
            channel=channel
        )
    
    def _generate_conversation_summary(
        self,
        intent: IntentType,
        qualification_data: QualificationData,
        conversation_history: List[str]
    ) -> str:
        """Generate human-readable conversation summary"""
        
        intent_labels = {
            IntentType.PRODUCT_INFO: "Info Produit",
            IntentType.INFO_CREDIT: "Info Crédit",
            IntentType.CREDIT_DOCUMENTS: "Documents Crédit",
            IntentType.CREDIT_ELIGIBILITY: "Éligibilité Crédit",
            IntentType.LOCATION_DELIVERY: "Logistique/Magasin",
            IntentType.SALES_ACHAT: "Vente/Achat",
            IntentType.COMMANDE: "Commande",
            IntentType.TRADEIN: "Reprise",
            IntentType.REPARATION: "Réparation",
            IntentType.SAV: "SAV",
            IntentType.HUMAIN: "Demande humain"
        }
        
        summary = f"Intent: {intent_labels.get(intent, 'Inconnu')}\n"
        
        if intent.is_purchase_related:
            if qualification_data.product_interest:
                summary += f"Produit: {qualification_data.product_interest}\n"
            if qualification_data.budget:
                summary += f"Budget: {qualification_data.budget} MAD\n"
            if qualification_data.urgency:
                summary += f"Urgence: {qualification_data.urgency}\n"
            if qualification_data.grade_preference:
                summary += f"Préférence: {qualification_data.grade_preference}\n"
        
        elif intent == IntentType.TRADEIN:
            if qualification_data.device_model:
                summary += f"Appareil: {qualification_data.device_model}\n"
            if qualification_data.device_condition:
                summary += f"État: {qualification_data.device_condition}\n"
            if qualification_data.has_accessories is not None:
                acc = "Oui" if qualification_data.has_accessories else "Non"
                summary += f"Accessoires: {acc}\n"
        
        elif intent == IntentType.REPARATION:
            if qualification_data.device_model:
                summary += f"Appareil: {qualification_data.device_model}\n"
            if qualification_data.issue_description:
                summary += f"Problème: {qualification_data.issue_description}\n"
        
        return summary.strip()
    
    def _extract_key_points(
        self,
        intent: IntentType,
        qualification_data: QualificationData
    ) -> List[str]:
        """Extract key points for quick review"""
        points = []
        
        if qualification_data.urgency == "immediate":
            points.append("🔴 URGENT - Client veut acheter maintenant")
        
        if qualification_data.budget and qualification_data.budget >= 10000:
            points.append(f"💰 Budget élevé: {qualification_data.budget} MAD")
        
        if intent.is_purchase_related and qualification_data.product_interest:
            points.append(f"📱 Intéressé par: {qualification_data.product_interest}")
        
        if intent == IntentType.TRADEIN:
            points.append("💵 Opportunité de reprise")
        
        if qualification_data.completion_percentage >= 100:
            points.append("✅ Lead qualifié - Prêt pour conversion")
        
        return points
    
    def _generate_recommended_action(
        self,
        intent: IntentType,
        qualification_data: QualificationData,
        handoff_reason: str
    ) -> str:
        """Generate recommended action for sales team"""
        
        if handoff_reason == "payment_financing":
            return "Contacter immédiatement pour discuter des options de paiement"
        
        if handoff_reason == "high_value":
            return "Lead à forte valeur - Priorité haute, proposer accompagnement personnalisé"
        
        if intent.is_purchase_related:
            if qualification_data.urgency == "immediate":
                return "Appeler dans l'heure - Client prêt à acheter"
            else:
                return "Envoyer proposition avec disponibilité et prix"
        
        if intent == IntentType.TRADEIN:
            return "Évaluer l'appareil et proposer un prix de reprise"
        
        if intent == IntentType.REPARATION:
            return "Établir un diagnostic et envoyer un devis"
        
        return "Contacter le client pour finaliser"
    
    def _estimate_value(
        self,
        intent: IntentType,
        qualification_data: QualificationData
    ) -> Optional[int]:
        """Estimate potential transaction value in MAD"""
        
        if intent.is_purchase_related:
            if qualification_data.budget:
                return qualification_data.budget
            # Default estimates based on product
            if qualification_data.product_interest:
                if "15" in qualification_data.product_interest:
                    return 8000
                elif "14" in qualification_data.product_interest:
                    return 6000
                elif "13" in qualification_data.product_interest:
                    return 4000
        
        elif intent == IntentType.TRADEIN:
            # Estimate reprise value (conservative)
            return 2000
        
        elif intent == IntentType.REPARATION:
            # Estimate repair value
            if qualification_data.issue_description:
                if "écran" in qualification_data.issue_description.lower():
                    return 800
                elif "batterie" in qualification_data.issue_description.lower():
                    return 500
            return 600
        
        return None


# Global instance
handoff_manager = HandoffManager()
