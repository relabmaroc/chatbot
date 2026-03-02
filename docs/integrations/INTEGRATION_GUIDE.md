# 🔗 Guide d'Intégration Google Sheets + Documents

Ce guide vous explique comment connecter votre chatbot à:
1. **Google Sheets** - pour le stock en temps réel
2. **Documents de crédit** - déjà configurés !

---

## 📊 Partie 1: Google Sheets (Stock de Produits)

### Étape 1: Préparer votre Google Sheet

Créez un Google Sheet avec ces colonnes (exactement ces noms):

| Modèle | Grade | Prix | Stock | Disponible | Couleur | Stockage |
|--------|-------|------|-------|------------|---------|----------|
| iPhone 15 Pro | Excellent | 9500 | 5 | Oui | Noir | 256GB |
| iPhone 15 | Bon | 7500 | 3 | Oui | Bleu | 128GB |
| iPhone 14 Pro | Excellent | 7000 | 2 | Oui | Or | 512GB |
| iPhone 14 | Bon | 5500 | 8 | Oui | Blanc | 128GB |

**Colonnes obligatoires:**
- `Modèle` - Nom du produit (ex: iPhone 15 Pro)
- `Grade` - État (Neuf, Excellent, Bon, Correct)
- `Prix` - Prix en MAD (nombre ou "5500 MAD")
- `Stock` - Quantité disponible (nombre)
- `Disponible` - Oui/Non

**Colonnes optionnelles:**
- `Couleur` - Couleur du produit
- `Stockage` - Capacité (128GB, 256GB, etc.)

### Étape 2: Créer un Service Account Google

1. Allez sur: https://console.cloud.google.com/
2. Créez un nouveau projet (ex: "Relab Chatbot")
3. Activez l'API Google Sheets:
   - Menu → APIs & Services → Library
   - Cherchez "Google Sheets API"
   - Cliquez "Enable"
4. Créez un Service Account:
   - Menu → APIs & Services → Credentials
   - Create Credentials → Service Account
   - Nom: "relab-chatbot-sheets"
   - Rôle: Viewer
5. Créez une clé JSON:
   - Cliquez sur le service account créé
   - Keys → Add Key → Create new key → JSON
   - **Téléchargez le fichier JSON**

### Étape 3: Partager votre Google Sheet

1. Ouvrez votre Google Sheet
2. Cliquez sur "Partager"
3. Copiez l'email du service account (dans le fichier JSON: `client_email`)
4. Collez-le et donnez accès "Viewer"

### Étape 4: Configurer le Chatbot

1. **Créez le dossier credentials:**
```bash
mkdir "/Users/amineghaiti/Library/Mobile Documents/com~apple~CloudDocs/RELAB/CHATBOT AI/credentials"
```

2. **Copiez le fichier JSON téléchargé:**
Renommez-le en `google-service-account.json` et placez-le dans le dossier `credentials/`

3. **Ajoutez la configuration au fichier .env:**
```bash
# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials/google-service-account.json
GOOGLE_SHEETS_INVENTORY_URL=https://docs.google.com/spreadsheets/d/VOTRE_ID_ICI/edit
```

**Pour trouver l'URL:**
- Ouvrez votre Google Sheet
- Copiez l'URL complète (elle contient `/d/XXXXX/`)

### Étape 5: Installer les dépendances

```bash
cd "/Users/amineghaiti/Library/Mobile Documents/com~apple~CloudDocs/RELAB/CHATBOT AI"
source venv/bin/activate
pip install -r requirements-sheets.txt
```

### Étape 6: Tester la connexion

```bash
python -c "
from integrations.inventory import init_inventory
from config import settings

if settings.google_sheets_credentials_file:
    success = init_inventory(
        settings.google_sheets_credentials_file,
        settings.google_sheets_inventory_url
    )
    if success:
        print('✅ Connexion Google Sheets réussie!')
    else:
        print('❌ Erreur de connexion')
else:
    print('⚠️  Configuration Google Sheets manquante')
"
```

---

## 📄 Partie 2: Documents de Crédit (Déjà Configuré!)

