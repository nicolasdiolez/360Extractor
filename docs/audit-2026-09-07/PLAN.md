# Plan d’amélioration de 360 Extractor

Base : commit `eef3edac24f4334180955848679137c123fa3e66`, audit du 7 septembre 2026. Les identifiants renvoient aux constats de [l’audit](RAPPORT.md). Le plan décrit les travaux proposés ; aucune correction applicative n’a été effectuée pendant l’audit.

L’objectif est de rendre Studio exploitable et ses exports fiables, puis d’améliorer la vitesse et les fonctions métier. Conserver le moteur Qt-free, les conversions géométriques et EXIF déjà testées. Corriger les contrats avant de restructurer davantage.

## 1. Ordre recommandé et charge

Les charges sont des **estimations de jours de travail effectif pour un développeur connaissant Python/Qt et le domaine**, tests et documentation compris. Ce ne sont ni des délais garantis ni un engagement de livraison. Elles supposent des décisions produit rapides et l’accès aux clips de référence ; la signature des applications, le matériel Windows/CUDA et la recette utilisateur peuvent allonger le calendrier.

| Lot | Résultat livrable | Constat couvert | Charge indicative | Dépendances |
|---|---|---|---:|---|
| L1 | Studio extrait, annule et se ferme correctement ; CI sur la vraie branche | B01, U01, R01, premiers tests R02 | 3–5 j | Aucune |
| L2 | Fichiers et états de résultat fiables ; aucun écrasement silencieux | B02, B03, D01, D02, D03, S03, manifeste S04 | 4–7 j | Contrats L1 ; travail core possible dès le début |
| L3 | Réglages, presets, aperçu et interface cohérents | U02–U07, I03, logs S04 | 4–7 j | L1 ; schéma de L2 |
| L4 | IA et filtrage qualité conformes à ce qu’annonce le produit | I01–I03, D04–D06, U04 | 4–7 j | L2, preview L3 |
| L5 | GPS/EXIF avec temps réels, provenance et erreurs explicites | G01–G05 | 5–9 j | L2 ; clips de référence |
| L6 | Export COLMAP réellement utilisable et validé | C01–C02, profils U06 | 3–6 j | L2, L4 ; L5 pour la géolocalisation |
| L7 | Installation reproductible, dépendances qualifiées et binaires testés | S01–S02, R03–R05, compléments R01–R02 | 4–7 j | Durcissement à commencer immédiatement ; livraison après L1–L6 |
| L8 | Performance mesurée, mémoire bornée et architecture consolidée | P01–P02, D05–D06, R05 | 4–7 j | Budget mémoire minimal dès L2 ; optimisations après les contrats |
| **Total** | **Socle desktop fiable et documenté** | **Tous les constats de l’audit** | **31–55 j** | Hors nouvelles fonctions exploratoires et attente externe |

Pour une personne dédiée, cela représente environ **6 à 11 semaines de réalisation**, auxquelles ajouter la recette sur des postes/captures externes. Le premier jalon peut être beaucoup plus court : L1 seul rétablit le parcours principal, mais ne suffit pas à autoriser une distribution fiable, car les erreurs de fichiers persistent avant L2.

Chemin principal : **contrats GUI → validation/résultats/sorties → preview et masques → GPS/COLMAP → recette des binaires**. L’analyse des dépendances et les corrections des déclencheurs CI commencent dès le début. Aucune refonte visuelle supplémentaire ni nouveau modèle IA n’est prioritaire avant la suppression des faux succès.

## 2. L1 — Rétablir le parcours d’extraction

**Travaux**

1. Introduire un `ProcessingController` Qt conservé par la fenêtre, propriétaire du worker et du thread. Le moteur conserve `run/stop` et ses callbacks ; le bridge conserve `attach` et ses vrais signaux.
2. Fixer les types des événements : progression en pourcentage et texte, index ou identifiant de job, résultat terminé/erreur/annulation. Préférer des identifiants stables aux positions dans une liste modifiable.
3. Connecter les événements aux cartes et au bilan. Remettre `is_processing`, boutons et progression dans un état cohérent même si le démarrage échoue.
4. Gérer un seul traitement actif, empêcher les mutations incohérentes de la file en cours et utiliser un instantané immuable des réglages de chaque job.
5. Réparer l’analyse du flou : le dictionnaire émis est transformé en recommandation documentée ; le résultat reste associé au job analysé, et non à celui sélectionné ultérieurement.
6. Arrêter/libérer analyse, miniatures et preview sur succès, erreur et fermeture ; remplacer le QThread par miniature par un pool borné. Éviter la création de QPixmap dans un worker : transmettre QImage puis créer les ressources GUI dans le thread Qt.
7. Faire fonctionner la CI sur les PR vers `dev` et `main`, et sur la branche de développement effective. Définir Qt offscreen au lancement du job GUI, installer PySide6 et dissocier ce job des tests core.

