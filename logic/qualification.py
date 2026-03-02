"""
Qualification Engine
Manages the qualification process for each intent type
"""
from typing import Dict, Any, Optional, List
from models.schemas import IntentType, QualificationData, Language, VariantDict
from logic.business_rules import business_rules
import re
import unicodedata

# Regular expressions for data extraction
EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_REGEX = r'(?:(?:\+|00)212|0)[5-7]\d{8}'
PRICE_REGEX = r'(\d+[\d\s]*)(?:dh|mad|dhs)'
ORDER_REGEX = r'#\d{4,6}'
CREDIT_FORM_URL = "https://drive.google.com/file/d/1ZKUFU3R5sDVkRdbh0SRF0Q7C1BygFfIa/view"


# =============================================================================
# NORMALIZATION UTILITIES
# =============================================================================
def normalize_user_input(text: str) -> str:
    """
    Normalize user input for robust matching:
    - Remove accents
    - Lowercase
    - Normalize spaces
    - Handle Moroccan currency variations
    """
    # Remove accents
    normalized = unicodedata.normalize('NFD', text)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    # Lowercase and normalize spaces
    normalized = ' '.join(normalized.lower().split())
    
    # Normalize currency: "dhs" "dh" "mad" "dirham" -> "dh"
    normalized = re.sub(r'\b(dhs|mad|dirhams?|dhm)\b', 'dh', normalized)
    
    return normalized


