# Audit de 360 Extractor — 7 septembre 2026

**Verdict : la branche Studio est la plus avancée en contenu, mais elle n’est pas prête à être distribuée.** Le moteur CLI possède un socle utile et fonctionne sur les cas nominaux testés. La nouvelle interface ne peut pas démarrer une extraction ; plusieurs chemins d’erreur produisent un faux succès ; les exports GPS et COLMAP dépassent ce que l’implémentation garantit réellement.

Ce rapport est accompagné du [plan d’amélioration](PLAN.md), de l’[inventaire de couverture](INVENTAIRE.md), de résultats de reproduction et d’une capture de la véritable interface. Il remplace les conclusions générales de l’ancien audit de juillet pour cette révision. Aucun fichier applicatif, réglage personnel, commit ou branche n’a été modifié par cet audit.

## 1. Version réellement auditée

| Élément | Vérification |
|---|---|
| Dépôt | `nicolasdiolez/360Extractor`, public, branche par défaut `main` |
| Branche de travail | `feat/ui-ux-studio-redesign` |
| Commit complet | `eef3edac24f4334180955848679137c123fa3e66` |
| Date du commit | 23 août 2026, 17:41:46, Europe/Paris |
| Synchronisation | HEAD identique à la tête de cette branche interrogée directement sur GitHub le 7 septembre |
| Référence `origin/main` | `0c9d86f` ; 21 commits propres à HEAD, aucun commit de main manquant |
| Référence `origin/dev` | `bb48ba2` ; 9 commits propres à HEAD et 1 commit propre à dev |
| Particularité de dev | Le commit propre à dev est le merge de la PR 19 ; aucun changement de fichier ne manque à HEAD depuis leur ancêtre commun. La branche Studio contient les changements de distribution, via son historique de branche. |
| Autres branches distantes | `claude/v4-foundation` et `claude/v34-distribution` : contenu déjà inclus ; respectivement 15 et 9 commits supplémentaires dans HEAD |
| Branche locale de distribution | `b476849`, en avance d’un commit sur sa référence distante ; ce commit est inclus dans HEAD |
| Dernier tag/release | `v3.3`, commit `138b8e9` ; HEAD a 24 commits supplémentaires |
| Version déclarée dans le code | `3.3.0`, malgré les évolutions « v4.0 foundation » et Studio non publiées |
| PR ouverte | Aucune retournée par l’API au moment de l’audit |
| Dernière CI distante visible | Réussite du 14 juillet 2026 sur `dev` ; aucune validation de la branche Studio parmi les exécutions récentes |
| État initial du répertoire | Propre, aucun changement suivi ni fichier non suivi annoncé par Git |

La vérification a utilisé `git ls-remote --heads --tags origin`, les comparaisons d’ascendance/contenu et l’API GitHub pour les PR, CI et releases. Un simple `git status` n’aurait pas suffi : les branches locales `main` et `dev` étaient en retard sur leurs références distantes.

**Conclusion sur la version : oui, le code audité correspond à la version de développement la plus avancée disponible dans ce dépôt et dans les branches locales examinées. Cela ne signifie pas qu’il s’agit de la version la plus stable.** Aucun changement de branche ou merge n’était nécessaire. Les forks externes et les branches privées d’autres dépôts ne sont pas inclus dans cette affirmation.

