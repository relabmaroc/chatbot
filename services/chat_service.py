"""
Chat Service
Main orchestrator for chat logic - REFACTORED FOR STRICT PIPELINE & STATE MACHINE
"""
from typing import Optional, List, Tuple, Dict, Any
from models.schemas import (
    ChatRequest, ChatResponse, Intent, IntentType, 
    QualificationData, Language, ConversationStatus, FlowType, HandoffReason
)
from models.database import get_db, Conversation, Message, Lead, Contact
from engine.intent_detector import intent_detector
from logic.qualification import qualification_engine
from logic.handoff_manager import handoff_manager
from llm.response_generator import response_generator
from llm.prompts import prompt_templates
from llm.client import llm_client
from logic.language_detector import language_detector
from logic.flow_manager import flow_manager, FlowStep, FlowAction, ConversationState
from logic.router import router
from sqlalchemy.orm.attributes import flag_modified
import integrations.inventory as inventory_integration
from integrations.inventory import inventory_manager
from integrations.shopify_client import shopify_client
from integrations.knowledge_base import knowledge_base, init_knowledge_base
from logic.business_rules import business_rules
from logic.memory_manager import MemoryManager
from services.n8n_service import n8n_service
from config import settings
from datetime import datetime
import uuid
import re
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Main chat orchestration service"""
    
    def __init__(self):
        self.intent_detector = intent_detector
        self.qualification_engine = qualification_engine
        self.handoff_manager = handoff_manager
        self.response_generator = response_generator
        self.prompt_templates = prompt_templates
        self.llm_client = llm_client
        self.memory_manager = MemoryManager()
        self.inventory = None
        self.knowledge = None
        
        # Initialize integrations
        self._init_integrations()
    
    def _init_integrations(self):
        """Initialize inventory and knowledge base"""
        import os
        
        try:
            # Initialize inventory if configured
            has_creds = settings.google_sheets_credentials_file or settings.google_sheets_credentials_json
            if has_creds and settings.google_sheets_inventory_url:
                logger.info("Initializing Google Sheets inventory...")
                
                creds_path = None
                if settings.google_sheets_credentials_file:
                    creds_path = os.path.abspath(settings.google_sheets_credentials_file)
                
                if inventory_integration.init_inventory(
                    spreadsheet_url=settings.google_sheets_inventory_url,
                    credentials_file=creds_path,
                    credentials_json=settings.google_sheets_credentials_json
                ):
                    self.inventory = inventory_integration.inventory_manager
                    logger.info("✅ Inventory initialized successfully")
                else:
                    logger.error("❌ Inventory initialization failed - check logs for specific error")
            else:
                logger.warning("⚠️ Google Sheets not configured in settings")
            
            # Initialize knowledge base
            logger.info("Initializing knowledge base...")
            self.knowledge = init_knowledge_base(settings.knowledge_base_dir)
            logger.info("✅ Knowledge base initialized")
            
        except Exception as e:
            logger.error(f"Error initializing integrations: {e}")
            import traceback
            traceback.print_exc()
    
    async def process_message(self, request: ChatRequest, db) -> ChatResponse:
        """
        STRICT PIPELINE:
        1. Language Detect (Stickiness applied)
        2. Context Check (Active Flow?)
        3. Intent Detect (LLM - only if needed)
        4. Router (Assign Flow / Handle Confirmation)
        5. Extraction (Standard + LLM)
        6. State Machine Execution (Get Action)
        7. Text Generation (Execute Action)
        """
        try:
            logger.info(f"Processing message: {request.message[:50]}...")

            # --- NEW: External n8n Workflow Override ---
            if settings.use_n8n_workflow:
                logger.info("Delegating message to n8n workflow...")
                # We still want to get or create a conversation to persist history locally
                conversation, _ = self._get_or_create_conversation(
                    db, request.conversation_id, request.identifier, request.channel
                )
                self._save_message(db, conversation.id, "user", request.message, None)
                
                response = await n8n_service.send_to_n8n(
                    message=request.message,
                    identifier=request.identifier,
                    channel=request.channel,
                    metadata=request.metadata,
                    conversation_id=conversation.id
                )
                
                # Save assistant message
                self._save_message(db, conversation.id, "assistant", response.message, response.intent)
                return response

            # Step 0: Whitelist check
            if settings.test_mode_enabled:
                allowed_users = [u.strip() for u in settings.allowed_test_users.split(",") if u.strip()]
                if request.identifier not in allowed_users:
                    return ChatResponse(message=None, conversation_id="ignored", should_handoff=False)

            # Step 1: Get Conversation & Contact
            conversation, is_new = self._get_or_create_conversation(
                db, request.conversation_id, request.identifier, request.channel
            )
            contact = conversation.contact
            
            # Retrieve Qualification Data
            qualification_data = self._get_qualification_data(db, conversation.id, IntentType.UNKNOWN)
            current_flow = getattr(conversation, 'intent_type', None) # We use intent_type as flow tracker mostly
            current_step = qualification_data.current_step

            # --- FIX 1: Sticky Language ---
            # Pass current_language to detector to enforce stickiness
            current_lang_enum = Language(conversation.language) if conversation.language in ["fr", "darija", "en"] else None
            language = language_detector.detect(request.message, current_language=current_lang_enum)
            
            # Update contact language if changed (and strong signal)
            if conversation.language != language.value:
                conversation.language = language.value
                contact.language = language.value
                db.commit()

            # Step 2: Context Check & Intent Detection
            # Should we skip intent detection?
            should_skip = intent_detector.should_skip_detection(current_flow, qualification_data.current_step)
            
            # Priority Check: Logistics keywords + Product Identified => COMMANDE override
            is_commande_override = False
            if qualification_data.product_interest:
                commande_keywords = ["livraison", "adresse", "retirer", "numéro", "telephone", "je prends", "commande"]
                if any(k in request.message.lower() for k in commande_keywords):
                    is_commande_override = True
                    should_skip = False # Force detection to confirm COMMANDE
            
            intent = None
            if should_skip and not is_commande_override:
                # We assume intent matches the current flow
                intent = Intent(
                    type=IntentType(current_flow) if current_flow else IntentType.UNKNOWN,
                    confidence=1.0,
                    language=language,
                    monetization_score=0
                )
            else:
                # Detect Intent
                conversation_history = self._get_conversation_history(db, conversation.id)
                intent = await self.intent_detector.detect(request.message, conversation_history)
                
                # Explicitly force COMMANDE if override logic applies
                if is_commande_override and intent.type != IntentType.COMMANDE:
                    if intent.confidence < 0.9:
                        logger.info("⚡️ Forcing COMMANDE intent due to context")
                        intent.type = IntentType.COMMANDE
            
            # Step 3: Router
            effective_intent_type, should_switch = router.route(intent.type, current_flow)
            
            # Don't switch if CONFIRMATION
            if should_switch and effective_intent_type != IntentType.UNKNOWN:
                current_flow = effective_intent_type.value
                conversation.intent_type = current_flow
                conversation.language = language.value
                conversation.monetization_score = intent.monetization_score
                qualification_data.intent_type = effective_intent_type
                db.commit()

            # Step 4: Save User Message
            self._save_message(db, conversation.id, "user", request.message, intent)

            # --- NEW: CRM Conditional Logic (If/Then) ---
            if intent.type == IntentType.TRADEIN and qualification_data.extra_data.get("last_purchased_product"):
                # User bought something before and now asks for trade-in
                last_prod = qualification_data.extra_data.get("last_purchased_product")
                if language == Language.FRENCH:
                    prefix = f"Toujours ravi de vous revoir ! On peut tout à fait reprendre votre ancien appareil pour votre {last_prod}. "
                else:
                    prefix = f"Ahlān bikt marra khra! N9edrou nbi3ou l'appareil l-9dim dialk bach n'profitiw f {last_prod}. "
                # We let the normal flow continue but with context
                pass

            if intent.type.is_purchase_related and qualification_data.extra_data.get("last_purchased_product"):
                # Suggest accessories for last purchase if they speak about accessories
                if re.search(r'\b(accessoires|coque|protection|chargeur)\b', request.message.lower()):
                    last_prod = qualification_data.extra_data.get("last_purchased_product")
                    if language == Language.FRENCH:
                        response_text = f"Pour votre {last_prod}, nous avons des coques MagSafe et des chargeurs rapides en stock ! Vous voulez voir les prix ?"
                    else:
                        response_text = f"Binsebba l {last_prod}, 3ndna les coques MagSafe w les chargeurs rapides! Bghiti t3ref l-prix?"
                    
                    self._save_message(db, request.conversation_id, "assistant", response_text, None, effective_intent_type)
                    return ChatResponse(message=response_text, conversation_id=request.conversation_id, intent=intent, metadata=qualification_data.dict())

            # Step 4: LLM Enrichment (Optional)
            # 1. Regex Extraction
            qualification_data = self.qualification_engine.extract_data_from_message(
                request.message, effective_intent_type, qualification_data
            )
            
            # --- FIX: Heuristic Product Selection (Handle "1", "2", "3" based on context) ---
            if effective_intent_type.is_purchase_related and request.message.strip().isdigit():
                try:
                    selection_idx = int(request.message.strip()) - 1
                    # Check against recently viewed products if possible, or perform implicit search
                    # For now, we rerun search to be safe, assuming stateless logic
                    if 0 <= selection_idx < 5 and qualification_data.product_interest:
                        if self.inventory:
                            from starlette.concurrency import run_in_threadpool
                            # Re-run search to get the context list
                            results = await run_in_threadpool(
                                self.inventory.search_product, 
                                qualification_data.product_interest, 
                                qualification_data.color_preference,
                                qualification_data.min_battery,
                                qualification_data.grade_preference
                            )
                            if results and selection_idx < len(results):
                                selected = results[selection_idx]
                                # Construct specific product string
                                new_interest = f"{selected.get('model')} {selected.get('storage_gb')}Go"
                                qualification_data.product_interest = new_interest
                                qualification_data.identified_price = selected.get('price')
                                qualification_data.color_preference = selected.get('color') or qualification_data.color_preference
                                qualification_data.grade_preference = selected.get('grade') or qualification_data.grade_preference
                                
                                # Auto-lock selection
                                qualification_data.selected_variant = selected
                                qualification_data.selection_locked = True
                                logger.info(f"✅ User selected product #{selection_idx+1}: {new_interest}")
                except Exception as e:
                    logger.error(f"Error in heuristic selection: {e}")
            
            # --- NEW: Explicit Selection Extraction (e.g., "le 2ème", "celui à 7590") ---
            # This should happen BEFORE LLM extraction, as it's a direct user command.
            if effective_intent_type.is_purchase_related and qualification_data.extra_data.get("available_variants"):
                explicit_selection = self.qualification_engine.extract_selection_explicit(
                    request.message, qualification_data.extra_data["available_variants"]
                )
                if explicit_selection:
                    qualification_data.selected_variant = explicit_selection
                    # Lock selection to prevent re-listing products if user confirms
                    qualification_data.selection_locked = True
                    logger.info(f"✅ Explicit selection detected: {explicit_selection}. Selection locked.")

            # 2. LLM Product Extraction (Strict JSON)
            # Only extract if we suspect product info is present and meaningful
            # AND we are in the early stages or user is refining
            if effective_intent_type.is_purchase_related:
                # Basic heuristic to avoid calling LLM on "Oui" or "Non"
                if len(request.message) > 4 and not re.match(r'^(oui|non|ok|merci|d\'accord)$', request.message.lower()):
                    try:
                        extracted_json = await self._extract_product_data_with_llm(request.message)
                        if extracted_json:
                            # Merge LLM data
                            if 'brand' in extracted_json and extracted_json['brand']: 
                                # Construct full product string if not present/override
                                # Only update if we don't have a product OR if the message seems to be a correction
                                if not qualification_data.product_interest or "non" in request.message.lower():
                                    prod_str = f"{extracted_json['brand']} {extracted_json.get('model') or ''} {extracted_json.get('storage_gb') or ''}Go".strip()
                                    qualification_data.product_interest = prod_str
                            
                            if 'storage_gb' in extracted_json and extracted_json['storage_gb']:
                                # Augment product interest if missing storage
                                if qualification_data.product_interest and str(extracted_json['storage_gb']) not in qualification_data.product_interest:
                                    qualification_data.product_interest += f" {extracted_json['storage_gb']}Go"

                            if 'color' in extracted_json and extracted_json['color']:
                                qualification_data.color_preference = extracted_json['color']
                            
                            if 'grade' in extracted_json and extracted_json['grade']:
                                qualification_data.grade_preference = extracted_json['grade']
                                
                            # Budget Update
                            if 'budget_mad' in extracted_json and extracted_json['budget_mad']:
                                qualification_data.budget = int(extracted_json['budget_mad'])
                    except Exception as e:
                        logger.error(f"Error in LLM extraction: {e}")

            # --- NEW: Objection Handling (e.g. credit fear) ---
            objection_response = await self._handle_objection(request.message, qualification_data, language)
            if objection_response:
                # If it's an objection, we manually override the flow for one turn
                # We stay in ACTIVE status
                self._save_message(db, request.conversation_id, "assistant", objection_response, None, effective_intent_type)
                return ChatResponse(
                    message=objection_response,
                    conversation_id=request.conversation_id,
                    intent=intent,
                    metadata=qualification_data.dict()
                )

            # --- NEW: Process Variant Selection ---
            if qualification_data.selected_variant:
                sel = qualification_data.selected_variant
                variants = qualification_data.extra_data.get("available_variants", []) if qualification_data.extra_data else []
                
                chosen = None
                # Case A: Selection is already a complete variant dict (new format)
                if isinstance(sel, dict) and 'model' in sel and 'price' in sel:
                    chosen = sel
                # Case B: Selection is the old index/price dict format
                elif isinstance(sel, dict) and "selection_type" in sel:
                    if sel["selection_type"] == "index":
                        idx = sel["value"] - 1
                        if 0 <= idx < len(variants):
                            chosen = variants[idx]
                    elif sel["selection_type"] == "price":
                        target_p = sel["value"]
                        if variants:
                            chosen = min(variants, key=lambda x: abs(x['price'] - target_p))

                if chosen:
                    qualification_data.product_interest = chosen.get('model', qualification_data.product_interest)
                    qualification_data.identified_price = chosen.get('price', qualification_data.identified_price)
                    qualification_data.extra_data["current_selection"] = chosen
                    # Don't set confirmed_variant yet, WAIT for user confirmation
            
            # Step 6: Flow Execution (State Machine)
            # Pass request.message to facilitate keyword-based state changes
            flow_result = flow_manager.get_next_action(effective_intent_type, request.message, qualification_data, language)
            
            # --- FIX: Smart Confirmation & Ambiguity ---
            # If user says "ok/oui" but didn't provide any new info extracted from regex/llm
            # OR if we are in CONFIRM_ORDER and receive a positive signal (fixing the "Intent: Commande" override issue)
            is_explicit_confirmation = False
            if flow_result.get("step") == FlowStep.CONFIRM_ORDER:
                 # Check for strong confirmation keywords regardless of intent
                 if re.search(r'\b(oui|ok|yes|d\'accord|c\'est bon|parfait|je confirme|confirm|valide|waha|wakha)\b', request.message.lower()):
                      is_explicit_confirmation = True

            if intent.type == IntentType.CONFIRMATION or is_explicit_confirmation:
                # Heuristic: did we extract ANYTHING new (variant, price, name, etc)?
                # We check if the message is very short and neutral OR explicitly confirmed in context
                is_neutral = is_explicit_confirmation or (len(request.message) < 10 and re.match(r'^(oui|ok|yes|d\'accord|c\'est bon|wa7a|wakha)$', request.message.lower()))
                
                if is_neutral:
                    # Case 1: After a list (SELECTION), ask "Lequel ?"
                    if flow_result.get("step") == FlowStep.ASK_SPECIFIC_MODEL:
                        flow_result["question"] = "D'accord, mais lequel de ces modèles préférez-vous précisément ?" if language == Language.FRENCH else "Wakha, walakin achmen wa7ed fhadou bghiti bdebt?"
                    # Case 2: After a choice (asking for delivery vs pickup)
                    elif flow_result.get("step") == FlowStep.ASK_FULFILLMENT:
                        flow_result["question"] = "Voulez-vous être livré ou préférez-vous le retrait en magasin ?" if language == Language.FRENCH else "Bghiti livraison wla tji l'ma7al tchedha?"
                    # Case 3: If we are in CONFIRMATION (waiting for variant validation), then "ok" is VALID
                    elif flow_result.get("step") == FlowStep.CONFIRM_ORDER:
                        # Check if this was a credit confirmation step
                        if qualification_data.payment_method == "credit" and qualification_data.professional_situation and not qualification_data.credit_confirmed:
                            qualification_data.credit_confirmed = True
                        else:
                            qualification_data.extra_data["confirmed_variant"] = qualification_data.extra_data.get("current_selection")
                        
                        # Re-evaluate flow to move to next state (LOGISTICS or next Credit step)
                        flow_result = flow_manager.get_next_action(effective_intent_type, request.message, qualification_data, language)
                else:
                    # User provided non-neutral confirmation (e.g. "Ok je prends celui à 2500")
                    # This should have been handled by the variant selection extraction above.
                    pass

            # --- FIX: Hesitation / Fatigue ---
            if qualification_data.preferred_criterion == "hesitation" and action == FlowAction.SHOW_PRODUCT_LIST:
                # Propose best compromise first
                matches = await self._perform_product_search_strict(qualification_data.product_interest, qualification_data, language)
                if matches:
                    # Move to CONFIRMATION state directly with the best compromise?
                    # Or just highlight it in the list.
                    # Let's highlight it.
                    pass
            
            # Extract Result
            current_state = flow_result.get("state") # ConversationState
            action = flow_result.get("action") # FlowAction
            question = flow_result.get("question")
            step_name = flow_result.get("step")
            
            # Update state persistence
            qualification_data.current_step = step_name.value if step_name else None
            self._persist_state(db, conversation, contact, qualification_data, intent.type)

            # Search KB (Background)
            kb_context = ""
            if self.knowledge:
                from starlette.concurrency import run_in_threadpool
                kb_results = await run_in_threadpool(self.knowledge.search, request.message, 2)
                if kb_results:
                    kb_context = "\n".join([r['content'] for r in kb_results])

            # Step 7: Formulation (Action-Based View Generation)
            response_text = ""
            should_handoff = False
            handoff_reason = None
            
            # --- ANTI-LOOP GUARD: Selection Lock ---
            # If selection is locked, NEVER relist. Hijack to confirmation or delivery.
            if qualification_data.selection_locked and action == FlowAction.SHOW_PRODUCT_LIST:
                logger.info("🔒 Selection lock ACTIVE. Hijacking SHOW_PRODUCT_LIST to CONFIRM_AND_ASK.")
                action = FlowAction.CONFIRM_AND_ASK
                question = business_rules.get_question(effective_intent_type, "confirm_order", language.value)

            # Handoff Logic
            if action == FlowAction.HANDOFF:
                should_handoff = True
                handoff_reason = "flow_complete"
            elif action == FlowAction.COMPLETE:
                # Flow is complete (e.g. order taken), but DO NOT handoff by default anymore.
                # Only handoff if explicitly required or via IntentType.SAV/HUMAIN.
                should_handoff = False 
                handoff_reason = None
                
                # --- NEW: Specific handling for COMPLETE based on Intent ---
                if effective_intent_type == IntentType.PRODUCT_INFO:
                    # User asked for info, we show it and move on
                    product_context = ""
                    if self.inventory and qualification_data.product_interest:
                        matches = await self._perform_product_search_strict(
                            qualification_data.product_interest, 
                            qualification_data,
                            language
                        )
                        if isinstance(matches, list) and matches:
                            product_context = self._format_product_list(matches[:3], language)
                        elif isinstance(matches, str):
                            product_context = matches # Case where search returned "not found" text
                    
                    if not product_context:
                        # Fallback for generic info
                        response_text = business_rules.get_template(IntentType.PRODUCT_INFO, 'brief', language.value)
                    else:
                        response_text = product_context

                elif effective_intent_type.is_credit_related:
                    response_text = business_rules.get_template(IntentType.INFO_CREDIT, 'brief', language.value)
                    footer = business_rules.get_template(IntentType.INFO_CREDIT, 'footer', language.value)
                    if footer: response_text += f"\n\n{footer}"
                
                else:
                    # Default closure
                    if language == Language.DARIJA:
                        response_text = "Mrehba bikom f ReLab! Ghadi n'jawboukoum f l-app 9riban."
                    else:
                        response_text = "Merci de votre visite chez ReLab ! Un conseiller reviendra vers vous si besoin."

            if should_handoff:
                # Logic is mostly handled by Handoff Manager
                lead_summary = self.handoff_manager.generate_lead_summary(
                    conversation_id=conversation.id,
                    user_id=request.identifier,
                    intent=effective_intent_type,
                    language=language,
                    qualification_data=qualification_data,
                    conversation_history=[], 
                    handoff_reason=handoff_reason,
                    channel=request.channel
                )
                self._save_lead(db, lead_summary, handoff_reason)
                conversation.status = ConversationStatus.HANDED_OFF.value
                db.commit()
                
                response_text = await self.response_generator.generate_handoff_message(
                    effective_intent_type, language, lead_summary.conversation_summary, "{}"
                )
            
            elif action == FlowAction.SHOW_PRODUCT_LIST:
                # --- ANTI-LOOP: Check if Selection is Locked ---
                if qualification_data.selection_locked and qualification_data.selected_variant:
                    logger.info(f"🔒 Selection is locked for {qualification_data.selected_variant}. Skipping relist.")
                    # Force jump to next step (likely confirmation or logistics)
                    # We manually override the action to keep the user in the funnel
                    action = FlowAction.CONFIRM_AND_ASK
                    question = business_rules.get_question(effective_intent_type, "confirm_order", language.value)
                
                if action == FlowAction.SHOW_PRODUCT_LIST: # Re-check action after potential override
                    # --- FIX: Strict Matching ---
                    product_context = ""
                    if self.inventory and qualification_data.product_interest:
                        matches = await self._perform_product_search_strict(
                            qualification_data.product_interest, 
                            qualification_data,
                            language
                        )
                        # Cache current results in ephemeral metadata for selection logic
                        if matches and isinstance(matches, list):
                            qualification_data.extra_data = qualification_data.extra_data or {}
                            qualification_data.extra_data["available_variants"] = [
                                {
                                    'id': m.get('id'),
                                    'model': m.get('model'), 
                                    'price': m.get('price'), 
                                    'storage': m.get('storage'), 
                                    'color': m.get('color'), 
                                    'battery': m.get('battery'), 
                                    'grade': m.get('grade')
                                } 
                                for m in matches[:4]
                            ]
                        
                        product_context = self._format_product_list(matches[:4] if isinstance(matches, list) else [], language)
                
                    # Generate response explaining products + Ask Question
                    # Note: We do NOT append the list blindly. We pass it as context.
                    # The Action implies we show list and ask a question (likely "Which one?" or "Next Step")
                    
                    response_text = await self.response_generator.generate_qualification_response(
                        effective_intent_type,
                        language,
                        question,
                        qualification_data,
                        kb_context=kb_context,
                        product_context=product_context
                    )
                    
                    # If product_context exists, we prepend it explicitly if the LLM didn't (safeguard)
                    # But ideally LLM handles it.
                    # For strictness: "Liste produits + Question"
                    if product_context and "produit" not in response_text.lower():
                        response_text = f"{product_context}\n\n{response_text}"

            elif action == FlowAction.CONFIRM_AND_ASK:
                # --- FIX: Conscious Confirmation (Variant Selection OR Credit) ---
                if step_name == FlowStep.CONFIRM_ORDER:
                    # Scenario A: Credit Confirmation (Professional Situation detected)
                    if qualification_data.payment_method == "credit" and qualification_data.professional_situation and not qualification_data.credit_confirmed:
                        situation = qualification_data.professional_situation.lower()
                        common_docs = business_rules.CREDIT_DOCS['common'].get(language.value, business_rules.CREDIT_DOCS['common']['fr'])
                        spec_docs = business_rules.CREDIT_DOCS.get(situation, {}).get(language.value, [])
                        
                        all_docs = common_docs + spec_docs
                        docs_str = "\n".join([f"- {d}" for d in all_docs])
                        
                        if language == Language.DARIJA:
                            question = f"Hahouma l-wra9 li ghadin n7tajou bach ndirou étude dyal dossier f 24h (0% intérêts):\n{docs_str}\n\nWach t'confirmé bach nkemlou l-logistique dial livraison?"
                        else:
                            question = f"Voici les documents nécessaires pour votre dossier de Crédit Gratuit Relab 0% (étude sous 24h) :\n{docs_str}\n\nEst-ce que vous confirmez pour passer à la livraison ?"
                    
                    # Scenario B: Basic Variant Confirmation
                    else:
                        variant = (qualification_data.extra_data or {}).get("current_selection")
                        if variant:
                            v_str = f"{variant['model']} - {variant.get('storage','')} - Batterie {variant.get('battery','')} - Grade {variant.get('grade','')}"
                            v_price = variant.get('price')
                            
                            if language == Language.DARIJA:
                                question = f"Wash t'confirmé {v_str} b {v_price} DH ?"
                            else:
                                question = f"Est-ce que tu confirmes ton choix : {v_str} au prix de {v_price} MAD ?"
                        else:
                            question = "D'accord, on confirme ce choix ?"

                prompt_instruction = f"Confirme ce que le client vient de dire (ex: 'C'est noté pour X') et pose ensuite la question : {question}"
                
                response_text = await self.response_generator.generate_qualification_response(
                    effective_intent_type,
                    language,
                    question, 
                    qualification_data,
                    kb_context=kb_context,
                    memory_context="INSTRUCTION PRIORITAIRE: Commence par une confirmation courte validant la réponse, PUIS pose la question de validation."
                )

            elif action == FlowAction.PRESENT_INFO:
                # --- NEW: Order Tracking Presentation ---
                if step_name == FlowStep.PRESENT_STATUS:
                    # 1. Fetch Order from Shopify
                    order = await shopify_client.get_order_by_name(qualification_data.order_name)
                    
                    if not order:
                        response_text = business_rules.get_template(IntentType.ORDER_TRACKING, 'not_found', language.value)
                    else:
                        # 2. Verify Identity (Email or Phone)
                        norm = shopify_client.normalize_order_status(order)
                        auth_success = False
                        
                        if qualification_data.email_search and norm["email"] == qualification_data.email_search:
                            auth_success = True
                        elif qualification_data.phone_number and norm["phone"] == qualification_data.phone_number:
                            auth_success = True
                            
                        if not auth_success:
                            response_text = business_rules.get_template(IntentType.ORDER_TRACKING, 'auth_failed', language.value)
                        else:
                            # 3. Success -> Store in Profile/Qualification
                            qualification_data.tracking_data = norm
                            # Record last purchase for CRM
                            qualification_data.extra_data["last_purchased_product"] = norm["product"]
                            
                            tracking_label = f"Lien de suivi : {norm['tracking_url']}" if norm["tracking_url"] else "Suivi indisponible pour l'instant."
                            
                            template = business_rules.get_template(IntentType.ORDER_TRACKING, 'status_present', language.value)
                            response_text = template.format(
                                order_id=norm["order_id"],
                                status=norm["status_label"],
                                product=norm["product"],
                                tracking=tracking_label
                            )
                
                # --- NEW: Credit Info Presentation ---
                elif effective_intent_type.is_credit_related:
                    response_text = business_rules.get_template(IntentType.INFO_CREDIT, 'brief', language.value)
                    
                    if qualification_data.professional_situation:
                        sit = qualification_data.professional_situation.lower()
                        common_docs = business_rules.CREDIT_DOCS['common'].get(language.value, business_rules.CREDIT_DOCS['common']['fr'])
                        spec_docs = business_rules.CREDIT_DOCS.get(sit, {}).get(language.value, [])
                        
                        all_docs = common_docs + (spec_docs if spec_docs else [])
                        docs_str = "\n".join([f"- {d}" for d in all_docs])
                        
                        header = business_rules.get_template(IntentType.CREDIT_DOCUMENTS, 'brief', language.value)
                        response_text += f"\n\n{header}\n{docs_str}"
                        
                        footer = "Voulez-vous démarrer le dossier de crédit ?" if language == Language.FRENCH else "Bghiti t'ebda l-dossier dyal l-credit?"
                        response_text += f"\n\n{footer}"
                    else:
                        footer = business_rules.get_template(IntentType.INFO_CREDIT, 'footer', language.value)
                        if footer: response_text += f"\n\n{footer}"

                # --- NEW: Generic Info (Location, etc.) ---
                elif effective_intent_type == IntentType.LOCATION_DELIVERY:
                    response_text = business_rules.get_template(IntentType.LOCATION_DELIVERY, 'brief', language.value)
            
            # =================================================================
            # ANTI-LOOP: Hash-Based Repetition Detection
            # =================================================================
            response_hash = qualification_data.compute_message_hash(response_text) if response_text else ""
            
            if qualification_data.last_bot_message_hash == response_hash and len(response_text) > 10:
                qualification_data.repeat_count += 1
                logger.warning(f"⚠️ Repetition detected (count={qualification_data.repeat_count})")
                
                # Strategy 1: At 2 repetitions, change approach (clarification question)
                if qualification_data.repeat_count == 2:
                    if language == Language.DARIJA:
                        response_text = "Sma7 lia, ma fhemtch mzyan. Wach t9der t'precisili achnou bghiti bdebt? (mesela: l'awel, le moins cher, wla 7efedlna numer)"
                    else:
                        response_text = "Pardon, je n'ai pas bien compris. Pouvez-vous me préciser votre choix ? (par exemple: le premier, le moins cher, ou indiquez le numéro)"
                    # Recalculate hash for new message
                    response_hash = qualification_data.compute_message_hash(response_text)
                
                # Strategy 2: At 3+ repetitions, offer human help (soft handoff)
                elif qualification_data.repeat_count >= 3:
                    if language == Language.DARIJA:
                        response_text = "Kanhasess belli kain chi mochkil. Bghiti nreddek 3la wa7ed mn l'équipe bach i3awnek daba nit?"
                    else:
                        response_text = "Je sens qu'il y a un souci de compréhension. Souhaitez-vous que je vous mette en relation avec un conseiller ?"
                    response_hash = qualification_data.compute_message_hash(response_text)
                    # NOTE: We do NOT force handoff here - user must confirm
            else:
                # Reset repeat count on successful new response
                qualification_data.repeat_count = 0
            
            qualification_data.last_bot_message_hash = response_hash
            qualification_data.last_question_asked = response_text

            # =================================================================
            # ZERO EMPTY RESPONSE GUARD
            # =================================================================
            if not response_text or not response_text.strip():
                logger.warning(
                    f"⚠️ EMPTY_RESPONSE_GUARD_TRIGGERED | "
                    f"intent={effective_intent_type} action={action} step={step_name} "
                    f"current_step={qualification_data.current_step} selection_locked={qualification_data.selection_locked} "
                    f"has_variants={bool(qualification_data.extra_data.get('available_variants'))}"
                )
                
                # Context-aware fallback
                if effective_intent_type.is_credit_related:
                    if language == Language.DARIJA:
                        response_text = "Je peux t'expliquer le crédit gratuit 0%. Tu es salarié / fonctionnaire / indépendant ?"
                    else:
                        response_text = "Je peux vous expliquer le fonctionnement de notre crédit gratuit 0%. Êtes-vous salarié, fonctionnaire ou indépendant ?"
                
                elif effective_intent_type == IntentType.PRODUCT_INFO:
                    prod = qualification_data.product_interest or "votre produit"
                    if language == Language.DARIJA:
                        response_text = f"Mrehba! Baghi t3ref ktr 3la {prod}? Wach t9der tgol lia achmen capacité (128/256/512 Go) bghiti?"
                    else:
                        response_text = f"Je peux vérifier le stock pour votre {prod}. Quelle capacité recherchez-vous (128/256/512 Go) ?"
                
                else:
                    if language == Language.DARIJA:
                        response_text = "Sma7 lia chwiya. Wach t9der tgol lia ach khssk? (produit, credit, suivi de commande wla reparation)"
                    else:
                        response_text = "Désolé, je n'ai pas bien saisi. Cherchez-vous un produit, des infos crédit, une réparation, ou le suivi d’une commande ?"

            
            # Final Persistence
            self._persist_state(db, conversation, contact, qualification_data, intent.type)
            self._save_message(db, conversation.id, "assistant", response_text, intent)
            
            return ChatResponse(
                message=response_text,
                conversation_id=conversation.id,
                intent=intent,
                should_handoff=should_handoff,
                handoff_reason=handoff_reason,
                next_action="continue"
            )

        except Exception as e:
            logger.error(f"Error in process_message: {e}", exc_info=True)
            return ChatResponse(
                message="Désolé, une erreur technique est survenue.",
                conversation_id=request.conversation_id,
                intent=None,
                should_handoff=False
            )

    # -------------------------------------------------------------------------
    # HELPER METHODS (Preserved & Updated)
    # -------------------------------------------------------------------------
    
    async def _perform_product_search_strict(self, query, qualification_data, language):
        """Strict product search wrapper with criteria sorting"""
        if not self.inventory: return []
        
        from starlette.concurrency import run_in_threadpool
        
        # 1. Search with Criterion
        results = await run_in_threadpool(
            self.inventory.search_product, 
            query, 
            qualification_data.color_preference,
            qualification_data.min_battery,
            qualification_data.grade_preference,
            qualification_data.preferred_criterion
        )
        
        # 2. Strict Filtering (Case Insensitive Token Match)
        # Ensure that critical tokens in query appear in model name
        filtered_results = []
        
        # Extract critical tokens from query (e.g. "Pro", "Max", "1TB", "Plus")
        # Ignore common words "iPhone", "Apple"
        critical_tokens = []
        if "pro" in query.lower(): critical_tokens.append("pro")
        if "max" in query.lower(): critical_tokens.append("max")
        if "plus" in query.lower(): critical_tokens.append("plus")
        if "mini" in query.lower(): critical_tokens.append("mini")
        
        # Storage check
        storage_match = re.search(r'(\d+)\s*(?:go|gb|g|tb|to)', query.lower())
        target_storage = None
        if storage_match:
            target_storage = storage_match.group(1) # just the number

        for p in results:
            model_lower = p.get('model', '').lower()
            storage_lower = str(p.get('storage', '')).lower()
            
            # Token Check
            if not all(token in model_lower for token in critical_tokens):
                continue
            
            # Storage Check (if query had storage)
            if target_storage:
                # Basic check: target '256' must be in '256GB' or '256 Go'
                if target_storage not in storage_lower and target_storage not in model_lower:
                    continue
            
            filtered_results.append(p)
            
        if not filtered_results and results:
            # --- FIX: Product Not Found Handling ---
            # If strict matching failed, return a "not found" message + top 2 general alternatives
            alt_list = self._format_product_list(results[:2], language)
            not_found_msg = "Désolé, je ne trouve pas exactement ce modèle en stock." if language == Language.FRENCH else "Sma7 lia, malqitch had l'modèle bdebt f'stock."
            return f"{not_found_msg}\n\nVoici les options les plus proches :\n{alt_list}"
            
        return filtered_results

    # ... [Keep other helper methods like _get_or_create_conversation, _parse_price etc from original file exactly as is] ...
    # DO NOT OMIT THEM IN FINAL FILE.
    
    def _get_or_create_conversation(self, db, conversation_id: Optional[str], identifier: str, channel: str):
        contact_key = f"{channel}:{identifier}"
        contact = db.query(Contact).filter(Contact.contact_key == contact_key).first()
        if not contact:
            contact = Contact(contact_key=contact_key); db.add(contact); db.commit(); db.refresh(contact)
        
        if conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv: 
                contact.last_seen_at = datetime.utcnow(); db.commit()
                return conv, False
        
        latest_conv = db.query(Conversation).filter(
            Conversation.contact_id == contact.id, Conversation.status.in_([ConversationStatus.ACTIVE.value])
        ).order_by(Conversation.created_at.desc()).first()
        if latest_conv: return latest_conv, False

        new_id = str(uuid.uuid4())
        conv = Conversation(id=new_id, contact_id=contact.id, channel=channel, status=ConversationStatus.ACTIVE.value)
        db.add(conv); db.commit(); db.refresh(conv)
        return conv, True

    def _get_conversation_history(self, db, conversation_id: str) -> List[str]:
        messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(10).all()
        return [msg.content for msg in reversed(messages)]

    def _save_message(self, db, conversation_id: str, sender: str, content: str, intent: Optional[Intent]):
        msg = Message(conversation_id=conversation_id, sender=sender, content=content, intent_type=intent.type.value if intent else None, intent_confidence=intent.confidence if intent else None)
        db.add(msg); db.commit()
    
    def _get_message_count(self, db, conversation_id: str) -> int:
        return db.query(Message).filter(Message.conversation_id == conversation_id).count()

    def _get_qualification_data(self, db, conversation_id: str, intent_type: IntentType) -> QualificationData:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv and "qualification" in conv.extra_data:
            try: return QualificationData(**conv.extra_data["qualification"])
            except: pass
        return QualificationData(intent_type=intent_type, completion_percentage=0, questions_asked=[])

    def _persist_state(self, db, conversation, contact, qualification_data, intent_type):
        conversation.extra_data["qualification"] = qualification_data.dict()
        flag_modified(conversation, "extra_data")
        db.commit()

    def _save_lead(self, db, lead_summary, handoff_reason):
        lead = Lead(
            conversation_id=lead_summary.conversation_id, user_id=lead_summary.user_id,
            intent_type=lead_summary.intent.value, language=lead_summary.language.value,
            channel=lead_summary.channel, qualification_data=lead_summary.qualification_data.dict(),
            estimated_value=lead_summary.estimated_value, conversation_summary=lead_summary.conversation_summary,
            key_points=lead_summary.key_points, recommended_action=lead_summary.recommended_action,
            handoff_reason=handoff_reason, status="pending"
        )
        db.add(lead); db.commit()

    async def _handle_objection(self, message: str, qualification_data: QualificationData, language: Language) -> Optional[str]:
        """Specific handling for customer objections"""
        msg_lower = message.lower()
        
        # Credit refusal objection
        if qualification_data.payment_method == "credit" and re.search(r'\b(ma9blonich|refus|pas accepté|acceptation|si non|refusé)\b', msg_lower):
            if language == Language.DARIJA:
                return "Matkhafch, 7na kanchoufo m3akom l'solution l-wa3ra. Ila mat9belch crédit, n9dro nchoufo Cash b'chi remise wla reprise dyal tilifoun dyalk dghya bach n9essou taman! Chnu ban lik?"
            else:
                return "Ne vous inquiétez pas, on étudie chaque cas sereinement. Si jamais le crédit n'est pas possible, on peut toujours regarder ensemble une option Cash avec remise ou une reprise rapide de votre ancien appareil pour baisser le prix. Qu'en pensez-vous ?"

        return None

    def _format_product_list(self, products: List, language: Language) -> str:
        if not products:
            return "Désolé, je ne trouve pas de variante disponible pour ce modèle." if language == Language.FRENCH else "Sma7 lia, malqitech chi variante lihoum f'stock."
            
        summary = "Voici les meilleures variantes disponibles :\n" if language == Language.FRENCH else "Hahouma l'variants li kaynin :\n"
        for i, p in enumerate(products[:4], 1):
            summary += f"{i}. {self.inventory.format_product_info(p, language.value)}\n"
        
        summary += "\nLequel préférez-vous ? (Vous pouvez répondre par le numéro ou le prix)" if language == Language.FRENCH else "\nAchmen wa7ed bghiti? (Tqder tjawb b'reqm wla b'taman)"
        return summary

    def _format_storage_label(self, storage: Any) -> str:
        if storage is None or storage == "?": return "?Go"
        if isinstance(storage, (int, float)) or str(storage).isdigit(): return f"{int(storage)}Go"
        storage_text = str(storage)
        if re.search(r"(go|gb|tb|to)", storage_text.lower()): return storage_text
        return f"{storage_text}Go"

    async def _extract_product_data_with_llm(self, message: str) -> Optional[Dict]:
        system_prompt = self.prompt_templates.get_product_extractor_prompt()
        user_prompt = f"Message client : \"{message}\""
        try:
            response = await self.llm_client.generate_response(system_prompt=system_prompt, user_message=user_prompt, temperature=0)
            import json
            clean_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_response)
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON extraction: {e}")
            return None

# Global instance
chat_service = ChatService()
