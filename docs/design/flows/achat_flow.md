# Achat Flow (Tunnel de Vente)

1. **Détection** : `sales_achat` ou `product_info`.
2. **Action Backend** : 
   - Recherche stock (API Sheets).
   - Calcul mensualités (4x, 6m, 12m).
3. **Transition vers Commande** :
   - Si le client dit "Ok", "Je prends", "Livre moi".
   - Verrouiller l'item en stock temporairement.
4. **Transition vers Crédit** :
   - Si le client demande "Comment payer par mois" ou "Crédit gratuit".