Sources vérifiables : [commit audité](https://github.com/nicolasdiolez/360Extractor/commit/eef3edac24f4334180955848679137c123fa3e66), [dernière CI de dev](https://github.com/nicolasdiolez/360Extractor/actions/runs/29333741553), [release v3.3](https://github.com/nicolasdiolez/360Extractor/releases/tag/v3.3).

## 2. Périmètre et niveau de preuve

L’inventaire comprend **78 fichiers suivis**, dont **37 fichiers Python de l’application** et **10 fichiers de tests automatisés**. Les couches examinées sont : interface, CLI, configuration, orchestration, géométrie, qualité d’image, IA, télémétrie, EXIF, export COLMAP, écritures, performance, sécurité, tests, dépendances, packaging, CI, documentation, scripts de démonstration et artefacts locaux.

Trois niveaux sont distingués :

- **Reproduit** : comportement obtenu avec le code actuel sur des entrées synthétiques ou par injection contrôlée d’une panne.
- **Établi par le code / configuration** : contrat incompatible, contrôle absent ou comportement visible dans les sources ; pas de simulation d’un usage réel complet.
- **À qualifier en conditions réelles** : compatibilité caméra, précision IA, comportement GPU ou exploitation dans un logiciel tiers. Une hypothèse n’est pas présentée comme un résultat validé.

L’environnement d’exécution testé est macOS 26.6.2 arm64 avec Python **3.13**, PySide6 6.10.1, OpenCV 4.11.0.86, NumPy 2.2.6, Ultralytics 8.4.14, torch 2.7.1, torchvision 0.22.1 et Pillow 11.3.0. Le `python3` par défaut de la machine est **3.14.6 et ne dispose pas des dépendances applicatives** ; les essais utilisent explicitement Python 3.13. Les versions exactes des 42 dépendances requises présentes sont consignées dans `dependencies.json`.

Les tests ont utilisé des médias temporaires. Aucun fichier utilisateur n’a été traité. Les outils additionnels ont été installés dans un dossier temporaire, et la construction du paquet a utilisé une copie des fichiers suivis.

## 3. Résultats des vérifications

| Vérification | Résultat | Interprétation |
|---|---|---|
| Suite complète `pytest -q` | 108 tests et 20 sous-tests passent, puis arrêt avec code **134** et `QThread: Destroyed while thread '' is still running` | Échec global du processus ; les assertions réussies masquent un défaut de cycle de vie Qt |
| Sous-ensemble sans tests Studio | 100 tests et 20 sous-tests passent, code 0 | Socle nominal du moteur et des utilitaires fonctionnel |
| Couverture de ce sous-ensemble | Processor 69 %, télémétrie 43 %, géométrie 100 % des instructions ; IA et analyseur 0 % | Mesure limitée aux tests sans interface ; ne constitue pas la couverture de la suite complète ni des branches |
| Couverture totale affichée sur tout `src/extractor360` pour ce sous-ensemble | 28 % | Les fichiers GUI inclus dans le dénominateur ne sont volontairement pas exécutés ; ne pas utiliser ce chiffre isolément |
| Ruff sur les fichiers applicatifs, tests et scripts | 2 imports inutilisés dans les scripts d’illustration | Le contrôle bloquant configuré échoue |
| Mypy configuré par le dépôt | 21 erreurs dans 7 fichiers | Plusieurs erreurs relèvent des alias Qt et des annotations ; ce n’est pas un décompte de 21 bugs d’exécution |
| Mypy avec contrôle des fonctions non annotées | 81 erreurs dans 15 fichiers | Identifie notamment les méthodes et signaux inexistants du lancement GUI |
| Vérification version/changelog | Réussite, version 3.3.0 | Cohérence formelle seulement ; ne prouve ni stabilité, ni fraîcheur fonctionnelle des notes |
| Construction wheel | Réussite avec outils de build temporaires | La wheel contient 42 entrées mais **aucun `.qss`** |
| Cohérence des dépendances installées | `pip check` réussit | Ne vérifie pas la sécurité, la prise en charge GPU ou la qualité fonctionnelle |
| Audit OSV | 42 paquets interrogés ; 8 paquets signalés, 35 identifiants GHSA distincts | Alertes de l’environnement local, doublons PYSEC/GHSA non additionnés ; exploitabilité non démontrée |
| Inférence réelle du modèle local | Chargement YOLO26n-seg et inférence CPU sur image uniforme réussis | Valide le chargement et le contrat minimal, pas la qualité de segmentation sur opérateurs |
| CLI réelle | Extraction flat réussie ; réimport des résultats lors d’un second scan récursif reproduit | Parcours nominal fonctionnel, idempotence du traitement par dossier défaillante |
| Rendu Qt réel | Capture à 1520 × 920 avec options avancées ouvertes | Débordements et contrôles tronqués visibles dans l’inspecteur |

Les journaux, JSON, inventaires et la capture sont conservés dans ce dossier. Les essais d’audit complètent les tests existants ; ils ne les remplacent pas et ne modifient pas leurs attentes.

## 4. Ce qui mérite d’être conservé

Le paquet unique `extractor360` évite les collisions de noms génériques. Les imports lourds sont différés : la CLI n’importe ni Qt ni torch sans nécessité. La séparation entre événements du moteur et signaux Qt est une bonne fondation, même si Studio ne respecte plus ce contrat.

La géométrie est vectorisée ; les cartes fixes OpenCV et `grab()` sur les images intermédiaires évitent du travail inutile. Les écritures attendues à chaque frame bornent une partie de la mémoire. Les captures du moteur sont libérées dans un `finally`. Le masque nadir peut fonctionner sans IA. Les conversions de coordonnées, les quaternions et plusieurs allers-retours EXIF disposent déjà de tests utiles.

Le XML GPX utilise `defusedxml`, les processus FFmpeg sont appelés avec une liste d’arguments sans `shell=True`, et les noms personnalisés passent par `basename`. La configuration CLI a une priorité explicite défauts → JSON → arguments. La version et les notes de release possèdent un contrôle dédié. Ces éléments doivent rester couverts pendant les corrections.

## 5. Constats bloquant une livraison

### B01 — L’interface ne peut pas lancer l’extraction

**Reproduit.** `MainWindow.start_processing()` échoue immédiatement : `ProcessingBridge` n’a pas d’attribut `log_message`. D’autres incompatibilités suivent : `LogPanel.append_log`, `ProcessingBridge.all_finished`, l’argument `bridge` du constructeur et les méthodes `ProcessingWorker.start()` / `cancel()` n’existent pas. Le vrai moteur fournit `run()` et `stop()` ; le bridge fournit `attach()` et `finished`. La progression réelle est `(pourcentage, message)`, tandis que Studio la traite comme `(courant, total)`.

L’état `is_processing` est positionné avant l’erreur : le bouton est désactivé et l’application reste logiquement « en traitement ». Les événements de début, succès et erreur des jobs ne sont pas connectés aux cartes.

**Références :** `ui/main_window.py:1192–1237`, `ui/workers.py:8–31`, `core/processor.py:34–76`, `ui/log_panel.py:200`.

**Correction :** rétablir le contrat existant avec un contrôleur Qt conservé par la fenêtre, un thread explicitement géré, `bridge.attach(worker)`, et des états de jobs mis à jour à partir des événements. Restaurer l’état UI dans tous les chemins d’échec. **Acceptation :** cliquer sur « Extract Dataset » traite un média réel, écrit les fichiers, affiche leur nombre, termine sans crash et permet un deuxième lancement.

### B02 — Une écriture échouée peut être déclarée réussie

**Reproduit : 6 images annoncées, 0 fichier écrit, 0 erreur et événement `job_finished`.** Les futures sont attendues sans appeler `result()`. `images_written` augmente à la soumission et non après une écriture réussie. En parallèle, `FileManager.save_image()` et `save_mask()` ignorent le booléen de `cv2.imwrite`, et leurs booléens de retour ne sont pas exploités. `ensure_directory()` absorbe l’exception que son appelant croit pouvoir intercepter. Le writer EXIF masque aussi la distinction entre perte des métadonnées et échec total de l’image.

**Références :** `core/processor.py:147–153, 574–588, 641–656`, `utils/file_manager.py:8–40`, `core/exif_writer.py:118–139`.

**Correction :** remonter les erreurs d’écriture, examiner chaque future, compter les fichiers confirmés et traiter séparément image, masque, EXIF et manifeste. Utiliser des fichiers temporaires suivis d’un remplacement atomique. **Acceptation :** disque plein, répertoire interdit et panne de writer donnent un job en erreur, une CLI non nulle et des statistiques exactes ; aucune réussite fictive.

### B03 — Les collisions de noms détruisent silencieusement des sorties

**Reproduit : six vues deviennent un seul JPEG avec `image_pattern="same"`, le manifeste en annonce six.** Le nommage personnalisé ne vérifie ni unicité par vue/frame, ni collision image/masque. Deux sources `a/clip.mp4` et `b/clip.mov` partagent aussi `clip_processed` dans un même dossier de sortie. Une relance écrase les noms communs et laisse les anciennes vues ou anciens masques non régénérés : le dataset mélange alors plusieurs configurations.

**Références :** `core/processor.py:135–147, 577–621`, `core/job.py:22`.

**Correction :** construire un plan de sortie avant traitement, identifier chaque source et chaque run, détecter les collisions, et proposer des politiques explicites « nouveau dossier », « reprendre », « remplacer ». Vérifier les collisions de casse et les noms réservés sous Windows. **Acceptation :** deux sources homonymes et deux configurations successives restent distinctes ; aucun masque périmé n’est réutilisé ; une collision personnalisée est refusée avant la première écriture.

## 6. Interface, réglages et parcours

### U01 — Analyse du flou et gestion des threads cassées — priorité majeure

**Reproduit pour le contrat ; risque de fermeture établi par le code.** `BlurAnalysisWorker.finished` émet un dictionnaire. `_on_blur_analysis_finished()` attend deux nombres. Le chemin `error` ne demande pas l’arrêt du QThread. Il n’existe pas de fermeture globale coordonnant analyse, preview, miniatures et extraction. La miniature repose sur `__del__`, un `wait(500)` et une référence à un QObject susceptible d’être déjà détruit. Un QThread par carte fait également mal évoluer l’import de gros lots.

La fin de la suite complète a effectivement provoqué un crash QThread. L’attribution exacte de chaque crash à une miniature ou à l’analyse n’a pas été isolée ; les défauts de cycle de vie sont néanmoins explicites.

**Références :** `ui/workers.py:34–49`, `ui/main_window.py:1144–1188`, `ui/video_card.py:213–237, 299`, absence de `closeEvent` dans MainWindow.

**Action :** contrat de résultat unique, nettoyage sur succès et erreur, arrêt coopératif suivi de `join`/`wait`, résultat appliqué au job analysé même si la sélection a changé. Un pool borné pour les miniatures. Tester fermeture, retrait de carte pendant chargement et analyse impossible.

### U02 — Les réglages ne sont plus sauvegardés et certains sont perdus — priorité majeure

**Établi par le code et round-trip reproduit.** Aucune invocation de `save_settings()` n’existe dans la nouvelle fenêtre. `on_setting_changed()` modifie uniquement la mémoire du singleton quand aucune carte n’est sélectionnée ; les réglages par job ne sont pas persistés. Le getter GUI supprime `quality` et `active_cameras`, et l’interface ne représente plus les modèles L/X/personnalisés ni les valeurs de pitch arbitraires. Les champs de nommage personnalisé sont créés sans parent ni ajout dans un layout : ils ne sont pas accessibles.

Une sélection peut émettre `on_setting_changed()` pendant `set_ui_from_settings()` car plusieurs contrôles ne sont pas bloqués, provoquant des réassignations intermédiaires et des recalculs inutiles. Les cartes multisélectionnées reçoivent le même dictionnaire. Aucun modèle explicite de valeurs « mixtes » n’existe.

**Références :** `ui/main_window.py:651–655, 773–934`, `core/settings_manager.py:64–117`.

**Action :** schéma de réglages commun ; conservation des clés non modifiées ; copies par job ; chargement UI sous garde transactionnelle ; sauvegarde atomique des préférences ; restauration d’une session et d’une sélection de caméras. Tester redémarrage et aller-retour exhaustif avec valeurs non standard.

### U03 — Des éléments de démonstration se présentent comme des résultats réels — priorité majeure

**Reproduit / établi par le code.** L’overlay IA dessine une ellipse fixe sur la face Down, sans consulter YOLO, le mode IA ou les classes. Le nadir peut être dessiné même si son export est désactivé. Sur une image uniforme avec IA désactivée, l’overlay modifie effectivement l’image et le score de flou. Le badge « Apple Metal (MPS) GPU Active » est une chaîne constante, affichée aussi sur un environnement CPU ou Windows. Le temps estimé est toujours `nombre_images × 0,05 s`.

**Références :** `ui/preview_widget.py:134–156`, `ui/main_window.py:181, 1130`.

**Action :** preview issue du même masque que l’export ; chargement IA asynchrone avec cache ; overlay identifié comme indisponible tant qu’il n’est pas calculé ; matériel réellement détecté ; estimation basée sur une mesure ou clairement indiquée comme non disponible. Les illustrations de documentation doivent être identifiées comme telles.

### U04 — L’aperçu ne représente pas toujours l’image exportée — priorité majeure

Il utilise toujours six faces Cube, même pour Ring/Fibonacci ; il écrase une image flat dans un carré de 800 × 800 ; il ignore Lanczos ; il ne reprend pas le `BORDER_WRAP` du moteur. Le score de flou est calculé à la résolution preview et après accentuation/overlays, alors que l’export évalue le flou avant accentuation, à la résolution de sortie. La résolution affichée devient 800 × 800, ce qui peut être confondu avec la résolution d’export.

La génération protège les réponses d’anciens workers après qu’un nouveau worker a été lancé ; elle n’annule pas les travaux obsolètes et ne change pas immédiatement au premier changement de réglage. Le volume de travaux concurrents reste à borner.

**Références :** `ui/preview_widget.py:98–159, 343–419` ; `core/processor.py:461–509`.

**Action :** source unique des vues et opérations, ratio natif préservé, choix « résolution preview / export » explicite, scores évalués sur la même représentation, file de preview bornée. Comparer automatiquement preview et export pour les trois layouts et le mode flat.

### U05 — Des contrôles sont coupés dans l’inspecteur — priorité majeure

**Vérification visuelle réelle :** avec les options avancées ouvertes, la largeur minimale des layouts internes dépasse le panneau fixé à 360 px et le défilement horizontal est désactivé. Les cases de faces, certaines valeurs numériques et des libellés passent hors champ. Voir `studio-audit.png`. La taille minimale de fenêtre 1280 × 820 pose aussi problème sur les écrans de 768 px de haut ou à forte mise à l’échelle.

Les caractères de 10–11 px, les gris faibles, les cibles étroites et l’absence de navigation clavier explicite demandent une passe accessibilité. Le `ScrollBlocker` est instancié mais jamais installé. L’icône multi-résolution est utile, mais le bundle conserve `icon=None` dans la spec.

**Références :** `ui/main_window.py:57–58, 263–294, 551–563`, `ui/styles.qss`, `360Extractor.spec:113`.

**Action :** grilles sur plusieurs lignes, labels adaptables, inspecteur redimensionnable, panneaux repliables, ordre de tabulation et indicateurs de focus. Recette à 1280 × 720, 1366 × 768 et mises à l’échelle 100/150/200 %, sur les OS visés. Il s’agit de cibles de conception, pas de tailles actuellement supportées et vérifiées.

### U06 — Les presets sont partiels et leur libellé devient trompeur — priorité majeure

**Reproduit :** au premier affichage, « Postshot » est sélectionné alors que les réglages sont Ring et IA désactivée ; le nombre de caméras peut rester désactivé en Ring après restauration. Après passage en flat, appliquer « COLMAP Calibrated Rig » laisse `is_360=False`, et le moteur saute l’export COLMAP. D’autres valeurs héritées (pitch, classes, masques, format de noms, filtres) ne sont pas réinitialisées de manière déterministe. Modifier un réglage ne bascule pas le preset vers « Custom ».

**Références :** `ui/main_window.py:155–166, 715–768, 843–849, 919–943`.

**Action :** presets complets et versionnés, appliqués atomiquement, avec préconditions et dérivation du libellé à partir des réglages effectifs. Tester toutes les transitions entre presets, y compris depuis flat et depuis un profil personnalisé.

### U07 — Petits parcours interrompus — priorité intermédiaire

Le bouton « Open » cherche `_extracted`, alors que le moteur écrit `_processed`. Avec un dossier personnalisé, il ouvre le dossier racine plutôt que le sous-dossier du job. « Click to Browse » dans la dropzone n’est relié à aucun dialogue ; le bouton de lecture de la timeline n’a pas d’action. La dropzone disparaît après le premier import, sans autre surface de dépôt configurée. Une carte terminée peut être relancée sans politique claire de remplacement. Les extensions diffèrent entre GUI (`.insv`) et CLI (`.avi`, `.mkv`).

**Références :** `ui/main_window.py:210–212, 952–969, 1022–1026, 1072–1078, 1205–1208`, `ui/preview_widget.py:298–301`, `ui/widgets.py:70–73`, `main.py:123–130`.

**Action :** stocker le chemin de sortie réellement utilisé sur le résultat du job ; connecter ou retirer les contrôles sans action ; unifier l’import et les extensions ; séparer « nouvelle extraction » et « retraiter ».

## 7. Moteur, fichiers et qualité

### D01 — Pas de validation commune des entrées — priorité majeure

**Reproduit :** zéro caméra ou `active_cameras=[99]` donne un succès avec zéro image ; un JSON racine `[]` provoque une exception non maîtrisée dans SettingsManager ; une sortie personnalisée inexistante est remplacée silencieusement par le dossier source. Les nombres non finis, FOV nul/hors limites, tailles négatives/excessives, types JSON incorrects, modes inconnus et indices hors intervalle ne sont pas validés par un contrat commun.

**Références :** `core/settings_manager.py:71–82, 138–236`, `main.py:67–156`, `core/processor.py:140–158, 195–221`.

**Action :** parsing et validation avant création de fichiers ; erreur lisible avec champ en cause ; vérifier existence/écriture de la destination ; ne pas rediriger silencieusement la sortie. Différencier liste vide, toutes les caméras et aucune caméra. Vérifier l’unicité des noms et une estimation mémoire/disque avant exécution.

### D02 — L’import récursif reprend les résultats antérieurs — priorité majeure

**Reproduit via la CLI réelle :** une source flat traitée une fois devient deux entrées au scan du dossier parent ; le JPEG généré est retraité. Le scan inclut les sous-dossiers `_processed` et la destination, puis potentiellement les masques PNG. Les doublons de source ne sont pas éliminés et l’ordre n’est pas garanti.

**Références :** `main.py:128–132`, `ui/main_window.py:970–978`.

**Action :** exclure les répertoires de sortie et datasets connus, normaliser les chemins, dédupliquer, trier et afficher le plan d’import. Tester deux exécutions consécutives et un dossier contenant déjà images, masques et exports.

### D03 — Annulation, décodage interrompu et résultats partiels mal représentés — priorité majeure

Le worker émet `job_finished` après un arrêt coopératif et écrit un manifeste sans état « cancelled ». La fermeture du pool via `stop()` ne donne pas une politique claire aux écritures déjà soumises. Le pool n’est pas fermé explicitement dans le chemin normal. Un `read()`/`grab()` échoué est traité comme fin normale sans distinction avec un fichier tronqué ; une source qui s’ouvre mais ne fournit aucune frame peut se terminer sans erreur.

**Références :** `core/processor.py:75–76, 98–120, 391–411, 637–696`.

**Action :** état explicite par job `pending/running/succeeded/failed/cancelled`, cause de fin, résultat partiel consultable, fermeture garantie des ressources. Annulation observée entre phases et pendant FFmpeg/inférence quand possible. Ne pas déclarer complet un dataset interrompu.

### D04 — Le filtre de flou intelligent mélange les caméras — priorité intermédiaire

**Reproduit :** sur une image uniforme à score zéro, le mode Smart rejette les cinq premières faces Cube puis force l’acceptation de Down. Le compteur de skips et l’historique sont communs aux faces. Une vue de ciel influence ainsi le seuil d’une vue de sol et le plancher de qualité peut être contourné à chaque frame.

**Références :** `core/processor.py:283–288, 468–504`.

**Action :** historique par caméra ou métrique réellement agrégée par frame ; distinguer plancher absolu et variation relative ; ne pas accepter une image vide pour satisfaire un quota. Faire du fallback une politique visible. Tester orientations riches/pauvres en texture, nuit et flou de mouvement.

### D05 — L’adaptatif référence une image avant de savoir si elle sera conservée — priorité intermédiaire

`last_extracted_frame` est mis à jour avant les filtres de flou/IA et avant les écritures. Si toutes les vues sont rejetées, les décisions suivantes sont prises par rapport à une image qui n’appartient pas au dataset. `MotionDetector` transforme toute exception en score zéro, donc une défaillance devient une décision « pas de mouvement ». Le redimensionnement 256 × 144 déforme les panoramas 2:1 et les images portrait ; le seuil n’a pas de calibration documentée par géométrie.

**Références :** `core/processor.py:437–447`, `core/motion_detector.py:6–44` ; comparaison au document local `plans/adaptive_extraction_architecture.md`.

**Action :** mettre à jour la référence après conservation réelle ; distinguer erreur et immobilité ; ratio adapté ; intervalle maximal sans image et suivi de couverture. Clarifier que l’adaptatif actuel ne peut qu’éliminer les points d’échantillonnage fixes, pas récupérer un mouvement entre eux.

### D06 — Entrées 360 et qualité des pixels insuffisamment qualifiées — priorité intermédiaire

Aucun contrôle ne vérifie qu’une entrée marquée 360 est un panorama cousu. Une extension `.insv` acceptée ne constitue pas une prise en charge du double fisheye natif. Le pipeline `cv2.imread` par défaut produit des images couleur 8 bits ; les canaux alpha, profils ICC, métadonnées originales et le HDR/10–16 bits ne sont pas conservés par un contrat documenté. Le mode flat réencode les images plutôt que de préserver leur fichier original. Les cartes de projection sont testées en dimensions et en opérations, mais pas par des références visuelles indépendantes aux pôles/coutures.

**Action :** prévol codec/dimensions/ratio/projection/orientation/profondeur/couleur ; avertissement ou refus justifié ; parcours « média déjà cousu » explicite ; tests repères aux pôles et à ±180°. Définir une politique couleur SDR assumée ou une vraie chaîne HDR, avant de revendiquer la conservation photographique.

## 8. IA et masques

### I01 — Une IA indisponible est transformée en passage sans masque — priorité majeure

**Reproduit :** le constructeur intercepte une erreur de chargement et conserve `model=None` ; `process_batch()` retourne l’image sans masque. Le traitement peut donc réussir alors que l’utilisateur a demandé la suppression de l’opérateur. Le service défectueux reste mémorisé pour les jobs suivants utilisant le même modèle.

**Références :** `core/ai_model.py:72–89, 142–143`, `core/processor.py:62–72`.

**Action :** chargement validé avant traitement ; échec explicite ou choix utilisateur d’un mode dégradé ; aucune dégradation implicite ; modèle, hash, périphérique et mode réellement appliqué consignés dans le manifeste.

### I02 — « Native Softness » n’est pas une probabilité native — priorité majeure

**Reproduit et vérifié dans Ultralytics installé.** Les masques fournis par `process_mask`/`process_mask_native` sont binarisés. Sur un tenseur `uint8` représentatif, le chemin `feather_mask=True` produit uniquement 0 et 255 : le redimensionnement est effectué avant conversion en float. Même avec une entrée flottante déjà binaire, un lissage ne recréerait pas une probabilité de segmentation.

Pour les images flat non carrées, redimensionner directement `res.masks.data` sans retirer les bandes de mise au format peut déplacer/déformer le masque. Le cas exact dépend des dimensions et du prétraitement YOLO ; il exige des références annotées.

**Références :** `core/ai_model.py:108–126, 171–176` ; Ultralytics installé `utils/ops.py:481–524`, `models/yolo/segment/predict.py:99–105`. La [référence officielle Ultralytics](https://docs.ultralytics.com/reference/utils/ops) documente les sorties binaires et les opérations de remise à l’échelle.

**Action :** choisir un contrat binaire robuste ou un feather explicite après conversion flottante ; si des probabilités sont voulues, récupérer les données avant seuillage par une intégration testée. Utiliser des masques à la taille d’origine ou supprimer correctement les bandes. Tester portrait, paysage, objets partiels et bords.

### I03 — Sélection des faces/classes et sémantique de skip ambiguës — priorité majeure

Les cases GUI ne représentent que les faces Cube. En Ring/Fibonacci, garder « Down » sélectionné rend l’ensemble éligible vide sans validation : l’IA ne masque rien. Désélectionner toutes les cases signifie au contraire « toutes les faces ». Les classes inconnues sont ignorées ; tout décocher réactive silencieusement la personne par fallback. « Plants » désigne seulement la classe COCO `potted plant`, et non toute végétation. « Skip Frame » saute des vues, pas nécessairement toute la frame.

**Références :** `core/settings_manager.py:119–134`, `core/ai_classes.py:63–83`, `core/processor.py:256–277, 531–549, 590–592`, `ui/main_window.py:551–563`.

**Action :** construire la sélection depuis les vues effectives ; rejeter les sélections vides incompatibles ; séparer « toutes » et « aucune » ; afficher les classes effectivement retenues ; distinguer skip par vue et skip de capture complète. Mesurer rappel opérateur, faux positifs sur affiches, continuité temporelle et couverture des contours.

## 9. Télémétrie, EXIF et photogrammétrie

### G01 — Le parseur CAMM n’est pas conforme au format standard — priorité majeure

**Reproduit :** un paquet GPS standard de type 5 et un paquet standard de type 6 valides retournent zéro échantillon. Le code lit le type 6 comme 20 octets `(lat, lon, alt)`, alors qu’il contient notamment temps GPS, type de fix, coordonnées et mesures de précision/vitesse, sur 56 octets. Le type 5 est absent ; le type 0 est traité comme vide alors qu’il contient 12 octets. Le scan de resynchronisation peut interpréter un payload comme un nouvel en-tête.

Les tests existants construisent le même paquet simplifié que le parseur : ils valident cette erreur au lieu de vérifier l’interopérabilité. [Spécification CAMM de Google](https://developers.google.com/streetview/publish/camm-spec).

**Référence :** `utils/camm_parser.py:43–59, 79–118`, `tests/test_parsers.py:94–127`.

**Action :** table de types conforme, respect des frontières des paquets et de leurs temps de présentation ; fixtures issues de la spécification et de caméras réelles ; aucune heuristique silencieuse présentée comme GPS exact.

### G02 — GPMF : chronologie estimée et portée des facteurs de conversion incorrecte — priorité majeure

Les timestamps sont incrémentés à 18 Hz fixes ; les vrais temps de paquets, les interruptions et les indicateurs de qualité ne sont pas utilisés. `SCAL` est conservé dans une seule entrée `GPS5`, quelle que soit la portée du flux `STRM` : les échelles d’un capteur peuvent contaminer un autre si le flux attendu ne réémet pas ses facteurs. GPS9, les fixes, précisions et IMU ne sont pas traités. **Reproduit également :** `_unpack_values(..., "B", ...)` lève `IndexError` car `fmt_map[type_char][1]` est utilisé sur une chaîne d’un caractère.

**Référence :** `utils/gpmf_parser.py:13–18, 77–84, 156, 174–236`.

**Action :** facteurs limités au flux, lecture des tags de qualité et temps réels ; tests à plusieurs capteurs, fréquences et trous ; prise en charge documentée des variantes. Ne pas confondre filtration des coordonnées invalides et synchronisation correcte.

### G03 — Cap caméra, temps de capture et altitude sont trop affirmatifs — priorité majeure

Le cap de déplacement GPS est additionné au yaw virtuel et écrit comme direction optique absolue. Une caméra tenue de côté, orientée vers l’arrière ou stabilisée peut avoir une orientation différente de sa trajectoire. Sans orientation mesurée du rig, cette métadonnée est une hypothèse. Le temps de capture vient du `mtime` moins la durée ; une copie du fichier suffit à rendre cette date fausse. Les vidéos à fréquence variable et les coupures ne sont pas gérées par des timestamps réels.

Les altitudes relatives au décollage, ellipsoïdales et au niveau de la mer sont écrites via la même structure EXIF sans qualification suffisante du référentiel. « Relative (AGL) » dans l’interface n’équivaut pas à une hauteur mesurée au-dessus du terrain.

**Références :** `core/processor.py:316–327, 402–410, 625–636`, `core/telemetry.py:300–329`, `core/exif_writer.py:86–110`, `ui/main_window.py:638–642`.

**Action :** conserver provenance, référentiel et incertitude ; privilégier les temps capture/PTS réels ; ne produire une direction optique que si l’orientation du rig est connue ou son hypothèse choisie explicitement. Préserver l’information « inconnue » plutôt que fabriquer une précision.

### G04 — Extraction et interpolation GPS : états trompeurs et limites de robustesse — priorité majeure

La présence d’une piste suffit à fixer `has_gps=True` et à retourner `True` même si FFmpeg échoue ou si le parseur ne fournit aucun point. La classe n’efface pas tout son état au début d’une nouvelle extraction, ce qui la rend dangereuse si elle est réutilisée. Les sous-processus n’ont aucun timeout ni annulation, leurs sorties sont chargées intégralement en mémoire.

L’interpolation prolonge les premiers/derniers points hors de la plage et traverse les trous sans seuil de validité. Les longitudes sont interpolées naïvement à travers l’antiméridien. Les listes de temps sont reconstruites à chaque lookup, trois fois par frame avec le calcul de cap.

**Références :** `core/telemetry.py:69–149, 155–256, 258–296`.

**Action :** résultat structuré `absent/valid/partial/failed`, remise à zéro systématique, limite de taille et temps, collecte des PTS, index temporel persistant, seuils de trous et qualité, interpolation adaptée. Reporter les dégradations dans le manifeste et dans le bilan final.

### G05 — GPX/SRT : prise en charge plus étroite que la présentation — priorité intermédiaire

**Reproduit :** GPX 1.0 avec son namespace retourne zéro point ; le namespace est déclaré mais jamais utilisé. Seul le sidecar `.gpx` en minuscules est recherché. Un `.SRT` externe DJI n’est pas lu : seuls les sous-titres intégrés au conteneur sont examinés. Les temps GPX sont ramenés à zéro au premier point, sans alignement explicite avec le départ de la vidéo. Les IMU sont ignorées par les parseurs actuels malgré plusieurs mentions « GPS/IMU ».

**Références :** `utils/gpx_parser.py:21–37, 47–73`, `utils/srt_parser.py`, `core/telemetry.py:74–88, 127–135`.

**Action :** GPX 1.0/1.1, extensions insensibles à la casse, SRT externe, offset de synchronisation et prévisualisation de la trace. Limiter la promesse à GPS tant qu’une chaîne IMU n’est pas implémentée et validée.

### C01 — Les rotations du rig ne sont pas utilisées par le script COLMAP — priorité majeure

Les quaternions exportés sont cohérents avec la géométrie interne et leurs tests d’aller-retour sont utiles. Mais `reconstruct.sh` ne lit jamais `rig_rotations.json`, n’appelle pas de configuration de rig et n’associe pas les vues d’une même capture. Il fixe seulement les intrinsèques avec une caméra partagée. Le README promet pourtant que COLMAP n’a plus qu’à estimer la trajectoire.

**Référence :** `core/colmap_export.py:133–189`, `README.md` section DJI → COLMAP. Le [workflow officiel de rigs COLMAP](https://colmap.github.io/rigs.html) exige une configuration des capteurs et de leurs captures synchronisées.

**Action :** soit annoncer précisément « intrinsèques fixées et rotations fournies à intégrer », soit générer et appliquer un véritable rig pour une version de COLMAP choisie. Tester une reconstruction dont les vues ont le même centre et des rotations fixes, avec certaines vues filtrées. Ne pas supposer qu’un JSON personnalisé est un format natif consommé automatiquement.

### C02 — Les masques ne sont pas raccordés au pipeline COLMAP — priorité majeure

Le script ne transmet aucun `mask_path` et parcourt le dossier où cohabitent images et masques. Les masques `.mask.png` sont donc susceptibles d’être importés comme images, et ne sont pas appliqués à la détection de points. Le conseil de pattern `"{image_name}.png"` fourni par le README exporté donne actuellement un suffixe `.png.png`, car le moteur ajoute `.png` si `{ext}` est absent. Le preset COLMAP ne configure ni ce format ni une arborescence dédiée.

**Références :** `core/colmap_export.py:161–169, 216–218`, `core/processor.py:603–611`, `ui/main_window.py:752–764`. La [documentation officielle des masques COLMAP](https://colmap.github.io/faq.html#mask-image-regions) impose leur dossier et leur correspondance de noms.

**Action :** export `images/`, `masks/`, liste blanche des images, `mask_path` explicite et noms contrôlés. Le script doit refuser les datasets incomplets et distinguer création/reprise d’une base. Préférer un matching temporel/spatial borné à l’exhaustif pour les longues vidéos. Valider l’import et le masquage dans le logiciel réel.

## 10. Performance et ressources

### P01 — Les réglages autorisent des charges mémoire disproportionnées — priorité majeure

Toutes les maps et toutes les vues d’une frame sont gardées en mémoire ; les intermédiaires de géométrie sont principalement en float64. Les maximums GUI 64 vues × 8192² nécessitent **24 Gio de cartes fixes + 12 Gio d’images BGR**, avant les intermédiaires, l’image source, les masques et l’IA. Ce calcul découle des tableaux réellement alloués ; ce scénario extrême n’a pas été exécuté.

Mesure locale indicative de la génération d’une seule map, source 8192 × 4096, sans IA :

| Sortie | Temps | Pic mémoire du processus | Carte fixe conservée |
|---|---:|---:|---:|
| 512² | 0,014 s | 82,4 Mio | 1,5 Mio |
| 1024² | 0,052 s | 184,4 Mio | 6 Mio |
| 2048² | 0,175 s | 592,5 Mio | 24 Mio |

Ce microbenchmark n’est pas un débit d’extraction complet ni une mesure GPU. **Action :** prévision mémoire, budget selon machine, génération par blocs ou float32 validé, cache borné des maps, lots IA adaptatifs et traitement des vues par petits groupes.

### P02 — Travail coûteux répété dans le thread UI et pipeline peu recouvert — priorité intermédiaire

Chaque changement de réglage rouvre toutes les vidéos pour recalculer l’estimation ; le scan des dossiers est synchrone. Les estimations utilisent la résolution export même en flat, négligent les masques et les filtres, arrondissent le nombre de frames de manière différente du moteur et ignorent les caméras actives. Le moteur attend chaque groupe d’écritures avant de passer à la frame suivante ; le modèle reçoit toutes les vues d’un coup. L’analyseur ignore la sélection de caméras et Lanczos.

**Références :** `ui/main_window.py:1092–1138`, `core/processor.py:450–656`, `core/analyzer.py:67–79`.

**Action :** métadonnées mises en cache à l’import, estimation asynchrone et formulée comme intervalle ; profil par étape, cache du gris pour l’adaptatif, pipeline à files bornées. Les optimisations GPU/décodage doivent être conditionnées à des mesures de bout en bout et à l’équivalence des sorties.

## 11. Sécurité, confidentialité et diagnostic

### S01 — Huit dépendances installées ont des avis de sécurité — priorité majeure de maintenance

La fermeture des dépendances applicatives installées sur **cette machine** a été interrogée auprès d’OSV : 42 paquets, 8 signalés, 35 GHSA distincts, aucun avis GHSA retiré dans la réponse consultée. La présence de versions non verrouillées dans le dépôt signifie qu’un autre poste ou un build neuf peut résoudre des versions différentes.

| Paquet local | Version | Familles d’alertes à trier |
|---|---|---|
| filelock | 3.18.0 | Courses sur fichiers de verrouillage et liens symboliques |
| fonttools | 4.58.4 | Écriture de fichiers/XML dans des fonctions de manipulation de fontes |
| idna | 3.10 | Entrées spécialement construites dans l’encodage de domaines |
| Pillow | 11.3.0 | Décodeurs, fontes, opérations d’images et consommation mémoire |
| requests | 2.32.3 | Credentials `.netrc` et fichiers temporaires |
| setuptools | 80.9.0 | Exclusions de distribution source et normalisation Unicode |
| torch | 2.7.1 | Gestion de ressources et opérations bas niveau spécifiques |
| urllib3 | 2.0.7 | Redirections, en-têtes sensibles et décompression |

**Aucune compromission ni exploitabilité de ces 35 avis dans un parcours applicatif n’a été démontrée.** Plusieurs concernent des fonctions que l’application n’appelle pas directement. Le rapport brut et les versions corrigées annoncées par avis se trouvent dans `osv-results.json` et `osv-advisories.json`. Exemples documentés : [Requests / .netrc](https://osv.dev/vulnerability/GHSA-9hjg-9r4m-mvj7), [urllib3 / redirections](https://osv.dev/vulnerability/GHSA-qccp-gfcp-xxvc).

**Action :** mettre à jour dans un environnement isolé, vérifier l’applicabilité des avis, tester la combinaison torch/torchvision/Ultralytics et produire un verrouillage reproductible par plateforme. Scanner le paquet effectivement distribué, y compris ses bibliothèques natives. Ne pas assimiler `pip check` à un audit de sécurité.

### S02 — Les modèles personnalisés sont du code de confiance — priorité majeure conditionnelle

Le CLI/JSON peut transmettre n’importe quel chemin `.pt` à YOLO. Dans Ultralytics installé, `torch_load` force `weights_only=False` lorsqu’absent. Ouvrir un checkpoint tiers ne doit donc pas être traité comme lire une simple image. Aucun fichier malveillant n’a été exécuté pendant l’audit. La [politique de sécurité PyTorch](https://github.com/pytorch/pytorch/security/policy) précise que les modèles non fiables doivent être considérés comme du code non fiable.

**Références :** `core/ai_classes.py:25–43`, `core/ai_model.py:76–86`.

**Action :** registre de modèles officiels, cache privé stable, provenance et empreinte vérifiées, parcours explicite pour un modèle utilisateur de confiance ; isoler les modèles non fiables. Ne pas changer aveuglément `weights_only` sans vérifier la compatibilité du format Ultralytics. Ce risque est distinct des avis de vulnérabilité de la bibliothèque.

### S03 — Protection des sorties et fichiers entrants à compléter — priorité intermédiaire

`basename` bloque le parcours `../` direct mais ne protège pas contre un fichier ou dossier de sortie préexistant sous forme de lien symbolique. Les noms et chemins peuvent être très longs, incompatibles Windows ou contenir du texte interprété comme HTML par les logs. Les tailles de médias, de JSON, de GPX et les profondeurs des tags GPMF ne sont pas bornées par l’application. Les parseurs et codecs natifs opèrent sur les fichiers choisis par l’utilisateur, y compris potentiellement issus de tiers.

**Action :** destination privée par run, contrôle des chemins résolus/liens, écritures atomiques, budgets de taille/durée/profondeur et arrêt propre. Tester les dénis de service avec des fixtures inoffensives et bornées. La recherche ciblée de signatures de clés privées/tokens sur les fichiers suivis n’a trouvé aucune correspondance ; cela ne certifie pas l’absence de tout secret dans l’historique Git.

### S04 — Logs dupliqués, non bornés et diagnostic incomplet — priorité intermédiaire

**Reproduit :** un message du logger Application360 apparaît deux fois, car le même handler est installé sur lui et sur root avec propagation. Après 600 messages, le document Qt ne contient qu’un bloc ; la limite de 500 blocs ne limite donc pas les lignes ajoutées via `<br>`. Le message est inséré en HTML sans échappement. Les handlers ne sont pas retirés à la fermeture du panneau. La hauteur globale de 90 px contredit l’expansion interne à 150 px.

**Références :** `ui/log_panel.py:143–180`, `ui/main_window.py:252–254`, `utils/logger.py`.

Les infos de `TelemetryHandler` et `FileManager` utilisent des loggers de module alors que le logger configuré de la CLI est Application360 : certaines informations de dégradation n’ont pas le même niveau de visibilité. Le manifeste ne contient ni commit, empreinte source/modèle, versions effectives, état final, liste des fichiers validés ni dégradations. Il expose en revanche les chemins absolus ; les métadonnées GPS sont sensibles si les images sont partagées.

**Action :** une chaîne de logging, texte échappé, blocs réellement bornés, nettoyage à fermeture ; résultat structuré par job ; manifeste versionné et atomique ; export d’un rapport de support avec chemins expurgés et choix explicite d’inclure le GPS.

## 12. Packaging, CI et maintenance

### R01 — La CI ne protège pas la branche où la refonte a été développée — priorité majeure

Le workflow ne se déclenche au push que sur `main`, `dev`, `claude/**`, ni sur `feat/**`, et au pull request que vers `main`. La contribution demande pourtant des PR vers `dev`. Les dépendances du job de test excluent PySide6, mais le nouveau `test_studio_ui.py` l’importe sans condition : cette configuration ne peut pas exécuter la nouvelle suite telle quelle. Les dernières CI vertes datent d’avant la refonte. Mypy reste informatif et ne contrôle pas les corps non annotés, précisément là où le contrat de démarrage s’est cassé.

**Références :** `.github/workflows/ci.yml:3–7, 29–30, 58–66`, `tests/test_studio_ui.py:13`, `pyproject.toml:78–84`.

**Action :** protéger les branches/PR réellement utilisées ; séparer tests core et GUI ; installer les dépendances GUI dans le job adapté ; déclarer Qt offscreen avant lancement ; tester la sortie du processus, pas seulement les assertions ; rendre le typage progressif bloquant sur les interfaces critiques.

### R02 — Les tests ont des angles morts sur les promesses principales — priorité majeure

Les tests GUI couvrent surtout construction, setters et présence de widgets. Aucun ne clique sur l’extraction. Les faux MP4 utilisés pour la file ne valident pas la lecture. L’analyseur n’est pas exercé par la suite core, l’IA non plus. Les fixtures CAMM reflètent le format erroné. Les tests COLMAP vérifient des fichiers/chaînes, pas l’exécution du workflow. Les tests lisent le singleton de configuration utilisateur au lieu d’imposer partout un état isolé ; les répertoires temporaires de plusieurs tests ne sont pas nettoyés.

Les scripts locaux `verify_*` ne sont ni suivis ni collectés normalement ; le script de caméras fait référence à `create_dummy_video.py`, absent. Aucun pourcentage de couverture ne suffit à rattraper ces problèmes de pertinence.

**Action :** tests de parcours complets, injection de pannes, fixtures indépendantes des parseurs et jeux de référence annotés ; isolation de la configuration ; nettoyage déterministe ; tests d’interopérabilité réels et tests installés hors checkout. Détail dans le plan.

### R03 — Installation et distribution incomplètes — priorité majeure

**Wheel reproduite :** `styles.qss` est absent, faute de déclaration package-data. Le lancement depuis le checkout cache le défaut. La spec PyInstaller inclut bien la QSS, mais aucun poids `.pt` ni `ffmpeg`/`ffprobe`. Le commentaire « nano bundled » est donc inexact pour le build propre décrit. Le poids local est ignoré par Git, et sa résolution par simple nom dépend du répertoire courant.

La release publiée `v3.3` contient **zéro asset**, alors que le README propose des applications macOS/Windows prêtes à télécharger. Deux familles de bundles locaux coexistent : `Application360.app` annonce `0.0.0`, et `360 Extractor.app` annonce `3.3.0`. Ils n’apportent aucune preuve d’une construction depuis le commit Studio ; ils n’ont pas été utilisés comme base de l’audit.

**Références :** `pyproject.toml:48–59`, `360Extractor.spec:46–65, 111–115`, `.github/workflows/release.yml`, `.gitignore` et `local-artifacts.json`.

**Action :** package-data explicite ; test d’installation wheel ; modèle provisionné dans un cache connu ou ressource embarquée vérifiable ; prévol FFmpeg et mode hors ligne documenté ; build propre, provenance commit, smoke-test GUI + IA + télémétrie sur une machine vierge. Préparer signature/notarisation et notices des composants avant une distribution publique fiable.

### R04 — Reproductibilité et scripts d’installation fragiles — priorité intermédiaire

Les dépendances et outils de build n’ont que des bornes minimales ; aucun lock, matrice Python ou rapport de provenance binaire n’est fourni. Les listes `requirements.txt` et `pyproject.toml` sont dupliquées. La promesse Python ≥3.10 n’est testée en CI qu’en 3.11 ; l’environnement local par défaut illustre ce manque de guide.

Le helper CUDA désinstalle d’abord les paquets existants, dépend du dossier courant pour `requirements.txt`, traite plusieurs échecs comme avertissements puis annonce une fin réussie ; `setup_gpu()` retournant False n’impose pas un code non nul au programme principal. Le diagnostic ne vérifie ni FFmpeg/ffprobe ni l’ensemble des dépendances ni une inférence. Les URL CUDA fixes exigent une matrice de compatibilité maintenue. La release peut construire depuis un tag sans dépendre d’une CI complète de la même révision ; la relance peut remplacer des assets d’une release déjà publique.

**Action :** environnement isolé recommandé et identifié, résolution vérifiée avant remplacement, codes de retour corrects, dépendances/outils verrouillés, smoke-tests du même commit que la release, garde empêchant le remplacement involontaire d’artefacts publiés. Créer un inventaire de composants et licences effectivement embarqués ; ceci ne remplace pas une revue juridique de distribution.

### R05 — Documentation et architecture divergent du produit — priorité intermédiaire

La documentation cite un `AppController` et un `SignalManager` inexistants, décrit une ancienne navigation, ne couvre pas complètement les nouveaux paramètres, confond parfois Ring par défaut et indices Cube, promet IMU et rig appliqué, et maintient une version 3.3.0 identique pour des contenus très différents. La capture CLI est générée avec des messages et performances inventés par le script, dont `images.txt` que l’export ne crée pas. L’ancien audit excluait la sécurité et certaines recommandations sont déjà réalisées : le recopier aurait réintroduit des constats obsolètes.

`MainWindow` concentre 1 236 lignes et `processor.py` 716. Les chaînes UI servent de valeurs métiers ; les extensions, paramètres et transformations sont dupliqués. Sidebar et toggle personnalisés sont encore présents mais inutilisés dans Studio. `.claude/settings.local.json` versionne des autorisations et chemins de travail propres au développeur ; il ne contient pas de secret détecté, mais n’a pas sa place comme configuration partagée implicite.

**Action :** documentation générée depuis le schéma et `--help`, exemples exécutables, captures de vrais parcours, architecture décrivant les classes réelles, notes Studio datées ; contrôleur de jobs typé et étapes de pipeline testables ; supprimer ou isoler les composants de maquette/devenus inutiles. Éviter une réécriture intégrale tant que les contrats et tests de comportement ne sont pas stabilisés.

## 13. Limites explicites et recette encore nécessaire

L’examen couvre toutes les couches identifiées du dépôt, avec une profondeur adaptée et tracée dans l’inventaire. Il ne peut certifier toutes les combinaisons de médias, appareils et logiciels externes sans leurs jeux de données et environnements. Les points suivants restent **non validés expérimentalement**, et sont intégrés au plan de recette :

- Qualité IA sur de vraies scènes avec opérateurs partiels, affiches, animaux, ciel, contre-jour, trépied et coutures 360 ; débit et mémoire MPS/CUDA. L’essai effectué est une inférence CPU sur image uniforme.
- Variantes GoPro/Insta360/DJI/Kandao, GPS9, stabilisation, double fisheye natif et synchronisation sur longues vidéos réelles ; flux 10 bits/HDR/VFR/HEVC très haute résolution.
- Reconstruction complète COLMAP/GLOMAP, import RealityScan/Metashape/Postshot et bénéfice mesuré sur un dataset témoin. Les spécifications ont été consultées, les logiciels tiers n’ont pas été exécutés.
- Lancement natif Windows/Linux, écrans HiDPI, lecteurs d’écran, CUDA et politiques de signature/notarisation. Le rendu inspecté est Qt offscreen sur macOS.
- Build et test d’une application PyInstaller complète sur machine vierge. La wheel a été construite et inspectée ; les anciens bundles locaux ont été inventoriés, pas désassemblés ni considérés comme à jour.
- Recherche exhaustive de secrets dans tout l’historique, fuzzing prolongé des codecs, sécurité de toutes les bibliothèques natives embarquées et audit juridique détaillé des licences. L’analyse OSV porte sur les paquets Python installés requis et la recherche de secrets sur des signatures ciblées dans les fichiers suivis.

Ces limites n’empêchent pas de décider les premières corrections : les blocages démontrés doivent être résolus avant l’ajout de nouvelles fonctions ou une publication de Studio.
