# Structures types des documents — Consultant QSE IA

Statut : BROUILLON v0.1 — proposé par l'assistant IA, à valider par Amine Boukha.
Ces structures servent de gabarits au générateur documentaire (service 1) et de
grille de lecture à l'analyseur documentaire (service 2 : « ce document répond-il
à l'exigence ? »). Chaque gabarit indique ce que l'agent préremplit et ce que le
responsable doit fournir ou valider.

## 0. Règles communes à tous les documents

**Cartouche obligatoire (en-tête ou première page)**
- Raison sociale et logo (fourni par le client)
- Titre du document, code (voir codification), version, date d'application
- Rédacteur / vérificateur / approbateur (nom, fonction, date, signature ou validation électronique)
- Statut : *projet* / *en vigueur* / *périmé*
- Historique des versions (tableau : version, date, nature de la modification)

**Codification proposée** : `[FAMILLE]-[PROCESSUS]-[NN]` avec familles POL (politique), PRO (processus), PR (procédure), IT (instruction), ENR (enregistrement), PL (plan/programme), RAP (rapport). Exemple : `PR-SST-03 Consignation des énergies`. Le client peut imposer sa propre codification : le générateur la respecte.

**Longueurs cibles** : politique 1 page ; fiche processus 1–2 pages ; procédure 2–5 pages ; instruction 1–2 pages, illustrée ; enregistrement 1 page.

**Langue** : celle choisie par l'utilisateur (FR ou EN). Les instructions destinées aux opérateurs peuvent être doublées de pictogrammes et d'une version arabe fournie par le client.

**Mention de brouillon** : tout document généré porte « Projet généré — à valider par [responsable] » en filigrane jusqu'à approbation.

---

## 1. Politique (SST / qualité / environnement / énergie)

| Section | Contenu attendu | Agent préremplit | Responsable fournit / valide |
|---|---|---|---|
| Titre et périmètre | Norme visée, sites, activités | depuis le formulaire (Q1, Q8, Q10) | valide |
| Contexte et raison d'être | 2–3 phrases sur l'activité et ses enjeux | depuis Q2, Q13 | reformule à son goût |
| Engagements | Un paragraphe par engagement exigé par la norme, adapté aux dangers réels (45001 : conditions sûres, suppression des dangers, conformité, amélioration, consultation) | propose à partir de Q19 et Q24 | tranche ce qu'il tient réellement |
| Axes prioritaires | 3 à 5 axes reliés aux risques majeurs et aux objectifs | depuis analyse des risques et Q68 | valide |
| Déploiement | Comment la politique est communiquée, revue (fréquence) | proposé | valide |
| Signature | Nom, fonction du dirigeant, date | depuis Q18 | signe |

**Critères de conformité pour l'analyseur** : signée par la direction ; datée ; contient les engagements exigés ; mentionne une revue ; cohérente avec les dangers de l'activité (pas générique) ; preuve de diffusion demandée.

## 2. Fiche processus

| Section | Contenu | Agent | Responsable |
|---|---|---|---|
| Identification | Nom, code, pilote, type (management / réalisation / support) | depuis Q23 | valide |
| Finalité | Une phrase : à quoi sert le processus | propose | valide |
| Données d'entrée / de sortie | Éléments déclencheurs, livrables | propose | corrige |
| Activités principales | 5 à 10 étapes, éventuellement en logigramme | propose | corrige |
| Interfaces | Processus amont / aval, fournisseurs, clients internes | propose | valide |
| Ressources | Humaines, matérielles, informationnelles | depuis Q27, Q57 | complète |
| Risques et exigences liés | Risques SST / qualité / environnement du processus ; exigences normatives et légales concernées | croise analyse des risques et modèle d'exigences | valide |
| Documents associés | Procédures, instructions, enregistrements | depuis la liste des documents | valide |
| Indicateurs | 2 à 4 indicateurs : définition, formule, fréquence, cible, source | propose | fixe les cibles |
| Revue | Fréquence de la revue de processus | propose | valide |

## 3. Procédure

