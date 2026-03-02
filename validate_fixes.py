
import sys
import unittest
import re
from unittest.mock import MagicMock
from models.schemas import Language, IntentType, QualificationData, Intent
from logic.language_detector import LanguageDetector
from engine.intent_detector import IntentDetector
from logic.flow_manager import FlowManager, FlowStep, ConversationState, FlowAction, is_generic_product_interest
from logic.router import Router
from logic.qualification import QualificationEngine

class TestChatbotLogicRefined(unittest.TestCase):
    
    def setUp(self):
        self.lang_detector = LanguageDetector()
        self.intent_detector = IntentDetector()
        self.flow_manager = FlowManager()
        self.router = Router()
        self.qualification_engine = QualificationEngine()

    # ----------------------------------------------------------------
    # 1. TEST GENERIC VS SPECIFIC
    # ----------------------------------------------------------------
    def test_generic_classification(self):
        print("\n🔍 Testing Generic Classification...")
        self.assertTrue(is_generic_product_interest("iPhone 15"))
        self.assertTrue(is_generic_product_interest("Samsung S23"))
        
        self.assertFalse(is_generic_product_interest("iPhone 15 Pro"))
        self.assertFalse(is_generic_product_interest("iPhone 15 128Go"))
        self.assertFalse(is_generic_product_interest("iPhone 15 Noir"))

    # ----------------------------------------------------------------
    # 2. TEST FLOW: GENERIC PRODUCT TRIGGERS LIST
    # ----------------------------------------------------------------
    def test_generic_triggers_list(self):
        print("\n🔍 Testing Generic triggers List...")
        # Scenario: "Je veux iPhone 15"
        data = QualificationData(intent_type=IntentType.COMMANDE, product_interest="iPhone 15")
        
        # Even if product_interest exists, if it's generic, state should be SELECTION
        result = self.flow_manager.get_next_action(IntentType.COMMANDE, "Je veux iPhone 15", data, Language.FRENCH)
        self.assertEqual(result["state"], ConversationState.SELECTION)
        self.assertEqual(result["action"], FlowAction.SHOW_PRODUCT_LIST)
        self.assertEqual(result["step"], FlowStep.ASK_SPECIFIC_MODEL)

    # ----------------------------------------------------------------
    # 3. TEST SMART CONFIRMATION
    # ----------------------------------------------------------------
    def test_smart_confirmation_after_list(self):
        print("\n🔍 Testing Smart Confirmation after list...")
        # Imagine the previous question was "Lequel ?" (after a list)
        # User says "ok"
        data = QualificationData(intent_type=IntentType.COMMANDE, product_interest="iPhone 15")
        
        # Simulated chat_service logic:
        # 1. Flow manager says we are in SELECTION/ASK_SPECIFIC_MODEL
        flow_result = self.flow_manager.get_next_action(IntentType.COMMANDE, "ok", data, Language.FRENCH)
        
        # 2. Intent detected is CONFIRMATION
        # 3. We check if logic repeats the question
        message = "ok"
        if len(message) < 5 and re.match(r'^(oui|ok|yes|d\'accord|c\'est bon)$', message.lower()):
            if flow_result.get("step") == FlowStep.ASK_SPECIFIC_MODEL:
                 flow_result["question"] = "REPEAT_QUESTION"
        
        self.assertEqual(flow_result["question"], "REPEAT_QUESTION")

    # ----------------------------------------------------------------
    # 4. TEST PRODUCT INFO FLOW
    # ----------------------------------------------------------------
    def test_product_info_flow(self):
        print("\n🔍 Testing Product Info Flow...")
        # User asks for price
        data = QualificationData(intent_type=IntentType.PRODUCT_INFO, product_interest="iPhone 15 Pro")
        
        result = self.flow_manager.get_next_action(IntentType.PRODUCT_INFO, "C'est quoi le prix?", data, Language.FRENCH)
        
        # Should stay in ProductInfoFlow and not ask for Name/Phone immediately
        self.assertEqual(result["state"], ConversationState.CONFIRMATION)
        self.assertEqual(result["action"], FlowAction.COMPLETE)

    # ----------------------------------------------------------------
    # 5. TEST OVERWRITE (Correction)
    # ----------------------------------------------------------------
    def test_overwrite_correction(self):
        print("\n🔍 Testing Overwrite Correction...")
        data = QualificationData(intent_type=IntentType.COMMANDE, product_interest="iPhone 14")
        
        # User corrects: "En fait je veux le 15 Pro"
        updated_data = self.qualification_engine.extract_data_from_message(
            "En fait je veux le iPhone 15 Pro", IntentType.COMMANDE, data
        )
        
        self.assertEqual(updated_data.product_interest, "iPhone 15 Pro")
        
        # Update phone number
        data.phone_number = "0611111111"
        updated_data = self.qualification_engine.extract_data_from_message(
            "mon numéro c'est 0622222222", IntentType.COMMANDE, data
        )
        self.assertEqual(updated_data.phone_number, "0622222222")

if __name__ == '__main__':
    unittest.main()
