# APPORTS DE L'EXPERT — CE QUE TU DOIS FOURNIR

**Complément du cahier des charges v1.0 — Consultant QSE IA**
**Destinataire :** Amine Boukha
**Objet :** tout ce que seul un praticien QSE peut fournir, dans le format exact où la plateforme le consomme, avec un exemple par apport et l'ordre dans lequel s'y prendre.

---

## 0. LE PARTAGE DES RÔLES

Le code, l'architecture, l'infrastructure, les tests, le site, le design : c'est le travail de l'agent de code, cadré par le cahier des charges.

Ce document liste **l'autre moitié** : le contenu métier que personne ne peut inventer à ta place. C'est l'actif de l'entreprise. Rien de ce qui suit ne doit être généré par une IA puis accepté sans relecture — c'est précisément ce que tes concurrents feront, et c'est ce qui rendra leurs produits génériques.

Règle de travail : tu produis, je structure et je relis, Claude Code intègre. Tu n'as rien à formater parfaitement — un fichier Excel ou un texte brut suffit, la mise en forme est mon travail.

---

## 1. VUE D'ENSEMBLE

| # | Apport | Priorité | Temps estimé | Bloque quoi |
|---|---|---|---|---|
| 1 | Modèle d'exigences ISO 45001 | Immédiate | 8–12 h | Tout : Services 1, 2, 3 |
| 2 | Modèles 9001, 14001 et 50001 (HLS commun + spécifique) | Phase 0 | 9–14 h | Services 1 et 2 multi-normes, offre énergie |
| 3 | Référentiels terrain — 4 secteurs restants | Phase 1 | 3–4 h | Service 3 hors bureaux/BTP |
| 4 | Questions du formulaire de cadrage | Phase 0 | 3–4 h | Service 1 |
| 5 | Structures types des documents | Phase 2 | 4–6 h | Service 1 |
| 6 | Échelles et barèmes | Phase 0 | 2 h | Services 2 et 3 |
| 7 | Arbre de décision des outils qualité | Phase 1 | 1–2 h | Plans d'action |
| 8 | Sources réglementaires Maroc | Phase 1 | 3–4 h | Veille |
| 9 | Glossaire FR/EN | Phase 0 | 2–3 h | Interface, documents |
| 10 | Identité, juridique, coordonnées | Phase 0 | 2 h | Site vitrine, CGV |
| 11 | Jeux de test réels annotés | Phase 0–1 | 4–6 h | Mesure de la qualité |
| 12 | Pilotes | Phase 0 | 2–3 h de contacts | Tout retour terrain |

Total : environ **45 à 60 heures** de travail d'expert, étalées sur septembre et octobre. L'apport 1 conditionne tout ; commence par lui.

---

## 2. APPORT 1 — LE MODÈLE D'EXIGENCES ISO 45001

### 2.1 Ce que c'est

Chaque exigence auditable de la norme, **reformulée dans tes mots**, avec ce qu'un auditeur vérifie, ce qu'il demande comme preuve, et les questions qu'il pose. C'est le cœur de la plateforme : les trois services s'y branchent.

### 2.2 La règle de reformulation — droit d'auteur

Les normes ISO sont protégées. La plateforme **ne doit jamais contenir une phrase de la norme**. Ce n'est pas un détail : c'est ce qui peut faire fermer le produit.

**Comment reformuler légalement :** écris l'exigence comme **ce qu'un auditeur constate quand elle est satisfaite**, pas comme l'injonction de la norme.

| À ne pas faire | À faire |
|---|---|
| Recopier la phrase de la norme en changeant deux mots | Décrire l'état attendu : « Un processus d'identification des dangers est en place, appliqué, et tenu à jour. » |
| Reprendre les notes, les annexes, les définitions | Écrire tes propres définitions dans le glossaire |
| Structurer en « L'organisme doit… » | Structurer en état constaté, preuve, question |
| Citer une liste de la norme item par item | Reformuler les items en catégories dans tes mots |

Test simple : si ta phrase pouvait figurer telle quelle dans un support de formation que tu as toi-même rédigé sans autorisation d'ISO, c'est une reformulation. Si tu hésites, c'est probablement trop proche.

### 2.3 Le format

Un enregistrement par exigence. Tu peux travailler dans Excel avec ces colonnes, dans cet ordre ; Claude Code écrira le convertisseur.

