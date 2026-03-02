# Credit Flow (Financement 0%)

1. **Inquiry** : `info_credit`.
2. **Qualification** : `credit_eligibility`. 
   - Backend vérifie Salaire > 2500 MAD et Type de contrat.
3. **Documents** : `credit_documents`.
   - Backend génère un lien de téléchargement (ou demande photos).
4. **Handoff** : Dès que les documents sont cités ou que le profil est OK.
