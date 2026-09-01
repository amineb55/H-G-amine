# Registre des dettes — Consultant QSE IA

Chaque entrée reste ici jusqu'à sa levée, avec son échéance. Une dette n'est
jamais supprimée sans un commit qui la lève explicitement.

| # | Dette | Origine | Échéance | Statut |
|---|---|---|---|---|
| D1 | **Couverture EN complète du site vitrine.** La v1 ne porte l'anglais que sur cinq pages clés (Accueil, Méthode, Évaluation HSE, Programme pilote, À propos) — arbitrage du propriétaire produit pour l'échéance de septembre, pas une révision du spec. Le §9.1 exige le site entier en FR et EN. | Cahier des charges §9.1 vs brief marketing §13, arbitré le 01/09/2026 | **Avant l'ouverture commerciale de décembre 2026** | Ouverte |
| D2 | **Resserrement de l'allowlist de vocabulaire.** `app/config.py` (valeurs par défaut des sélecteurs de backend) et deux messages de log opérateur dans `app/main.py` nomment « firestore » et « gcs ». Toléré et signalé dans `tests/test_vocabulary.py` ; à resserrer quand la surface de configuration sera retravaillée (P9). | Décision I1, confirmée par le propriétaire produit le 01/09/2026 | Phase 1 | Ouverte |
| D3 | **Acteur réel dans le journal d'audit.** Tant que l'authentification (I4) n'est pas livrée, les entrées du journal portent l'acteur `unauthenticated`. P1 exige l'acteur réel sur chaque validation. | I3 (multi-location avant authentification) | I4 | Ouverte |
