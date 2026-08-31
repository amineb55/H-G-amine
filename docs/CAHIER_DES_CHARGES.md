# CAHIER DES CHARGES — CONSULTANT QSE IA

**Version 1.0 — 31 août 2026**
**Propriétaire du produit :** Amine Boukha, QSE, ISO 9001 / 14001 / 45001
**Statut :** Document de référence produit et technique — base de développement
**Langue de travail :** français. Annexe A (prompt de développement) en anglais.

---

## 0. OBJET ET USAGE DE CE DOCUMENT

Ce cahier des charges définit la plateforme **Consultant QSE IA** : ce qu'elle fait, ce qu'elle refuse de faire, comment elle est construite, et dans quel ordre. Il sert de référence unique pour :

- le développement (chaque prompt donné à l'agent de code s'y rattache) ;
- les pilotes clients et consultants (ce qu'on leur promet, ce qu'on ne leur promet pas) ;
- les conditions générales et la documentation de conformité (données, vie privée, surveillance) ;
- l'arbitrage : toute demande de fonctionnalité qui contredit un principe de la section 2 est refusée ou renvoyée à une révision de ce document.

Le socle technique existant (agent d'inspection HSE : détection de secteur, analyse photo/vidéo, criticité à quatre niveaux, validation humaine, PDF, e-mails, Cloud Run, Firestore, Cloud Storage) constitue la **version 0** du Service 3 et la preuve d'architecture. Ce document en est l'extension.

---

## 1. VISION ET POSITIONNEMENT

### 1.1 Mission

Permettre à toute organisation, et à tout consultant, de concevoir, auditer et maintenir un système de management QSE aligné sur les normes ISO — en jours au lieu de semaines — avec la rigueur d'un praticien certifié, et sans jamais retirer à l'humain la décision.

### 1.2 Promesse

- **Pour le consultant :** faire en trois jours ce qui en prenait quinze, et suivre dix clients avec la capacité d'en suivre trois.
- **Pour l'entreprise :** disposer d'un système documentaire, d'un audit à blanc et d'une surveillance des risques HSE sans attendre la disponibilité d'un consultant, tout en gardant la validation d'un professionnel.

### 1.3 Ce que le produit est

Un agent qui réalise le travail **analytique et documentaire** d'un consultant QSE : diagnostic, cartographie, rédaction, audit documentaire, préparation d'audit terrain, consolidation, analyse des risques, veille, plans d'action, préparation de revue de direction — et qui **agit** : assigne, notifie, relance, escalade.

**Un seul système, trois portes d'entrée.** Commercialement, le produit se vend en trois services (documentation, audit, évaluation HSE) parce que les clients achètent des résultats nommables. Techniquement, c'est **un seul système connecté** : exigences → processus → risques et opportunités → documents → preuves → audits → non-conformités → actions → indicateurs → revue de direction → amélioration. Chaque service est une vue sur ce cœur commun, jamais une application séparée. La caméra, plus tard, n'est qu'une source de preuves supplémentaire pour ce même cœur.

### 1.4 Ce que le produit n'est pas, et ne promettra jamais

| Le produit ne… | Parce que… |
|---|---|
| …certifie pas | Seul un organisme accrédité certifie. |
| …n'affirme jamais qu'un système est « conforme » | La conformité porte sur ce qui est appliqué, pas sur ce qui est écrit. L'interface et les documents disent « couverture », « écart », « prêt à déployer », « auto-évaluation ». |
| …ne remplace pas la conviction de la direction ni la conduite du changement | C'est le cœur humain du métier de consultant. |
| …n'anime pas une formation en présence | Il produit les supports, les quiz, les fiches. |
| …n'identifie jamais une personne | Il détecte des situations, pas des fautes individuelles. |
| …ne reproduit jamais le texte d'une norme ISO | Les normes sont protégées par le droit d'auteur. |

Cette liste est publiée sur le site (page « Méthode »). Elle est un argument de crédibilité, pas une faiblesse.

### 1.5 Cibles

1. **Entreprises** — PME et ETI : industrie, BTP, tertiaire, santé, logistique, hôtellerie-restauration. Utilisateurs : responsable QSE/HSE, direction, pilotes de processus, responsables de zone.
2. **Consultants QSE** — indépendants et cabinets, gérant plusieurs clients.
3. Secondaire — groupes multi-sites, organismes de formation.

### 1.6 Niveau de qualité visé

L'agent vise une qualité **supérieure à la moyenne des livrables de consultants** sur les tâches analytiques et documentaires, mesurée par : exhaustivité contre le modèle d'exigences (100 % des exigences applicables traitées), traçabilité (chaque affirmation liée à une exigence, une preuve ou une source), cohérence (aucune contradiction entre documents), et zéro affirmation réglementaire sans source. Cette qualité est mesurée (section 12), pas déclarée.

---

## 2. PRINCIPES NON NÉGOCIABLES

Ces dix principes s'appliquent à tous les modules. Une fonctionnalité qui en viole un est refusée.

**P1 — L'agent propose, l'humain décide.** Aucun document, constat, criticité, règle, suggestion réglementaire ou modification d'apprentissage ne devient effectif sans validation humaine explicite. Même geste partout : garder / modifier / supprimer.

**P2 — Preuve avant affirmation.** Tout constat porte une preuve (image, extrait de document, référence) et un niveau de confiance. Sous le seuil, il est « à vérifier », jamais affirmé.

**P3 — Aucune personne identifiée.** Les constats désignent des situations, des zones, des rôles. Jamais un individu, jamais une description physique. Les visages sur les captures conservées sont floutés.

**P4 — Indépendance structurelle.** Le module qui rédige et le module qui vérifie sont séparés : prompts distincts, contextes distincts, espaces distincts dans l'interface. Le vérificateur ne lit que le modèle d'exigences et les preuves, jamais les instructions de rédaction. Principe d'ISO 19011.

**P5 — Source officielle unique.** Le module réglementaire ne s'appuie que sur la source officielle du pays. Si elle n'existe pas ou n'est pas exploitable, l'utilisateur fournit le texte et en atteste l'origine. Aucune suggestion sans source liée.

**P6 — Aucune reproduction de texte normatif.** Le modèle d'exigences contient des exigences **reformulées** et les numéros de clause. Jamais le texte de la norme. Les utilisateurs sont invités à se procurer les normes auprès des organismes officiels.

**P7 — Transparence temporelle.** Avant toute action longue : durée estimée affichée. Pendant : étapes réelles, jamais fictives. Après : notification (in-app et e-mail). L'utilisateur peut partir et revenir.

**P8 — Souveraineté et étanchéité des données.** Chaque espace est hermétique. Le client possède ses données, peut les exporter intégralement et les faire supprimer. Aucun apprentissage inter-clients sur des données identifiables.

**P9 — Interchangeabilité des fournisseurs.** Chaque dépendance externe (modèle d'IA, stockage, base, e-mail, authentification) est derrière une interface neutre avec un seul fichier d'implémentation. Aucun nom de fournisseur hors de ce fichier.

**P10 — Langue choisie, appliquée partout.** Français ou anglais. Le choix de l'utilisateur s'applique à l'interface, aux conversations, aux rapports, aux e-mails et à tous les fichiers produits.

---

## 3. RÉFÉRENTIELS ET MODÈLE D'EXIGENCES

### 3.1 Normes couvertes

La plateforme couvre la **famille des normes de systèmes de management** ISO, celles qui partagent la structure HLS (chapitres 4 à 10) et donnent lieu à certification. Elle est extensible à toute norme de cette famille par ajout d'un jeu d'exigences validé — sans modification du code. Les normes de guidage (non certifiables) sont intégrées comme méthodes, jamais comme référentiels d'audit.

| Phase | Norme | Rôle |
|---|---|---|
| 1 | ISO 45001:2018 | Santé et sécurité au travail — référentiel fondateur |
| 1 | ISO 9001:2015 | Qualité |
| 1 | ISO 14001:2015 | Environnement |
| 1 | ISO 50001:2018 | Management de l'énergie — quatrième norme fondatrice : revue énergétique, situation de référence, usages énergétiques significatifs, indicateurs de performance énergétique, plans d'action, conception et achats économes en énergie, mesure et surveillance |
| 2 | ISO 14064-1:2018 | Quantification et déclaration des émissions de gaz à effet de serre au niveau de l'organisme — indispensable pour la décarbonation, les rapports extra-financiers et l'export vers l'Union européenne (mécanisme d'ajustement carbone aux frontières) |
| 2 | ISO 50002:2014 | Audits énergétiques — méthode du diagnostic énergétique, en appui de 50001 |
| 2 | ISO 45003:2021 | Risques psychosociaux (extension de 45001) |
| 3 | ISO 22000, 27001, 13485, 39001, 22301, 37001 | Sécurité des aliments, sécurité de l'information, dispositifs médicaux, sécurité routière, continuité d'activité, anti-corruption — selon demande des pilotes, secteur par secteur |
| Cadres | ISO 31000, ISO 19011, ISO 26000, ISO 14040/14044 | Non certifiables — gestion des risques, audit, responsabilité sociétale, analyse du cycle de vie. Utilisés comme méthodes et comme grilles de lecture, jamais comme référentiels de conformité |

Les quatre normes de phase 1 partagent la structure HLS. Le modèle exploite ce tronc commun : une organisation visant un **système intégré qualité–environnement–sécurité–énergie** ne renseigne les exigences communes qu'une fois, et ne rédige qu'un seul manuel, une seule politique, un seul jeu de procédures communes.

**Énergie et climat.** 50001 et 14064-1 forment ensemble l'offre « énergie propre » : maîtrise de la consommation d'un côté, comptabilité carbone de l'autre. Les deux s'appuient sur des données mesurées (compteurs, factures, facteurs d'émission) que le formulaire de cadrage collecte spécifiquement, et sur des méthodes de calcul auditables. Le Service 2 produit pour ces normes un audit énergétique documentaire et un bilan d'émissions structuré ; le Service 1 génère les procédures de revue énergétique, de suivi des indicateurs et de collecte des données d'émissions.

**Condition d'ajout d'une norme.** Chaque jeu d'exigences est rédigé ou validé par un praticien qualifié sur la norme concernée. Le propriétaire du produit est certifié 9001, 14001 et 45001 ; pour 50001 et 14064-1, soit une qualification complémentaire est acquise, soit un auditeur énergie et carbone partenaire valide le contenu avant mise en production. Aucune norme n'est proposée aux clients sans cette validation, et l'interface affiche pour chaque norme le nom et la qualification du validateur.

### 3.2 Méthodes de référence

- **Audit :** ISO 19011:2018 — principes d'intégrité, présentation impartiale, conscience professionnelle, confidentialité, indépendance, approche fondée sur les preuves et sur les risques.
- **Risques :** ISO 31000:2018 comme cadre ; méthodes sectorielles (cotation SST type gravité × probabilité × exposition, AMDEC, analyse des aspects et impacts environnementaux, arbre des causes).
- **Amélioration :** cycle PDCA, appliqué au système du client et à la plateforme elle-même (section 4.4).

### 3.3 Réglementation nationale

Registre de sources officielles par pays, en fichier de configuration :

| Pays | Source officielle | Domaines |
|---|---|---|
| Maroc | Bulletin officiel ; textes consolidés du SGG | Code du travail (loi 65-99), décrets SST, loi 09-08 (données), environnement |
| France | Légifrance | Code du travail, Code de l'environnement |
| Autres | Ajoutés à la demande, validés un par un | — |

### 3.4 Le modèle d'exigences — cœur de la plateforme

Chaque exigence est un enregistrement structuré, rédigé et validé par un expert certifié, versionné :

```
exigence:
  id: "45001-8.1.2"                   # norme + clause
  norme: "ISO 45001:2018"
  famille: systeme_de_management      # ou cadre_methodologique (31000, 19011, 26000)
  certifiable: true
  validateur: "nom, qualification"    # affiché dans l'interface
  chapitre: 8
  intitule_fr: "..."                  # reformulation, jamais le texte de la norme
  intitule_en: "..."
  type: documentaire | mise_en_oeuvre | enregistrement
  preuves_attendues: [...]            # ce qu'un auditeur demande
  questions_audit: [...]              # questions types, FR/EN
  applicabilite:
    secteurs: [tous | liste]
    taille_min: null
  hls_commun: true                    # partagé 9001/14001/45001
  equivalences: ["9001-8.1", "14001-8.1"]
  regles_terrain: ["BTP-01", "BTP-02"]   # règles d'inspection dérivées
  documents_types: ["procedure", "enregistrement"]
  processus_types: []                 # processus types concernés, liés à la cartographie du client à l'usage
  risques_types: []                   # risques ET opportunités associés
  indicateurs_types: []               # KPI types de suivi
  version: 3
  valide_par: "expert"
  date_validation: "2026-09-..."
```

Les trois services consomment ce modèle : le Service 1 génère à partir des exigences, le Service 2 audite contre les exigences, le Service 3 détecte selon les règles dérivées. Ce modèle est l'actif principal de l'entreprise. Il est stocké en données structurées, jamais en dur dans le code, et son évolution suit un flux de validation (section 4.4).

**Les relations forment un graphe.** Exigence ↔ processus ↔ risque/opportunité ↔ document ↔ preuve ↔ constat ↔ action ↔ indicateur : ces liens sont des données de première classe. Ils permettent la propagation d'impact — un processus modifié liste les risques, documents, formations, exigences et audits à revoir ; un texte réglementaire changé liste les éléments du système concernés. C'est un graphe **logique**, porté par des champs de relation dans la base existante : aucune base de données de graphe n'est introduite tant qu'un besoin mesuré ne l'exige pas.

### 3.5 Le modèle de preuve

Toute affirmation produite par la plateforme — constat terrain, écart d'audit, couverture documentaire, suggestion réglementaire — est portée par un objet preuve unique et uniforme :

```
constat:
  enonce: "..."                        # formulation factuelle
  preuves: [image | extrait_document | enregistrement | observation | entretien | kpi]
  sources: [...]                       # document+section, capture+horodatage, texte+article
  confiance: 0.0–1.0
  exigence_associee: "45001-8.1.2"
  reglementation_associee: null | ref_source_officielle
  statut: propose | a_verifier | valide | rejete
  hierarchie_mesures: null             # pour les actions : voir §4.3.3
```

Une affirmation sans preuve n'existe pas dans le système : elle est bloquée à la production, pas signalée par un avertissement. Le format de sortie type est : constat proposé + preuves citées + confiance + exigence + statut « à valider » — jamais un jugement nu (« l'entreprise ne maîtrise pas ses déchets »).

### 3.6 Le moteur d'applicabilité

Aucune exigence n'est considérée applicable par défaut. À la création d'un espace, chaque exigence passe par une évaluation d'applicabilité (secteur, activités, taille, périmètre, obligations), proposée par l'agent et validée par l'humain. Règle absolue : **non applicable ≠ non traité** — toute exclusion porte une justification enregistrée, datée et signée, comme dans un vrai dossier de certification. Le dénominateur de tout score n'inclut que les exigences applicables, et la liste des exclusions justifiées figure dans chaque rapport.

---

## 4. LES SERVICES

### 4.1 SERVICE 1 — SYSTÈME DOCUMENTAIRE

**Objectif :** produire, à partir d'un formulaire préétabli, l'ensemble documentaire d'un système de management aligné sur la ou les normes choisies, prêt à être adapté et déployé.

#### 4.1.1 Formulaire de cadrage

Formulaire adaptatif, sauvegardé à chaque étape, assisté par l'agent conversationnel (section 4.6). Sections :

1. **Identité** — raison sociale, secteur, effectif, sites, langue de travail, logo.
2. **Périmètre** — normes visées, processus inclus, exclusions justifiées.
3. **Contexte (ch. 4)** — enjeux internes et externes, parties intéressées et leurs attentes.
4. **Organisation** — organigramme, rôles, pilotes de processus, délégations.
5. **Processus (ch. 4.4 / 8)** — activités, entrées, sorties, interfaces, ressources, indicateurs existants.
6. **Risques connus** — accidents passés, dangers identifiés, aspects environnementaux, exigences clients.
7. **Réglementation** — pays, secteur, autorisations, obligations connues.
8. **Existant** — documents déjà en place (téléversement), certifications antérieures.

Le formulaire est **profond par construction** : c'est la qualité des réponses qui empêche le manuel générique. L'agent signale les sections trop pauvres pour produire un document spécifique et refuse de générer tant qu'un minimum n'est pas atteint.

#### 4.1.2 Cartographie des processus

Générée depuis le formulaire : processus de management, de réalisation, de support ; interactions ; pour chaque processus, une fiche (finalité, pilote, entrées, sorties, ressources, indicateurs, risques, documents associés, exigences couvertes). Rendu en schéma (SVG) modifiable et en fiches. Révisable à tout moment ; toute modification propage aux documents liés (avec liste des impacts).

#### 4.1.3 Documents produits

Selon les normes retenues, en version 1 :

- Politique QSE (ou Q, E, SST séparées)
- Manuel du système de management (optionnel dans les versions 2015/2018, mais attendu par la plupart des clients)
- Fiches processus et cartographie
- Procédures obligatoires et recommandées : maîtrise de l'information documentée, audit interne, non-conformités et actions correctives, identification des dangers et évaluation des risques, veille et conformité réglementaire, préparation et réponse aux situations d'urgence, communication, compétences et sensibilisation, achats et prestataires, maîtrise opérationnelle, revue de direction, consultation et participation des travailleurs (45001)
- Instructions de travail types par secteur
- Modèles d'enregistrements : registres, fiches, formulaires
- Matrice des responsabilités, matrice de couverture exigences → documents
- Programme d'audit, planning de revue de direction
- Analyse des risques initiale (structure remplie depuis le formulaire, cotation proposée)
- Tableau d'objectifs et d'indicateurs

Chaque document porte : code, version, statut, auteur (agent), validateur, date, langue, exigences couvertes.

#### 4.1.4 Maîtrise documentaire (clause 7.5)

Codification paramétrable, versionnement, statuts (projet → en revue → approuvé → obsolète), flux d'approbation (rédacteur, vérificateur, approbateur), historique des modifications, liste de diffusion, dates de revue.

#### 4.1.5 Rendu et formats

DOCX (modifiable) et PDF, aux couleurs et logo du client, dans la langue choisie. Régénération possible dans l'autre langue. Export complet en archive.

#### 4.1.6 Transparence temporelle

- Formulaire : 1 à 3 heures de travail utilisateur, en plusieurs sessions.
- Génération de l'ensemble documentaire : **20 à 60 minutes** selon le nombre de documents, annoncé avant lancement avec le décompte.
- Chaque document est disponible dès qu'il est produit, sans attendre la fin de l'ensemble.

#### 4.1.7 Qualité intégrée

Matrice de couverture obligatoire : chaque exigence applicable est rattachée à au moins un document ; les exigences non couvertes sont listées explicitement. Contrôle de cohérence inter-documents (rôles, codes, termes). Aucune phrase de norme reproduite (contrôle automatique).

---

### 4.2 SERVICE 2 — AUDIT À BLANC

**Objectif :** évaluer l'écart entre un système de management et les exigences d'une norme, selon la méthode ISO 19011, en deux modes.

- **Mode A — Documentaire seul :** analyse du système documentaire du client.
- **Mode B — Documentaire + terrain :** mode A, plus checklist terrain remplie par l'utilisateur et renvoyée pour consolidation.

#### 4.2.1 Préparation

Périmètre, critères (normes, réglementation applicable), plan d'audit, et génération d'une checklist adaptée : uniquement les exigences applicables au secteur et au périmètre, avec questions et preuves attendues.

#### 4.2.2 Mode A — analyse documentaire

Ingestion des documents du client (DOCX, PDF, XLSX, images de documents). Pour chaque exigence :

- niveau de couverture sur quatre degrés : non traité (0) · amorcé (25) · en place mais incomplet (60) · couvert et documenté (100) ;
- **non applicable** exclu du dénominateur ;
- citation de la preuve : document, section, extrait ;
- écart formulé et recommandation.

Résultat : score de **couverture documentaire** par chapitre et global, liste des écarts priorisée, liste des documents manquants.

#### 4.2.3 Mode B — terrain

Export de la checklist en fichier Excel et en formulaire web mobile. L'utilisateur la remplit sur site avec quatre réponses possibles — conforme, non conforme, non applicable, observation — et un **champ preuve obligatoire** (document consulté, personne rencontrée, observation, enregistrement). Retour sur la plateforme, consolidation.

Résultat : second score de **mise en œuvre**, distinct du score documentaire, et **croisement des deux** : liste des contradictions (« la procédure existe et est couverte ; le terrain montre qu'elle n'est pas appliquée sur deux processus »). C'est le livrable le plus recherché par les directions.

#### 4.2.4 Classification des constats

Non-conformité majeure (défaillance systémique ou exigence non couverte), mineure (écart ponctuel sur un système en place), observation, point fort. L'agent propose, l'auditeur valide.

#### 4.2.5 Rapport d'audit

Structure : identification, périmètre, critères, méthode, synthèse exécutive d'une page, scores par chapitre (documentaire et mise en œuvre), constats détaillés avec preuves, points forts, opportunités, non-conformités classées, plan d'action proposé, signatures. DOCX et PDF, langue choisie.

#### 4.2.6 Indépendance structurelle (P4)

Le module Vérification est un espace séparé dans l'interface, avec ses propres prompts. Il n'a accès qu'au modèle d'exigences et aux preuves fournies. Il ignore l'existence du module Rédaction et ne peut pas lire ses instructions. Un client qui a généré ses documents avec le Service 1 est prévenu que l'audit à blanc reste une auto-évaluation et non un audit indépendant au sens de la certification.

#### 4.2.7 Transparence temporelle

- Mode A : **10 à 40 minutes** selon le volume documentaire, annoncé après ingestion.
- Mode B : durée terrain à la main de l'utilisateur ; consolidation **15 à 30 minutes**.

#### 4.2.8 Vocabulaire imposé

Jamais « conforme à ISO … ». Toujours « couverture », « écart », « auto-évaluation », « prêt pour audit ». Le vocabulaire est vérifié automatiquement à la génération.

---

### 4.3 SERVICE 3 — ÉVALUATION HSE

**Objectif :** détecter, hiérarchiser, assigner et suivre les risques de sécurité observables, depuis des médias fournis ou depuis les caméras existantes du site.

#### 4.3.1 Mode média (existant, version 0)

Dépôt de photos ou vidéo → détection automatique du secteur (refus si indéterminé) → analyse contre le référentiel → constats avec preuve, clause, criticité observée à quatre niveaux, justification, confiance → validation, correction, rejet, ajout par l'auditeur → e-mail personnalisé par responsable, alerte séparée pour arrêt immédiat, escalade direction → PDF. Le média source est détruit après extraction des preuves.

Évolutions prévues : plan d'action avec outil qualité adapté (5 Pourquoi, Ishikawa, Pareto, AMDEC) ; **hiérarchie des mesures de prévention imposée dans toute proposition d'action** — élimination, puis substitution, puis protection collective, puis mesures organisationnelles, puis EPI en dernier recours, avec justification quand un niveau supérieur est écarté ; balayage systématique par zone pour réduire les oublis ; règles supplémentaires (électricité, sols) ; suivi de levée avec vérification par nouvelle capture.

**Détection de secteur affinée :** quand la confiance est insuffisante, l'agent n'oppose pas un refus sec — il affiche ses hypothèses classées (« BTP 42 % · Industrie 35 % · Logistique 23 % ») avec la mention « contexte insuffisant, sélection humaine requise ». L'audit ne démarre jamais sur un secteur incertain, mais l'information de détection n'est pas perdue et le choix humain est éclairé.

#### 4.3.2 Mode caméras (nouveau)

**Connecteur caméras** — ajout d'une caméra (adresse, identifiants chiffrés), ONVIF/RTSP, test de connexion, état de santé, définition de zones et de lignes par caméra.

**Moteur de détection local** — s'exécute **sur site**, sur un boîtier fourni ou un serveur du client, **sans IA générative et sans connexion sortante continue**. Détections : mouvement dans une zone, franchissement de ligne, présence dans une zone d'exclusion, immobilité anormale, motif de chute, présence hors plage horaire. Configurable par caméra. Le flux ne quitte jamais le site. Seules les **captures d'événements** sont transmises, avec leurs métadonnées (caméra, zone, horodatage), après floutage des visages.

**Chaîne d'un événement :**

1. Détection locale → capture(s) + métadonnées → transmission chiffrée
2. E-mail au responsable de la zone, avec la capture
3. Le responsable ouvre l'événement sur la plateforme
4. Il choisit **Évaluer** → l'agent analyse contre le référentiel, produit constat, criticité, plan d'action → validation → notification → suivi
5. Ou il classe l'événement sans évaluation (faux déclenchement, situation connue), avec motif

**Quota d'évaluations :** 200 évaluations IA par mois incluses par site, au-delà facturation à l'usage à tarif bas. **Les motifs graves — chute, personne au sol, zone d'exclusion franchie — sont évalués automatiquement et hors quota.** Le quota fait payer l'usage intensif ; il ne doit jamais faire hésiter sur une alerte.

#### 4.3.3 Suivi des non-conformités

Cycle complet : ouverte → assignée → **correction immédiate** (mise en sécurité) → **analyse de cause racine** (outil qualité adapté, §4.4 du document Apports) → **action corrective** → vérification de réalisation → **vérification d'efficacité** (nouvelle capture, constat ou indicateur, après un délai adapté) → clôturée. Relances automatiques à J-1, J, J+2 ; escalade au N+1 à J+3 ; tableau de bord des retards.

Deux règles issues de la pratique d'audit, appliquées par le système :

- **Correction ≠ action corrective.** Retirer le câble du sol n'est pas traiter la cause. Une NC ne peut pas être clôturée sur la seule correction immédiate : la clôture exige soit une action corrective avec preuve d'efficacité, soit une décision humaine explicite « correction suffisante », motivée et tracée.
- **Détection de récurrence.** Le système rapproche les NC par règle, zone, processus, cause et responsable. Une NC réapparue malgré une action déclarée réalisée est signalée : « 3 occurrences en 60 jours, 2 actions précédentes, aucune preuve d'efficacité — cause probablement non traitée ». C'est ce signal, pas le comptage des NC, qui a de la valeur pour une direction.

#### 4.3.4 Confidentialité et acceptabilité sociale

Floutage des visages sur toute capture conservée. Reporting au niveau de la zone, jamais de l'individu. Aucune reconnaissance faciale, aucun suivi de personne. Documentation prête à l'emploi pour la déclaration CNDP (Maroc) et l'information des instances représentatives : finalité (prévention des accidents en zones à risque), données traitées, durée de conservation, droits. Cette documentation fait partie du produit.

#### 4.3.5 Transparence temporelle

- Analyse d'un média : **20 secondes à 3 minutes** selon la taille.
- Évaluation d'un événement caméra : **moins de 2 minutes**.
- Rapport et e-mails : immédiats après validation.

---

### 4.4 BRIQUE TRANSVERSALE — AMÉLIORATION CONTINUE (PDCA)

**Objectif :** que la plateforme apprenne de chaque usage sans jamais changer seule ses règles.

**Trois niveaux :**

1. **Mémoire par espace** — règles spécifiques, organigramme, vocabulaire, historique des inspections et audits, NC récurrentes. Une NC relevée trois fois sur un site devient « récurrente, cause racine non traitée ».
2. **Apprentissage des corrections** — chaque correction de criticité, rejet, ajout manuel, faux positif est un signal horodaté (les champs `original_*` existent déjà). Agrégés, ces signaux révèlent les erreurs systématiques du moteur.
3. **Amélioration inter-espaces** — uniquement sur des motifs agrégés et anonymisés (« BTP-03 sur-détecté sur chantiers ») ; jamais sur des documents ou données identifiables. Inscrit dans les conditions générales.

**Boucle :** collecte (Check) → proposition avec preuve (Act) — « sur 15 inspections, BTP-03 abaissé 12 fois : changer le défaut ? » → validation par l'expert ou le consultant (Plan) → déploiement versionné (Do) → mesure.

**Tableau de bord « Qualité du moteur » :** taux de correction par règle, taux de faux positifs, taux de constats manqués (ajouts manuels), tendance mensuelle. Visible par l'administrateur de l'espace.

---

### 4.5 BRIQUE TRANSVERSALE — VEILLE RÉGLEMENTAIRE

Registre de sources officielles par pays (section 3.3). Contrôle périodique. Chaque suggestion porte obligatoirement : source, lien, date, extrait de référence. L'utilisateur garde ou écarte. Pas de source → pas de suggestion. Si la source officielle est absente ou inexploitable : l'utilisateur téléverse le texte, atteste son origine, l'agent extrait les exigences avec pointeur vers l'article et la page.

Rattachement des textes aux processus et aux exigences du client ; alerte sur changement ; registre de conformité réglementaire exportable (exigence, texte, applicabilité, état, preuve, responsable).

**Cycle de vie de chaque texte.** Le registre porte, pour chaque référence : source, date de publication, date d'entrée en vigueur, version, statut (en vigueur / modifié / abrogé), articles applicables, date de dernière vérification humaine. Un texte dont une modification est détectée passe en statut « potentiellement modifié » et redevient une suggestion à valider — jamais une mise à jour silencieuse.

**Analyse d'impact d'un changement.** Quand un texte change ou entre en vigueur, l'agent parcourt le graphe de relations (§3.4) et produit la liste des éléments concernés — processus, risques, documents, exigences internes, formations — avec la mention « N éléments nécessitent une revue ». La revue elle-même reste humaine.

---

### 4.6 BRIQUE TRANSVERSALE — ASSISTANT DE CADRAGE ET DE RECHERCHE

Conversation en français ou anglais, dont le rôle est délimité :

- comprendre ce que l'utilisateur veut accomplir ;
- proposer le parcours (quel service, quelles étapes, quelle durée estimée) ;
- guider pas à pas, répondre aux questions de méthode ;
- aider à remplir le formulaire de cadrage ;
- **répondre à toute question, y compris hors du périmètre validé** — autre norme, autre pays, concept, méthode — en recherchant sur le web et dans les sources publiques, avec citation systématique des sources.

**Deux régimes de réponse, distincts à l'écran et dans le code :**

| Régime | Contenu | Usage |
|---|---|---|
| **Validé** | Modèle d'exigences signé par un praticien qualifié ; registre réglementaire vérifié | Seul contenu autorisé dans les audits, documents générés et rapports livrés |
| **Recherche** | Réponses issues de recherche web et de connaissances générales, sources citées | Information et orientation uniquement ; bandeau permanent « Réponse documentaire non validée par un expert — ne constitue pas un référentiel d'audit » ; jamais injecté dans un livrable |

**Limite légale, affichée à l'utilisateur quand c'est pertinent :** les normes ISO sont des documents protégés et payants. L'agent ne télécharge ni ne reproduit leur texte ; il exploite les informations publiques (périmètre, structure, synthèses), répond avec ses connaissances générales sourcées, et oriente vers l'achat officiel (IMANOR, ISO, AFNOR). Les textes réglementaires publics, eux, sont récupérés depuis leurs sources officielles sans restriction.

**Boucle d'extension du catalogue.** Chaque question hors périmètre est journalisée (norme, pays, fréquence). Au-delà d'un seuil de demande, l'agent le signale au propriétaire du produit, prépare un brouillon de jeu d'exigences marqué « en attente de validation », et ce brouillon suit le circuit complet : garde anti-copyright, relecture, validation par un praticien qualifié sur le domaine, intégration au régime validé avec le nom du validateur affiché. La demande réelle pilote l'extension du catalogue ; aucun contenu ne passe du régime recherche au régime validé sans ce circuit.

L'assistant ne produit **jamais** de conclusion d'audit ni de constat : ceux-ci ne sortent que des modules structurés, sur preuves.

---

### 4.7 BRIQUE TRANSVERSALE — RECHERCHE OUVERTE

**Objectif :** répondre à toute question — norme non couverte, réglementation d'un autre pays, méthode, définition, comparaison — sans jamais se limiter au contenu validé de la plateforme, et transformer la demande récurrente en extension du produit.

**Le principe : deux régimes, visuellement distincts et jamais mélangés.**

| | Régime « Recherche » | Régime « Moteur validé » |
|---|---|---|
| Alimente | Les réponses de l'assistant | Les audits, documents, constats, registres, scores |
| Source | Recherche web en direct, textes officiels publics téléchargés | Modèle d'exigences et règles validés par un expert nommé |
| Affichage | Bandeau « Information issue de recherche — sources citées, non validée par un expert de la plateforme » | Nom et qualification du validateur |
| Peut produire | Une réponse sourcée, une synthèse, un texte réglementaire archivé avec son pointeur | Un livrable engageant |

**Règles du régime Recherche :**

1. Toute réponse cite ses sources avec lien et date de consultation. Une affirmation réglementaire sans source officielle est refusée — le principe P5 s'applique aussi ici.
2. L'agent peut télécharger et archiver les **textes officiels publics** (lois, décrets, bulletins officiels — les textes de loi ne sont pas protégés par le droit d'auteur dans la plupart des juridictions), avec pointeur de source et date. Ces archives alimentent les réponses, jamais directement les registres clients.
3. L'agent **ne télécharge jamais le texte d'une norme ISO ou payante** : ces textes sont protégés et vendus. Il répond à partir de sources publiques légitimes et renvoie vers l'organisme officiel pour l'acquisition. Aucune exception, quelle que soit la demande de l'utilisateur.
4. Une réponse de recherche ne peut **jamais** déclencher un audit, générer un document livrable, coter un risque ni entrer dans un registre client. Le passage de l'un à l'autre suit le circuit ci-dessous.

