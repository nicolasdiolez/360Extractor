# Implémentation des corrections — 7 septembre 2026

Branche : `codex/audit-corrections`, basée sur `eef3edac24f4334180955848679137c123fa3e66`. Le rapport d’audit reste un document historique de cette révision. Ce document décrit les corrections qui lui succèdent, enregistrées et poussées dans le commit `82cf24a` ; aucune nouvelle version publique ni aucun binaire signé n’a été publié.

**Les trois blocages démontrés sont corrigés et couverts par des tests de régression. Le plan complet n’est pas déclaré terminé : la qualification de production, plusieurs variantes métier et les profils matériels restent ouverts.**

## Livrables et tests

**Validation finale : 154 tests et 20 sous-tests passent dans l’environnement neuf, avec un code de sortie 0.** Ruff, typage des quatre modules critiques, cohérence des dépendances et contrôle de version passent également. Le paquet reconstruit a été installé hors du dépôt et vérifié avec les mêmes dépendances.

- Studio lance une extraction réelle d’image et de vidéo, met à jour les cartes et permet une deuxième extraction. Erreur, annulation et fermeture sont testées dans un processus Qt séparé, dont le code de sortie est vérifié.
- Le moteur valide les réglages et refuse les collisions avant les écritures. Chaque run dispose d’un dossier distinct. Les erreurs OpenCV/EXIF/masque remontent, toutes les futures sont examinées et les compteurs reflètent les fichiers confirmés.
- Image et masque sont préparés entièrement avant publication ; un index décrit les couples confirmés. Ce n’est pas une transaction de système de fichiers couvrant deux noms : après une coupure brutale, le manifeste initial reste `running` et l’index peut être partiel. Aucune reprise automatique n’est revendiquée.
- Réglages persistants, qualité JPEG, modèles L/X/personnalisés, pitch personnalisé, vues actives et filtres de faces sont conservés. La multisélection modifie les valeurs éditées, sans recopier toutes les valeurs du dernier média sur les autres.
- Aperçu calculé à la résolution export, score avant sharpening/overlay, layouts réels et proportions flat. Les pixels preview/export sont comparés sur Cube, Ring, Fibonacci et flat. Les masques affichés proviennent du moteur IA et du disque nadir, pas d’une ellipse de démonstration.
- Masques IA à la taille d’origine, feather explicite, chargement/inférence en erreur visible, micro-lots de deux images. Les modèles personnalisés exigent une confiance explicite. Le cache et les réglages Ultralytics sont séparés de l’installation personnelle générale ; la synchronisation d’événements de cette instance est désactivée.
- CAMM types 5/6 corrigés, offsets PTS conservés, échelles GPMF par stream, types octets et indicateur de fix corrigés, GPX 1.0/1.1 et sidecars SRT. Sous-processus bornés en temps/taille et annulables ; interpolation limitée à la trace et aux petits intervalles, passage d’antiméridien traité.
- L’échantillonnage en secondes utilise les timestamps du décodeur. Les estimations FPS sont signalées quand nécessaires. Mtime n’est plus présenté comme date de capture et la trajectoire GPS n’est plus présentée comme orientation optique. L’altitude inconnue ou relative est omise des EXIF.
- Le lanceur COLMAP applique les rigs avant matching séquentiel, construit des dossiers par caméra et place les masques dans une arborescence distincte. Il utilise uniquement l’index des sorties confirmées et un nouveau workspace.
- Projections calculées par tuiles ; miniatures et aperçu dans des pools bornés ; métadonnées des médias mises en cache pour les estimations. L’estimation de durée fictive et le badge GPU permanent ont été retirés.
- QSS inclus dans la wheel et lanceur de reconstruction inclus dans la spec PyInstaller. CI étendue aux branches utilisées, tests Qt dédiés, interfaces critiques typées et publication d’assets existants protégée. Le diagnostic et l’installation GPU renvoient des échecs explicites.

## Deux environnements examinés

| Environnement | Validation |
|---|---|
| Python 3.13.3 et dépendances historiques de la machine | Suite complète passée après les premières corrections ; le crash Qt initial ne se reproduit plus. Paquet installé hors checkout, thème chargé, CLI et petite inférence CPU réelles validés. |
| Environnement temporaire neuf `/private/tmp/360-corrections-venv` | Versions récentes installées sous contraintes de sécurité ; suite complète, lint, cohérence des dépendances, typage critique et petite inférence CPU validés. Résultats finaux dans [VALIDATION.json](VALIDATION.json). |