**Recette bloquante**

- Import d’une vraie petite vidéo et d’une image synthétique ; clic d’extraction ; nombre et dimensions de fichiers corrects ; progression et statut terminal concordants.
- Deux extractions successives dans la même session, dont une en erreur ; aucune fenêtre bloquée ni référence de thread invalide.
- Annulation pendant génération des maps et pendant traitement ; fermeture pendant miniatures et analyse ; code de sortie du processus égal à zéro à fermeture normale.
- Série de tests d’interface exécutée dans un sous-processus avec timeout : aucune terminaison QThread et aucune exception Qt ignorée.
- Test d’import headless toujours réussi ; le core ne doit pas dépendre de Qt pour réparer la GUI.

**Livrable :** une interface fonctionnelle sur un dataset temporaire, avec test de parcours qui échoue sur le commit audité et réussit sur la correction.

## 3. L2 — Fiabiliser les datasets et la configuration

**Travaux**

1. Définir un schéma `JobSettings` partagé : types, valeurs finies, bornes de résolution/FOV/intervalle/qualité, enums internes et migration des anciens alias. Préserver les paramètres volontairement non édités dans l’UI.
2. Construire un `OutputPlan` avant toute écriture : sources normalisées, vues effectives, noms, formats, répertoire réel, budget de mémoire et d’espace disque. Détecter collisions de noms/casse/extensions, noms Windows interdits et liens symboliques suspects.
3. Exclure la destination et les datasets antérieurs du scan d’entrée ; dédupliquer les médias et trier de façon stable. Ne pas déplacer silencieusement les résultats lorsque la destination est invalide.
4. Définir un `WriteResult` pour image, masque et métadonnées, ou lever une exception structurée. Vérifier les retours OpenCV et toutes les futures. Mettre les compteurs à jour après confirmation.
5. Écrire atomiquement : fichiers temporaires dans la destination, renommage une fois complets. Garantir la cohérence du couple image/masque et la présence d’un manifeste terminal, même partiel.
6. Donner un identifiant au run et séparer nouveau traitement, reprise et remplacement. En cas de reprise, vérifier empreinte source et réglages ; ne pas mélanger sorties produites à différentes résolutions ou différents layouts.
7. Introduire un `JobResult` avec état terminal, causes, nombres demandés/rejetés/écrits/échoués, chemin exact, warnings et durées par étape. La CLI renvoie des codes stables pour succès, échec et interruption ; le GUI affiche le même résultat.
8. Fermer pools/captures dans tous les chemins. Distinguer fin normale et arrêt de décodage anticipé autant que le backend le permet ; exposer une lecture partielle plutôt que la cacher.

**Recette bloquante**

| Cas | Résultat attendu |
|---|---|
| Writer renvoie False ou lève une erreur | Job en échec ; compteur de fichiers égal aux fichiers réels ; CLI non nulle |
| Disque plein au milieu d’un lot | Dataset partiel identifiable ; aucun fichier tronqué déclaré valide |
| Deux médias homonymes | Deux ensembles indépendants ou erreur explicite avant exécution |
| Pattern `same`, image/masque identiques | Collision refusée avant écriture |
| Deux scans successifs du dossier parent | Les sorties du premier run ne deviennent pas des sources |
| JSON liste/null, NaN, résolution négative, FOV nul | Validation explicite avant chargement IA et création de sortie |
| Caméras `[99]`, toutes désactivées | Erreur ou choix intentionnel explicite, aucun succès trompeur |
| Annulation | État cancelled/partial, fichiers terminés comptés, reprise contrôlée possible |
| Changement de format/layout entre runs | Aucune ancienne vue ni ancien masque dans le nouveau dataset |