| Colonne | Contenu | Obligatoire |
|---|---|---|
| `id` | norme-clause, ex. `45001-6.1.2.1` | Oui |
| `chapitre` | 4 à 10 | Oui |
| `titre_fr` | Titre court de l'exigence, dans tes mots | Oui |
| `titre_en` | Traduction | Oui (je peux la faire) |
| `exigence_fr` | 2 à 5 lignes : l'état attendu, reformulé | Oui |
| `exigence_en` | Traduction | Oui (je peux la faire) |
| `type` | `documentaire` / `mise_en_oeuvre` / `enregistrement` | Oui |
| `preuves_attendues` | Liste : ce que tu demandes en audit | Oui |
| `questions_audit` | 2 à 4 questions que tu poses réellement | Oui |
| `documents_types` | Quel document couvre normalement cette exigence | Oui |
| `hls_commun` | oui / non — partagée avec 9001 et 14001 | Oui |
| `equivalences` | ids 9001 et 14001 correspondants, si commun | Si commun |
| `applicabilite` | `tous` ou liste de secteurs ; conditions d'exclusion | Oui |
| `regles_terrain` | ids de règles d'inspection dérivées, si pertinent | Non |
| `erreurs_frequentes` | Ce que tu vois rater le plus souvent en audit | Fortement conseillé |
| `poids` | 1 (mineur) à 3 (structurant) pour la pondération du score | Oui |

### 2.4 Exemple complet — un enregistrement rédigé selon la règle

```yaml
id: 45001-6.1.2.1
chapitre: 6
titre_fr: Identification des dangers
titre_en: Hazard identification
exigence_fr: >
  L'organisme dispose d'une méthode structurée, appliquée et actualisée, pour
  repérer les dangers liés à ses activités. Cette méthode couvre les situations
  normales et anormales, les situations d'urgence, les personnes présentes sur
  site quel que soit leur statut, l'organisation du travail et les facteurs
  humains, les équipements et l'environnement de travail, ainsi que les
  changements prévus. Elle prend en compte les incidents passés.
exigence_en: >
  The organisation applies a structured, current method to identify the hazards
  arising from its activities. The method covers routine and non-routine
  situations, emergencies, everyone present on site regardless of status, work
  organisation and human factors, equipment and the working environment, and
  planned changes. It takes past incidents into account.
type: mise_en_oeuvre
preuves_attendues:
  - Procédure ou méthode d'identification des dangers, datée et approuvée
  - Registre ou inventaire des dangers par activité et par zone
  - Traces de mise à jour après changement, incident ou nouvelle activité
  - Participation des travailleurs visible (comptes rendus, signatures)
questions_audit:
  - Comment identifiez-vous les dangers d'une nouvelle activité avant son démarrage ?
  - Montrez-moi la dernière mise à jour de votre inventaire des dangers et ce qui l'a déclenchée.
  - Les sous-traitants et visiteurs sont-ils couverts ? Où ?
  - Quel incident récent a modifié votre analyse ?
documents_types:
  - procedure_identification_dangers
  - registre_dangers
  - analyse_risques
hls_commun: non
equivalences: []
applicabilite: tous
regles_terrain: [BTP-01, BTP-02, BTP-08, BUR-02]
erreurs_frequentes: >
  Inventaire fait une fois à la certification et jamais mis à jour ; sous-traitants
  oubliés ; situations d'urgence traitées dans un autre document sans lien ;
  aucune trace de consultation des travailleurs.
poids: 3
```

Remarque : aucune phrase de cet exemple n'est celle de la norme. Le contenu est celui que tu enseignerais.

### 2.5 L'ordre de travail

1. **Chapitres 6, 8, 9, 10** — planification, réalisation, évaluation, amélioration. Ce sont les plus audités et ceux qui portent les Services 2 et 3.
2. **Chapitres 4, 5, 7** — contexte, leadership, support.
3. Marque `hls_commun: oui` dès que l'exigence existe aussi en 9001 et 14001 : tu ne l'écriras qu'une fois.

Volume attendu : environ 60 à 70 enregistrements pour 45001.

### 2.6 Livraison

