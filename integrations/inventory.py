"""
Google Sheets Integration for Product Inventory
Fetches real-time stock, prices, and availability
"""
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InventoryManager:
    """Manages product inventory from Google Sheets"""
    
    def __init__(self, spreadsheet_url: str, credentials_file: str = None, credentials_json: str = None):
        """
        Initialize Google Sheets connection
        
        Args:
            spreadsheet_url: URL of the Google Sheet
            credentials_file: Path to Google service account JSON
            credentials_json: Raw JSON string of Google service account
        """
        self.credentials_file = credentials_file
        self.credentials_json = credentials_json
        self.spreadsheet_url = spreadsheet_url
        self.client = None
        self.sheet = None
        self.cache = {}
        self.cache_expiry = None
        self.cache_duration = timedelta(minutes=5)  # Cache for 5 minutes
        
    def connect(self):
        """Connect to Google Sheets"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            if self.credentials_json:
                import json
                info = json.loads(self.credentials_json)
                creds = Credentials.from_service_account_info(
                    info,
                    scopes=scopes
                )
            else:
                creds = Credentials.from_service_account_file(
                    self.credentials_file,
                    scopes=scopes
                )
            
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_url(self.spreadsheet_url)
            
            logger.info("Connected to Google Sheets successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            return False
    
    def get_products(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get all products from inventory
        Uses cache to avoid excessive API calls
        
        Returns:
            List of product dictionaries
        """
        # Check cache
        if not force_refresh and self.cache and self.cache_expiry:
            if datetime.now() < self.cache_expiry:
                logger.info("Returning cached inventory")
                return self.cache.get('products', [])
        
        # Fetch from Google Sheets
        try:
            if not self.client:
                self.connect()
            
            # Assume first worksheet contains inventory
            worksheet = self.sheet.get_worksheet(0)
            
            # Get all records (assumes first row is headers)
            records = worksheet.get_all_records()
            
            # Parse products - Adapted for Relab's specific columns
            products = []
            for record in records:
                # Build model name from Appareil + Capacité
                appareil = record.get('Appareil', '')
                capacite = record.get('Capacité', record.get('Capacite', ''))
                couleur = record.get('Couleur', '')
                
                # Combine to create full model name
                model_parts = [appareil]
                if capacite:
                    model_parts.append(capacite)
                model = ' '.join(filter(None, model_parts))
                
                # Determine grade from multiple columns
                etat_batterie = record.get('Etat Batterie', record.get('État Batterie', ''))
                grade_ecran = record.get('Grade Ecran', record.get('Grade Écran', ''))
                grade_coque = record.get('Grade Coque', '')
                
                # Create a composite grade description
                grade_parts = []
                if grade_ecran:
                    grade_parts.append(f"Écran: {grade_ecran}")
                if grade_coque:
                    grade_parts.append(f"Coque: {grade_coque}")
                if etat_batterie:
                    grade_parts.append(f"Batterie: {etat_batterie}")
                
                grade = ' | '.join(grade_parts) if grade_parts else 'Reconditionné'
                
                # Get price
                prix = record.get('Prix de Vente Relab', record.get('Prix', 0))
                price = self._parse_price(prix)
                
                # Determine availability - if price > 0, assume available
                available = price > 0
                stock = 1 if available else 0  # Assume 1 in stock if price exists
                
                # Only add if we have a valid model and price
                if model.strip() and price > 0:
                    product = {
                        'model': model,
                        'grade': grade,
                        'price': price,
                        'stock': stock,
                        'available': available,
                        'color': couleur,
                        'storage': capacite,
                        'battery': etat_batterie,
                        'screen_grade': grade_ecran,
                        'body_grade': grade_coque,
                    }
                    products.append(product)

            
            # Update cache
            self.cache['products'] = products
            self.cache_expiry = datetime.now() + self.cache_duration
            
            logger.info(f"Fetched {len(products)} products from Google Sheets")
            return products
            
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            # Return cached data if available
            return self.cache.get('products', [])
    
    def search_product(self, query: str, color: str = None, min_battery: int = None, grade_pref: str = None, criterion: str = None) -> List[Dict]:
        """
        Search for products matching query and optional filters
        """
        products = self.get_products()
        query_lower = query.lower()
        color_lower = color.lower() if color else None
        
        matches = []
        
        # Robust normalization for matching
        def normalize(text):
            text_str = str(text) if text is not None else ""
            return re.sub(r'[\s\-_]', '', text_str.lower()).replace('go', 'g').replace('gb', 'g')
        
        normalized_query = normalize(query)

        def extract_storage_gb(text: str) -> Optional[int]:
            storage_match = re.search(r'(\d+)\s*(go|gb|g|tb|to)\b', text.lower())
            if not storage_match:
                return None
            value = int(storage_match.group(1))
            unit = storage_match.group(2)
            if unit in {"tb", "to"}:
                return value * 1024
            return value

        def detect_qualifiers(text: str) -> set:
            text_lower = text.lower()
            normalized = re.sub(r'[\s\-_]', '', text_lower)
            qualifiers = set()
            if re.search(r'\bpro\b', text_lower) or "promax" in normalized:
                qualifiers.add("pro")
            if re.search(r'\bmax\b', text_lower) or "promax" in normalized:
                qualifiers.add("max")
            if re.search(r'\bplus\b', text_lower):
                qualifiers.add("plus")
            return qualifiers

        query_qualifiers = detect_qualifiers(query_lower)
        query_storage_gb = extract_storage_gb(query_lower)

        def is_match_with_filters(product: Dict, require_storage: bool = True) -> bool:
            model_val = product.get('model', '')
            model_lower = str(model_val).lower()
            normalized_model = normalize(model_val)

            if not (normalized_query in normalized_model or normalized_model in normalized_query):
                return False

            model_qualifiers = detect_qualifiers(model_lower)
            if "pro" in query_qualifiers and "pro" not in model_qualifiers:
                return False
            if "max" in query_qualifiers and "max" not in model_qualifiers:
                return False
            if "plus" in query_qualifiers and "plus" not in model_qualifiers:
                return False

            if require_storage and query_storage_gb is not None:
                model_storage_gb = extract_storage_gb(model_lower)
                if model_storage_gb != query_storage_gb:
                    return False

            return True
        
        for product in products:
            if is_match_with_filters(product, require_storage=True):
                # Filter by Color
                if color_lower:
                    prod_color = str(product.get('color', '')).lower()
                    if color_lower not in prod_color:
                        continue
                
                # Filter by Battery
                if min_battery:
                    bat_str = str(product.get('battery', '')).replace('%', '').strip()
                    if bat_str.isdigit() and int(bat_str) < min_battery:
                        continue
                
                matches.append(product)

        if query_storage_gb is not None and not matches:
            for product in products:
                if is_match_with_filters(product, require_storage=False):
                    if color_lower:
                        prod_color = str(product.get('color', '')).lower()
                        if color_lower not in prod_color:
                            continue

                    if min_battery:
                        bat_str = str(product.get('battery', '')).replace('%', '').strip()
                        if bat_str.isdigit() and int(bat_str) < min_battery:
                            continue

                    matches.append(product)
        
        # --- NEW: CRITERIA SORTING ---
        if criterion == "price":
            matches.sort(key=lambda x: x['price'])
        elif criterion == "quality":
            # Priority: Battery desc, then Grade Screen, then Grade Body
            def quality_score(p):
                bat = str(p.get('battery', '0')).replace('%', '').strip()
                bat_val = int(bat) if bat.isdigit() else 0
                grade_map = {'A+': 5, 'A': 4, 'B+': 3, 'B': 2, 'C': 1, 'D': 0}
                screen = grade_map.get(str(p.get('screen_grade', '')).upper(), 0)
                body = grade_map.get(str(p.get('body_grade', '')).upper(), 0)
                return (bat_val, screen, body)
            matches.sort(key=quality_score, reverse=True)
        elif criterion == "capacity":
            def storage_val(p):
                s = str(p.get('storage', '0')).lower()
                val = re.search(r'(\d+)', s)
                if not val: return 0
                num = int(val.group(1))
                if 'to' in s or 'tb' in s: num *= 1024
                return num
            matches.sort(key=storage_val, reverse=True)
        elif criterion == "hesitation":
            # Best Compromise: Good grade, decent price (mid-range), decent battery
            def compromise_score(p):
                # We want a high score for: Good Grade, Good Battery, Medium Price
                bat = str(p.get('battery', '0')).replace('%', '').strip()
                bat_val = int(bat) if bat.isdigit() else 80
                grade_map = {'A+': 5, 'A': 4, 'B+': 3, 'B': 2, 'C': 1, 'D': 0}
                screen = grade_map.get(str(p.get('screen_grade', '')).upper(), 0)
                
                # For price, we prefer the middle of the available range
                prices = [m['price'] for m in matches]
                if not prices: return (screen, bat_val)
                avg_price = sum(prices) / len(prices)
                price_score = 100 - (abs(p['price'] - avg_price) / avg_price * 100) # Higher if close to average
                
                return (screen, bat_val, price_score)
            matches.sort(key=compromise_score, reverse=True)
            
        return matches

    def find_recommendations(self, target_model: str, target_price: Optional[int] = None) -> List[Dict]:
        """
        Find closest available products based on budget and performance
        """
        all_products = [p for p in self.get_products() if p['available'] and p['stock'] > 0]
        if not all_products:
            return []

        recommendations = []
        target_lower = target_model.lower()
        
        # 1. Same Series (e.g. iPhone 15 Pro -> iPhone 15 or iPhone 14 Pro)
        # Extract base name (e.g. "iPhone 15")
        # Extract base name (e.g. "iPhone 15")
        base_match = re.search(r'(iphone\s*\d+)', target_lower)
        if base_match:
            base_name = base_name_val = base_match.group(1)
            series_matches = [p for p in all_products if base_name_val in str(p.get('model', '')).lower() and str(p.get('model', '')).lower() != target_lower]
            recommendations.extend(series_matches[:2])

        # 2. Budget similarity (+/- 15%) if price is provided OR inferred
        if not recommendations and target_price:
            price_matches = [
                p for p in all_products 
                if abs(p['price'] - target_price) / target_price <= 0.20
                and p not in recommendations
            ]
            # Sort by proximity to target price
            price_matches.sort(key=lambda x: abs(x['price'] - target_price))
            recommendations.extend(price_matches[:2])
            
        # 3. Performance alternatives (if iPhone, suggest same generation or +-1)
        if not recommendations:
            # Fallback to just returning a mix of available popular products
            recommendations.extend(all_products[:2])

        # Remove duplicates while preserving order
        seen = set()
        final_recs = []
        for r in recommendations:
            if r['model'] not in seen:
                final_recs.append(r)
                seen.add(r['model'])
        
        return final_recs[:3]

    def get_product_by_model(self, model: str, grade: Optional[str] = None) -> Optional[Dict]:
        """
        Get specific product by model and grade
        
        Args:
            model: Product model (e.g., "iPhone 15")
            grade: Product grade (e.g., "Excellent", "Bon")
            
        Returns:
            Product dict or None
        """
        products = self.search_product(model)
        
        if not products:
            return None
        
        # If grade specified, filter by grade
        if grade:
            grade_lower = grade.lower()
            for product in products:
                if grade_lower in product['grade'].lower():
                    return product
        
        # Return first available product
        for product in products:
            if product['available'] and product['stock'] > 0:
                return product
        
        # Return first product even if not available
        return products[0] if products else None
    
    def check_availability(self, model: str) -> Dict:
        """
        Check availability and pricing for a model
        
        Returns:
            Dict with availability info
        """
        products = self.search_product(model)
        
        if not products:
            return {
                'available': False,
                'message': f"Désolé, nous n'avons pas trouvé '{model}' dans notre stock.",
                'alternatives': []
            }
        
        available_products = [p for p in products if p['available'] and p['stock'] > 0]
        
        if not available_products:
            return {
                'available': False,
                'message': f"'{model}' est actuellement en rupture de stock.",
                'alternatives': self._get_alternatives(model)
            }
        
        # Group by grade
        by_grade = {}
        for product in available_products:
            grade = product['grade']
            if grade not in by_grade:
                by_grade[grade] = []
            by_grade[grade].append(product)
        
        return {
            'available': True,
            'model': model,
            'options': by_grade,
            'min_price': min(p['price'] for p in available_products),
            'max_price': max(p['price'] for p in available_products),
        }
    
    def _parse_price(self, price_value) -> int:
        """Parse price from various formats"""
        if isinstance(price_value, (int, float)):
            return int(price_value)
        
        if isinstance(price_value, str):
            # Remove currency symbols and spaces
            price_str = price_value.replace('MAD', '').replace('DH', '').replace(' ', '').replace(',', '')
            try:
                return int(float(price_str))
            except ValueError:
                return 0
        
        return 0
    
    def _get_alternatives(self, model: str) -> List[str]:
        """Get alternative models"""
        # Simple logic: suggest similar models
        all_products = self.get_products()
        
        # Extract base model (e.g., "iPhone 15" from "iPhone 15 Pro")
        base_model = model.split()[0:2]  # e.g., ["iPhone", "15"]
        
        alternatives = set()
        for product in all_products:
            if product['available'] and product['stock'] > 0:
                product_model = product['model']
                # Check if similar
                if base_model[0] in product_model and product_model != model:
                    alternatives.add(product_model)
        
        return list(alternatives)[:3]  # Return max 3 alternatives
    
    def format_product_info(self, product: Dict, language: str = 'fr') -> str:
        """
        Format product information for display
        
        Args:
            product: Product dictionary
            language: Response language (fr, darija, en)
            
        Returns:
            Formatted string
        """
        if language == 'darija':
            return f"""📱 {product['model']}
💰 Prix: {product['price']} DH
⭐ État: {product['grade']}
📦 Stock: {product['stock']} disponible(s)
{f"🎨 Couleur: {product['color']}" if product['color'] else ""}
{f"💾 Stockage: {product['storage']}" if product['storage'] else ""}"""
        
        elif language == 'en':
            return f"""📱 {product['model']}
💰 Price: {product['price']} MAD
⭐ Condition: {product['grade']}
📦 Stock: {product['stock']} available
{f"🎨 Color: {product['color']}" if product['color'] else ""}
{f"💾 Storage: {product['storage']}" if product['storage'] else ""}"""
        
        # French (Default) logic with special labels
        bat_str = str(product.get('battery', '')).replace('%', '').strip()
        bat_val = int(bat_str) if bat_str.isdigit() else 100
        
        labels = []
        if bat_val < 75: 
            labels.append("⚠️ Batterie faible")
        if str(product.get('screen_grade', '')).upper() == 'D' or str(product.get('body_grade', '')).upper() == 'D':
            labels.append("⚠️ État dégradé (D)")
            
        label_text = f" ({' | '.join(labels)})" if labels else ""
        
        return f"""📱 {product['model']}{label_text}
💰 Prix: {product['price']} MAD
⭐ État: {product['grade']}
📦 Stock: {product['stock']} disponible(s)
{f"🎨 Couleur: {product['color']}" if product['color'] else ""}
{f"💾 Stockage: {product['storage']}" if product['storage'] else ""}"""


# Global instance (will be initialized with credentials)
inventory_manager = None


def init_inventory(spreadsheet_url: str, credentials_file: str = None, credentials_json: str = None):
    """Initialize global inventory manager"""
    global inventory_manager
    inventory_manager = InventoryManager(
        spreadsheet_url=spreadsheet_url,
        credentials_file=credentials_file,
        credentials_json=credentials_json
    )
    return inventory_manager.connect()