**Livrables :** schéma documenté, tests de panne, manifeste versionné, plan d’export consultable depuis GUI/CLI. Une reprise complète peut être incrémentale, mais la prévention des mélanges et l’état partiel sont obligatoires dès ce lot.

## 4. L3 — Rendre l’interface fidèle et lisible

**Travaux**

1. Préférences globales, réglages par job et presets ont des responsabilités distinctes. Sauvegarde atomique et migration de la configuration, restauration après relance. Préparer un fichier projet versionné contenant file, réglages, sources et résultats.
2. Restaurer qualité JPEG, caméras actives, modèles L/X/personnalisés et vrais champs de nommage. Présenter les paramètres incompatibles comme tels, sans les perdre lors d’une sélection.
3. Charger les widgets sous un blocage global des notifications ; appliquer un seul changement métier à la fin. Gérer les valeurs mixtes en multisélection et copier les settings par job.
4. Transformer les presets en profils complets/versionnés, avec format de sortie et préconditions 360/flat. Si les valeurs changent, afficher « Custom ». Tester les transitions dans toutes les directions.
5. Utiliser `GeometryProcessor.generate_views` pour la sélection preview et masquage ; préserver le ratio flat. Une seule implémentation pour projection, bords, interpolation et accentuation.
6. Retirer l’ellipse IA fictive et le badge GPU constant. Afficher un état de calcul réel ou « aperçu du masque indisponible » ; raccord au masque réel dans L4. Distinguer résolution de preview, résolution export et score de qualité de référence.
7. Réorganiser l’inspecteur : cases de faces en grille, entrées sur lignes séparées, largeur ajustable, labels adaptatifs, panneaux repliables sur petit écran. Corriger hauteur/expansion des logs.
8. Brancher dropzone, navigation de dossier et lecture timeline, ou retirer les contrôles tant que leur fonction n’est pas disponible. Afficher le chemin précis de sortie et permettre de l’ouvrir depuis le résultat.
9. Mise à jour asynchrone des estimations sur métadonnées mises en cache ; pas d’ouverture de tous les fichiers à chaque mouvement de slider. Expliquer que les filtres diminuent le nombre estimé et intégrer les masques au volume.
10. Revoir focus, clavier, taille de texte et contraste ; raccourcis macOS/Windows cohérents. Installer effectivement les filtres de molette nécessaires.

**Recette bloquante :** toutes les options lisibles à 1366 × 768 et lors de la mise à l’échelle retenue ; ajout de plusieurs médias sans gel prolongé ; réglages conservés à la relance ; aperçu des vues exactes en Cube/Ring/Fibonacci/flat ; aucune mention d’IA ou GPU actif sans mesure correspondante ; le bouton de dossier ouvre les fichiers du bon run.

## 5. L4 — Masques et qualité d’image vérifiables

**Travaux**

1. Échec de chargement/inférence explicite ; mode dégradé seulement intentionnel. Enregistrer modèle, empreinte, version, périphérique, taille d’inférence et classes effectives.
2. Distinguer segmentation binaire et feather. Implémenter le feather en flottant avec une opération documentée et un rayon à l’échelle de l’image ; ne revendiquer une probabilité native que si le backend fournit réellement les valeurs avant seuillage.
3. Reprojeter le masque à la taille originale sans bandes de mise au format ; contrôler l’alignement sur images portrait et paysage. Prévoir lot et taille d’inférence bornés par la mémoire disponible.
4. Faire fonctionner la sélection de faces sur tous les layouts ; distinguer toutes/aucune ; valider les classes inconnues et les sélections incompatibles ; expliciter les limites COCO.
5. Définir deux politiques de skip : vue seule ou ensemble des vues d’un instant. Une politique partielle doit rester cohérente avec l’export de rig.
6. Corriger l’historique de flou par vue et empêcher l’acceptation forcée d’images vides. Calculer et afficher les scores sur la même représentation.
7. Mettre à jour la référence de mouvement après une image réellement conservée ; traiter une erreur de flot optique comme erreur, pas comme score nul ; ajouter une borne d’écart temporel entre images retenues.
8. Définir la politique de pixels : entrée cousue ou flat, orientation, SDR/HDR, alpha, ICC, profondeur ; documenter les conversions et pertes autorisées.

**Jeu d’essai minimal :** scènes synthétiques avec repères connus ; photos/vidéos annotées avec personne entière, bras partiel, opérateur au nadir, personne sur affiche, faible lumière, coutures panoramiques, image portrait, végétation et trépied.

