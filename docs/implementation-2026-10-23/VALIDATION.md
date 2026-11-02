# Corrections de l’audit — 23 octobre 2026

Les 26 constats fonctionnels de l’audit ont reçu une correction dans les sources, avec des régressions automatisées. Le risque d’écrasement lors du staging COLMAP est également corrigé. La branche est `codex/audit-fixes-2026-10-23`, issue de `1b9e1f8`. Ces changements sont non publiés ; les tags et binaires existants restent inchangés.

La validation locale porte sur macOS arm64, Python 3.13.17 et les dépendances du nouveau verrou. **304 tests et 20 sous-tests passent, sans test ignoré**. Le wheel installé hors du dépôt et une extraction avec inférence réelle sur CPU passent aussi. Cela ne qualifie pas les binaires Windows, les GPU ou la qualité de reconstruction sur des médias réels.

## Résultats par constat

| Constat | Correction et preuve principale |
| --- | --- |
| F01 — mélange des pôles | Extension verticale séparée du bouclage horizontal, y compris les taps Lanczos. Oracle indépendant pour les pôles et la couture dans `test_geometry_analyzer.py` ; parité aperçu/export. |
| F02 — interruption et index incomplet | SIGINT coopératif, drainage des futures, erreurs conservées et manifeste terminal après les écritures. Vrais signaux envoyés entre compteur et index : 6 fichiers = 6 lignes = compteur 6, état annulé, sortie 130. |
| F03 — préréglages multisélection | Application explicite des champs du profil à toutes les cartes ; modèle personnalisé, confiance et réglages sans rapport conservés. Test avec cartes initialement hétérogènes. |
| F04 — valeurs valides écrasées | Domaines des widgets alignés et conservation de la valeur originale lorsque seul son affichage est arrondi. Tests de précision, préférences et modification indépendante sur plusieurs cartes. |
| F05 — modèle sans segmentation | Generate Mask refuse un détecteur et les détections sans masques ; Skip Frame reste compatible avec un détecteur. Tests de contrats et inférence CPU réelle séparée. |
| F06 — préférence mal formée | Les membres de `ai_mask_cameras` doivent être des chaînes, même IA désactivée ; les préférences invalides reviennent aux valeurs par défaut. Démarrage Studio testé. |
| F07 — analyse obsolète | Révision et copie des réglages associés à l’analyse ; un résultat tardif ne remplace plus les modifications intervenues depuis. |
| F08 — analyse sans validation | Validation du snapshot et du budget avant lecture, annulation pendant les tuiles de projection. Tests de refus préalable et d’annulation. |
| F09 — faces non actualisées | Reconstruction des contrôles quand le nombre de caméras/la géométrie change. Une sélection devenue indisponible reste explicitement signalée pour éviter de transformer silencieusement sa portée en « toutes les faces ». |
| F10 — fausse altitude | Altitude absente et provenance relative conservées ; aucune altitude orthométrique inventée, latitude/longitude maintenues. Tests de bout en bout SRT/GPX et EXIF. |
| F11 — dépassement EXIF | Numérateur et dénominateur rationnels bornés ; valeurs positives et négatives à 5 000 m testées par relecture EXIF. |
| F12 — statut SRT embarqué | Statut, source et provenance temporelle mis à jour après extraction effective. |
| F13 — dernière trame manquante | Suppression de la tolérance N−1. Déficit sur compte explicite en erreur ; compte conteneur estimé identifié et signalé par avertissement. Sans probe, le compte annoncé par le décodeur sert de garde stricte. |
| F14 — encodage JSON | Lecture UTF-8 explicite des configs CLI et préférences ; test avec chemin accentué non échappé. |
| F15 — coercition des caméras JSON | Les listes JSON conservent leurs types jusqu’au validateur ; booléens, fractions et mauvais conteneurs sont rejetés avec sortie 2. |
| F16 — temps d’aperçu VFR | Horodatage de l’image décodée, provenance et repli FPS explicites ; test avec un vrai petit fichier VFR généré par FFmpeg. |
| F17 — provenance FPS perdue | Horloge commune accumulant les sources temporelles, y compris sur les trames non retenues ; manifeste `mixed` et avertissement conservés. |
| F18 — date liée à l’option GPS | Lecture facultative de la date conteneur indépendamment du GPS et des sidecars ; absence de ffprobe non bloquante ; aucune date de fichier utilisée comme date de prise de vue. |
| F19 — choix de sidecar instable | Ordre déterministe : GPX valide avant SRT, avec repli si candidat invalide. |
| F20 — estimation sous-évaluée | Même normalisation des pas Frames que le moteur, inclusion de la première et de la dernière trame admissible ; compte présenté comme une estimation. |
| F21 — aperçu non annulable | Jeton d’annulation, points de contrôle et rejet des résultats périmés. Les appels natifs en cours restent non préemptibles. |
| F22 — rétention de modèles | Libération du service moteur à la fin ; invalidation du cache d’aperçu ; suspension et attente asynchrone de l’aperçu avant extraction. Annuler/fermer pendant cette attente est testé. |
| F23 — aperçu Skip Frame | Le mode d’export est respecté, avec indication visible de la vue rejetée. |
| F24 — dossiers créés trop tôt | Noms/collisions validés avant dossier de sortie, métadonnées, projection et modèle IA ; les erreurs préalables ne créent aucune sortie. |
| F25 — prérequis COLMAP tardifs | Vérification du rig, de l’exécutable et de tout l’index avant staging. Tests de rig absent/corrompu et de COLMAP absent sans création de workspace. |
| F26 — CLI Windows muet | Exécutable console distinct partageant le même bundle avec Studio. Contrat du vrai spec testé ; smoke exige version/aide visibles et décode explicitement UTF-8. Le binaire Windows reste à tester en CI/machine cible. |
| Sécurité de l’index COLMAP | Sources confinées au dataset, composants portables, destinations uniques, copie exclusive et EEXIST fatal. Tests d’évasion, symlink, doublon et course conservant les fichiers sentinelles. |
| Lacunes de tests | Mode adaptatif collecté par pytest avec assertions ; oracle de rig indépendant ; smoke du wheel réellement installé hors checkout ; sortie du smoke binaire décodée sans dépendre de la locale. |
| Typage | Les diagnostics globaux sont corrigés : 43 sources sans erreur avec la configuration actuelle. Contrôle global devenu bloquant en CI ; vérification renforcée des corps non typés maintenue sur quatre modules critiques. |

