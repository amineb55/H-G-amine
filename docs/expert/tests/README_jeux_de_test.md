# Jeux de test annotés — gabarit (apport 11)

Ce dossier reçoit les jeux de test réels d'Amine. Le harnais d'évaluation les
lit pour calculer précision, rappel et accord de criticité, par règle et par
secteur. Rien n'est utilisable avant qu'Amine ait fourni des médias réels et
leurs annotations : aucun exemple synthétique ne doit être ajouté ici.

Le script `valider_et_exporter.py` du même dossier vérifie les YAML experts et
génère les classeurs Excel de relecture.

## 1. Photos et vidéos terrain — `tests/terrain/<secteur>/`

Un fichier `annotations.yaml` par secteur, une entrée par média :

```yaml
- media: industrie/IMG_0012.jpg          # chemin relatif ; aucune personne identifiable
  secteur: industrie
  contexte: "Atelier d'usinage, poste de fraisage, en production"
  constats_attendus:
    - regle: IND-01
      criticite: 4
      zone: "Fraiseuse au centre de l'image, carter arrière retiré"
      escalade_appliquee: [ESC-01]         # personne exposée visible
    - regle: IND-12
      criticite: 2
      zone: "Copeaux au sol côté droit"
  pieges:                                  # ce qui ressemble à une NC sans en être une
    - regle: IND-09
      raison: "Porte au fond fermée par une ventouse asservie à l'alarme, pas une cale"
  auteur: "Amine Boukha"
  date: 2026-09-15
```

Volume visé : 15 à 20 médias par secteur, avec au moins un média « sans aucune
NC » par secteur (mesure des faux positifs).

## 2. Systèmes documentaires anonymisés — `tests/documentaire/<client_anonyme>/`

Le dossier contient les documents (PDF, DOCX) et un `attendu.yaml` :

```yaml
organisme: "CLIENT-A (anonymisé)"
secteur: logistique
norme: 45001
couverture_attendue:
  45001-4.1: 60
  45001-5.2: 100
  45001-6.1.2.1: 25
  # ... une ligne par exigence applicable (0 / 25 / 60 / 100)
score_chapitre_attendu: {4: 55, 5: 70, 6: 40, 7: 60, 8: 35, 9: 30, 10: 45}
constats_audit_attendus:
  - exigence: 45001-6.1.2.2
    classification: NCM
    justification: "Grille de cotation absente, analyse non datée"
```

Volume visé : 2 à 3 systèmes, si possible de secteurs et de maturités différents.

## 3. Checklist terrain remplie — `tests/checklist/`

Une checklist réelle anonymisée (le format de l'application, mode B) et le
rapport consolidé attendu (`attendu.md`) : liste des constats, classification,
plan d'action. Sert à tester la consolidation.

## 4. Métriques calculées par le harnais

- Précision et rappel par règle et par secteur (constats attendus vs. détectés).
- Accord de criticité : part des constats détectés avec le même niveau que l'annotation (± 0 et ± 1).
- Taux de faux positifs sur les pièges et sur les médias sans NC.
- Écart moyen de couverture documentaire par exigence et par chapitre.
- Tout changement de prompt ou de règle doit être accompagné du rapport avant / après.