**Le circuit d'extension par la demande — c'est l'amélioration continue demandée :**

1. Chaque question portant sur une norme ou un pays non couvert est comptée comme une **demande**.
2. Au-delà d'un seuil (ou sur décision), l'agent assemble un **dossier brouillon** : projet de modèle d'exigences reformulées, sources réglementaires candidates marquées « à vérifier », règles terrain candidates — exactement le format des brouillons v0.1.
3. Ce dossier entre dans le **circuit de validation experte** (praticien qualifié, nommé).
4. Une fois validé, le contenu bascule dans le régime Moteur et devient utilisable par les trois services.

Ainsi l'agent cherche tout, répond à tout, apprend de la demande — et rien de non validé ne touche jamais un livrable client. C'est la seule articulation compatible avec P1 et P5.

---

## 5. MODÈLE DE DONNÉES ET MULTI-LOCATION

### 5.1 Hiérarchie

```
Organisation (type : entreprise | consultant | groupe)
 └── Espace (client d'un consultant, ou site d'une entreprise)
      ├── Projets documentaires
      ├── Audits
      ├── Inspections et événements
      ├── Registre réglementaire
      ├── Non-conformités et plans d'action
      ├── Documents (versionnés)
      └── Journal d'audit (qui a fait quoi, quand)
```