## Dépendances et exécution

Le verrou `constraints/macos-arm64-py313.lock` contient 60 paquets avec leurs empreintes. Il a été résolu et installé dans un environnement neuf, sans les paquets de Python global. Versions principales : Pillow 13.0.0, certifi 2026.10.23, urllib3 2.8.0, PySide6 6.12.0, OpenCV 5.0.0.93, NumPy 2.5.4, torch 2.14.1, torchvision 0.29.1 et Ultralytics 8.4.184. Les outils de build passent à setuptools 84.2.1, PyInstaller 6.22.3 et hooks 2026.9.

Le minimum devient Python 3.11 pour intégrer les correctifs de Pillow 13, qui abandonne Python 3.10. Les seuils certifi/urllib3 sont relevés. Sources primaires : [notes Pillow 13](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html), [avis certifi](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2), [avis urllib3](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g). Le contrôle OSV du 23 octobre ne retourne aucun avis pour les **68 dépendances et outils tiers installés** ; ce résultat n’est pas une garantie d’absence de vulnérabilité.

| Contrôle local final | Résultat | Preuve |
| --- | --- | --- |
| `QT_QPA_PLATFORM=offscreen python -m pytest -q` | 304 tests, 20 sous-tests ; 0 ignoré | [pytest.txt](pytest.txt) |
| `python -m ruff check .` | Réussi | [ruff.txt](ruff.txt) |
| `python -m mypy src` | 43 fichiers, 0 erreur | [mypy.txt](mypy.txt) |
| mypy critique avec `--check-untyped-defs --follow-imports=silent` | 4 fichiers, 0 erreur | [mypy-critical.txt](mypy-critical.txt) |
| `python scripts/check_release.py` | Cohérence 4.0.1 conservée | [release-check.txt](release-check.txt) |
| `python -m pip check` | Aucune dépendance incohérente | [VALIDATION.json](VALIDATION.json) |
| Wheel construit et installé, smoke `python -I` depuis un autre dossier | Import site-packages, QSS, CLI, pixels flat, Cube/nadir et runner autonome | [wheel-smoke.txt](wheel-smoke.txt) |
| CLI du wheel avec modèle YOLO local sur CPU | Chargement, inférence, image et masque natifs confirmés | [installed-ai-smoke.json](installed-ai-smoke.json) |
| Environnement complet, FFmpeg/ffprobe et inférence CPU | Réussi | [check-env.txt](check-env.txt) |
| OSV | 68 paquets, aucun avis retourné | [requête](osv-query.json), [réponse](osv-response.json), [versions](dependencies.json) |

