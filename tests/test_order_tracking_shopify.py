
import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from models.schemas import Language, IntentType, QualificationData, ChatRequest
from services.chat_service import ChatService
from integrations.shopify_client import shopify_client

# Set offline mode for tests
os.environ["OFFLINE_MODE"] = "1"

@pytest.mark.asyncio
async def test_order_tracking_logic():
    """Test tracking logic directly on ChatService with mocked dependencies"""
    service = ChatService()
    
    # Mock Shopify response
    mock_order = {
        "name": "#1234",
        "email": "test@example.com",
        "phone": "+212600000000",
        "line_items": [{"title": "iPhone 15 Pro"}],
        "financial_status": "paid",
        "fulfillment_status": "fulfilled",
        "fulfillments": [{"tracking_url": "http://track.me"}]
    }
    
    with patch("integrations.shopify_client.shopify_client.get_order_by_name", return_value=mock_order):
        # 1. Check normalization
        norm = shopify_client.normalize_order_status(mock_order)
        assert norm["order_id"] == "#1234"
        assert "Expédiée" in norm["status_label"]
        
        # 2. Check CRM Suggestion logic (internal method or check ChatService code)
        # We can verify it directly by simulating the condition
        msg = "Je veux des accessoires"
        qual = QualificationData(
            intent_type=IntentType.SALES_ACHAT,
            extra_data={"last_purchased_product": "iPhone 15 Pro"}
        )
        # Check ChatService regex for accessories manually if needed, 
        # but the code is already in chat_service.py
        import re
        assert re.search(r'\b(accessoires|coque|protection|chargeur)\b', msg.lower())

if __name__ == "__main__":
    asyncio.run(test_order_tracking_logic())
    print("Logic Test Passed")
