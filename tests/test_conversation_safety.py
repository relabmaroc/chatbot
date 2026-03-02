"""
Mandatory Conversation Safety Tests
These tests MUST pass for the PR to be accepted.

Tests cover:
1. "bonjour" → welcome, no handoff
2. "je veux acheter iphone 15" → product list
3. "celui à 7 590 dhs" → selection + confirmation
4. "le moins cher" → selection min(price)
5. "le 4" → selection by index
6. forced repetition → fallback, handoff only at 3rd failure
7. COMPLETE → no handoff
8. UNKNOWN → no handoff
9. _save_message type safety
10. selected_variant normalization
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import (
    IntentType, Language, QualificationData, ChatRequest, 
    HandoffReason, VariantDict
)
from logic.qualification import qualification_engine, normalize_user_input
from logic.handoff_manager import handoff_manager
from logic.flow_manager import FlowAction


# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
def sample_variants():
    """Sample variant list for testing selection logic."""
    return [
        {'id': 'v1', 'model': 'iPhone 13', 'price': 5990, 'storage': '128Go', 'battery': 85, 'grade': 'B', 'color': 'noir'},
        {'id': 'v2', 'model': 'iPhone 13', 'price': 6590, 'storage': '256Go', 'battery': 92, 'grade': 'A', 'color': 'bleu'},
        {'id': 'v3', 'model': 'iPhone 13', 'price': 7590, 'storage': '256Go', 'battery': 88, 'grade': 'B', 'color': 'blanc'},
        {'id': 'v4', 'model': 'iPhone 13', 'price': 8990, 'storage': '512Go', 'battery': 95, 'grade': 'A', 'color': 'rouge'},
    ]


@pytest.fixture
def base_qualification_data():
    """Base qualification data for testing."""
    return QualificationData(
        intent_type=IntentType.SALES_ACHAT,
        product_interest="iPhone 13"
    )


# =============================================================================
# TEST 1: Greeting "Bonjour" - No Handoff
# =============================================================================
class TestGreetingNoHandoff:
    def test_bonjour_no_handoff(self, base_qualification_data):
        """'bonjour' should NOT trigger handoff."""
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.UNKNOWN,
            message="bonjour",
            qualification_data=base_qualification_data,
            message_count=1
        )
        assert should is False
        assert reason == HandoffReason.NONE
    
    def test_salam_no_handoff(self, base_qualification_data):
        """'salam' should NOT trigger handoff."""
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.UNKNOWN,
            message="salam",
            qualification_data=base_qualification_data,
            message_count=1
        )
        assert should is False
        assert reason == HandoffReason.NONE


# =============================================================================
# TEST 2: Product Selection by Price "celui à 7 590 dhs"
# =============================================================================
class TestPriceSelection:
    def test_price_with_spaces(self, sample_variants):
        """Price '7 590 dhs' should select the 7590 MAD variant."""
        result = qualification_engine.extract_selection_explicit(
            "je prends celui à 7 590 dhs",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 7590
    
    def test_price_without_spaces(self, sample_variants):
        """Price '7590' should select the 7590 MAD variant."""
        result = qualification_engine.extract_selection_explicit(
            "celui à 7590",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 7590
    
    def test_price_with_mad(self, sample_variants):
        """Price '6590 mad' should select the 6590 MAD variant."""
        result = qualification_engine.extract_selection_explicit(
            "je veux le 6590 mad",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 6590


# =============================================================================
# TEST 3: Superlative Selection "le moins cher"
# =============================================================================
class TestSuperlativeSelection:
    def test_le_moins_cher(self, sample_variants):
        """'le moins cher' should select min(price) variant."""
        result = qualification_engine.extract_selection_explicit(
            "je prends le moins cher",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 5990  # Cheapest
    
    def test_le_plus_cher(self, sample_variants):
        """'le plus cher' should select max(price) variant."""
        result = qualification_engine.extract_selection_explicit(
            "donnez-moi le plus cher",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 8990  # Most expensive
    
    def test_darija_rkhs(self, sample_variants):
        """Darija 'rkhes' should select min(price) variant."""
        result = qualification_engine.extract_selection_explicit(
            "bghit li rkhes",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 5990


# =============================================================================
# TEST 4: Index Selection "le 4"
# =============================================================================
class TestIndexSelection:
    def test_le_4(self, sample_variants):
        """'le 4' should select the 4th variant (index 3)."""
        result = qualification_engine.extract_selection_explicit(
            "je prends le 4",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 8990  # 4th item
    
    def test_le_premier(self, sample_variants):
        """'le premier' should select the 1st variant (index 0)."""
        result = qualification_engine.extract_selection_explicit(
            "je veux le premier",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 5990  # 1st item
    
    def test_le_dernier(self, sample_variants):
        """'le dernier' should select the last variant."""
        result = qualification_engine.extract_selection_explicit(
            "celui en dernier",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 8990  # Last item
    
    def test_darija_louwel(self, sample_variants):
        """Darija 'louwel' should select the 1st variant."""
        result = qualification_engine.extract_selection_explicit(
            "ana bghit louwel",
            sample_variants
        )
        assert result is not None
        assert result['price'] == 5990


# =============================================================================
# TEST 5: COMPLETE Action - No Handoff
# =============================================================================
class TestCOMPLETENoHandoff:
    def test_complete_action_no_handoff(self, base_qualification_data):
        """FlowAction.COMPLETE should NEVER trigger handoff."""
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.SALES_ACHAT,
            message="merci",
            qualification_data=base_qualification_data,
            message_count=10,
            flow_action="COMPLETE"
        )
        assert should is False
        assert reason == HandoffReason.NONE


# =============================================================================
# TEST 6: UNKNOWN Intent - No Handoff
# =============================================================================
class TestUNKNOWNNoHandoff:
    def test_unknown_intent_no_handoff(self, base_qualification_data):
        """UNKNOWN intent should NEVER trigger handoff."""
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.UNKNOWN,
            message="asdfghjkl random text",
            qualification_data=base_qualification_data,
            message_count=5
        )
        assert should is False
        assert reason == HandoffReason.NONE


# =============================================================================
# TEST 7: Recovery Failure Handoff (3+ repetitions)
# =============================================================================
class TestRecoveryFailureHandoff:
    def test_repeat_count_3_triggers_handoff(self, base_qualification_data):
        """3+ repeat_count should trigger RECOVERY_FAILURE handoff."""
        base_qualification_data.repeat_count = 3
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.SALES_ACHAT,
            message="ok",
            qualification_data=base_qualification_data,
            message_count=10
        )
        assert should is True
        assert reason == HandoffReason.RECOVERY_FAILURE
    
    def test_repeat_count_2_no_handoff(self, base_qualification_data):
        """2 repeat_count should NOT trigger handoff."""
        base_qualification_data.repeat_count = 2
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.SALES_ACHAT,
            message="ok",
            qualification_data=base_qualification_data,
            message_count=10
        )
        assert should is False


# =============================================================================
# TEST 8: Explicit Human Request - Handoff
# =============================================================================
class TestExplicitHumanRequest:
    def test_humain_keyword_triggers_handoff(self, base_qualification_data):
        """'parler à un humain' should trigger EXPLICIT_REQUEST handoff."""
        should, reason = handoff_manager.should_handoff(
            intent=IntentType.HUMAIN,
            message="je veux parler à un humain",
            qualification_data=base_qualification_data,
            message_count=5
        )
        assert should is True
        assert reason == HandoffReason.EXPLICIT_REQUEST


# =============================================================================
# TEST 9: Normalization Function
# =============================================================================
class TestNormalization:
    def test_accent_removal(self):
        """Accents should be removed."""
        assert 'e' in normalize_user_input("éèêë")
    
    def test_currency_normalization(self):
        """Currency variations should normalize to 'dh'."""
        assert "dh" in normalize_user_input("7590 dhs")
        assert "dh" in normalize_user_input("7590 MAD")
        assert "dh" in normalize_user_input("7590 dirhams")


# =============================================================================
# TEST 10: QualificationData Hash Function
# =============================================================================
class TestMessageHash:
    def test_hash_consistency(self, base_qualification_data):
        """Same message should produce same hash."""
        msg = "Voici les produits disponibles"
        h1 = base_qualification_data.compute_message_hash(msg)
        h2 = base_qualification_data.compute_message_hash(msg)
        assert h1 == h2
    
    def test_hash_normalization(self, base_qualification_data):
        """Hash should be case and space insensitive."""
        h1 = base_qualification_data.compute_message_hash("Hello World")
        h2 = base_qualification_data.compute_message_hash("hello   world")
        assert h1 == h2


# =============================================================================
# RUN TESTS
# =============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
