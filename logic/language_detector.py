"""
Heuristic Language Detector
Strictly regex-based detection, no LLM usage.
"""
import re
from typing import Optional
from models.schemas import Language

class LanguageDetector:
    """Detects language using strong regex signals"""
    
    DARIJA_PATTERNS = [
        r'\b(bghit|bghina|3afak|lla|wach|chno|chnou|kifach|3lach|ach)\b',
        r'\b(kayn|kayenin|machi|mazal|daba|ghir|chi|chi haja)\b',
        r'\b(chhal|b?ch?7al|fein|fin|waqtach|imta)\b',
        r'\b(s?l?a7|sla7|tser|mkser|mksour)\b',
        r'\b(nbi3|nbadel|nbadlo|kridi|wra9|wraq)\b',
        r'\b(mezyan|bez?zaf|mzyan|wakha|safi)\b'
    ]
    
    def detect(self, text: str, current_language: Optional[Language] = None) -> Language:
        """
        Detect language from text.
        If current_language is provided, we only switch if there is a STRONG signal.
        """
        if not text:
            return current_language or Language.FRENCH
            
        text_lower = text.lower()
        
        # 1. Darija Check (Strong Signals)
        for pattern in self.DARIJA_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return Language.DARIJA
        
        # 2. Heuristic for English
        english_words = r'\b(what|how|where|when|price|much|can|you|thanks|please)\b'
        if re.search(english_words, text_lower, re.IGNORECASE):
            return Language.ENGLISH
            
        # 3. If we already have a language and the input is short/neutral, STICK to it.
        # Short/Neutral inputs often don't contain language-specific keywords.
        neutral_pattern = r'^(ok|oui|non|merci|d\'accord|yes|no|thanks|choukran|safi|wakha|mehdi|youssef|mohamed|amine|\d+|[a-z]{1,4})$'
        if current_language and (len(text) < 5 or re.match(neutral_pattern, text_lower)):
            return current_language

        # 4. Default to French (or current if set)
        return current_language or Language.FRENCH

# Global instance
language_detector = LanguageDetector()