**Mesures à suivre :** faux négatifs sur opérateur, faux positifs sur scène statique, recouvrement masque/référence, erreur de bord, continuité temporelle, nombre de vues retenues, mémoire et latence. Les seuils d’acceptation IA doivent être fixés après constitution du corpus représentatif ; inventer aujourd’hui un score de précision serait trompeur.

**Recette bloquante :** panne IA ne produit aucun « succès masqué » ; masque aligné à la taille de l’export ; comportement binaire/feather vérifié sur les pixels ; image noire rejetée ; sélection de faces cohérente ; aperçu et export utilisent le même résultat.

## 6. L5 — Géolocalisation et métadonnées traçables

**Travaux**

1. Introduire une lecture préservant les frontières et PTS des paquets de métadonnées. Évaluer un backend FFmpeg/PyAV par prototype ciblé ; choisir après validation des pistes CAMM/GPMF du corpus, sans migrer tout le moteur à l’aveugle.
2. CAMM : table standard des types 0–7, GPS minimal/complet, fix et précision, timestamps, rejet explicite des paquets invalides. Garder une éventuelle variante fournisseur dans un parseur distinct et identifié.
3. GPMF : portée des `SCAL` par stream, types octets corrigés, temps réels et tags de qualité, GPS5/GPS9 selon sources, tests multi-capteurs et paquets tronqués.
4. GPX 1.0/1.1 et SRT sidecar ; extensions insensibles à la casse ; offset utilisateur/calibration si la trace et la vidéo ne commencent pas ensemble. Afficher source et plage temporelle de la trace.
5. Index temporel en cache, seuil de gap et de précision, pas d’extrapolation illimitée. Gérer doublons de temps et passage d’antiméridien. Ne pas considérer la seule présence d’une piste comme succès GPS.
6. Cap optique : uniquement avec orientation connue du rig, ou hypothèse explicitement activée. Une trajectoire GPS seule n’impose pas la direction de prise de vue.
7. Temps de capture : métadonnées réelles et PTS d’abord ; mtime seulement comme approximation marquée ou omis. Différencier altitude relative, ellipsoïdale et orthométrique ; ne pas les convertir sans information de référence.
8. Timeouts, budgets de mémoire, arrêt des sous-processus et bilan `absent/partial/failed/valid`. Reporter l’information effective dans le manifeste et l’UI.

**Recette bloquante :** paquets officiels indépendants du parseur ; vérification à au moins trois instants par clip réel ; début/fin/trou de signal ; synchronisation ne dérivant pas avec la durée ; absence GPS sans fausse coordonnée ni succès fictif ; métadonnées d’orientation absentes si inconnues ; altitudes/provenance explicites.

**Livrable :** matrice caméra/firmware/format testés, fixture anonymisée par variante et résultats de comparaison. L’export IMU ou le nivellement automatique restent un chantier distinct tant que cette base GPS n’est pas validée.

## 7. L6 — Connecter réellement les logiciels de reconstruction

**Travaux**

1. Choisir et documenter la version de COLMAP supportée. Générer la structure `images/`, `masks/`, fichiers de calibration et configuration de rig appliquée, plutôt qu’un JSON seulement informatif.
2. Donner aux capteurs des identifiants stables et associer les images d’un même instant ; encoder rotations fixes et translations nulles du rig virtuel ; gérer les vues absentes à cause des filtres.
3. Conserver les intrinsèques fixes si la validation géométrique confirme le modèle ; contrôler les conventions, centre du pixel, orientation, taille et FOV par des références indépendantes.
4. Utiliser une liste blanche d’images et `mask_path` ; vérifier exactement les suffixes. Les masques ne doivent jamais être des images de reconstruction.
5. Définir matching adapté à une séquence vidéo : voisinage temporel/spatial contrôlé plutôt qu’exhaustif systématique. Distinguer nouveau workspace et reprise ; fournir une invocation utilisable sur Windows sans supposer Bash.
6. Définir des profils d’export distincts pour RealityScan/Metashape/Postshot, limités aux comportements confirmés dans chaque logiciel. Conserver un export générique documenté.