Un fichier Excel `exigences_45001.xlsx`, ou un fichier texte par exigence. Placé dans `docs/expert/exigences/`. Je relis chaque enregistrement avant intégration : cohérence, reformulation, traduction.

---

## 3. APPORT 2 — MODÈLES 9001, 14001 ET 50001

Même format. Grâce au tronc commun HLS, tu ne rédiges que :

- les exigences **spécifiques** à chaque norme :
  - 9001 : exigences clients, conception et développement, maîtrise des produits et services non conformes, satisfaction client, prestataires externes ;
  - 14001 : aspects et impacts environnementaux, obligations de conformité, perspective de cycle de vie, communication externe, préparation aux situations d'urgence environnementale ;
  - 50001 : revue énergétique, usages énergétiques significatifs, situation énergétique de référence, indicateurs de performance énergétique, collecte des données énergétiques, conception et achats tenant compte de l'énergie, plan de mesure ;
- les **nuances** des exigences communes quand elles diffèrent réellement (ex. la politique : mêmes engagements de structure, engagements de fond différents).

Volume attendu : 25 à 35 enregistrements spécifiques par norme, plus les ajustements de nuance.

**Point d'honnêteté sur 50001.** Tu es certifié 9001, 14001 et 45001. Pour l'énergie, deux options : acquérir la qualification (formation auditeur 50001, quelques jours), ou faire valider ton jeu d'exigences par un auditeur énergie partenaire avant mise en production. La plateforme affichera le nom et la qualification du validateur de chaque norme — c'est un gage de sérieux, pas une contrainte. Même règle, plus tard, pour ISO 14064-1 (bilan carbone) : c'est un domaine à part, avec ses facteurs d'émission et ses méthodes de calcul, qui exige un praticien du carbone.

**Données spécifiques à collecter pour l'énergie**, à intégrer au formulaire de cadrage (apport 4) : sources d'énergie et compteurs, factures sur douze mois, équipements les plus consommateurs, variables d'influence (production, météo, occupation), projets d'efficacité en cours. Sans ces données, aucune revue énergétique n'est possible, et l'agent doit refuser de la générer.

---

## 4. APPORT 3 — RÉFÉRENTIELS TERRAIN, QUATRE SECTEURS

Tu as déjà rédigé les tableaux bureaux et BTP, ils sont intégrés. Il reste **industrie, santé, logistique, hôtellerie-restauration** dans le format existant (`app/rules/*.yaml`), 12 règles chacun. Pour chaque règle, ajoute deux champs nouveaux :

- `indices_visuels` — ce que le moteur doit repérer sur une image pour lever la règle (« bouteille de gaz non arrimée », « produit sans étiquette sur étagère », « issue obstruée »). C'est ce qui améliore le plus la détection.
- `exclusions` — situations qui ressemblent à une NC mais n'en sont pas (« zone en cours de nettoyage signalée », « stockage temporaire balisé »). C'est ce qui réduit les faux positifs.

Rappelle-toi que l'échelle de criticité par défaut de chaque règle n'est qu'un point de départ : le moteur escalade selon la situation observée.

---

## 5. APPORT 4 — LES QUESTIONS DU FORMULAIRE DE CADRAGE

Le formulaire (cahier des charges §4.1.1) a huit sections. J'en fournis la structure ; tu fournis **les questions qui font la différence entre un manuel spécifique et un manuel générique**. Pour chaque section :

