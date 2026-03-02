import os
import httpx
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ShopifyClient:
    """
    Shopify Admin API Client with Mock Support.
    """
    def __init__(self):
        self.store_domain = os.getenv("SHOPIFY_STORE_DOMAIN", "relab-test.myshopify.com")
        self.access_token = os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN")
        self.api_version = os.getenv("SHOPIFY_API_VERSION", "2024-01")
        self.offline_mode = os.getenv("OFFLINE_MODE", "0") == "1"
        
        self.base_url = f"https://{self.store_domain}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token or "",
            "Content-Type": "application/json"
        }
        
        # Fixtures for Offline Mode
        self.mock_orders = [
            {
                "id": 123456,
                "name": "#1234",
                "email": "test@example.com",
                "phone": "+212600000000",
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
                "created_at": "2024-01-01T10:00:00Z",
                "line_items": [{"title": "iPhone 15 Pro"}],
                "fulfillments": [
                    {
                        "tracking_url": "https://tracking.relab.ma/1234",
                        "status": "success"
                    }
                ]
            },
            {
                "id": 555555,
                "name": "#5555",
                "email": "fail@example.com",
                "phone": "+212611111111",
                "financial_status": "paid",
                "fulfillment_status": None,
                "created_at": "2024-01-20T10:00:00Z",
                "line_items": [{"title": "MacBook Air M2"}]
            },
            {
                "id": 999999,
                "name": "#9999",
                "email": "cancel@example.com",
                "status": "cancelled",
                "cancelled_at": "2024-01-25T10:00:00Z",
                "line_items": [{"title": "AirPods Pro"}]
            }
        ]

    async def get_order_by_name(self, order_name: str) -> Optional[Dict[str, Any]]:
        """Get order by display name (e.g. #1234)"""
        if self.offline_mode:
            logger.info(f"[MOCK] Looking up order {order_name}")
            return next((o for o in self.mock_orders if o["name"] == order_name), None)
        
        # Real API call
        params = {"name": order_name, "status": "any"}
        return await self._request("GET", "/orders.json", params=params, extract_first="orders")

    async def search_orders_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Search orders associated with an email"""
        if self.offline_mode:
            return [o for o in self.mock_orders if o["email"] == email]
        
        params = {"email": email, "status": "any"}
        return await self._request("GET", "/orders.json", params=params, extract_list="orders")

    async def search_orders_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """Search orders associated with a phone number"""
        if self.offline_mode:
            return [o for o in self.mock_orders if o["phone"] == phone]
        
        # Cleaning phone for Shopify search (often stored without + in some contexts, but Shopify likes exact)
        params = {"phone": phone, "status": "any"}
        return await self._request("GET", "/orders.json", params=params, extract_list="orders")

    def normalize_order_status(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Shopify order data to a clean internal format"""
        if not order: return {}
        
        status = "En préparation"
        if order.get("cancelled_at"):
            status = "Annulée"
        elif order.get("fulfillment_status") == "fulfilled":
            status = "Expédiée / Livrée"
        elif order.get("financial_status") == "authorized":
            status = "En attente de paiement"
            
        tracking_url = None
        fulfillments = order.get("fulfillments", [])
        if fulfillments:
            tracking_url = fulfillments[0].get("tracking_url")
            
        product = order["line_items"][0]["title"] if order.get("line_items") else "Produit"
        
        return {
            "order_id": order.get("name"),
            "status_label": status,
            "financial_status": order.get("financial_status"),
            "fulfillment_status": order.get("fulfillment_status"),
            "tracking_url": tracking_url,
            "product": product,
            "email": order.get("email"),
            "phone": order.get("phone")
        }

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        # Rate limit handling and retry logic
        extract_first = kwargs.pop("extract_first", None)
        extract_list = kwargs.pop("extract_list", None)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(3):
                try:
                    response = await client.request(method, f"{self.base_url}{path}", headers=self.headers, **kwargs)
                    
                    if response.status_code == 429: # Rate Limit
                        wait_time = int(response.headers.get("Retry-After", 2))
                        logger.warning(f"Shopify Rate Limit hit. Waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    response.raise_for_status()
                    data = response.json()
                    
                    if extract_first:
                        items = data.get(extract_first, [])
                        return items[0] if items else None
                    if extract_list:
                        return data.get(extract_list, [])
                    return data
                    
                except httpx.HTTPStatusError as e:
                    logger.error(f"Shopify API error {e.response.status_code}: {e.response.text}")
                    if e.response.status_code in [401, 403]:
                        break # Authenticaton error, don't retry
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Shopify request failed: {e}")
                    await asyncio.sleep(1)
            return None

# Global instance
shopify_client = ShopifyClient()