**Recette bloquante :** reconstruction réelle d’un petit dataset témoin ; vérification que le rig est chargé et que le masque empêche les points dans la région exclue ; aucune image masque dans la base ; nombres de caméras/captures/images cohérents. Comparer au minimum taux d’images enregistrées, erreur de reprojection, temps et structure de rig avec le pipeline sans priors.

L’effet sur la qualité de reconstruction doit être mesuré avant toute affirmation commerciale de gain. Les connaissances exactes du rig virtuel sont un atout, mais le stitching de la caméra et la scène peuvent introduire des erreurs que le simple modèle ne corrige pas.

## 8. L7 — Rendre l’installation et la publication fiables

**Travaux**

1. Déclarer la QSS comme donnée de package ; tester `pip install` de la wheel dans un dossier sans checkout. Vérifier aussi le sdist et le lanceur console.
2. Choisir un cache privé stable pour les modèles et inclure leur provenance. Proposer un bootstrap explicite ou un poids embarqué ; documenter le comportement hors ligne et ne jamais dépendre du CWD.
3. Détecter FFmpeg/ffprobe et tester leurs capacités avant extraction GPS ; si embarqués, inclure versions et notices dans l’inventaire de distribution.
4. Résoudre et verrouiller une combinaison compatible de dépendances sur chaque plateforme ; scanner les versions effectivement embarquées. Traiter les huit paquets signalés, avec justification documentée des éventuelles exceptions d’applicabilité.
5. Une source de dépendances et des extras adaptés : core/CLI, GUI, IA, développement. Une installation headless légère doit être possible sans imposer plusieurs distributions OpenCV concurrentes.
6. Réécrire le diagnostic pour afficher l’interpréteur utilisé, valider toutes les dépendances nécessaires au mode choisi, tester une petite inférence et signaler les outils externes manquants. Le helper CUDA prépare/résout avant remplacement et renvoie un code cohérent avec son résultat.
7. Matrice CI : Python minimum réellement supporté et versions cibles, core sur les trois OS ; GUI sur macOS/Windows ; IA CPU sur chaque changement pertinent et MPS/CUDA sur postes dédiés ou recette planifiée. Contrats typés critiques bloquants ; réduction graduelle du bruit Qt.
8. Build release depuis un commit qualifié, avec version, empreinte Git, hashes des assets, inventaire des composants, notes correctes et smoke-tests. Ne pas réécrire silencieusement une release déjà publique.
9. Signature/notarisation et icônes de bundle vérifiées selon la plateforme. Télécharger puis lancer les artefacts réellement produits sur une machine vierge avant de mettre à jour le lien de téléchargement.
10. Corriger README, aide, presets, exemples et captures ; supprimer les performances illustratives présentées comme des mesures. Ranger les anciennes maquettes et retirer les autorisations/chemins personnels de la configuration versionnée lors d’une correction dédiée.

**Recette bloquante :** paquet installé hors sources avec thème présent ; première extraction GUI/CLI, IA et GPS dans l’artefact ; version et commit retrouvables dans le diagnostic et le manifeste ; téléchargement effectif des assets macOS/Windows ; aucun avis applicable connu non traité sans décision explicite et documentée.

## 9. L8 — Optimiser après mesure et consolider l’architecture

**Travaux**

1. Instrumenter décodage, projection, filtrage, IA, encodage, EXIF et disque. Mesurer le pic RAM/VRAM et les files d’attente ; distinguer premier lancement, cache chaud et chargement des poids.
2. Conserver les métadonnées des médias, les maps réutilisables et la version réduite/grise de la dernière image retenue. Clés de cache complètes et budgets d’éviction.
3. Générer les cartes avec moins d’intermédiaires ou par tuiles. Évaluer float32 par comparaison numérique/pixel ; ne pas sacrifier la couture ou les pôles pour un gain de mémoire.
4. Séparer le pipeline en étapes testables `MediaSource`, `ProjectionPlan`, `QualityFilter`, `MaskService`, `OutputWriter`, sans changer les résultats de référence. Des files bornées superposent décodage, IA et écriture avec pression de retour.
5. Limiter batch IA, nombre de writers et travaux de preview selon la machine ; fallback CPU contrôlé si la mémoire GPU manque ; annulation prioritaire.
6. Évaluer le seek par timestamps et la projection GPU uniquement sur des benchmarks pertinents. Conserver un chemin CPU de référence et contrôler l’équivalence des sorties.
7. Supprimer les chemins GUI obsolètes et les styles dupliqués après sécurisation des parcours. Déplacer la logique métier hors de MainWindow, pas dans un nouveau monolithe.