Les documents suivants sont **déjà créés** dans le dossier `knowledge/`:

### ✅ credit_policy.json
Contient:
- Conditions de crédit (montant min: 3000 MAD)
- Durée max: 12 mois
- Taux d'intérêt: 0% sur 3 mois, 5% sur 6-12 mois
- Documents requis (CIN, justificatif revenu, etc.)
- En FR, Darija, et EN

### ✅ warranty.json
Contient:
- Durée de garantie: 12 mois
- Ce qui est couvert
- Ce qui est exclu
- Processus SAV

### ✅ faq.json
Contient:
- Questions fréquentes
- Horaires, adresse, paiements, etc.
- En FR, Darija, et EN

**Vous pouvez modifier ces fichiers** pour adapter les informations à votre entreprise!

---

## 🎯 Comment le Chatbot Utilise Ces Données

### Exemple 1: Recherche de Produit

**Client**: "Bghit nchri iPhone 15"

**Chatbot**:
1. Détecte l'intent "achat"
2. Cherche "iPhone 15" dans Google Sheets
3. Trouve les produits disponibles
4. Affiche les options avec prix et stock réels

**Réponse**:
```
📱 iPhone 15 disponible:

💎 Excellent - 9500 MAD (5 en stock)
✨ Bon - 7500 MAD (3 en stock)

Ch7al budget dyalek?
```

### Exemple 2: Question sur le Crédit

**Client**: "Wach n9der nkhles b crédit?"

**Chatbot**:
1. Détecte mention de "crédit"
2. Récupère les infos de `credit_policy.json`
3. Affiche les conditions

**Réponse**:
```
💳 Crédit disponible:
• Montant minimum: 3000 DH
• Durée max: 12 mois
• Conditions:
  - CIN valide
  - Justificatif de revenu
  - Acompte minimum 30%
  - Saken f Maroc
  - 3andek 21 3am wla ktar

Wa7ed mn l'équipe ghadi yatsel bik bach nkemmlo!
```

---

## 🔄 Mode Sans Google Sheets

Si vous ne configurez pas Google Sheets, le chatbot fonctionne quand même!

Il utilisera:
- ✅ Les documents de crédit (déjà configurés)
- ✅ La FAQ
- ✅ Les informations de garantie
- ⚠️ Mais ne pourra pas donner de prix/stock en temps réel

**Recommandation**: Configurez Google Sheets pour une expérience complète!

---

## 📝 Modifier les Documents

### Modifier la Politique de Crédit

Éditez `knowledge/credit_policy.json`:

```json
{
  "fr": {
    "min_amount": 5000,  // Changez le montant minimum
    "max_duration_months": 24,  // Changez la durée max
    ...
  }
}
```

### Ajouter une Question FAQ

Éditez `knowledge/faq.json`:

```json
{
  "fr": [
    {
      "question": "Nouvelle question?",
      "answer": "Réponse ici",
      "keywords": ["mot1", "mot2"]
    }
  ]
}
```

---

## ✅ Checklist de Configuration

- [ ] Google Sheet créé avec les bonnes colonnes
- [ ] Service Account Google créé
- [ ] Fichier JSON téléchargé
- [ ] Google Sheet partagé avec le service account
- [ ] Fichier JSON placé dans `credentials/`
- [ ] `.env` mis à jour avec les URLs
- [ ] Dépendances installées (`pip install -r requirements-sheets.txt`)
- [ ] Connexion testée
- [ ] Documents de crédit vérifiés/modifiés si nécessaire

---

## 🆘 Problèmes Courants

### "Permission denied" sur Google Sheets
→ Vérifiez que vous avez partagé le Sheet avec l'email du service account

### "File not found: credentials/..."
→ Vérifiez que le fichier JSON est bien dans le dossier `credentials/`

### "Invalid credentials"
→ Re-téléchargez le fichier JSON du service account

### Le chatbot ne trouve pas les produits
→ Vérifiez les noms de colonnes dans votre Google Sheet (respectez la casse)

---

**Besoin d'aide?** Les logs du serveur (`python main.py`) vous indiqueront si la connexion Google Sheets fonctionne!