Le nouvel environnement contient notamment PySide6 6.11.2, OpenCV 5.0.0.93, NumPy 2.5.3, Ultralytics 8.4.142, torch 2.14.0, torchvision 0.29.0 et Pillow 12.3.0. Il n’a pas remplacé l’interpréteur ou les dépendances habituels de l’utilisateur.

**59 paquets ont été interrogés auprès d’OSV, sans avis retourné pour ces versions au moment du contrôle.** Cela ne certifie ni toutes les bibliothèques natives, ni l’absence de vulnérabilité inconnue. Le résultat concerne le nouvel environnement, pas l’ancien encore installé sur la machine. Preuves : [inventaire](qualified-dependencies.json), [réponses OSV](qualified-osv-results.json), [versions publiées PyPI](dependency-release-check.json).

La résolution macOS arm64/Python 3.13 et ses hashes sont conservés dans [le lock](../../constraints/macos-arm64-py313.lock). Les [contraintes de sécurité](../../constraints/security-minimums.txt) servent au chemin d’installation documenté et à la release. Elles ne remplacent pas un lock Windows/CUDA.

## Résultats de performance et packaging

Sur le même interpréteur, pour une carte 2048 × 2048 depuis un panorama 8192 × 4096, le pic tracé passe de **544,0 à 100,0 Mio**. Les temps mesurés sont respectivement 0,168 s et 0,169 s : aucun gain de vitesse n’est revendiqué. Les coordonnées des cartes comparées pour quatre orientations sont identiques. Ce sont des mesures ciblées, pas un benchmark de l’extraction complète ou de VRAM. Voir [geometry-validation.json](geometry-validation.json).

La wheel est construite et testée hors checkout : QSS présente et chargée, CLI fonctionnelle, masque CPU 96 × 64. Voir [installed-package-validation.json](installed-package-validation.json) et [qualified-ai-smoke.json](qualified-ai-smoke.json). La reconstruction COLMAP complète et le build PyInstaller sur machine vierge ne sont pas validés par ces essais.

## État de chacun des huit chantiers

| Lot | Réalisé | Reste à réaliser ou qualifier |
|---|---|---|
| L1 — Extraction et cycle de vie | Contrôleur, événements réels, snapshots, cartes, annulation, miniatures et analyse, tests de sortie de processus | Recette native Windows et fermeture pendant des appels longs GPU/codecs ; Qt ne permet pas d’interrompre arbitrairement un appel natif bloqué. |
| L2 — Sorties et schéma | Validation commune, préflight des noms, nouveaux dossiers, écritures vérifiées, index et manifeste, exclusion des sorties, états terminaux | Véritable reprise vérifiée, hash du média complet, prévision d’espace disque, export du plan avant lancement et résistance documentée à une coupure électrique. |
| L3 — Réglages et interface | Persistance, paramètres préservés, multisélection, presets, noms/qualité/vues, aperçu cohérent, contrôles principaux lisibles, logs bornés | Fichier projet sauvegardé, indication visuelle de toutes les valeurs mixtes, métadonnées entièrement asynchrones, recette accessibilité/HiDPI. Lecture automatique de timeline retirée ; scrubber conservé. |
| L4 — IA et qualité | Erreurs explicites, alignement des masques, feather, validation classes/faces, flou par vue sans acceptation forcée, référence de mouvement après écriture | Corpus annoté réel et métriques, politique de skip de toute une capture, calibration du seuil de flou, HDR/alpha/ICC, empreinte/provenance des poids. |
| L5 — GPS | CAMM standard, PTS paquets, GPX/SRT, échelles/fix GPMF, gaps/dateline, origine des temps et altitudes, limites des sous-processus | GPS9 refusé explicitement ; fixtures de chaque fournisseur, offset/calibration de sidecar, GPSU/GPS9 et qualité/précision complète, longs VFR/HEVC et repères d’orientation. |
| L6 — COLMAP | Index, masques séparés, configuration relative au capteur de référence, rig_configurator, matching séquentiel, lanceur portable | COLMAP absent de la machine de qualification : reconstruction réelle et vérification de la base indispensables ; profils RealityScan/Metashape/Postshot à qualifier. |
| L7 — Dépendances et livraison | Nouvel environnement sans avis OSV retourné, lock macOS, contraintes, thème empaqueté, CI et contrôle de release, diagnostic, configuration personnelle retirée de Git sans supprimer le fichier local | Locks Windows/CUDA, distributions core/gui/ai séparées, poids/FFmpeg hors ligne, signature/notarisation, binaires téléchargés sur machine vierge et notices complètes. |
| L8 — Performance et structure | Tuilage, budget de projection, petits lots IA, pools limités, cache de métadonnées et modules de validation/sorties/reconstruction | Profilage de bout en bout, budgets RAM/VRAM globaux, cache d’éviction, étapes instrumentées et files de traitement superposées ; anciens widgets à retirer après recette. |