| Section | Contenu | Agent | Responsable |
|---|---|---|---|
| 1. Objet | Ce que la procédure organise, en une phrase | propose | valide |
| 2. Domaine d'application | Sites, activités, personnes concernées, exclusions | propose | valide |
| 3. Références | Exigences normatives (par id du modèle), textes réglementaires, documents liés | remplit depuis le modèle et le registre | vérifie |
| 4. Définitions | Termes du glossaire utilisés | remplit depuis le glossaire | — |
| 5. Responsabilités | Qui fait quoi (tableau RACI simplifié) | propose depuis Q5, Q21 | corrige |
| 6. Description | Étapes numérotées : quand, qui, quoi, comment, avec quel document ; logigramme si plus de 6 étapes | propose | adapte à la pratique réelle |
| 7. Enregistrements | Liste des enregistrements produits, durée de conservation, lieu | propose | valide |
| 8. Annexes | Formulaires, schémas | génère les formulaires liés | valide |

**Critères de conformité** : objet et domaine clairs ; responsabilités attribuées ; étapes traçables ; enregistrements identifiés avec conservation ; références exactes ; approuvée par une personne différente du rédacteur.

## 4. Instruction de travail / mode opératoire

Une page recto, lisible au poste. Sections : opération concernée ; risques du poste (pictogrammes) ; EPI obligatoires ; étapes en phrases courtes, numérotées, avec photo ou schéma ; « si … alors » (que faire en cas d'anomalie) ; qui contacter. L'agent génère le texte et les pictogrammes standard ; le responsable fournit les photos réelles du poste et valide chaque étape avec un opérateur.

## 5. Enregistrement (registre, fiche, formulaire)

Champs minimaux : identifiant unique, date, lieu / zone, personne, objet, résultat, signature ou validation, champ « observations ». Pour les registres : colonnes fixes, une ligne par événement, numérotation continue. L'agent génère le gabarit vide et une ligne d'exemple ; le responsable choisit le support (papier, tableur, application).

## 6. Programme d'audit (annuel ou pluriannuel)

Tableau : processus ou site audité ; exigences couvertes (ids du modèle) ; justification de la fréquence (niveau de risque, résultats précédents, changements) ; période ; auditeur ; statut. L'agent propose le programme à partir de l'analyse des risques et des poids des exigences ; le responsable fixe les dates et les auditeurs.

## 7. Plan d'audit (pour un audit donné)

Objectifs, périmètre, critères (norme, documents internes, textes), équipe, planning heure par heure (ouverture, entretiens par fonction, visite terrain, préparation des conclusions, clôture), méthodes (entretien, observation, revue documentaire), confidentialité. L'agent génère le plan et la liste de questions par entretien depuis le modèle ; le responsable ajuste les disponibilités.

## 8. Rapport d'audit

1. Synthèse : périmètre, dates, équipe, conclusion générale, nombre de constats par catégorie (NCM, NCm, OBS, PF).
2. Résultats par chapitre ou processus : pour chaque exigence auditée, état constaté, preuves examinées, classification.
3. Constats détaillés : un bloc par constat — id, exigence concernée (id du modèle), description factuelle, preuve, classification, réponse attendue.
4. Points forts.
5. Annexes : plan d'audit, personnes rencontrées, documents examinés.

L'agent rédige les constats à partir de l'analyse documentaire et des retours terrain saisis ; l'auditeur humain valide chaque constat et sa classification avant diffusion.

## 9. Compte rendu de revue de direction

Entrées examinées (une rubrique par entrée exigée par la norme, avec les données présentées) ; conclusions sur la pertinence, l'adéquation et l'efficacité du système ; décisions (tableau : décision, responsable, échéance, ressources) ; communication prévue aux travailleurs. L'agent prépare le dossier d'entrée depuis les indicateurs, constats, actions et registre ; la direction décide et signe.

## 10. Grille d'analyse des risques (par poste ou activité)

Colonnes : unité de travail / tâche ; danger ; situation dangereuse ; dommage possible ; personnes exposées (y compris sous-traitants, visiteurs) ; mesures existantes ; gravité ; probabilité ; criticité brute ; coefficient de maîtrise ; criticité résiduelle ; classe (barème) ; mesures complémentaires (dans l'ordre de la hiérarchie) ; responsable ; échéance ; date de mise à jour. L'agent préremplit dangers et situations types du secteur à partir des règles terrain et du formulaire ; les cotations proposées sont marquées « proposition » ; le responsable cote avec les travailleurs concernés.