Les empreintes des sources/test/configs examinés sont dans [source-hashes.json](source-hashes.json). Le SHA-256 du wheel et les limites détaillées sont dans [VALIDATION.json](VALIDATION.json). Les tests utilisent des fixtures synthétiques et des répertoires isolés ; ils ne lisent pas les préférences personnelles.

## Qualification restante

- Exécution de cette branche en CI Linux/Windows, nouveau lanceur console et binaires complets : contrats automatisés ajoutés, mais aucune exécution locale Windows ni reconstruction de bundle durant cette session.
- Inférence MPS/CUDA, précision des masques sur des personnes réelles, corpus caméra/GPS et reconstruction COLMAP complète : non qualifiés par les fixtures synthétiques. Le COLMAP externe est simulé dans les tests du runner.
- Les crashs natifs Windows historiques ne sont pas déclarés résolus par cette validation macOS. La signature/notarisation, l’inventaire complet des licences distribuées et le comportement de décodeurs natifs face à des ressources hostiles restent hors de cette qualification.
- Annulation coopérative : un décodeur ou modèle natif peut retarder l’arrêt. Une coupure brutale peut toujours laisser des fichiers partiels ; il n’y a pas de reprise automatique ni de transaction disque atomique pour une paire image/masque.
- Le build émet encore l’avertissement de dépréciation du champ de licence TOML historique ; la session ne change pas les droits de licence ni ne choisit une nouvelle expression juridique.

## Fichiers conservés et nettoyage proposé

À garder : modifications de la branche et ce dossier de preuves. Le wheel temporaire sert uniquement à la validation et n’est pas une publication.

À déplacer à la Corbeille après accord : `/private/tmp/application360-fixes-2026-10-23` (environnement, caches, modèles de test, fixtures, journaux et wheels). Mesure des blocs physiques avec `F_LOG2PHYS_EXT` et union des extents : environ **2,8 Go**, hors métadonnées APFS, contre environ 5,3 Go si les clones étaient comptés deux fois. Les fichiers de mesure sont conservés dans ce dossier. L’espace libre a été contrôlé avant l’installation ; il est passé sous 20 Gio et aucune construction lourde de binaire n’a été engagée ensuite.

Autre dossier à examiner pour nettoyage : `/private/var/folders/b0/4jf7z07j3tv328rbhgcxqdj80000gn/T/pytest-of-Nicolas/pytest-0` (environ 3,8 Mio du premier lot). `build/lib` et `src/360_extractor.egg-info` préexistants ont été actualisés par le build, environ 0,4 Mio ; le gros répertoire PyInstaller préexistant n’a pas été reconstruit ni supprimé. Aucun nettoyage final sans accord n’a été effectué.