- les questions à poser à tout organisme ;
- les questions **par secteur** (ce qu'il faut savoir d'un chantier qu'on ne demande pas à un bureau) ;
- pour chaque question, ce que la réponse alimente (quel document, quelle exigence) ;
- le **seuil minimal** : quelles questions doivent être remplies avant que la génération soit autorisée.

Exemple de question sectorielle utile, section Processus, secteur BTP : « Qui autorise le démarrage d'une tâche en hauteur, et sur quel document ? » — la réponse alimente la procédure de maîtrise opérationnelle et l'exigence 8.1.

---

## 6. APPORT 5 — STRUCTURES TYPES DES DOCUMENTS

Pour chaque type de document que le Service 1 produit, il me faut **ton sommaire type** — la structure que tu utilises et que les certificateurs acceptent :

- politique (engagements obligatoires, longueur, signature) ;
- fiche processus (rubriques) ;
- procédure (sommaire, niveau de détail, ce qui doit y figurer pour être auditable) ;
- instruction de travail ;
- enregistrement / formulaire ;
- programme d'audit, plan d'audit, rapport d'audit ;
- compte rendu de revue de direction (les entrées et sorties attendues) ;
- analyse des risques (colonnes de ta grille).

Et, si tu en as, **deux ou trois exemples anonymisés de bons documents** que tu as produits. C'est la référence de style la plus précieuse : l'agent produira dans ton style, pas dans un style générique.

---

## 7. APPORT 6 — ÉCHELLES ET BARÈMES

À fixer une fois, par écrit, parce que toute la cotation en dépend :

1. **Criticité des constats** — les quatre niveaux existent ; confirme les délais par niveau et ajoute les critères d'escalade que tu appliques (cumul de dangers, étendue, nombre de personnes exposées).
2. **Cotation des risques** — ta grille (gravité × probabilité × exposition ou autre), ses échelles, ses seuils d'acceptabilité.
3. **Classification des NC d'audit** — tes critères majeure / mineure / observation / point fort, avec un exemple de chaque.
4. **Couverture documentaire** — les quatre degrés (0/25/60/100) : donne un exemple de document à chaque degré pour une même exigence.
5. **Pondération** — le champ `poids` du modèle d'exigences : quelles exigences pèsent le plus dans un score.

---

## 8. APPORT 7 — ARBRE DE DÉCISION DES OUTILS QUALITÉ

Une table : nature de la NC → outil d'analyse → livrable attendu.

| Nature de la NC | Outil | Livrable |
|---|---|---|
| Ponctuelle, cause évidente | Correction directe | Action, responsable, délai |
| Récurrente | 5 Pourquoi | Chaîne causale, action sur la cause racine |
| Multifactorielle | Ishikawa | Diagramme, causes retenues, actions |
| Volume élevé de NC hétérogènes | Pareto | Priorisation des 20 % de causes |
| Risque à évaluer avant action | AMDEC | Grille, criticité, plan |
| Incident grave | Arbre des causes | Faits, enchaînement, mesures |

Complète, corrige, ajoute les cas que tu rencontres. Précise pour chaque outil ce que l'agent peut préremplir et ce qui doit rester à la main de l'humain.

---

## 9. APPORT 8 — SOURCES RÉGLEMENTAIRES MAROC

Pour la veille (P5), il me faut de toi :

1. **L'adresse exacte** de chaque source officielle utilisable : Bulletin officiel, portail du SGG, sites ministériels qui publient les textes consolidés — avec ton avis sur leur fiabilité et leur fraîcheur.
2. **La liste des textes structurants** SST, environnement, données : numéro, intitulé, date, domaine, à qui ils s'appliquent. Pas le texte — la référence.
3. **Le rattachement** de chaque texte aux exigences du modèle (quel texte alimente quelle clause).
4. Les cas où **aucune source officielle exploitable n'existe** : c'est là que l'utilisateur devra téléverser le texte.

---

## 10. APPORT 9 — GLOSSAIRE FR/EN

Cent à cent cinquante termes QSE, avec ta définition en français, la traduction anglaise **d'usage professionnel** (pas littérale), et les faux amis à éviter. Ce glossaire sert à l'interface, aux documents, et à la page publique qui sera citée par les moteurs génératifs. Il doit être dans tes mots — c'est aussi une protection contre le droit d'auteur des définitions normatives.

---

## 11. APPORT 10 — IDENTITÉ ET JURIDIQUE

- Nom définitif du produit et nom de domaine (vérifier la disponibilité en `.com`, `.ma`, `.ai`).
- Logo ou brief pour le créer ; couleurs si tu veux t'écarter de la palette actuelle.
- Structure juridique porteuse, coordonnées, numéro d'identification, pays d'établissement — pour les CGV, la politique de confidentialité, les factures.
- Ton conseil juridique de référence pour valider les CGV et le contrat de sous-traitance de données (loi 09-08, RGPD si clients européens). Je rédige les projets ; un juriste les valide.
- Ta biographie professionnelle et tes certifications, pour la page « À propos » — c'est un élément de crédibilité mesuré par les moteurs de recherche.

---

## 12. APPORT 11 — JEUX DE TEST RÉELS ANNOTÉS

C'est ce qui permet de **mesurer** la qualité au lieu de la déclarer (cahier des charges §12).

1. **Photos et vidéos par secteur** — 15 à 20 par secteur, prises par toi, avec pour chacune la liste des NC qu'un auditeur doit y relever, leur criticité, et les pièges (ce qui ressemble à une NC mais n'en est pas). Aucune personne identifiable, ou floutée.
2. **Deux ou trois systèmes documentaires anonymisés** — d'anciens clients ou reconstitués — avec le score de couverture que tu leur attribuerais, chapitre par chapitre. C'est le jeu de test du Service 2 mode A.
3. **Une checklist terrain remplie** réelle, anonymisée, pour tester la consolidation du mode B.