### 5.2 Utilisateurs et rôles

| Rôle | Périmètre | Droits |
|---|---|---|
| Propriétaire | Organisation | Tout, facturation, suppression |
| Administrateur | Organisation | Gestion des espaces et utilisateurs |
| Consultant | Espaces délégués | Lecture, rédaction, audit, validation |
| Auditeur | Espace | Validation des constats, audits |
| Responsable | Espace, zone | Voit et traite les NC qui lui sont assignées |
| Lecteur | Espace | Consultation |

### 5.3 Étanchéité

Toute requête est filtrée par espace au niveau du modèle de données, jamais seulement dans l'interface. Des **tests d'isolation automatisés** tentent des accès croisés à chaque déploiement ; un échec bloque la mise en production.

### 5.4 Propriété, séparation, suppression

Le client final possède les données de son espace. Le consultant en a un accès délégué, révocable. À la fin d'une relation consultant–client : transfert de l'espace au client, ou export intégral (archive : documents, audits, rapports, journal) puis suppression vérifiée. Durée de conservation paramétrable par espace, avec valeur par défaut adaptée aux obligations d'archivage SST (trois ans minimum recommandé, configurable).

### 5.5 Visibilité client / consultant

Le client final voit ce que son consultant marque comme **publié** ; les brouillons restent au consultant. Ce réglage est par document. Réponse aux deux questions ouvertes : oui, le client peut voir — au moment où le consultant le décide ; et les données appartiennent au client.