class QualificationEngine:
    """Manages lead qualification process"""
    
    def __init__(self):
        self.rules = business_rules
    
    def get_next_question(
        self,
        intent: IntentType,
        current_data: QualificationData,
        language: Language
    ) -> Optional[str]:
        """
        Determine the next qualification question to ask
        Returns None if qualification is complete
        """
        if not intent.is_purchase_related and intent not in [IntentType.TRADEIN, IntentType.REPARATION]:
            return None
        
        # Get required and optional fields
        config = self.rules.QUALIFICATION_FIELDS.get(intent, {})
        required_fields = config.get('required', [])
        optional_fields = config.get('optional', [])
        
        # Check which required fields are missing
        for field in required_fields:
            # Skip budget if user has already specified a product of interest
            if field == 'budget' and current_data.product_interest:
                continue
                
            if getattr(current_data, field, None) is None:
                return self.rules.get_question(intent, field, language.value)
        
        # If all required fields are filled, ask one optional question
        for field in optional_fields:
            if getattr(current_data, field, None) is None:
                # Only ask if we haven't asked too many questions
                if len(current_data.questions_asked) < 4:
                    return self.rules.get_question(intent, field, language.value)
        
        return None  # Qualification complete
    
    def extract_data_from_message(
        self,
        message: str,
        intent: IntentType,
        current_data: QualificationData
    ) -> QualificationData:
        """
        Extract qualification data from user message
        Uses pattern matching and heuristics
        """
        message_lower = message.lower()
        
        # Extract product interest (for Purchase-related intents)
        if intent.is_purchase_related:
            # Overwrite logic: Allow updating product interest if a clear match is found
            # Comprehensive product patterns
            product_patterns = [
                r'(iphone\s*\d+\s*(?:pro|plus|max|mini|s|c|se)?(?:\s*(?:pro|max|plus))?)',
                r'(samsung\s*(?:galaxy)?\s*[a-z0-9\s]+)',
                r'(macbook\s*(?:air|pro)?(?:\s*m\d)?(?:\s*pro|max)?)',
                r'(ipad\s*(?:pro|air|mini)?(?:\s*\d+)?)',
                r'(imac\s*(?:m\d)?)',
                r'(apple\s*watch\s*(?:series|ultra)?\s*\d*)',
                r'(airpods\s*(?:pro|max|\d)?)',
                r'(nintendo\s*switch(?:\s*oled|\s*lite)?)',
                r'(playstation\s*\d+|ps\d+)',
                r'(xbox\s*(?:series)?\s*[a-z]?)',
            ]
            
            for pattern in product_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    # Clean up the matched string
                    product = match.group(1).strip()
                    # Capitalize nicely
                    if 'iphone' in product:
                        product = product.replace('iphone', 'iPhone')
                    elif 'macbook' in product:
                        product = product.replace('macbook', 'MacBook')
                    
                    # Capitalize common suffixes
                    for suffix in ['Pro', 'Max', 'Plus', 'Mini', 'Ultra', 'SE']:
                        product = re.sub(rf'\b{suffix}\b', suffix, product, flags=re.IGNORECASE)
                        
                    # Extract storage if present
                    storage_match = re.search(r'\b(\d{2,4})\s*(?:go|gb|g)\b', message_lower)
                    if storage_match:
                        storage = storage_match.group(1)
                        # Append storage to product name (e.g. iPhone 13 128Go)
                        product += f" {storage}Go"
                    
                    # Extract color preference
                    colors = ['noir', 'blanc', 'bleu', 'rouge', 'vert', 'or', 'argent', 'gris', 'violet', 'rose', 'gold', 'silver', 'black', 'white', 'blue', 'red', 'green', 'grey', 'gray', 'purple', 'pink', 'minuit', 'lumière stellaire', 'starlight', 'midnight']
                    for color in colors:
                        if color in message_lower:
                            current_data.color_preference = color
                            break
                    
                    # Extract battery preference
                    battery_match = re.search(r'batterie\s*(?:>|superieur|sup|min)?\s*(\d{2,3})', message_lower)
                    if battery_match:
                        try:
                            bat_val = int(battery_match.group(1))
                            if bat_val <= 100:
                                current_data.min_battery = bat_val
                        except:
                            pass
                        
                    current_data.product_interest = product.title() if product.islower() else product
                    break
        
        # Extract budget
        if current_data.budget is None:
            # Stricter budget regex: requires currency symbol OR "budget" keyword context
            # Avoids confusion with storage (256Go) or model numbers (iPhone 14)
            
            # 1. Explicit Currency Match: "2000dh", "2000 mad"
            explicit_budget_match = re.search(r'(\d+[\d\s]*)(?:dh|mad|dhs)', message_lower)
            if explicit_budget_match:
                try:
                    val = int(explicit_budget_match.group(1).replace(' ', ''))
                    if val > 100: # Sanity check
                        current_data.budget = val
                except: pass
            
            # 2. Context Match: "budget 2000", "max 2000"
            elif re.search(r'\b(budget|prix|max)\b', message_lower):
                # Find numbers that are NOT likely storage or models
                # Negative lookahead for storage units
                nums = re.findall(r'\b(\d{3,5})\b(?!\s*(?:go|gb|g|tb|to))', message_lower)
                for num in nums:
                     try:
                        val = int(num)
                        # Heuristic: Budget likely > 500 for phones
                        if val > 400: 
                             current_data.budget = val
                             break
                     except: pass
        
        # --- NEW: Improved Selection Tolerance ---
        if intent in [IntentType.SALES_ACHAT, IntentType.COMMANDE]:
            # Use cached variants if available, otherwise we can't do explicit selection here
            available_variants = current_data.extra_data.get("available_variants", [])
            selection = self.extract_selection_explicit(message_lower, available_variants)
            if selection:
                current_data.selected_variant = selection
                current_data.selection_locked = True # LOCK it once chosen
                # logger.info(f"✅ Selection locked: {selection}")

        # Extract payment method
        if current_data.payment_method is None:
            if re.search(r'\b(cash|comptant|especes|daba|maintenant|immédiat|tout de suite|espèce|cash)\b', message_lower):
                current_data.payment_method = "cash"
            elif re.search(r'\b(credit|crédit|facilité|4x|mensualité|traite|financement|12 mois|mois|plusieurs fois|7essilate|tashilat|tasli7at)\b', message_lower):
                current_data.payment_method = "credit"
        
        # Extract professional situation (Crucial for Credit)
        if current_data.professional_situation is None or intent == IntentType.INFO_CREDIT:
            situations = {
                "salarié": r'\b(salarie|salarié|prive|privé|entreprise|travail|poste|cdi|cdd|kheddam|sharika)\b',
                "fonctionnaire": r'\b(fonctionnaire|etat|état|makhzen|public|dawla|tanmya)\b',
                "liberal": r'\b(liberal|libéral|medecin|médecin|avocat|independant|indépendant|freelance|auto-entrepreneur|doctor)\b',
                "commerçant": r'\b(commercant|commerçant|boutique|hanout|magasin|registre|RC|tijara|moul hanout)\b',
                "retraité": r'\b(retraite|retraité|pension|3atyal|moussin)\b',
                "indépendant": r'\b(independant|indépendant|freelance|auto-entrepreneur|liberal|libéral|bo7di|raci)\b'
            }
            # Special case for "indépendant" mapping to match business rules keys
            if re.search(r'\b(independant|freelance|liberal|bo7di|auto-entrepreneur)\b', message_lower):
                 current_data.professional_situation = "indépendant"
            else:
                for sit, pattern in situations.items():
                    if re.search(pattern, message_lower):
                        current_data.professional_situation = sit
                        break

        # Extract urgency
        if current_data.urgency is None:
            if re.search(r'\b(urgent|maintenant|aujourd\'hui|daba)\b', message_lower):
                current_data.urgency = "immediate"
            elif re.search(r'\b(semaine|simana)\b', message_lower):
                current_data.urgency = "this_week"
            elif re.search(r'\b(flexible|machi mosta3jel)\b', message_lower):
                current_data.urgency = "flexible"
        
        # Extract grade preference (for Purchase-related intents)
        if intent.is_purchase_related and current_data.grade_preference is None:
            if re.search(r'\b(neuf|jdid|nouveau)\b', message_lower):
                current_data.grade_preference = "neuf"
            elif re.search(r'\b(reconditionné|excellent)\b', message_lower):
                current_data.grade_preference = "excellent"
            elif re.search(r'\b(bon|mezyan)\b', message_lower):
                current_data.grade_preference = "bon"
        
        # --- NEW: Extract Preferred Criterion ---
        if intent.is_purchase_related:
            # 1. PRICE
            if re.search(r'\b(moins cher|budget|pas cher|meilleur prix|rkhis|low cost)\b', message_lower):
                current_data.preferred_criterion = "price"
            # 2. QUALITY
            elif re.search(r'\b(batterie|état|grade|propre|nxq|original|état neuf)\b', message_lower):
                current_data.preferred_criterion = "quality"
            # 3. CAPACITY
            elif re.search(r'\b(stockage|capacité|espace|mémoire|go|gb|tb|to)\b', message_lower):
                # Only set as main criterion if budget/price isn't mentioned
                if not current_data.preferred_criterion:
                    current_data.preferred_criterion = "capacity"
            # 4. AESTHETIC
            elif re.search(r'\b(couleur|noir|blanc|bleu|rouge|gold|argent)\b', message_lower):
                if not current_data.preferred_criterion:
                    current_data.preferred_criterion = "aesthetic"
            # 5. HESITATION / FATIGUE
            elif re.search(r'\b(hésite|sais pas|difficile|choix|fatigué|trop|perdu|compliqué)\b', message_lower):
                current_data.preferred_criterion = "hesitation"

        # --- NEW: Extract Variant Selection ---
        # Heuristic for selecting from a list (e.g. "le premier", "celui à 2000")
        if current_data.current_step == "ask_specific_model" or current_data.product_interest:
             available_variants = current_data.extra_data.get("available_variants", [])
             if available_variants:
                 selection_v = self.extract_selection_explicit(message_lower, available_variants)
                 if selection_v:
                     current_data.selected_variant = selection_v
                     current_data.selection_locked = True
        
        # Extract device model (for TRADEIN/REPARATION)
        if intent in [IntentType.TRADEIN, IntentType.REPARATION]:
            if current_data.device_model is None:
                iphone_match = re.search(r'iphone\s*(\d+)(\s*pro)?', message_lower)
                if iphone_match:
                    model = f"iPhone {iphone_match.group(1)}"
                    if iphone_match.group(2):
                        model += " Pro"
                    current_data.device_model = model
        
        # Extract device condition (for TRADEIN)
        if intent == IntentType.TRADEIN and current_data.device_condition is None:
            if re.search(r'\b(excellent|mezyan bezzaf|parfait)\b', message_lower):
                current_data.device_condition = "excellent"
            elif re.search(r'\b(bon|mezyan|good)\b', message_lower):
                current_data.device_condition = "bon"
            elif re.search(r'\b(moyen|machi bezzaf|average)\b', message_lower):
                current_data.device_condition = "moyen"
            elif re.search(r'\b(cassé|mkser|broken)\b', message_lower):
                current_data.device_condition = "cassé"
        
        # Extract accessories (for TRADEIN)
        if intent == IntentType.TRADEIN and current_data.has_accessories is None:
            if re.search(r'\b(oui|yes|3andi|kayn|avec)\b', message_lower):
                current_data.has_accessories = True
            elif re.search(r'\b(non|no|ma3andich|bla|sans)\b', message_lower):
                current_data.has_accessories = False
        
        # Extract issue description (for REPARATION)
        if intent == IntentType.REPARATION and current_data.issue_description is None:
            if re.search(r'\b(écran|screen|mkser)\b', message_lower):
                current_data.issue_description = "écran cassé"
            elif re.search(r'\b(batterie|battery)\b', message_lower):
                current_data.issue_description = "problème batterie"
            elif re.search(r'\b(eau|water|ma)\b', message_lower):
                current_data.issue_description = "dégât des eaux"
            elif re.search(r'\b(eau|water|ma)\b', message_lower):
                current_data.issue_description = "dégât des eaux"
            # Removed generic fallback to enforce specific symptom detection
        
        # Extract fulfillment type
        if current_data.fulfillment_type is None:
            if re.search(r'\b(magasin|agence|maarif|ma8rib|pousser|venir|sur place|récupérer|nji|neji|nemchi)\b', message_lower):
                current_data.fulfillment_type = "pickup"
            elif re.search(r'\b(livraison|livrer|envoyer|domicile|sift|sayfat|casa|rabat|tanger|agadir|marrakech|fes|meknes|oujda)\b', message_lower):
                current_data.fulfillment_type = "delivery"

        # Extract contact info for delivery
        phone_match = re.search(PHONE_REGEX, message)
        if phone_match:
            current_data.phone_number = phone_match.group(0)

        if current_data.full_name is None:
            # Context-aware extraction: If we explicitly asked for the name
            if current_data.current_step == "ask_name":
                 # Assume the whole message is the name (with length sanity check)
                 clean_name = message.strip()
                 if 2 < len(clean_name) < 50:
                     current_data.full_name = clean_name.title()
            else:
                # Heuristic for name: "Je m'appelle X" ou "C'est X"
                name_match = re.search(r'(?:je m\'appelle|c\'est|ana)\s+([a-z\s]{3,30})', message_lower)
                if name_match:
                    current_data.full_name = name_match.group(1).strip().title()

        if current_data.delivery_address is None and current_data.fulfillment_type == "delivery":
            # Context-aware extraction: If we explicitly asked for address
            if current_data.current_step == "ask_address":
                 if len(message) > 5:
                     current_data.delivery_address = message.strip()
            else:
                # Heuristic for address: "à [Address]" or mentioning a city with "livre moi à"
                address_match = re.search(r'(?:adresse|rue|avenue|bd|boulevard|hay|lot|logement|résidence|app|imm|à|fi)\s+([a-z0-9\s,]{5,100})', message_lower)
                if address_match:
                    current_data.delivery_address = address_match.group(1).strip()

        # --- NEW: Order Tracking Extraction ---
        order_match = re.search(ORDER_REGEX, message)
        if order_match:
            current_data.order_name = order_match.group(0)
            
        email_match = re.search(EMAIL_REGEX, message)
        if email_match:
            current_data.email_search = email_match.group(0)

        # Update completion percentage
        current_data.completion_percentage = self.calculate_completion(intent, current_data)
        
        return current_data
    
    def calculate_completion(self, intent: IntentType, data: QualificationData) -> int:
        """Calculate qualification completion percentage"""
        if not intent.is_purchase_related and intent not in [IntentType.TRADEIN, IntentType.REPARATION]:
            return 100
        
        config = self.rules.QUALIFICATION_FIELDS.get(intent, {})
        required_fields = config.get('required', [])
        
        if not required_fields:
            return 100
        
        filled = 0
        for field in required_fields:
            if getattr(data, field, None) is not None:
                filled += 1
        
        return int((filled / len(required_fields)) * 100)

    def extract_selection_explicit(self, message: str, available_variants: List[Dict]) -> Optional[Dict]:
        """
        Detects product selection by Price, Index, Superlative, or Description.
        Returns the variant DICT (VariantDict format).
        
        Handles:
        - Price: "celui à 7590", "7 590 dhs", "le 7590"
        - Index: "le premier", "le 4", "le dernier"
        - Superlative: "le moins cher", "le plus cher", "le meilleur"
        - Attributes: "le 256Go bleu", "grade A"
        """
        if not available_variants:
            return None

        # Normalize input for robust matching
        normalized = normalize_user_input(message)
        # Also keep a version without spaces for price extraction
        no_spaces = normalized.replace(" ", "")
        
        # 0. Superlative Matching (PRIORITY - "le moins cher", "le plus cher")
        superlatives = {
            r'\b(moins cher|rkhe[sc]|lerkhe[sc]|arkhe[sc])\b': 'min_price',
            r'\b(plus cher|ghali|lghali)\b': 'max_price',
            r'\b(meilleur|best|a7san)\b': 'best_quality',
            r'\b(plus grande? batterie|meilleure? batterie)\b': 'max_battery',
        }
        for pattern, strategy in superlatives.items():
            if re.search(pattern, normalized):
                if strategy == 'min_price':
                    return min(available_variants, key=lambda x: x.get('price', float('inf')))
                elif strategy == 'max_price':
                    return max(available_variants, key=lambda x: x.get('price', 0))
                elif strategy == 'best_quality':
                    # Best quality = highest grade (A > B > C) or highest battery
                    grade_order = {'a': 3, 'b': 2, 'c': 1, 'excellent': 3, 'bon': 2, 'moyen': 1}
                    return max(available_variants, key=lambda x: grade_order.get(str(x.get('grade', '')).lower(), 0))
                elif strategy == 'max_battery':
                    return max(available_variants, key=lambda x: x.get('battery', 0))
        
        # 1. Price Matching ("7590", "7 590 dh", etc.)
        prices_mentioned = re.findall(r'(\d{3,})', no_spaces)
        for pm in prices_mentioned:
            try:
                target_price = int(pm)
                for v in available_variants:
                    v_price = v.get('price', 0)
                    if v_price and abs(v_price - target_price) < 50:  # Tolerance +/- 50 MAD
                        return v
            except ValueError:
                continue

        # 2. Index Matching ("le premier", "le 4", darija)
        indices = {
            r'\b(1|premier|premiere?|louwel|lwel|lawel)\b': 0,
            r'\b(2|deuxieme|tani|tanya|ettani)\b': 1,
            r'\b(3|troisieme|talt|talta|ettal[ti])\b': 2,
            r'\b(4|quatrieme|rabe3|rab3a|errabe3)\b': 3,
            r'\b(5|cinquieme|khames|khamsa)\b': 4,
            r'\b(derniere?|lkher|lekher|lakher)\b': -1
        }
        for pattern, idx in indices.items():
            if re.search(pattern, normalized):
                actual_idx = idx if idx >= 0 else len(available_variants) - 1
                if 0 <= actual_idx < len(available_variants):
                    return available_variants[actual_idx]

        # 3. Attribute Matching ("le 256Go", "grade A", "bleu")
        for v in available_variants:
            # Grade matching
            grade = str(v.get('grade', '')).lower()
            if grade and re.search(rf'\bgrade\s*{re.escape(grade)}\b', normalized):
                return v
            
            # Storage matching with model context
            storage = str(v.get('storage', '')).lower()
            storage_num = re.sub(r'[^0-9]', '', storage)
            if storage_num and storage_num in no_spaces:
                # Verify model context to avoid false positives
                model_parts = str(v.get('model', '')).lower().split()
                if any(part in normalized for part in model_parts if len(part) > 2):
                    return v
            
            # Color matching
            color = str(v.get('color', '')).lower()
            if color and len(color) > 2 and color in normalized:
                return v

        return None

    
    def is_qualified(self, intent: IntentType, data: QualificationData) -> bool:
        """Check if lead is sufficiently qualified"""
        return data.completion_percentage >= 100
    
    def check_for_credit_request(self, message: str) -> Optional[str]:
        """
        Check if user is asking for credit form/info and return the link
        """
        msg_lower = message.lower()
        credit_triggers = [
            "dossier", "formulaire", "papiers", "wra9", "wraq", 
            "fiche", "fs", "signalétique", "pdf"
        ]
        credit_context = ["crédit", "credit", "financement", "tashilat", "traite"]
        
        # Check if message contains both credit context and form request
        has_credit_ctx = any(ctx in msg_lower for ctx in credit_context)
        has_form_req = any(trig in msg_lower for trig in credit_triggers)
        
        if has_credit_ctx and has_form_req:
            return f"📄 Pour le dossier de crédit, vous pouvez remplir cette Fiche Signalétique : {CREDIT_FORM_URL}"
            
        return None


# Global instance
qualification_engine = QualificationEngine()
