# 🔧 Configuration de Votre Google Sheet - Guide Pas à Pas

Votre Google Sheet: https://docs.google.com/spreadsheets/d/1uuiuTTVnIzqmsYNFctr6saKuDOu6Z5IFbLw7IQVOAko/edit

✅ **Déjà fait**: L'URL est configurée dans le chatbot!

## 📋 Étapes Restantes (10 minutes)

### Étape 1: Créer un Service Account Google

1. **Allez sur Google Cloud Console**:
   - Ouvrez: https://console.cloud.google.com/

2. **Créez un nouveau projet**:
   - Cliquez sur le menu déroulant en haut (à côté de "Google Cloud")
   - Cliquez "NEW PROJECT"
   - Nom du projet: `Relab Chatbot`
   - Cliquez "CREATE"

3. **Activez l'API Google Sheets**:
   - Dans le menu ☰ (hamburger), allez dans: **APIs & Services** → **Library**
   - Cherchez: `Google Sheets API`
   - Cliquez dessus
   - Cliquez **"ENABLE"**

4. **Créez un Service Account**:
   - Dans le menu ☰, allez dans: **APIs & Services** → **Credentials**
   - Cliquez **"CREATE CREDENTIALS"** → **"Service Account"**
   - Nom: `relab-chatbot-sheets`
   - Description: `Service account for Relab chatbot to read inventory`
   - Cliquez **"CREATE AND CONTINUE"**
   - Rôle: Sélectionnez **"Viewer"** (ou laissez vide)
   - Cliquez **"DONE"**

5. **Téléchargez la clé JSON**:
   - Dans la liste des Service Accounts, cliquez sur celui que vous venez de créer (`relab-chatbot-sheets`)
   - Allez dans l'onglet **"KEYS"**
   - Cliquez **"ADD KEY"** → **"Create new key"**
   - Choisissez **"JSON"**
   - Cliquez **"CREATE"**
   - **Un fichier JSON sera téléchargé automatiquement** 📥

---

### Étape 2: Copier l'Email du Service Account

1. **Ouvrez le fichier JSON téléchargé** avec TextEdit
2. **Cherchez la ligne** `"client_email":`
3. **Copiez l'email** (il ressemble à: `relab-chatbot-sheets@xxxxx.iam.gserviceaccount.com`)

---

### Étape 3: Partager Votre Google Sheet

1. **Ouvrez votre Google Sheet**:
   https://docs.google.com/spreadsheets/d/1uuiuTTVnIzqmsYNFctr6saKuDOu6Z5IFbLw7IQVOAko/edit

2. **Cliquez sur le bouton "Partager"** (en haut à droite)

3. **Collez l'email du service account** que vous avez copié

4. **Changez le rôle en "Viewer"** (Lecteur)

5. **Décochez "Notify people"** (pas besoin d'envoyer un email)

6. **Cliquez "Partager"**

---

### Étape 4: Installer le Fichier JSON dans le Chatbot

1. **Créez le dossier credentials**:
   ```bash
   mkdir "/Users/amineghaiti/Library/Mobile Documents/com~apple~CloudDocs/RELAB/CHATBOT AI/credentials"
   ```

2. **Renommez le fichier JSON téléchargé**:
   - Nom actuel: probablement quelque chose comme `relab-chatbot-xxxxx.json`
   - Nouveau nom: `google-service-account.json`

3. **Déplacez le fichier**:
   - Glissez-déposez le fichier `google-service-account.json` dans le dossier:
   ```
   /Users/amineghaiti/Library/Mobile Documents/com~apple~CloudDocs/RELAB/CHATBOT AI/credentials/
   ```

---

### Étape 5: Installer les Dépendances Google Sheets

```bash
cd "/Users/amineghaiti/Library/Mobile Documents/com~apple~CloudDocs/RELAB/CHATBOT AI"
source venv/bin/activate
pip install -r requirements-sheets.txt
```

---

### Étape 6: Tester la Connexion

```bash
cd "/Users/amineghaiti/Library/Mobile Documents/com~apple~CloudDocs/RELAB/CHATBOT AI"
source venv/bin/activate
python -c "
from integrations.inventory import init_inventory
from config import settings

success = init_inventory(
    settings.google_sheets_credentials_file,
    settings.google_sheets_inventory_url
)

if success:
    print('✅ Connexion Google Sheets réussie!')
    from integrations.inventory import inventory_manager
    products = inventory_manager.get_products()
    print(f'📦 {len(products)} produits trouvés')
    if products:
        print(f'Exemple: {products[0]}')
else:
    print('❌ Erreur de connexion')
"
```

---

## 📊 Structure Attendue de Votre Google Sheet

Votre Google Sheet devrait avoir ces colonnes (première ligne = en-têtes):

| Modèle | Grade | Prix | Stock | Disponible | Couleur | Stockage |
|--------|-------|------|-------|------------|---------|----------|
| iPhone 15 Pro | Excellent | 9500 | 5 | Oui | Noir | 256GB |
| iPhone 15 | Bon | 7500 | 3 | Oui | Bleu | 128GB |

**Colonnes obligatoires**:
- `Modèle` - Nom du produit
- `Grade` ou `État` - État du produit
- `Prix` ou `Price` - Prix en MAD
- `Stock` ou `Quantité` - Nombre disponible
- `Disponible` - Oui/Non

**Colonnes optionnelles**:
- `Couleur` ou `Color`
- `Stockage` ou `Storage`

---

## ✅ Checklist

- [ ] Projet Google Cloud créé
- [ ] API Google Sheets activée
- [ ] Service Account créé
- [ ] Fichier JSON téléchargé
- [ ] Email du service account copié
- [ ] Google Sheet partagé avec le service account
- [ ] Dossier `credentials/` créé
- [ ] Fichier JSON renommé et déplacé
- [ ] Dépendances installées (`pip install -r requirements-sheets.txt`)
- [ ] Connexion testée

---

## 🎯 Après Configuration

Une fois configuré, le chatbot pourra:

**Client**: "Bghit nchri iPhone 15"

**Bot**: 
```
📱 iPhone 15 disponible:

💎 Excellent - 9500 MAD (5 en stock)
✨ Bon - 7500 MAD (3 en stock)

Ch7al budget dyalek?
```

Les prix et stocks seront **automatiquement mis à jour** depuis votre Google Sheet!

---

## 🆘 Problèmes Courants

### "Permission denied"
→ Vérifiez que vous avez bien partagé le Sheet avec l'email du service account

### "File not found: credentials/google-service-account.json"
→ Vérifiez que le fichier est bien dans le dossier `credentials/` avec le bon nom

### "Invalid credentials"
→ Re-téléchargez le fichier JSON du service account

### Le chatbot ne trouve pas les produits
→ Vérifiez que votre Google Sheet a bien les colonnes: Modèle, Prix, Stock, Disponible

---

**Besoin d'aide?** Suivez les étapes dans l'ordre et vérifiez chaque ✅
