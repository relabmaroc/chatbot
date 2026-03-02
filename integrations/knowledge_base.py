"""
Document Knowledge Base
Manages credit policy and other business documents
"""
import os
import json
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DocumentKnowledgeBase:
    """Manages business documents and policies"""
    
    def __init__(self, documents_dir: str):
        """
        Initialize document knowledge base
        
        Args:
            documents_dir: Directory containing document files
        """
        self.documents_dir = documents_dir
        self.documents = {}
        self.load_documents()
    
    def load_documents(self):
        """Load all documents from directory"""
        try:
            # Load credit policy
            credit_policy_path = os.path.join(self.documents_dir, 'credit_policy.json')
            if os.path.exists(credit_policy_path):
                with open(credit_policy_path, 'r', encoding='utf-8') as f:
                    self.documents['credit_policy'] = json.load(f)
                logger.info("Loaded credit policy document")
            
            # Load warranty info
            warranty_path = os.path.join(self.documents_dir, 'warranty.json')
            if os.path.exists(warranty_path):
                with open(warranty_path, 'r', encoding='utf-8') as f:
                    self.documents['warranty'] = json.load(f)
                logger.info("Loaded warranty document")
            
            # Load FAQ
            faq_path = os.path.join(self.documents_dir, 'faq.json')
            if os.path.exists(faq_path):
                with open(faq_path, 'r', encoding='utf-8') as f:
                    self.documents['faq'] = json.load(f)
                logger.info("Loaded FAQ document")
            
            logger.info(f"Loaded {len(self.documents)} document(s)")
            
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
    
    def get_credit_policy(self, language: str = 'fr') -> Dict:
        """
        Get credit/financing policy information
        
        Args:
            language: Response language
            
        Returns:
            Credit policy info
        """
        policy = self.documents.get('credit_policy', {})
        
        if not policy:
            return {
                'available': False,
                'message': 'Information non disponible'
            }
        
        return policy.get(language, policy.get('fr', {}))
    
    def get_credit_conditions(self, language: str = 'fr') -> str:
        """
        Get formatted credit conditions
        
        Returns:
            Formatted string with credit conditions
        """
        policy = self.get_credit_policy(language)
        
        if not policy.get('available'):
            if language == 'darija':
                return "Makaynch credit daba, khass tkhles cash."
            elif language == 'en':
                return "Credit not available currently, cash payment only."
            else:
                return "Le crédit n'est pas disponible actuellement, paiement comptant uniquement."
        
        # Format conditions
        conditions = policy.get('conditions', [])
        min_amount = policy.get('min_amount', 0)
        max_duration = policy.get('max_duration_months', 0)
        
        if language == 'darija':
            text = f"💳 Crédit disponible:\n"
            text += f"• Montant minimum: {min_amount} DH\n"
            text += f"• Durée max: {max_duration} mois\n"
            if conditions:
                text += "• Conditions:\n"
                for cond in conditions:
                    text += f"  - {cond}\n"
        elif language == 'en':
            text = f"💳 Credit available:\n"
            text += f"• Minimum amount: {min_amount} MAD\n"
            text += f"• Max duration: {max_duration} months\n"
            if conditions:
                text += "• Conditions:\n"
                for cond in conditions:
                    text += f"  - {cond}\n"
        else:  # French
            text = f"💳 Crédit disponible:\n"
            text += f"• Montant minimum: {min_amount} MAD\n"
            text += f"• Durée maximale: {max_duration} mois\n"
            if conditions:
                text += "• Conditions:\n"
                for cond in conditions:
                    text += f"  - {cond}\n"
        
        return text.strip()
    
    def get_warranty_info(self, language: str = 'fr') -> str:
        """Get warranty information"""
        warranty = self.documents.get('warranty', {}).get(language, {})
        
        if not warranty:
            return "Information non disponible"
        
        duration = warranty.get('duration', '12 mois')
        coverage = warranty.get('coverage', [])
        
        if language == 'darija':
            text = f"🛡️ Garantie: {duration}\n"
            if coverage:
                text += "Kayghettiw:\n"
                for item in coverage:
                    text += f"• {item}\n"
        elif language == 'en':
            text = f"🛡️ Warranty: {duration}\n"
            if coverage:
                text += "Covers:\n"
                for item in coverage:
                    text += f"• {item}\n"
        else:
            text = f"🛡️ Garantie: {duration}\n"
            if coverage:
                text += "Couvre:\n"
                for item in coverage:
                    text += f"• {item}\n"
        
        return text.strip()
    
    def search_faq(self, query: str, language: str = 'fr') -> Optional[str]:
        """
        Search FAQ for answer
        
        Args:
            query: User question
            language: Response language
            
        Returns:
            Answer if found, None otherwise
        """
        faq = self.documents.get('faq', {}).get(language, [])
        
        if not faq:
            return None
        
        query_lower = query.lower()
        
        # Simple keyword matching
        for item in faq:
            question = item.get('question', '').lower()
            keywords = item.get('keywords', [])
            
            # Check if query matches question or keywords
            if any(kw.lower() in query_lower for kw in keywords):
                return item.get('answer')
            
            if query_lower in question or question in query_lower:
                return item.get('answer')
        
        return None

    def search(self, query: str, limit: int = 2) -> List[Dict]:
        """
        Generic search across all documents
        Returns list of chunks with 'content' and 'source'
        """
        results = []
        query_lower = query.lower()
        
        # 1. Search FAQ
        for lang in ['fr', 'darija', 'en']:
            faq_answer = self.search_faq(query, lang)
            if faq_answer:
                results.append({'content': faq_answer, 'source': 'faq'})
                break
        
        # 2. Check Credit Policy Keywords
        credit_keywords = ['crédit', 'credit', 'paiement', 'facilité', 'mensualité', 'traite', 'kridi', 'financement']
        if any(kw in query_lower for kw in credit_keywords):
            # Add credit conditions as context
            for lang in ['fr', 'darija']:
                conditions = self.get_credit_conditions(lang)
                if conditions:
                    results.append({'content': conditions, 'source': 'credit_policy'})
        
        # 3. Check Warranty Keywords
        warranty_keywords = ['garantie', 'assurance', 'panne', 'bloqué', 'marche pas']
        if any(kw in query_lower for kw in warranty_keywords):
            for lang in ['fr', 'darija']:
                warranty = self.get_warranty_info(lang)
                if warranty:
                    results.append({'content': warranty, 'source': 'warranty'})

        return results[:limit]


# Global instance
knowledge_base = None


def init_knowledge_base(documents_dir: str):
    """Initialize global knowledge base"""
    global knowledge_base
    knowledge_base = DocumentKnowledgeBase(documents_dir)
    return knowledge_base
