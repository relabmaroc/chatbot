"""
Intent Detection Engine
Combines keyword-based detection with LLM classification
"""
from typing import Tuple, List, Optional
from models.schemas import Intent, IntentType, Language
from langdetect import detect, LangDetectException
import re
import logging

logger = logging.getLogger(__name__)


import os

class IntentDetector:
    """Detects user intent from messages"""
    
    # Keyword patterns for each intent (French + Darija)
    INTENT_KEYWORDS = {
        IntentType.SALES_ACHAT: [
            # French
            r'\b(acheter|achat|commander|je veux|je cherche|je voudrais|intéressé)\b',
            # Darija
            r'\b(chri|chrit|chira|bghit|bghina)\b',
        ],
        IntentType.PRODUCT_INFO: [
            # French
            r'\b(prix|disponible|stock|combien|coûte|coute|fiche|technique|caractéristique)\b',
            # Darija
            r'\b(b?ch?7al|chhal|kayn|kayenin)\b',
        ],
        IntentType.TRADEIN: [
            # French
            r'\b(reprise|reprendre|vendre|échanger|trade)\b',
            r'\b(?:ancien|vieux|mon)\s+(?:téléphone|iphone|appareil)\b',
            # Darija
            r'\b(nbi3|nbadel|nbadlo)\b',
            r'\b(?:telephone|tilifoun)\s+(?:9dim|qdim)\b',
        ],
        IntentType.REPARATION: [
            # French
            r'\b(réparation|réparer|casser|cassé|écran|batterie|panne)\b',
            r'\b(fixer|fix|problème)\b',
            # Darija
            r'\b(s?l?a7|sla7|tser|mkser|mksour)\b',
            r'\b(l3akal|mochkil)\b',
        ],
        IntentType.SAV: [
            # French
            r'\b(garantie|sav|retour|remboursement)\b',
            r'\b(réclamation|plainte|problème.*achat|commande.*problème)\b',
            # Darija
            r'\b(garantie|mouchkil f l-commande)\b',
        ],
        IntentType.HUMAIN: [
            # French
            r'\b(parler|conseiller|vendeur|humain|personne|quelqu\'un|agent|responsable|directeur)\b',
            r'\b(appeler|téléphoner|contact|numéro.*téléphone)\b',
            # Darija
            r'\b(?:n?hdert?|nkellem|chi wa7ed|chi mas2oul)\b',
            r'\b(?:bghit|bghina)\s+(?:n?hdert?|nkellem|chi 7ed)\b',
        ],
        IntentType.LOCATION_DELIVERY: [
            # French
            r'\b(horaire|adresse|localisation|où|quand|comment|magasin|boutique|showroom|livraison|livrer)\b',
            # Darija
            r'\b(fin|fein|waqtach|kifach|l?ma7al|7anut|livraison)\b',
        ],
        IntentType.CREDIT_DOCUMENTS: [
            r'\b(document|papier|wra9|wraq|justificatif|dossier|justif)\b',
        ],
        IntentType.INFO_CREDIT: [
            # Credit/Financing (Both FR/Darija)
            r'\b(crédit|credit|financement|facilité|traite|kridi)\b',
        ],
        IntentType.COMMANDE: [
            r'\b(je prends|commande|acheter|paiement)\b',
        ],
        IntentType.CONFIRMATION: [
            r'\b(ok|d\'accord|oui|yes|confirme|valide|c\'est bon|parfait|super|yep|ouais)\b',
        ],
        IntentType.ORDER_TRACKING: [
            r'\b(suivi|commande|tracking|status|livraison|expédié|où est)\b',
            r'\b(fin wsla|dakchi|suivre)\b',
        ],
    }
    
    # Darija-specific patterns
    DARIJA_PATTERNS = [
        r'\b(bghit|bghina|3afak|lla|wach|chno|chnou|kifach|3lach)\b',
        r'\b(kayn|kayenin|machi|mazal|daba|ghir)\b',
        r'\b(chhal|b?ch?7al|fein|fin|waqtach)\b',
    ]

    def __init__(self):
        self.prompts_dir = os.path.join(os.getcwd(), "chatbot", "intent")
        self.classification_prompt = self._load_intent_prompt()

    def _load_intent_prompt(self) -> Optional[str]:
        """Load intent detector prompt from design artifacts"""
        path = os.path.join(self.prompts_dir, "intent_detector.prompt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Error loading intent prompt: {e}")
        return None
    
    def should_skip_detection(self, current_flow: Optional[str], current_step: Optional[str]) -> bool:
        """
        Check if we should skip intent detection because of active flow.
        """
        # If we have a clear active flow and step (and not just started/completed)
        if current_flow and current_step and current_step not in ["init", "complete"]:
            return True
        return False
    
    def detect_language(self, text: str) -> Language:
        """Detect message language"""
        # Check for Darija patterns first
        text_lower = text.lower()
        for pattern in self.DARIJA_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return Language.DARIJA
        
        # Use langdetect for French/English
        try:
            lang_code = detect(text)
            if lang_code == 'fr':
                return Language.FRENCH
            elif lang_code == 'en':
                return Language.ENGLISH
            else:
                return Language.FRENCH  # Default to French
        except LangDetectException:
            return Language.FRENCH
    
    def keyword_based_detection(self, text: str) -> Tuple[IntentType, float, List[str]]:
        """Fast keyword-based intent detection"""
        text_lower = text.lower()
        scores = {}
        matched_keywords = {}
        
        for intent, patterns in self.INTENT_KEYWORDS.items():
            score = 0
            keywords = []
            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    score += len(matches)
                    keywords.extend(matches)
            scores[intent] = score
            matched_keywords[intent] = keywords
        
        # Get best match
        if max(scores.values()) > 0:
            best_intent = max(scores, key=scores.get)
            confidence = min(scores[best_intent] * 0.3, 0.95)  # Cap at 0.95
            return best_intent, confidence, matched_keywords[best_intent]
        
        return IntentType.UNKNOWN, 0.0, []
    
    def calculate_monetization_score(self, intent: IntentType, text: str) -> int:
        """Calculate monetization potential (0-100)"""
        base_scores = {
            IntentType.PRODUCT_INFO: 60,
            IntentType.INFO_CREDIT: 40,
            IntentType.CREDIT_DOCUMENTS: 50,
            IntentType.CREDIT_ELIGIBILITY: 50,
            IntentType.LOCATION_DELIVERY: 30,
            IntentType.SALES_ACHAT: 90,
            IntentType.COMMANDE: 100,
            IntentType.TRADEIN: 70,
            IntentType.REPARATION: 60,
            IntentType.SAV: 30,
            IntentType.HUMAIN: 50,
            IntentType.ORDER_TRACKING: 40,
            IntentType.UNKNOWN: 10,
        }
        
        score = base_scores.get(intent, 10)
        
        # Boost for urgency indicators
        urgency_patterns = [
            r'\b(urgent|maintenant|aujourd\'hui|daba|daba daba)\b',
            r'\b(besoin|bghit|lazem)\b',
        ]
        for pattern in urgency_patterns:
            if re.search(pattern, text.lower(), re.IGNORECASE):
                score = min(score + 10, 100)
        
        # Boost for budget mentions
        if re.search(r'\d{3,}', text):  # Numbers with 3+ digits
            score = min(score + 5, 100)
        
        return score
    
    async def detect(self, text: str, conversation_history: List[str] = None) -> Intent:
        """
        Main intent detection method
        Uses keyword-based detection first, falls back to LLM if needed
        """
        # Detect language
        language = self.detect_language(text)
        
        text_lower = text.lower()
        
        # Keyword-based detection
        intent_type, confidence, keywords = self.keyword_based_detection(text)
        
        # 0. Greeting Check: "Bonjour", "Salam", etc. should not be over-interpreted
        greetings = [r'\b(bonjour|salut|salam|coucou|hi|hello|bonsoir|hey)\b']
        is_greeting = any(re.search(p, text_lower, re.IGNORECASE) for p in greetings)
        
        # If it's a short greeting (<= 2 words), force UNKNOWN to prevent aggressive handoffs
        if is_greeting and len(text_lower.split()) <= 2:
            return Intent(type=IntentType.UNKNOWN, confidence=1.0, language=language, monetization_score=0)

        # Ambiguity check: "batterie" is often shadowed by IntentType.REPARATION 
        # but could be a product question during ACHAT related intents
        is_ambiguous = "batterie" in keywords or "battery" in keywords
        
        # If confidence is low or ambiguous, use LLM
        if (confidence < 0.6 or is_ambiguous) and conversation_history:
            from llm.client import llm_client
            
            logger.info(f"Using LLM for intent detection (Confidence: {confidence:.2f}, Ambiguous: {is_ambiguous})")
            llm_result = await llm_client.classify_intent(
                text, 
                conversation_history, 
                system_prompt=self.classification_prompt
            )
            
            if llm_result and llm_result.get("confidence", 0) > confidence:
                try:
                    intent_type = IntentType(llm_result["intent"])
                    confidence = llm_result["confidence"]
                    logger.info(f"LLM overrode intent: {intent_type} ({confidence:.2f})")
                except ValueError:
                    logger.warning(f"Invalid intent from LLM: {llm_result['intent']}")
        
        # Calculate monetization score
        monetization_score = self.calculate_monetization_score(intent_type, text)
        
        return Intent(
            type=intent_type,
            confidence=confidence,
            language=language,
            monetization_score=monetization_score,
            keywords=keywords
        )


# Global instance
intent_detector = IntentDetector()