---

## 6. EXPÉRIENCE UTILISATEUR ET NAVIGATION

### 6.1 Deux surfaces

- **Site vitrine** (public, statique, très rapide) — présente les trois services, la méthode, les tarifs, le contenu. Section 9.
- **Application** (authentifiée) — l'outil.

### 6.2 Navigation de l'application

Menu principal, sept entrées, toujours visible :

**Tableau de bord** · **Documentation** (Service 1) · **Audit** (Service 2) · **Évaluation HSE** (Service 3) · **Veille** · **Amélioration** · **Espaces** (consultants) — plus **Paramètres**.

Chaque page de service suit le même gabarit : *Ce que ça fait · Ce qu'il vous faut · Temps estimé · Commencer*. Un utilisateur qui arrive sur n'importe quelle page comprend en dix secondes où il est et ce qu'il peut faire.

### 6.3 Composant de transparence temporelle (P7)

Réutilisé partout. Avant lancement : fourchette de durée et ce qui l'influence. Pendant : étapes réelles remontées par le traitement (jamais de progression fictive ; les étapes indissociables s'affichent ensemble). Après : notification in-app et e-mail avec lien direct. L'utilisateur peut fermer l'onglet à tout moment.

### 6.4 Langues (P10)

Bascule FR/EN dans l'en-tête. Langue par défaut de l'organisation, surcharge par utilisateur. Tout fichier produit porte un attribut de langue et peut être régénéré dans l'autre. Catalogues de traduction en fichiers ; aucune chaîne en dur dans les gabarits.

