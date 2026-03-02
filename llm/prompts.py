import os
import logging
from typing import Optional, Dict

from models.schemas import IntentType, Language

logger = logging.getLogger(__name__)

# Mapping from IntentType to prompt filename prefixes
INTENT_FILE_MAP = {
    IntentType.SALES_ACHAT: "sales_achat",
    IntentType.PRODUCT_INFO: "product_info",
    IntentType.COMMANDE: "commande",
    IntentType.INFO_CREDIT: "info_credit",
    IntentType.CREDIT_DOCUMENTS: "credit_documents",
    IntentType.CREDIT_ELIGIBILITY: "credit_eligibility",
    IntentType.LOCATION_DELIVERY: "location_delivery",
    IntentType.TRADEIN: "tradein",
    IntentType.REPARATION: "reparation",
    IntentType.SAV: "sav",
    IntentType.HUMAIN: "human_handoff",
    IntentType.UNKNOWN: "sales_achat"
}


class PromptTemplates:
    """Centralized prompt templates with dynamic loading from design artifacts"""
    
    def __init__(self):
        self.prompts_dir = os.path.join(os.getcwd(), "chatbot", "prompts")

    def _load_prompt_file(self, prefix: str, role: str) -> Optional[str]:
        """Load prompt from chatbot/prompts directory"""
        filename = f"{prefix}.{role}.prompt"
        path = os.path.join(self.prompts_dir, filename)
        
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    logger.debug(f"Loaded dynamic prompt: {filename}")
                    return content
            except Exception as e:
                logger.error(f"Error loading prompt file {filename}: {e}")
        return None

    def get_response_system_prompt(self, intent: IntentType, language: Language) -> str:
        """Get system prompt for response generation"""
        
        # 1. Try to load dynamic prompt from design artifacts
        prefix = INTENT_FILE_MAP.get(intent)
        if prefix:
            dynamic_prompt = self._load_prompt_file(prefix, "system")
            if dynamic_prompt:
                return dynamic_prompt

        # 2. Fallback to hardcoded base prompt
        base_prompt = """Tu es Amine, Conseiller Commercial Senior chez Relab.ma.
TON OBJECTIF: Transformer chaque conversation en vente (priorité Cash, sinon Crédit) tout en créant une vraie connexion humaine.

POSITIONNEMENT EXCLUSIF:
- **Produits**: Relab vend UNIQUEMENT des appareils d'occasion de haute qualité.
- **Terminologie**: Utilise UNIQUEMENT le terme "**occasion premium**".
- **INTERDIT**: N'utilise JAMAIS le mot "reconditionné". Si un client pose la question, explique que nos produits sont de l'occasion premium testée et garantie.

STYLE & RYTHME (VITAL):
- **Écoute active**: Adapte-toi au client. S'il est pressé, sois direct. S'il pose des questions, prends le temps de répondre avant de "vendre".
- **Naturel (Code-switching)**: Mixe le français et le darija comme dans une vraie discussion au Maroc.
- **PAS DE REDONDANCE**: Si le client a déjà dit qu'il payait Cash ou s'il a déjà choisi la livraison, n'y reviens JAMAIS.
- **Zéro Pavé**: Maximum 2-3 phrases courtes.
- **CASH FIRST (CRITIQUE)**: Pousse toujours le paiement Cash comme première option.
- **CONFIDENTIALITÉ CRÉDIT**: Ne montre JAMAIS de calculs de mensualités (ex: "808 MAD/mois") de manière proactive. Tu ne dois donner ces chiffres QUE si le client demande explicitement "C'est quoi les mensualités ?" ou s'il confirme vouloir passer par un crédit.

FRAMEWORK DE VENTE (PRIORITÉ CASH):

1. ACCROCHE & CASH FIRST:
Pousse toujours le Cash en priorité car c'est plus simple et plus rapide pour le client.
Exemple: "Le Cash est le moyen le plus rapide pour bloquer l'appareil. Tu préfères régler Cash ou tu veux qu'on regarde le crédit gratuit ?"

2. TRANSITION DIRECTE:
Si le client dit "Cash", ne confirme pas le paiement indéfiniment. Enchaîne DIRECTEMENT sur la logistique : "Ok mezyan. Tu veux passer au magasin à Maarif ou tu préfères une livraison ?"

3. QUALIFICATION CRÉDIT (Si besoin):
Si le client hésite, propose les facilités (12 mois ou 4x sans frais). 
Question clé : "On a des solutions souples. Pour voir ce qu'il te faut comme docs, c'est quoi ta situation pro? (Salarié, fonctionnaire...)"

GESTION DES OBJECTIONS (AVEC EMPATHIE):
- **Chèque**: "T'inquiète, c'est juste un spécimen (modèle) pour ton RIB. C'est pas une garantie, c'est juste pour le dossier de la banque."
- **CNSS**: "Le crédit gratuit demande la CNSS pour prouver le salaire. Si tu l'as pas, on peut regarder pour le 4X sans frais à la place, c'est plus souple."

📍 4, Rue El Yarmouke, Maarif, Casablanca.
📞 +212 7 03 15 20 30

LOGISTIQUE (IMPORTANCE CRITIQUE):
- **Livraison**: On livre partout au Maroc.
- **Délais**: Casablanca f < 2 heures (très rapide!), autres villes du Maroc en moins de 48 heures.
- **Le Choix**: Une fois que le client est intéressé, propose-lui TOUJOURS le choix entre :
    1. Venir au magasin à Maarif (4, Rue El Yarmouke).
    2. Livraison à domicile (Casa < 2h, Maroc < 48h).
- **Collecte**: Si livraison choisie, récupère poliment : Nom, Adresse complète et Téléphone.

RÈGLES D'OR:
- Ne réponds pas à tout d'un coup. Un point à la fois.
- Si le client est en Darija, réponds principalement en Darija avec quelques mots de Français.
- Termine souvent par une question ouverte pour garder le rythme.
"""
        return base_prompt
    
    def format_response_prompt(
        self,
        intent: IntentType,
        language: Language,
        data_to_include: str,
        next_question: str = None
    ) -> str:
        """Format the user prompt for response generation"""
        
        # 1. Try dynamic user prompt
        prefix = INTENT_FILE_MAP.get(intent)
        if prefix:
            dynamic_prompt = self._load_prompt_file(prefix, "user")
            if dynamic_prompt:
                # Replace placeholders
                prompt = dynamic_prompt.replace("{{client_context}}", data_to_include)
                prompt = prompt.replace("{{language}}", language.value)
                if next_question:
                    prompt += f"\n\nPose cette question pour continuer: {next_question}"
                return prompt

        # 2. Fallback
        prompt = f"Génère une réponse basée sur ces informations:\n{data_to_include}\n"
        
        if next_question:
            prompt += f"\nPose cette question: {next_question}\n"
        
        prompt += "\nRéponds de manière naturelle et engageante. UNE SEULE QUESTION PAR MESSAGE."
        
        return prompt
    
    def get_handoff_message_prompt(
        self,
        intent: IntentType,
        language: Language,
        summary: str
    ) -> str:
        """Get prompt for handoff message generation"""
        
        system_prompt = self.get_response_system_prompt(intent, language)
        
        # Try dynamic human handoff prompt
        user_prompt = self._load_prompt_file("human_handoff", "user")
        if user_prompt:
            user_prompt = user_prompt.replace("{{summary}}", summary)
            user_prompt = user_prompt.replace("{{language}}", language.value)
        else:
            # Fallback
            system_prompt += "\n\nCONTEXTE: Tu vas transférer le client à un conseiller humain."
            user_prompt = f"""Génère un message de transition pour informer le client qu'un conseiller va le contacter.

Résumé de la conversation:
{summary}

Le message doit:
- Remercier le client
- Confirmer qu'un conseiller va le contacter
- Être rassurant et professionnel
- Être court (2 phrases max)"""
        
        return system_prompt, user_prompt
    
    def get_product_extractor_prompt(self) -> str:
        """Get system prompt for product data extraction"""
        content = self._load_prompt_file("product_extractor", "system")
        if not content:
            logger.error("Failed to load product_extractor.system.prompt!")
            # Fallback (though we just created the file)
            return "Tu es un extracteur de données produits. Extrais brand, model, storage, condition."
        return content



# Global instance
prompt_templates = PromptTemplates()
