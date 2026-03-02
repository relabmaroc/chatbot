
import sys
import unittest
import re
from unittest.mock import MagicMock
from models.schemas import Language, IntentType, QualificationData, Intent
from logic.qualification import QualificationEngine
from integrations.inventory import InventoryManager
from logic.flow_manager import FlowManager, ConversationState, FlowAction, FlowStep

class TestSalesLogicRefined(unittest.TestCase):
    
    def setUp(self):
        self.qualification_engine = QualificationEngine()
        self.flow_manager = FlowManager()
        self.inventory = InventoryManager("http://example.com")
        self.products = [
            {'model': 'iPhone XS Max', 'price': 3000, 'battery': '80%', 'storage': '64Go', 'screen_grade': 'A', 'body_grade': 'A', 'available': True, 'stock': 1},
            {'model': 'iPhone XS Max', 'price': 2500, 'battery': '72%', 'storage': '64Go', 'screen_grade': 'B', 'body_grade': 'C', 'available': True, 'stock': 1},
        ]

    def test_hesitation_to_compromise(self):
        print("\n🔍 Testing Hesitation detection...")
        data = QualificationData(intent_type=IntentType.COMMANDE)
        # Message: "je ne sais pas trop, j'hésite"
        d1 = self.qualification_engine.extract_data_from_message("je ne sais pas trop, j'hésite", IntentType.COMMANDE, data)
        self.assertEqual(d1.preferred_criterion, "hesitation")
        
        # Test selection "compromise" extraction
        data.product_interest = "iPhone XS Max"
        d2 = self.qualification_engine.extract_data_from_message("propose moi un bon compromis", IntentType.COMMANDE, data)
        self.assertIsNotNone(d2.selected_variant)
        self.assertEqual(d2.selected_variant["selection_type"], "compromise")

    def test_strict_confirmation_flow(self):
        print("\n🔍 Testing Strict Confirmation Flow path...")
        data = QualificationData(
            intent_type=IntentType.COMMANDE, 
            product_interest="iPhone XS Max",
            identified_price=2500,
            extra_data={"current_selection": self.products[1]}
        )
        
        # Scenario 1: Variant not confirmed yet -> State should be CONFIRMATION
        state = self.flow_manager.get_next_action(IntentType.COMMANDE, "celui à 2500", data, Language.FRENCH)
        self.assertEqual(state["state"], ConversationState.CONFIRMATION)
        self.assertEqual(state["step"], FlowStep.CONFIRM_ORDER)
        
        # Scenario 2: User says "ok" -> Ambiguity check? 
        # In this state, "ok" should confirm.
        data.extra_data["confirmed_variant"] = self.products[1]
        state2 = self.flow_manager.get_next_action(IntentType.COMMANDE, "ok", data, Language.FRENCH)
        # Now it should move to LOGISTICS
        self.assertEqual(state2["state"], ConversationState.LOGISTICS)

    def test_overwrite_resets_confirmation(self):
        print("\n🔍 Testing Overwrite resets confirmation...")
        data = QualificationData(
            intent_type=IntentType.COMMANDE, 
            product_interest="iPhone XS Max",
            identified_price=2500,
            extra_data={"confirmed_variant": self.products[1]}
        )
        
        # User changes mind
        updated_data = self.qualification_engine.extract_data_from_message("en fait je prefere le iPhone 15", IntentType.COMMANDE, data)
        self.assertEqual(updated_data.product_interest, "iPhone 15")
        
        # Simulate chat_service logic: if product_interest changes, we should probably clear confirmed_variant?
        # Actually our extract_data_from_message doesn't clear it, but the state machine will see it's generic or needs selection.
        
        # Mocking the state machine reaction
        state = self.flow_manager.get_next_action(IntentType.COMMANDE, "iPhone 15", updated_data, Language.FRENCH)
        # iPhone 15 is generic -> SELECTION
        self.assertEqual(state["state"], ConversationState.SELECTION)

if __name__ == '__main__':
    unittest.main()
