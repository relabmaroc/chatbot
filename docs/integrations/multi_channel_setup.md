# Guide de Configuration Multi-Canal (Relab)

Ce guide détaille les étapes pour activer Instagram, WhatsApp et l'Email sur votre chatbot.

## 1. Instagram & WhatsApp (Meta Developer Portal)

Les deux canaux utilisent la plateforme Meta Graph API.

### Étapes :
1. **Créer une App** : Allez sur [Meta for Developers](https://developers.facebook.com/) et créez une application de type "Business".
2. **Ajouter les Produits** : Ajoutez "Instagram Graph API" et "WhatsApp".
3. **Configuration du Webhook** :
   - URL de rappel : `https://votre-app.railway.app/webhook/instagram` (ou `/whatsapp`)
   - Jeton de vérification : Choisissez un texte (ex: `relab_secret_2024`) et ajoutez-le à votre fichier `.env` (`INSTAGRAM_VERIFY_TOKEN`).
   - Abonnements aux domaines : Cochez `messages`.
4. **Générer un Jeton d'Accès** : Générez un jeton d'accès permanent pour votre page et ajoutez-le à `.env` (`INSTAGRAM_ACCESS_TOKEN`).

### Variables d'environnement Meta :
- `INSTAGRAM_VERIFY_TOKEN` / `WHATSAPP_VERIFY_TOKEN`
- `INSTAGRAM_ACCESS_TOKEN` / `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID` (Trouvé dans le tableau de bord WhatsApp Meta)

---

## 2. Email (Inbound Webhook)

Pour recevoir des emails, nous utilisons un système de Webhook (recommandé : SendGrid ou Postmark).

### Étapes (Exemple SendGrid) :
1. **Inbound Parse** : Allez dans Settings > Inbound Parse.
2. **Ajouter un domaine** : Configurez un sous-domaine (ex: `bot.relab.ma`) avec un enregistrement MX pointant vers SendGrid.
3. **URL du Webhook** : Pointez vers `https://votre-app.railway.app/webhook/email?token=relab-secure-token`.

### Variables d'environnement SMTP (pour répondre) :
- `SMTP_USER` : Votre adresse email (ex: `hello@relab.ma`).
- `SMTP_PASSWORD` : Votre mot de passe d'application.
- `SMTP_HOST` : `smtp.gmail.com` (pour Gmail/Workspace).
- `SMTP_PORT` : `587`.

---

## 🏗️ Architecture des Webhooks
- **Instagram** : `GET/POST /webhook/instagram`
- **WhatsApp** : `GET/POST /webhook/whatsapp`
- **Email** : `POST /webhook/email`

Toutes les conversations sont centralisées dans votre **Relab Dashboard** pour une gestion unifiée.
