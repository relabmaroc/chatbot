"""
Business Rules Configuration
Centralized configuration for all business logic
"""
from models.schemas import IntentType


class BusinessRules:
    """Centralized business rules"""
    
    # Handoff triggers
    HIGH_VALUE_THRESHOLD = 5000  # MAD - trigger human handoff
    MAX_BOT_MESSAGES = 10  # Max messages before suggesting human
    
    # Payment/financing keywords that trigger immediate handoff
    PAYMENT_KEYWORDS = [
        # French
        r'\b(paiement|payer|carte|espèces|virement|financement)\b',
        r'\b(crédit|facilité|mensualité|acompte)\b',
        # Darija
        r'\b(khlas|nkhles|d?flous|credit)\b',
    ]
    
    TRACKING_KEYWORDS = [
        r'\b(suivi|commande|tracking|status|livraison|expédié|où est|fin wsla|dakchi)\b'
    ]
    
    # Qualification requirements per intent
    QUALIFICATION_FIELDS = {
        IntentType.SALES_ACHAT: {
            'required': ['product_interest', 'fulfillment_type'],
            'optional': ['professional_situation', 'budget', 'full_name', 'delivery_address', 'phone_number'],
            'questions': {
                'product_interest': {
                    'fr': "Quel produit vous intéresse ? (ex: iPhone 15, iPhone 14 Pro...)",
                    'darija': "Achmen produit kaytssalek? (matalan: iPhone 15, iPhone 14 Pro...)",
                    'en': "Which product are you interested in? (e.g., iPhone 15, iPhone 14 Pro...)"
                },
                'payment_method': {
                    'fr': "Excellent choix ! Le Cash est le moyen le plus rapide d'assurer votre achat (recommandé). Vous souhaitez payer au Comptant/Cash ou vous préférez voir nos options de Crédit ?",
                    'darija': "Mezyan bezzaf ! Cash hiya l'wa3ra bach tkhless dghya (ana ka nnes7ek biha). Bghiti tkhless Cash wla bghiti nchoufo les options dyal Crédit ?",
                    'en': "Excellent choice! Cash is the fastest way to secure your purchase (recommended). Would you like to pay Cash or would you prefer to see our Credit options?"
                },
                'fulfillment_type': {
                    'fr': "C'est noté ! On livre partout au Maroc (Casa en < 2h, autres villes en < 48h) ou vous pouvez passer à l'agence à Maarif dès aujourd'hui. Vous préférez la Livraison ou le Retrait en magasin ?",
                    'darija': "Wakha! Ka ndiro livraison f ga3 l-moudoun (Casa f < 2h, moudoun khrin f < 48h) wla t9der tji l'agence f Maarif lyoum. Chno bghiti: Livraison wla tji l'magasin?",
                    'en': "Got it! We deliver all over Morocco (Casa in < 2h, other cities in < 48h) or you can pick it up at our Maarif store today. Would you prefer Delivery or Pickup?"
                },
                'professional_situation': {
                    'fr': "Parfait. On a bien le Crédit Gratuit Relab (0 % d'intérêts) sur 12 mois ou le paiement en 4 fois. Pour vous lister les documents nécessaires (réponse sous 24h après étude du dossier), êtes-vous salarié du privé, fonctionnaire/retraité ou indépendant ?",
                    'darija': "Parfait. Kayen Crédit Gratuit Relab (0 % intérêts) sur 12 mois wla paiement f 4 fois. Bach n3tikom la liste dyal les documents (réponse f 24h mn b3d drassa dyal dossier), wach ntoma salarié f privé, fonctionnaire/retraité wla indépendant?",
                    'en': "Perfect. We have Relab Free Credit (0% interest) over 12 months or 4x payment. To list the required documents (response within 24h after study), are you a private employee, civil servant/retired, or independent?"
                },
                'budget': {
                    'fr': "Quel est votre budget approximatif ?",
                    'darija': "Ch7al budget dyalek?",
                    'en': "What's your approximate budget?"
                },
                'full_name': {
                    'fr': "Très bien. Quel est votre Nom et Prénom pour la livraison ?",
                    'darija': "Mezyan. Achno smia w l-kenya dyalk l-livraison?",
                    'en': "Great. What is your Full Name for delivery?"
                },
                'delivery_address': {
                    'fr': "Quelle est votre adresse exacte de livraison ?",
                    'darija': "Achmen cinouane bghiti nssiftouh fih?",
                    'en': "What is your exact delivery address?"
                },
                'phone_number': {
                    'fr': "Quel est votre numéro de téléphone pour que le livreur vous contacte ?",
                    'darija': "Achno ra9m l-hatif dyalk l-livreur?",
                    'en': "What is your phone number for the delivery driver?"
                }
            }
        },
        IntentType.PRODUCT_INFO: {
            'required': ['product_interest'],
            'optional': ['budget'],
            'questions': {
                'product_interest': {
                    'fr': "Quel modèle vous intéresse précisément ? (ex: iPhone 15 Pro, MacBook Air M2...)",
                    'darija': "Achmen model bghiti t3ref 3lih ktr? (matalan: iPhone 15 Pro, MacBook Air M2...)",
                    'en': "Which model are you specifically interested in? (e.g., iPhone 15 Pro, MacBook Air M2...)"
                }
            }
        },
        IntentType.TRADEIN: {
            'required': ['device_model', 'device_condition'],
            'optional': ['has_accessories', 'urgency'],
            'questions': {
                'device_model': {
                    'fr': "Quel est le modèle de votre appareil ?",
                    'darija': "Achno model dyal tilifoun dyalek?",
                    'en': "What's your device model?"
                },
                'device_condition': {
                    'fr': "Dans quel état est votre appareil ? (excellent / bon / moyen / cassé)",
                    'darija': "Kifach 7alt tilifoun? (mezyan bezzaf / mezyan / machi bezzaf / mkser)",
                    'en': "What's your device condition? (excellent / good / average / broken)"
                },
                'has_accessories': {
                    'fr': "Avez-vous la boîte et les accessoires d'origine ?",
                    'darija': "3andek la boite w les accessoires?",
                    'en': "Do you have the original box and accessories?"
                },
                'urgency': {
                    'fr': "Quand souhaitez-vous faire la reprise ?",
                    'darija': "Waqtach bghiti tbadel tilifoun?",
                    'en': "When would you like to trade in?"
                }
            }
        },
        IntentType.REPARATION: {
            'required': ['device_model', 'issue_description'],
            'optional': ['urgency'],
            'questions': {
                'device_model': {
                    'fr': "Quel est le modèle de votre appareil ?",
                    'darija': "Achno model dyal tilifoun dyalek?",
                    'en': "What's your device model?"
                },
                'issue_description': {
                    'fr': "Quel est le problème ? (écran cassé / batterie / autre...)",
                    'darija': "Achno l mochkil? (écran mkser / batterie / haja khra...)",
                    'en': "What's the issue? (broken screen / battery / other...)"
                },
                'urgency': {
                    'fr': "Est-ce urgent ?",
                    'darija': "Wach mosta3jel?",
                    'en': "Is it urgent?"
                }
            }
        },
        IntentType.COMMANDE: {
            'required': ['full_name', 'phone_number', 'delivery_address'],
            'optional': [],
            'questions': {
                'full_name': {
                    'fr': "Parfait ! Pour finaliser la commande, quel est votre Nom et Prénom ?",
                    'darija': "Mezyan bezzaf! Bach nkemlo l'commande, achno smia w l-kenya dyalk?",
                    'en': "Perfect! To finalize the order, what is your Full Name?"
                },
                'phone_number': {
                    'fr': "Quel est votre numéro de téléphone pour la livraison ?",
                    'darija': "Achno ra9m l-hatif dyalk l-livraison?",
                    'en': "What is your phone number for delivery?"
                },
                'delivery_address': {
                    'fr': "Quelle est votre adresse exacte de livraison ?",
                    'darija': "Achmen cinouane bghiti nssiftouh fih?",
                    'en': "What is your exact delivery address?"
                }
            }
        },
        IntentType.INFO_CREDIT: {
            'required': ['professional_situation'],
            'optional': [],
            'questions': {
                'professional_situation': {
                    'fr': "Pour vous lister les documents nécessaires pour notre Crédit Gratuit 0 % (étude sous 24h), quelle est votre situation ? (Salarié privé, Fonctionnaire/Retraité ou Indépendant)",
                    'darija': "Bach n3tik la liste dyal wra9 dyal Crédit Gratuit 0 % (réponse f 24h), chno hiya l'wa33iya dyalk? (Salarié privé, Fonctionnaire/Retraité wla Indépendant)",
                    'en': "To list the documents for our 0% Free Credit (24h study), what is your situation? (Private employee, Civil servant/Retired, or Independent)"
                }
            }
        },
        IntentType.ORDER_TRACKING: {
            'required': ['order_name'],
            'optional': ['email_search', 'phone_number'],
            'questions': {
                'order_name': {
                    'fr': "Bien sûr ! Pouvez-vous me donner votre numéro de commande (ex: #1234) ?",
                    'darija': "Wakha! Momkin t3tini raqm l-commande dyalk (matalan #1234)?",
                    'en': "Of course! Could you provide your order number (e.g., #1234)?"
                },
                'email_search': {
                    'fr': "Pour vérifier votre identité, quel est l'email utilisé pour la commande ?",
                    'darija': "Bach n'verifiw, chno houwa l-email li derti f l-commande?",
                    'en': "To verify your identity, what email was used for the order?"
                }
            }
        },
    }
    
    # Credit documents configuration
    CREDIT_DOCS = {
        'common': {
            'fr': [
                "Copie CIN",
                "Justificatif d'adresse",
                "3 derniers relevés bancaires",
                "Spécimen de chèque ou Attestation de RIB",
                "Fiche signalétique (que je peux vous envoyer)"
            ],
            'darija': [
                "Copie CIN",
                "Justificatif d'adresse",
                "3 les derniers relevés bancaires",
                "Spécimen de chèque wla Attestation dyal RIB",
                "Fiche signalétique (n9der nssiftha lik)"
            ]
        },
        'salarié': {
            'fr': ["2 derniers bulletins de paie", "Attestation de travail", "Attestation de salaire", "Attestation CNSS"],
            'darija': ["2 les derniers bulletins de paie", "Attestation dyal khedma", "Attestation dyal salaire", "Attestation dyal CNSS"]
        },
        'fonctionnaire': {
            'fr': ["Attestation de salaire ou de pension", "État d'engagement"],
            'darija': ["Attestation dyal salaire wla pension", "État d'engagement"]
        },
        'retraité': {
            'fr': ["Attestation de pension", "État d'engagement"],
            'darija': ["Attestation dyal pension", "État d'engagement"]
        },
        'indépendant': {
            'fr': ["Carte professionnelle", "Registre du commerce (RC)"],
            'darija': ["Carte professionnelle", "Registre du commerce (RC)"]
        }
    }
    
    # Response templates per intent (fallback if LLM fails)
    RESPONSE_TEMPLATES = {
        IntentType.SALES_ACHAT: {
            'greeting': {
                'fr': "Quel modèle cherchez-vous ? Paiement Cash ou crédit gratuit ? 🤩",
                'darija': "Chno khsk bdebt? Payer Cash wla baghi tchouf crédit gratuit? 🤩",
                'en': "What model are you looking for? Cash payment or free credit? 🤩"
            },
            'handoff': {
                'fr': "Super ! Je t'envoie un conseiller pour finaliser tout ça. 🎯",
                'darija': "Mezyan bezzaf! Wa7ed mn l'équipe ghadi yatsel bik bach nkemlo. 🎯",
                'en': "Great! Connecting you with an advisor to finalize. 🎯"
            }
        },
        IntentType.TRADEIN: {
            'greeting': {
                'fr': "On peut racheter votre appareil. Quel modèle avez-vous ? 💰",
                'darija': "N9dro nchriw l'appareil dyalk. Achno 3ndk? 💰",
                'en': "We can buy your device. What model do you have? 💰"
            },
            'handoff': {
                'fr': "Parfait ! Un expert va évaluer votre appareil et vous proposer un prix. 💵",
                'darija': "Mezyan! Wa7ed expert ghadi y9ayem tilifoun dyalek w y3tik prix. 💵",
                'en': "Perfect! An expert will evaluate your device and offer you a price. 💵"
            }
        },
        IntentType.REPARATION: {
            'greeting': {
                'fr': "Je comprends, nous pouvons vous aider avec la réparation. 🔧",
                'darija': "Fhemt, n9drou n3awnoukoum f réparation. 🔧",
                'en': "I understand, we can help you with the repair. 🔧"
            },
            'handoff': {
                'fr': "Un technicien va vous contacter pour un diagnostic et un devis. 🛠️",
                'darija': "Wa7ed technicien ghadi yatsel bik bach y3tik devis. 🛠️",
                'en': "A technician will contact you for a diagnosis and quote. 🛠️"
            }
        },
        IntentType.PRODUCT_INFO: {
            'brief': {
                'fr': "Je suis là pour vous renseigner sur nos produits ! 📍",
                'darija': "Ana hna bach n3awnek t3ref l-prix w l-état dyal l-produit! 📍",
                'en': "I'm here to give you info about our products! 📍"
            }
        },
        IntentType.LOCATION_DELIVERY: {
            'brief': {
                'fr': "On livre partout au Maroc et on est à Maarif ! 📍",
                'darija': "L'adresse dyalna f Maarif w n9dro nssiftoulek tal l-dar! 📍",
                'en': "We deliver everywhere in Morocco and we are located in Maarif! 📍"
            }
        },
        IntentType.HUMAIN: {
            'handoff': {
                'fr': "Bien sûr ! Je vous mets en contact avec un conseiller. 👤",
                'darija': "Wakha! Ghadi nweslek m3a wa7ed mn l'équipe. 👤",
                'en': "Of course! I'll connect you with an advisor. 👤"
            }
        },
        IntentType.ORDER_TRACKING: {
            'status_present': {
                'fr': "Voici le statut de votre commande {order_id} :\n- État : {status}\n- Produit : {product}\n{tracking}",
                'darija': "Hahouwa l-statut dyal l-commande {order_id} :\n- l-7ala : {status}\n- Produit : {product}\n{tracking}",
            },
            'not_found': {
                'fr': "Désolé, je ne trouve pas de commande correspondant à ces informations. Un conseiller va vérifier pour vous.",
                'darija': "Sma7 lia, mal9itech l-commande b had l'ma3loumat. Wa7ed mn l'équipe ghadi ychouf m3ak.",
            },
            'auth_failed': {
                'fr': "L'email ne correspond pas à cette commande. Pour des raisons de sécurité, je ne peux pas afficher les détails. Un conseiller peut vous aider.",
                'darija': "L-email mamataba9ch m3a l-commande. Ma9dertch n'affichi les détails s7it l-protection dyal l'ma3loumat. Chi wa7ed mn l'équipe ghadi y3awnek.",
            }
        },
        IntentType.INFO_CREDIT: {
            'brief': {
                'fr': "Chez ReLab, on propose le **Crédit Gratuit 0%** sur 12 mois. C'est simple : pas d'intérêts, pas de frais cachés. Réponse en 24h après étude. 💳",
                'darija': "F ReLab, 3ndna **Crédit Gratuit 0%** 3la 12 chhar. Mafih la intérét la walo. L-jawab ka ikoun f 24h. 💳",
            },
            'footer': {
                'fr': "On peut démarrer le dossier ? Tu es salarié, fonctionnaire ou indépendant ?",
                'darija': "Nbdaou l-dossier? Wach ntoma salarié, fonctionnaire wla indépendant?",
            }
        },
        IntentType.CREDIT_DOCUMENTS: {
            'brief': {
                'fr': "Voici les documents pour constituer votre dossier de Crédit 0%. 📄",
                'darija': "Hahouma l-wra9 li khssk bach tdfa3 l-Crédit 0%. 📄",
            }
        }
    }
    
    @staticmethod
    def get_question(intent: IntentType, field: str, language: str) -> str:
        """Get qualification question for a field"""
        lang_key = language if language in ['fr', 'darija', 'en'] else 'fr'
        
        if intent in BusinessRules.QUALIFICATION_FIELDS:
            questions = BusinessRules.QUALIFICATION_FIELDS[intent].get('questions', {})
            if field in questions:
                return questions[field].get(lang_key, questions[field]['fr'])
        
        return ""
    
    @staticmethod
    def get_template(intent: IntentType, template_type: str, language: str) -> str:
        """Get response template"""
        lang_key = language if language in ['fr', 'darija', 'en'] else 'fr'
        
        if intent in BusinessRules.RESPONSE_TEMPLATES:
            templates = BusinessRules.RESPONSE_TEMPLATES[intent]
            if template_type in templates:
                return templates[template_type].get(lang_key, templates[template_type]['fr'])
        
        return ""


# Global instance
business_rules = BusinessRules()
