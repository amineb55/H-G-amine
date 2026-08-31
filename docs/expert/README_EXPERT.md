# docs/expert — Apports de l'expert QSE (brouillon v0.1)

**Projet :** Consultant QSE IA — **Expert :** Amine Boukha
**Statut global :** brouillons rédigés par l'assistant IA le 31 août 2026 (v0.1, approfondie aux quatre normes), **à relire, corriger et valider par Amine avant toute intégration**. Conformément au partage des rôles (document « Apports de l'expert », §14), la version retenue est celle de l'expert ; rien ici ne doit être intégré tel quel.

## 1. Contenu livré

| Apport | Fichier(s) | État | Volume |
|---|---|---|---|
| 1. Modèle d'exigences ISO 45001 | `exigences/exigences_45001_ch4-7.yaml`, `exigences/exigences_45001_ch8-10.yaml` (+ `exigences_45001_relecture.xlsx`) | brouillon complet, FR seulement | 55 enregistrements (cible 60-70 : Amine peut éclater 6.1.2.1, 8.1.1a ou 9.1.1a s'il le juge utile) |
| — liste des types de documents | `exigences/documents_types.yaml` | brouillon | 136 slugs (4 normes) |
| 2. Modèles 9001 / 14001 / 50001 | `exigences/exigences_9001.yaml`, `exigences_14001.yaml`, `exigences_50001.yaml` (+ onglets du classeur exigences) | brouillons complets, exigences spécifiques + nuances du tronc commun (champ `nuance_de`) | 29 + 19 + 20 enregistrements ; 50001 à faire valider par un auditeur énergie |
| 3. Référentiels terrain | `regles_terrain/industrie.yaml`, `sante.yaml`, `logistique.yaml`, `hotellerie_restauration.yaml` + **`environnement.yaml` (ENV, ISO 14001) et `energie.yaml` (ENE, ISO 50001), transverses à tous les secteurs** (+ `regles_terrain_relecture.xlsx`) | brouillon complet avec `indices_visuels` et `exclusions` | 6 × 12 = 72 règles |
| 4. Formulaire de cadrage | `formulaire/questions_cadrage.yaml` (+ `questions_cadrage_relecture.xlsx`) | brouillon complet | 88 questions : 70 communes / sectorielles + 9 spécifiques 9001 + 9 spécifiques 14001 + bloc énergie 50001 |
| 5. Structures types des documents | `structures_documents/structures_types.md` | brouillon | 10 gabarits |
| 6. Échelles et barèmes | `baremes/baremes.yaml` | brouillon, seuils à trancher | 4 niveaux, grille 4×4, NC, couverture, poids |
| 7. Arbre de décision outils qualité | `outils_qualite/arbre_decision.yaml` | brouillon | 6 questions, 9 branches |
| 8. Sources réglementaires Maroc | `reglementaire/sources_maroc.md` | brouillon, **toutes références « à vérifier »** | ~30 textes |
| 9. Glossaire FR/EN | `glossaire/glossaire_fr_en.yaml` (+ `glossaire_fr_en_relecture.xlsx`) | brouillon | 121 termes |
| Garde anti-copyright | `guard/motifs_interdits.yaml` | brouillon | motifs FR/EN |
| 11. Jeux de test | `tests/README_jeux_de_test.md` | gabarit d'annotation seulement | 0 média (Amine) |
| Outil de contrôle | `tests/valider_et_exporter.py` | fonctionnel | validation croisée + export Excel |
| 10. Identité / juridique, 12. Pilotes | — | **non produits** : dépendent de décisions et de contacts d'Amine (voir §5) | — |

Contrôle au 31/08/2026 : `python docs/expert/tests/valider_et_exporter.py` → 0 erreur ; les avertissements listent les équivalences HLS portées par le tronc commun (normal). Total : 123 exigences, 72 règles terrain, 88 questions, 136 types de documents, 121 termes.

## 2. Ordre de relecture conseillé (ce que le document « Apports » demande)

