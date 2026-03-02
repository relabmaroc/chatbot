"""
Response Generator
Combines business logic with LLM for natural responses
"""
from typing import Optional, List
from models.schemas import IntentType, Language, QualificationData
from logic.business_rules import business_rules
from llm.client import llm_client
from llm.prompts import prompt_templates
import logging

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates natural language responses"""
    
    def __init__(self):
        self.llm = llm_client
        self.templates = prompt_templates
        self.rules = business_rules
    
    async def generate_qualification_response(
        self,
        intent: IntentType,
        language: Language,
        next_question: Optional[str],
        qualification_data: QualificationData,
        memory_context: str = "",
        kb_context: str = "",
        product_context: str = ""
    ) -> str:
        """
        Generate response during qualification phase
        Uses LLM for natural formatting, falls back to templates
        """
        
        # If no next question AND no context to answer, qualification is truly complete
        if not next_question and not kb_context and not qualification_data.identified_price and not product_context:
            return await self.generate_qualified_response(intent, language, memory_context)
        
        # Build context for LLM
        data_summary = self._build_data_summary(qualification_data)
        
        # Get system prompt
        system_prompt = self.templates.get_response_system_prompt(intent, language)
        
        # Inject Memory Context
        if memory_context:
            system_prompt += f"\n\n{memory_context}"
            
        # Inject Knowledge Base Context (e.g. credit/warranty info)
        if kb_context:
            system_prompt += f"\n\n[INFORMATIONS COMPLÉMENTAIRES (KB)]\n{kb_context}\n\nUtilise ces infos pour répondre brièvement si le client a posé une question spécifique."

        # Build user prompt
        # We pass next_question=None here to avoid the template adding it weakly.
        user_prompt = self.templates.format_response_prompt(
            intent=intent,
            language=language,
            data_to_include=data_summary,
            next_question=None
        )
        
        # Inject Product Context HERE in user prompt, NOT in system prompt
        # This ensures it's part of the "data" but before the final instruction
        if product_context:
            user_prompt += f"\n\n[PRODUITS DISPONIBLES]\n{product_context}\n"
        
        # STRICT CONSTRAINT: MUST BE THE VERY LAST THING
        if next_question:
            user_prompt += f"\n\n🚨 INSTRUCTION ULTIME ET PRIORITAIRE 🚨 :\n1. Pose UNIQUEMENT cette question : '{next_question}'\n2. NE DIS RIEN D'AUTRE APRÈS CETTE QUESTION.\n3. STOP IMMÉDIATEMENT APRÈS LE POINT D'INTERROGATION."
        
        # Try LLM generation
        response = await self.llm.generate_response(
            system_prompt=system_prompt,
            user_message=user_prompt
        )
        
        # Fallback to template if LLM fails
        if not response:
            logger.warning("LLM failed, using template fallback")
            response = await self._get_template_response(intent, language, next_question)
        
        return response
    
    async def generate_qualified_response(
        self,
        intent: IntentType,
        language: Language,
        memory_context: str = ""
    ) -> str:
        """Generate response when qualification is complete"""
        
        # If we have memory context, we can make it more personal
        if memory_context:
            system_prompt = self.templates.get_response_system_prompt(intent, language)
            system_prompt += f"\n\n{memory_context}"
            user_prompt = "Remercie le client et confirme qu'un conseiller va le contacter. Sois pro et bref."
            response = await self.llm.generate_response(system_prompt, user_prompt)
            if response:
                return response

        template = self.rules.get_template(intent, 'handoff', language.value)
        if template:
            return template
        
        # Fallback
        if language == Language.DARIJA:
            return "Mezyan bezzaf! Wa7ed mn l'équipe ghadi yatsel bik daba. 🎯"
        elif language == Language.FRENCH:
            return "Parfait ! Un conseiller va vous contacter très prochainement. 🎯"
        else:
            return "Perfect! An advisor will contact you shortly. 🎯"
    
    async def generate_handoff_message(
        self,
        intent: IntentType,
        language: Language,
        summary: str,
        memory_context: str = ""
    ) -> str:
        """Generate handoff message to user"""
        
        system_prompt, user_prompt = self.templates.get_handoff_message_prompt(
            intent, language, summary
        )
        
        if memory_context:
            system_prompt += f"\n\n{memory_context}"
            
        response = await self.llm.generate_response(
            system_prompt=system_prompt,
            user_message=user_prompt
        )
        
        # Fallback
        if not response:
            template = self.rules.get_template(intent, 'handoff', language.value)
            if template:
                return template
            
            if language == Language.DARIJA:
                return "Chokran! Wa7ed mn l'équipe ghadi yatsel bik bach nkemmlo. 👤"
            elif language == Language.FRENCH:
                return "Merci ! Un conseiller va vous contacter pour finaliser. 👤"
            else:
                return "Thank you! An advisor will contact you to finalize. 👤"
        
        return response

    async def generate_info_response(
        self,
        message: str,
        language: Language,
        kb_context: str = "",
        memory_context: str = "",
        data_summary: str = ""
    ) -> str:
        """Generate specialized response for info requests using KB context"""
        
        # Get base system prompt for INFO intent
        system_prompt = self.templates.get_response_system_prompt(IntentType.PRODUCT_INFO, language)
        
        # Inject Memory Context if available
        if memory_context:
            system_prompt += f"\n\n{memory_context}"
            
        # Build specific user prompt for info/KB
        user_prompt = f"Répond à cette question client en utilisant les infos ci-dessous si elles sont pertinentes.\n\n"
        user_prompt += f"QUESTION: {message}\n\n"
        
        if data_summary:
            user_prompt += f"CONTEXTE ACTUEL:\n{data_summary}\n\n"
            
        if kb_context:
            user_prompt += f"INFOS CONTEXTE:\n{kb_context}\n\n"
        
        user_prompt += "Réponse courte, directe et sans émoji."
        
        # Try LLM generation
        response = await self.llm.generate_response(
            system_prompt=system_prompt,
            user_message=user_prompt
        )
        
        # Fallback to simple template if LLM fails or context is empty
        if not response:
            if language == Language.DARIJA:
                return "Ana hna bach n3awnek! Wach bghiti t3ref chi haja mo3ayana 3la les produits wla services dyalna?"
            elif language == Language.FRENCH:
                return "Je suis là pour vous aider ! Que souhaitez-vous savoir sur nos produits ou services ?"
            else:
                return "I'm here to help! What would you like to know about our products or services?"
        
        return response
    
    async def generate_greeting_response(
        self,
        intent: IntentType,
        language: Language,
        memory_context: str = ""
    ) -> str:
        """Generate greeting response at start of conversation"""
        
        # If we have memory, we should greet personally using LLM instead of template
        if memory_context:
            system_prompt = self.templates.get_response_system_prompt(intent, language)
            system_prompt += f"\n\n{memory_context}"
            
            # Strict instructions for returning users
            user_prompt = (
                "Salue le client de manière EXTRÊMEMENT directe et brève. "
                "INTERDIT: Ne dis JAMAIS 'Content de te retrouver' ou 'Ravi de vous revoir'. "
                "Va droit au but par rapport à ses préférences connues."
            )
            
            response = await self.llm.generate_response(
                system_prompt=system_prompt,
                user_message=user_prompt
            )
            if response:
                logger.info(f"Generated personal greeting (length: {len(response)}): {response[:50]}...")
                return response

        template = self.rules.get_template(intent, 'greeting', language.value)
        
        if template:
            return template
        
        # Default greeting
        if language == Language.DARIJA:
            return "Salam! Chno khsek lyoum? 😊"
        elif language == Language.FRENCH:
            return "Bonjour ! En quoi puis-je vous aider ? 😊"
        else:
            return "Hello! How can I help you? 😊"
    
    def _build_data_summary(self, qualification_data: QualificationData) -> str:
        """Build summary of collected data with instant credit calculation"""
        summary_parts = []
        
        if qualification_data.product_interest:
            summary_parts.append(f"Produit: {qualification_data.product_interest}")
            
        if qualification_data.identified_price:
            price = qualification_data.identified_price
            summary_parts.append(f"Prix identifié: {price} MAD")
            
            # Multi-option Credit calculation (INTERNAL DATA - DO NOT SHOW TO CLIENT UNLESS REQUESTED)
            summary_parts.append(f"[DONNÉES INTERNES - NE PAS MONTRER SAUF SI DEMANDÉ]")
            summary_parts.append(f"Calculs Crédit (Gratuit, 0% intérêt, 0 Avance):")
            summary_parts.append(f"- 12 Mois: {round(price / 12, 2)} MAD/mois")
            summary_parts.append(f"- 6 Mois: {round(price / 6, 2)} MAD/mois")
            summary_parts.append(f"- 4 Mois: {round(price / 4, 2)} MAD/mois")
            summary_parts.append(f"[FIN DES DONNÉES INTERNES]")
            
        if qualification_data.budget:
            summary_parts.append(f"Budget: {qualification_data.budget} MAD")
            
        if qualification_data.payment_method:
            summary_parts.append(f"Mode de paiement: {qualification_data.payment_method}")
            
        if qualification_data.professional_situation:
            summary_parts.append(f"Situation pro: {qualification_data.professional_situation}")
            
        if qualification_data.fulfillment_type:
            summary_parts.append(f"Retrait/Livraison: {qualification_data.fulfillment_type}")
            
        if qualification_data.full_name:
            summary_parts.append(f"Nom client: {qualification_data.full_name}")
            
        if qualification_data.delivery_address:
            summary_parts.append(f"Adresse livraison: {qualification_data.delivery_address}")
            
        if qualification_data.phone_number:
            summary_parts.append(f"Téléphone livraison: {qualification_data.phone_number}")
            
        if qualification_data.device_model:
            summary_parts.append(f"Appareil reprise: {qualification_data.device_model}")
            
        if qualification_data.device_condition:
            summary_parts.append(f"État reprise: {qualification_data.device_condition}")
        
        return "\n".join(summary_parts) if summary_parts else "Début de conversation"
    
    async def _get_template_response( # Made async
        self,
        intent: IntentType,
        language: Language,
        next_question: Optional[str]
    ) -> str:
        """Get template-based response as fallback"""
        
        if not next_question:
            return await self.generate_qualified_response(intent, language) # Awaited

        greeting = self.rules.get_template(intent, 'greeting', language.value)
        
        if greeting:
            return f"{greeting}\n\n{next_question}"
        
        return next_question


# Global instance
response_generator = ResponseGenerator()