Sans ces jeux, on ne saura jamais si le moteur s'améliore ou se dégrade.

---

## 13. APPORT 12 — LES PILOTES

Cinq organisations pour septembre : deux consultants, trois entreprises de secteurs différents. Pour chacune : nom, secteur, taille, contact, ce qu'elle attend, ce qu'elle accepte de tester, et ce qu'on lui promet en échange (gratuité, accompagnement, tarif préférentiel ensuite). Un accord écrit simple, même d'une page.

---

## 14. CE QUE JE FAIS DE MON CÔTÉ

Pour que la répartition soit claire :

- Je traduis en anglais tout ce que tu rédiges en français.
- Je structure tes apports dans les formats que la plateforme consomme.
- Je relis chaque exigence pour la reformulation et la cohérence, et je te signale ce qui me semble trop proche de la norme.
- Je rédige les projets de CGV, de politique de confidentialité, de dossier CNDP/CSE, de pages du site vitrine.
- Je prépare chaque prompt de développement en le rattachant au cahier des charges.
- Je ne rédige **jamais** à ta place une exigence, une règle terrain, un barème ou une définition : je peux te proposer un brouillon à corriger, mais la version retenue est la tienne.

---

## 15. PROMPT DE REMISE À CLAUDE CODE

À utiliser une fois les apports 1, 4, 6 et 9 livrés et relus (les autres suivent par phase). À coller après le prompt fondation de l'annexe A du cahier des charges.

```
The QSE expert's inputs are now in docs/expert/. Integrate them as data, not
code, and treat every file there as the single source of truth for its domain.

docs/expert/exigences/        requirements model (Excel or YAML per record)
docs/expert/regles_terrain/   sector rule sets (existing format + indices_visuels,
                              exclusions)
docs/expert/formulaire/       framing-form questions with section, sector,
                              feeds (document / requirement), and minimum-threshold flag
docs/expert/baremes/          severity levels and deadlines, risk-rating grid,
                              NC classification, coverage degrees, weights
docs/expert/outils_qualite/   NC nature → tool → deliverable decision table
docs/expert/glossaire/        FR/EN glossary
docs/expert/tests/            annotated media sets and documentary sets with
                              expected results

For each folder:
1. Write a loader with strict validation: unknown fields, missing mandatory
   fields, duplicate ids, unknown cross-references (equivalences, regles_terrain,
   documents_types) all fail loudly with the offending record named.
2. Add a copyright guard: a test that fails if any requirement text matches
   known standard phrasing patterns provided in docs/expert/guard/ (the expert
   maintains that list). Do not weaken this test to make it pass.
3. Expose the loaded data through the neutral interfaces already in place;
   no module reads these files directly except the loader.
4. Build the evaluation harness from docs/expert/tests/: run the analysis on
   every annotated item, compare with expected findings and severities, and
   output precision, recall and severity-agreement per rule and per sector.
   This harness becomes a required check before any prompt or rule change is
   merged.
5. Where an expert input contradicts the specification, stop and report the
   conflict with both texts quoted; do not choose.
6. Where an expert input is missing for a domain the code needs, generate
   nothing: leave an explicit "expert content pending" marker that is visible
   in the UI and blocks production use of that feature.

Report, per folder: records loaded, validation errors, cross-reference gaps,
and any record the copyright guard flagged for the expert's review.
```

---

*Commence par l'apport 1, chapitre 6 d'ISO 45001. Envoie-moi les cinq premiers enregistrements avant d'aller plus loin : on calera ensemble le niveau de reformulation et de détail, puis tu enchaîneras sur le reste avec une référence validée.*