## Correspondance avec les 37 constats

« Corrigé localement » signifie que le défaut décrit a une correction et une vérification dans le périmètre disponible ; cela ne remplace pas la recette matérielle du lot associé.

| Constats | État |
|---|---|
| B01, B02, B03 | Corrigés localement, régressions reproduites par tests. |
| U01 | Contrats et crash de suite corrigés ; appels natifs longs à qualifier. |
| U02 | Persistance/pertes de valeurs corrigées ; ergonomie des valeurs mixtes encore partielle. |
| U03, U04 | Démonstrations retirées, calculs réels ; parité des pixels testée, précision IA réelle à qualifier. |
| U05 | Débordements principaux corrigés ; audit complet d’accessibilité encore nécessaire. |
| U06, U07 | Presets et parcours principaux corrigés ; lecture automatique retirée, scrubber disponible. |
| D01, D02, D03 | Validation, scans et états corrigés ; budgets d’entrée natifs et panne d’alimentation partiellement couverts. |
| D04, D05 | Historique de flou et référence de mouvement corrigés ; calibration terrain à faire. |
| D06 | Conversions et limites documentées ; prise en charge avancée des pixels non implémentée. |
| I01, I02 | Pannes et masque doux corrigés, tests + inférence minimale. |
| I03 | Validation et faces dynamiques corrigées ; mode de skip de toute la capture non implémenté. |
| G01 | Parseur standard corrigé et paquets indépendants testés ; corpus caméra nécessaire. |
| G02 | Octets, échelles, fix et PTS améliorés ; GPS9/GPSU restent ouverts. |
| G03, G04 | Données affirmées sans preuve retirées, extraction/interpolation bornées ; métadonnées terrain à qualifier. |
| G05 | GPX/SRT améliorés ; alignement sidecar et IMU restent ouverts. |
| C01, C02 | Connexion du rig et des masques implémentée ; reconstruction réelle non certifiée. |
| P01, P02 | Allocation des cartes et tâches répétées réduites ; budgets globaux et profilage restent ouverts. |
| S01 | Profil macOS mis à jour et contrôlé ; l’ancien environnement conserve ses anciennes dépendances. |
| S02 | Confiance explicite exigée, cache isolé ; provenance cryptographique des modèles encore ouverte. |
| S03, S04 | Validation, dossiers isolés, logs et état/provenance améliorés ; protections natives, confidentialité fine et hash source restent ouverts. |
| R01, R02 | CI et tests de comportement enrichis ; matrice GPU et corpus métier encore nécessaires. |
| R03, R04 | Wheel corrigée, installation qualifiée localement et garde-fous ajoutés ; binaires et autres plateformes ouverts. |
| R05 | Architecture/README/changelog actualisés, configuration personnelle déversionnée ; consolidation complète des anciens composants encore ouverte. |

## Prochaine porte de livraison

La priorité suivante est la recette avec quelques clips réels représentatifs et une reconstruction COLMAP, puis le verrouillage Windows/CUDA et le test des binaires. Aucun bénéfice de reconstruction, taux de segmentation ou débit GPU ne doit être annoncé avant ces vérifications. Les améliorations exploratoires du second cycle du plan (cloud, stitching natif, inpainting, etc.) n’ont pas été engagées.

## Consolidation documentaire après implémentation

Les guides CLI/réglages, le README, les instructions de contribution et les notes Unreleased ont été harmonisés avec le code de correction. Le [protocole de recette](../CLI_TESTING_PROTOCOL.md) couvre Studio, CLI, GPS, reconstruction et binaires téléchargés ; la [feuille de route](../../IMPROVEMENTS.md) distingue les corrections réalisées des chantiers ouverts. Les rapports et résultats datés restent des preuves historiques ; la validation locale ci-dessus concerne la révision testée, pas une future release. La [CI du commit 82cf24a](https://github.com/nicolasdiolez/360Extractor/actions/runs/34151336481) a ensuite réussi, y compris les jobs multiplateformes configurés. Le numéro/date de la prochaine version restent à fixer après recette.

Vérification documentaire : 40 réglages par défaut et 2 contrôles additionnels comparés au code, 33 noms d’options CLI couverts, 21 commandes parsées et validées, et 9 cas CLI exécutés sur médias synthétiques (7 succès, 2 erreurs attendues). Les liens locaux et ancres ont été vérifiés. Le contrôle de version et les 20 tests des outils de release passent. Voir [documentation-validation.json](documentation-validation.json). Ces vérifications ne remplacent pas la recette sur médias réels ni celle des binaires.