**Matrice de mesure :** panorama 4K/8K, flat paysage/portrait, Cube 6 vues/Ring/Fibonacci, sorties 1024/2048/4096, JPG/PNG/TIFF, IA désactivée/nano/modèle plus gros, télémétrie active/non, MPS/CUDA/CPU, SSD local et destination plus lente.

**Critères :** aucune croissance mémoire non bornée avec la durée ; budget annoncé respecté dans une marge documentée ; aucun résultat périmé affiché après un nouveau réglage ; aucune dégradation de qualité sur les jeux de référence ; tableaux avant/après par étape. Ne pas annoncer « ×2 » ou « 20 images/s » sans mesure reproductible du cas visé.

## 10. Portes de validation

| Jalon | Condition pour le franchir |
|---|---|
| J1 — GUI remise en service | L1 validé, lancement/erreur/annulation/fermeture passent dans un vrai sous-processus Qt |
| J2 — Datasets fiables | L2 validé ; compteurs exacts, collisions refusées, états partiels explicites ; aucun blocage B01–B03 restant |
| J3 — Résultats fidèles | L3/L4 validés ; preview = paramètres réels ; masques alignés ; paramètres persistants ; contrôles accessibles |
| J4 — Compatibilité qualifiée | L5/L6 validés sur corpus réel ; documentation limitée à la matrice effectivement testée |
| J5 — Release candidate | L7 validé sur les artefacts téléchargés, pas seulement le checkout ; version/commit traçables ; avis de sécurité triés |
| J6 — Version optimisée | L8 mesuré et validé sans régression des J1–J5 |

Une release « core uniquement » peut être envisagée avant la fin de tous les lots si son périmètre exclut explicitement les fonctions non qualifiées. La publication de Studio complet doit attendre les critères correspondant à ses promesses. Le présent audit ne lance aucune publication.

## 11. Évolutions produit après stabilisation

Ces pistes constituent un second cycle, hors charge de 31–55 jours. Les ordonner par valeur utilisateur mesurée, sans reporter les corrections de fiabilité.

| Évolution | Valeur attendue | Prérequis / garde-fou |
|---|---|---|
| Projet sauvegardé et reprise robuste | Reprendre de longues extractions sans reconfigurer ni refaire les fichiers validés | Manifeste/résultats fiables ; empreintes sources et réglages |
| Vue de contrôle du dataset | Comprendre les trous de couverture, rejets de flou, masques et volume avant reconstruction | Statistiques par capture/vue et preview exacte |
| Réglages conseillés à partir du média | Choisir résolution, intervalle et vues adaptés à l’entrée et à la machine | Métadonnées, budgets et benchmarks représentatifs |
| Masque de ciel et objets ciblés supplémentaires | Réduire certaines erreurs de reconstruction | Corpus annoté, évaluation des faux positifs et licence du modèle |
| Outils de correction locale du masque | Corriger bras, perches et erreurs difficiles sans changer de modèle | Masques natifs alignés, undo/redo et historique par image |
| Stabilisation/nivellement IMU | Améliorer l’horizon et la cohérence des orientations | Télémétrie IMU réelle et repères capteur/caméra validés |
| Déduplication et choix de keyframes par couverture | Produire moins d’images tout en conservant la reconstruction | Mesures de reconstruction, pas seulement différences de pixels |
| Stitching double fisheye natif | Réduire les étapes externes pour certains modèles de caméra | Calibration fournisseur, couture et compensation d’exposition ; chantier distinct important |
| Traitement GPU distant | Décharger les lots lourds et exploiter la CLI | Jobs reproductibles, reprise, quotas, confidentialité des médias/GPS et modèle d’authentification |
| Inpainting génératif | Cas créatifs particuliers | Option séparée : des pixels inventés peuvent nuire à la cohérence géométrique ; conserver les images et masques originaux |

La priorité produit recommandée après la stabilisation est **projet/reprise + contrôle du dataset**, puis **qualité de masque et profils logiciels réellement validés**. Le cloud et le stitching natif demandent des architectures et des validations supplémentaires ; leur disponibilité ne doit pas être suggérée par une simple extension acceptée ou un exemple de CLI.