1. **Caler la référence** : relire les 5 premiers enregistrements du chapitre 6 dans `exigences_45001_relecture.xlsx` (45001-6.1.1 → 45001-6.1.3a). Corriger le niveau de détail, le ton, la longueur. Envoyer ces 5 lignes au partenaire de structuration avant d'enchaîner.
2. Relire le reste du chapitre 6, puis 8, 9, 10, puis 4, 5, 7. Pour chaque ligne : colonne *Validation* = OK / à modifier / à supprimer, colonne *Commentaire*. Ne pas hésiter à supprimer une preuve ou une question qui ne correspond pas à ce qu'Amine fait réellement en audit : c'est ce qui rend le produit spécifique.
3. Test copyright à faire soi-même : si une phrase est reconnaissable comme celle de la norme, la réécrire. Le script bloque déjà « doit / doivent » et les tournures normatives, mais il ne voit pas la paraphrase trop proche.
4. Barèmes (`baremes.yaml`) : trancher les délais (0 / 15 / 30 / 90 jours), les seuils de la grille 4×4, les coefficients de maîtrise, le seuil « prêt pour audit ». Ce sont des choix d'expert, pas des faits.
5. Règles terrain : vérifier surtout `indices_visuels` (ce qu'on voit) et `exclusions` (les faux positifs). Rattacher les règles BTP-xx et BUR-xx existantes aux exigences (champ `regles_terrain`) — l'assistant ne connaît pas leur contenu.
6. Formulaire : reformuler les questions dans le langage des clients marocains ; confirmer les `seuil_minimal`.
7. Réglementaire : vérifier chaque numéro de texte et chaque seuil sur le BO ou Adala avant d'enlever la mention « à vérifier ».

## 3. Mettre les fichiers dans le dépôt (Windows / PowerShell, pas à pas)

Prérequis : Git installé (fait en août), dépôt `H-G-amine` cloné (sinon : `git clone https://github.com/amineb55/H-G-amine.git`).

1. Télécharger `docs_expert_v0.1.zip` et le décompresser : clic droit → *Extraire tout*. On obtient un dossier `docs_expert_v0.1` contenant `docs\expert\...`.
2. Ouvrir PowerShell : touche Windows, taper `PowerShell`, Entrée.
3. Aller dans le dépôt (adapter le chemin) :
   `cd C:\Users\<votre_nom>\Documents\H-G-amine`
4. Copier le dossier (adapter le chemin du zip décompressé) :
   `Copy-Item -Recurse -Force "C:\Users\<votre_nom>\Downloads\docs_expert_v0.1\docs\expert" ".\docs\"`
   Si `docs` n'existe pas encore : `New-Item -ItemType Directory -Force docs` avant.
5. Vérifier : `Get-ChildItem -Recurse .\docs\expert | Select-Object FullName` — les YAML, MD et XLSX doivent apparaître.
6. Contrôler les fichiers (Python doit être installé ; sinon `winget install Python.Python.3.12`) :
   `pip install pyyaml openpyxl` puis `python .\docs\expert\tests\valider_et_exporter.py`
   Attendu : « 0 erreur(s) ».
7. Enregistrer dans Git :
   `git add docs/expert`
   `git commit -m "docs(expert): brouillons v0.1 des apports expert QSE"`
   `git push`
8. Quand la relecture est faite : reporter les corrections dans les YAML (ou renvoyer les XLSX annotés au partenaire de structuration qui le fera), relancer l'étape 6, recommiter.

Ne coller le prompt de remise à Claude Code (§15 du document « Apports ») **qu'après** validation des apports 1, 4, 6 et 9 : sinon le code intégrera des brouillons comme source de vérité.

## 4. Conventions utilisées

- Ids d'exigence : `norme-clause`, suffixe `a/b/c` quand une clause est éclatée (`45001-8.2a`). Le loader doit accepter ce suffixe.
- Tronc commun HLS : une exigence commune n'est écrite qu'une fois, dans le fichier 45001 (`hls_commun: oui`, `equivalences` vers les clauses 9001 / 14001). Les fichiers 9001 / 14001 / 50001 ne contiennent que les exigences spécifiques et les nuances ; le champ optionnel `nuance_de` indique l'enregistrement commun qu'une nuance précise. Le loader doit accepter ce champ et, pour une norme donnée, assembler : exigences communes du 45001 + exigences du fichier de la norme (une nuance remplace l'exigence commune qu'elle précise).
- Règles terrain : IND / SAN / LOG / HOR (+ BTP / BUR existantes) sont sectorielles et SST ; ENV et ENE sont transverses et s'activent quand 14001 ou 50001 est dans le périmètre choisi par l'utilisateur.
- `criticite_defaut` des règles terrain : 4 critique, 3 majeure, 2 mineure, 1 observation. Les clés des YAML terrain sont à aligner sur `app/rules/bureaux.yaml` et `btp.yaml` si le format diffère.
- Tout ce qui touche au droit marocain porte « à vérifier » tant qu'Amine n'a pas contrôlé le texte.
- `exigence_en` et `titre_en` : titres EN proposés, exigences EN vides (traduction prévue par le partenaire de structuration après validation du FR).

## 5. Ce qui reste et qui ne peut venir que d'Amine

**Apport 2** — relire les trois fichiers 9001 / 14001 / 50001 avec le même soin que 45001 (`plan_apport2_9001_14001_50001.yaml` reste comme carte des sujets couverts). Pour 50001 : choisir entre formation auditeur 50001 et validation par un auditeur énergie partenaire ; le nom du validateur sera affiché.

**Apport 10 — identité et juridique** (gabarit à remplir) :
- Nom définitif du produit (« Consultant QSE IA » n'est pas définitif) ; vérifier `.com`, `.ma`, `.ai`.
- Structure juridique porteuse, adresse, ICE / RC / IF, pays d'établissement.
- Juriste de référence (CGV, contrat de sous-traitance de données, loi 09-08, RGPD si clients européens).
- Biographie professionnelle et certifications (9001, 14001, 45001) pour la page « À propos ».
- Brief logo / couleurs.

**Apport 11** — 15 à 20 photos ou vidéos par secteur, prises par Amine, annotées selon `tests/README_jeux_de_test.md` ; 2 à 3 systèmes documentaires anonymisés avec score de couverture ; une checklist terrain remplie.

**Apport 12 — pilotes** (gabarit) : pour chacune des 5 organisations (2 consultants, 3 entreprises de secteurs différents) — nom, secteur, taille, contact, ce qu'elle attend, ce qu'elle accepte de tester, contrepartie (gratuité, accompagnement, tarif préférentiel), accord écrit d'une page.

**Décisions à prendre** : seuil d'effectif du comité de sécurité et d'hygiène (50 salariés — à confirmer) ; délais de déclaration d'accident ; rattachement des règles BTP/BUR ; confirmation que 45001 reste la norme de lancement.