### 6.5 Design

Sobre, professionnel, dense : fond clair, texte ardoise, les quatre couleurs de criticité comme seuls accents. Une police, deux graisses. Aucun dégradé décoratif, aucune animation gratuite. Mobile d'abord pour les écrans terrain (checklist, événements, validation). Contrastes conformes aux règles d'accessibilité usuelles.

---

## 7. EXIGENCES NON FONCTIONNELLES

### 7.1 Performance et montée en charge

- Pages applicatives : p95 < 1,5 s.
- Tout traitement > 3 s est asynchrone, via file de messages, avec reprise après interruption.
- Objectif de charge phase 1 : 500 organisations, 5 000 espaces, 2 000 traitements/heure ; architecture dimensionnée pour ×10 sans refonte.
- Limitation de débit par organisation ; idempotence de toute action déclenchant un envoi ou un coût.

### 7.2 Robustesse

Nouvelles tentatives avec délai croissant sur indisponibilité du modèle ; disjoncteur ; file d'attente persistante ; mode dégradé explicite (« analyse différée, vous serez notifié ») plutôt qu'échec silencieux. Aucun état partiel écrit.

### 7.3 Sécurité

Authentification par fournisseur d'identité (Google, Microsoft, e-mail avec lien magique), double facteur disponible, contrôle d'accès par rôles (section 5.2), chiffrement en transit et au repos, secrets dans un gestionnaire dédié et jamais dans le code ni les journaux (masquage automatique des valeurs secrètes dans toute sortie, y compris les traces d'erreur), URL signées à durée limitée pour les fichiers, journal d'audit immuable des actions, protection contre les injections par documents téléversés (le contenu d'un document est une donnée, jamais une instruction).

### 7.4 Données personnelles

RGPD et loi 09-08 : registre des traitements, base légale, contrat de sous-traitance type, région d'hébergement Europe par défaut avec option de résidence, droits d'accès et d'effacement outillés, durées de conservation paramétrées, floutage des visages, aucune donnée biométrique.

### 7.5 Observabilité et coûts

Journaux structurés, traces de bout en bout, coût par traitement (jetons, stockage), alertes de budget, tableau de bord de consommation par organisation.

### 7.6 Sauvegarde et continuité

Export quotidien de la base, versionnement du stockage, procédure de restauration testée trimestriellement, objectif de reprise < 4 h.

### 7.7 Tests

Tests unitaires ; tests d'intégration sur émulateurs ; tests de bout en bout par service ; tests d'isolation multi-espaces obligatoires ; tests de vocabulaire (aucun « conforme », aucun nom de fournisseur, aucun texte normatif) ; tests de langue (aucune chaîne dans l'autre langue).

### 7.8 Gouvernance de l'IA — traçabilité, versionnage, passerelle de sortie

**Chaque résultat d'IA est reproductible et explicable.** Tout constat, écart, document généré ou suggestion porte l'empreinte complète de son contexte de production : version du modèle d'exigences, version du référentiel terrain, version du prompt, identifiant et version du modèle d'IA, sources utilisées, entrée, sortie brute, validation ou modification humaine, résultat final. Réponse attendue à deux questions d'un client grand compte : « pourquoi l'IA a-t-elle classé cette situation en majeure ? » et « avec quel référentiel, quelle version, à quelle date ? ».

**Versionnage sémantique des artefacts de raisonnement.** Modèle d'exigences, référentiels terrain, barèmes, sources réglementaires, prompts : chacun porte un numéro de version, un journal de modifications, et un résultat référence toujours les versions exactes qui l'ont produit (« Inspection n° 4587 — référentiel BTP v2.1, modèle d'exigences v1.4 »). Toute montée de version passe par le circuit de validation de la brique 4.4.

**Passerelle de validation en sortie.** Avant qu'une réponse atteigne un utilisateur ou un livrable, elle traverse une chaîne de contrôles **bloquants** — pas des avertissements : preuve présente, exigence ou source rattachée, vocabulaire autorisé, aucun texte normatif, langue correcte, périmètre de l'espace respecté, aucun secret. Un échec produit « Bloqué — preuve insuffisante » (ou le motif exact), jamais une sortie dégradée. Ces contrôles existent déjà en tests d'intégration continue ; ils sont aussi exécutés à chaque production, parce qu'un test de déploiement ne protège pas d'une dérive à l'exécution.

---

## 8. ARCHITECTURE TECHNIQUE

### 8.1 Couches

```
Site vitrine (statique)      Application (API + interface)      Travailleurs (traitements)
        │                              │                                  │
        └──────────────── Plateforme Google Cloud ─────────────────────────┘
                 Cloud Run · Firestore · Cloud Storage · Pub/Sub
                 Cloud Tasks · Cloud Scheduler · Secret Manager · Identity
                                       │
                         Moteur local caméras (sur site du client)
```

### 8.2 Choix

- **Backend :** Python 3.11+, FastAPI. Rendu serveur avec interactivité progressive (HTMX/Alpine ou équivalent) pour la phase 1 ; un cadre frontal complet ne sera adopté que si un besoin d'interface le justifie, pas par principe.
- **Traitements :** Cloud Run (services et jobs), Pub/Sub pour la file, Cloud Tasks pour les relances programmées, Cloud Scheduler pour la veille.
- **Données :** Firestore (métier), Cloud Storage (fichiers, preuves, exports).
- **IA :** interface neutre unique ; modèle multimodal pour la vision ; routage par tâche pour le texte (rédaction longue, extraction, classification) ; choix du fournisseur par tâche modifiable en configuration.
- **Documents :** génération DOCX par gabarits, PDF par moteur de rendu ; gabarits aux couleurs du client.
- **Moteur local caméras :** service Python sur boîtier Linux, bibliothèque de vision légère, détecteur de personnes embarqué, connexion **sortante uniquement** (aucun port entrant), tampon local, synchronisation de configuration, mises à jour signées.
- **i18n :** catalogues de messages FR/EN, attribut de langue sur chaque objet produit.

### 8.3 Interfaces neutres (P9)

| Interface | Implémentation unique |
|---|---|
| Analyse (vision, texte) | `providers/` — un fichier par fournisseur |
| Stockage de fichiers | local, Cloud Storage |
| Base de données | mémoire, Firestore |
| File de traitements | tâches en arrière-plan, Pub/Sub |
| Notification e-mail | fournisseur transactionnel |
| Authentification | fournisseur d'identité |
| Génération de documents | moteur DOCX/PDF |

Aucun module hors de ces fichiers n'importe un SDK de fournisseur ni ne le nomme — y compris dans les descriptions de schémas envoyées aux modèles.

---

## 9. SITE VITRINE, SEO ET GEO

### 9.1 Principe

Le site vitrine est séparé de l'application, statique, servi par CDN, sans dépendance à l'application. Il existe en FR et EN avec balises de langue alternée, sitemap, données structurées.

### 9.2 Arborescence

Accueil · Service Documentation · Service Audit à blanc · Service Évaluation HSE · Méthode (les dix principes, ce que le produit ne fait pas) · Normes (une page par norme : ce qu'elle exige, comment la plateforme aide, sans reproduire le texte) · Secteurs (une page par secteur) · Pays (réglementation couverte) · Tarifs · Glossaire QSE · Blog · FAQ · À propos (parcours et certifications de l'auteur) · Contact.

### 9.3 SEO

Données structurées (Organisation, Application logicielle, FAQ, Article, Fil d'Ariane), performances (Core Web Vitals verts), pages ciblant les requêtes d'intention : « préparer un audit ISO 45001 », « modèle de procédure », « logiciel inspection sécurité chantier », en FR et EN. Contenu expert réel — issu du terrain — plutôt que volume.

### 9.4 GEO (optimisation pour les moteurs génératifs)

Les moteurs de réponse par IA citent ce qui est **factuel, structuré, attribuable et stable**. Donc : pages « qu'est-ce que », comparatifs, glossaire, méthodologie, avec définitions nettes en tête de page, tableaux, auteur identifié avec ses qualifications (E-E-A-T), nommage constant de l'entité « Consultant QSE IA », fichier `llms.txt`, contenu sans emphase marketing. La page « Méthode » est conçue pour être citée : elle expose des principes vérifiables.

---

## 10. MODÈLE TARIFAIRE

| Plan | Cible | Inclus |
|---|---|---|
| Solo | Consultant indépendant | 1 utilisateur, 3 espaces, 30 évaluations/mois |
| Site | Une entreprise, un site | Utilisateurs illimités, 200 évaluations/mois, Services 1 et 2 |
| Groupe | Multi-sites | Sur devis, tableau de bord consolidé |
| Consultant | Cabinet | N espaces, marque blanche, exports |

Options : évaluations supplémentaires à l'usage (tarif bas) ; mode caméras (boîtier + abonnement par site) ; audit à blanc à la mission pour les non-abonnés. Tarification régionale (plein tarif Europe, Amérique du Nord, Golfe ; 40 à 50 % Afrique, Asie du Sud-Est). Essai gratuit limité en volume, jamais en durée de conservation des données. Aucun tarif par utilisateur : la valeur est dans le travail réalisé, pas dans les sièges.

---

## 11. FEUILLE DE ROUTE

| Phase | Période | Livrables |
|---|---|---|
| **0 — Fondations** | Septembre 2026 | Multi-location et rôles, authentification, i18n FR/EN, modèle d'exigences 45001 puis 9001, 14001 et 50001, **modèle de preuve (§3.5), moteur d'applicabilité (§3.6), versionnage et journal IA, passerelle de sortie (§7.8)**, composant de transparence temporelle, système de design, tests d'isolation ; 5 pilotes gratuits (2 consultants, 3 entreprises dont une industrielle à forte consommation énergétique) |
| **1 — Audit documentaire** | Octobre | Service 2 mode A ; durcissement du Service 3 (plan d'action, balayage par zone, règles électricité/sols) ; veille Maroc ; site vitrine v1 |
| **2 — Documentation** | Novembre–décembre | Service 1 complet : formulaire, cartographie, génération, maîtrise documentaire ; premiers abonnements payants |
| **3 — Terrain, apprentissage, climat** | T1 2027 | Service 2 mode B ; brique PDCA ; espaces consultants avancés avec **tableau de pilotage multi-clients et priorités proposées** ; **préparation de revue de direction** (dossier complet assemblé depuis le graphe, décisions proposées, arbitrage humain) ; **évaluation de maturité** (5 niveaux, présentée comme auto-évaluation) ; veille France ; SEO/GEO complet ; ISO 14064-1 (bilan d'émissions) et 50002 (audit énergétique) avec validateur qualifié |
| **4 — Caméras** | T2 2027 | Connecteur, moteur local, chaîne d'événements, quota, documentation CNDP/CSE |

Chaque phase a une porte de sortie : les critères de la section 12 sont vérifiés avant d'ouvrir la suivante. Aucune fonctionnalité de phase N+1 ne démarre avant.

---

## 12. CRITÈRES D'ACCEPTATION ET INDICATEURS

### 12.1 Acceptation par module

- **Modèle d'exigences :** 100 % des clauses des normes de phase 1 modélisées, validées par l'expert, versionnées ; zéro texte normatif (test automatique).
- **Service 1 :** matrice de couverture complète ; cohérence inter-documents sans contradiction détectée ; génération < 60 min pour un jeu complet ; DOCX ouvrables et modifiables.
- **Service 2 :** score reproductible à ±5 points sur un même corpus ; chaque écart cité avec preuve ; mode B consolidé sans perte de réponse ; contradictions documenté/réel listées.
- **Service 3 :** taux de détection sur jeu de test annoté ≥ 80 % sur les règles majeures et critiques ; faux positifs < 15 % ; arrêt immédiat toujours détecté sur les cas canoniques.
- **Veille :** zéro suggestion sans source (test bloquant).
- **Multi-location :** zéro accès croisé sur la suite de tests d'isolation.
- **Langues :** zéro chaîne de l'autre langue dans un fichier produit (test).

### 12.2 Indicateurs d'exploitation

Taux de correction par règle (en baisse), taux de rejet, délai moyen de clôture des NC, part des événements caméra évalués, satisfaction des auditeurs pilotes, coût moyen par traitement, disponibilité mensuelle > 99,5 %.

---

## 13. RISQUES ET MITIGATIONS

| Risque | Mitigation |
|---|---|
| Hallucination réglementaire | Source officielle unique, suggestion bloquée sans source (P5) |
| Manuel générique refusé en certification | Profondeur du formulaire, seuil minimal avant génération, matrice de couverture, revue experte |
| Auto-validation du système par lui-même | Séparation structurelle rédaction/vérification (P4), avertissement client |
| Fuite entre espaces | Filtrage au niveau données, tests d'isolation bloquants |
| Indisponibilité du modèle | File persistante, reprises, mode dégradé notifié |
| Dérive des coûts | Quotas, coût par traitement suivi, alertes de budget |
| Rejet social ou juridique du mode caméras | Moteur local, aucun flux sortant, floutage, aucune identification, dossier CNDP/CSE fourni |
| Dépendance à un fournisseur | Interfaces neutres, routage configurable |
| Dispersion du périmètre | Portes de phase, principe de refus des demandes hors principes |
| Droit d'auteur sur les normes | Exigences reformulées, contrôle automatique, renvoi vers les organismes |

---

## 14. GLOSSAIRE

**Espace** — unité hermétique de données : un client d'un consultant, ou un site d'une entreprise.
**Modèle d'exigences** — base structurée des exigences reformulées des normes, cœur de la plateforme.
**Référentiel terrain** — ensemble de règles d'inspection dérivées du modèle d'exigences pour un secteur.
**Couverture documentaire** — degré auquel les documents traitent une exigence (0/25/60/100).
**Mise en œuvre** — degré auquel une exigence est appliquée sur le terrain, constaté par l'auditeur.
**Constat** — observation étayée par une preuve, rattachée à une règle ou une exigence, avec criticité.
**Arrêt immédiat** — niveau de criticité imposant la cessation de l'activité.
**Événement** — détection du moteur local, avec capture, en attente d'évaluation.
**Évaluation** — analyse par l'agent d'un média ou d'un événement, décomptée du quota.
**HLS** — structure commune des normes de systèmes de management ISO (chapitres 4 à 10).

---
---

# ANNEXE A — FOUNDATION PROMPT FOR CLAUDE CODE

*Paste this as the first prompt of the new development cycle. It establishes the project; subsequent prompts implement modules one at a time, each referencing the section of the specification it delivers.*

```
You are building CONSULTANT QSE IA — a multi-tenant platform where an AI agent
performs the analytical and documentary work of a QSE consultant under human
validation. The full specification is in docs/CAHIER_DES_CHARGES.md at the
repository root. Read it entirely before writing any code, then work strictly
by phases and sections; never implement a later phase early.

The existing codebase (HSE inspection agent: sector detection, media analysis,
four-level severity, human validation, PDF, email, Cloud Run, Firestore, Cloud
Storage) is version 0 of Service 3 and the reference architecture. Extend it;
do not rewrite it. Preserve every existing behaviour and every existing test.

TEN NON-NEGOTIABLE PRINCIPLES — enforce in code and in tests, not in comments:
P1  The agent proposes, the human decides. Nothing becomes effective without an
    explicit human validation action, stored with actor and timestamp.
P2  Evidence before assertion. Every finding carries evidence and a confidence;
    below threshold it is "to verify", never asserted.
P3  No individual is ever identified or described. Faces on retained captures
    are blurred. Findings reference zones and roles only.
P4  Structural independence: the Writing module and the Verification module are
    separate packages with separate prompts; Verification can only read the
    requirements model and the client's evidence. Enforce with an import
    boundary test.
P5  Regulatory suggestions require a linked official source. A suggestion with
    no source is rejected at the schema level.
P6  Never store or emit ISO standard text. Requirements are paraphrased with
    clause numbers. Add a test that fails if known standard phrasing appears.
P7  Time transparency: any job > 3 s runs asynchronously, exposes real stages
    (never fabricated), shows an estimate before start, and notifies on
    completion. The user must be able to close the tab at any time.
P8  Tenancy isolation is enforced in the data layer, not the UI. Every query is
    scoped by workspace. Add automated cross-tenant access tests that block
    deployment on failure.
P9  Every external dependency (AI provider, storage, database, queue, email,
    identity, document rendering) sits behind a neutral interface with exactly
    one implementation file. No vendor name anywhere else — including in
    pydantic Field descriptions sent to models, docstrings, and OpenAPI.
P10 French and English. User's choice applies to UI, conversations, reports,
    emails, and every produced file. No hardcoded strings in templates; message
    catalogs only. Produced files carry a language attribute.

PHASE 0 DELIVERABLES (this cycle — nothing else):
1. Data model and tenancy: Organisation → Workspace → (projects, audits,
   inspections, documents, regulatory register, non-conformities, audit log).
   Roles: owner, admin, consultant, auditor, assignee, reader. Permission matrix
   per spec §5.2. Migration of existing inspections into a default workspace.
2. Authentication via an identity provider behind a neutral interface
   (Google, Microsoft, email magic link); MFA capable.
3. i18n infrastructure: FR/EN catalogs, per-organisation default, per-user
   override, language attribute on every produced artefact, regeneration in the
   other language. Sweep the existing product into catalogs.
4. Requirements model: structured records per spec §3.4, stored as versioned
   data (YAML source of truth, loaded into Firestore), with loader validation,
   an authoring/validation workflow, and the HLS common-core mapping. Seed with
   ISO 45001 structure (paraphrased placeholders where expert content is
   pending — clearly marked, never invented as final).
5. Time-transparency component: reusable job runner exposing estimate, real
   stages, completion notification (in-app + email). Replace the existing
   landing-page progress logic with it.
6. Design system: extract the existing palette, type scale and components into
   a shared layer; the seven-entry navigation of §6.2; the service-page template
   (what it does / what you need / estimated time / start).
7. Test foundation: unit, integration on emulators, tenancy-isolation suite,
   vocabulary tests (no "conforme", no vendor names, no standard text),
   language tests.
8. Secrets redaction, structured logging, per-job cost tracking, budget alerts.

ENGINEERING RULES:
- Work in small, verified increments. After each, run the full test suite and
  report exactly what was verified against a real browser or real backend, and
  what could not be verified and why. Never claim behaviour you did not observe.
- When the spec is ambiguous or two instructions conflict, stop and ask with
  the options and a recommendation; do not guess.
- When you are unsure a library call, model name, or API behaves as assumed,
  verify by introspection or a real call before building on it.
- Preserve the existing async job architecture and neutral interfaces; extend
  them rather than duplicating.
- Every user-facing string, email, PDF and DOCX passes through i18n.
- Every new endpoint is scoped by workspace and covered by an isolation test.
- Every secret is read stripped of whitespace and redacted from all outputs.
- Commit in coherent units with messages that name the spec section delivered.

REPORTING FORMAT after each increment:
- What was delivered, mapped to spec section numbers.
- What was verified live, with the observation that proves it.
- What was not verified, and what a human must check.
- Decisions taken where the spec left room, with the alternative rejected.
- Terminology or domain judgement calls flagged for the QSE expert's review.

Start by reading docs/CAHIER_DES_CHARGES.md end to end. Then propose the
Phase 0 work breakdown as an ordered list of increments with the tests each
one adds. Do not write code until that plan is acknowledged.
```

---

*Fin du document. Révision prévue à la clôture de chaque phase.*
