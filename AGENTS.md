# 360 Extractor : contrat de développement

Application Studio Qt et CLI de préparation de médias 360° ou plats pour photogrammétrie et Gaussian Splatting. Le paquet est `src/extractor360/` ; `src/main.py` est un lanceur de développement. La version vient de `src/extractor360/core/version.py`.

## Trouver le bon contexte

| Travail | Lire |
|---|---|
| Installation, commandes et contribution | [CONTRIBUTING.md](CONTRIBUTING.md), puis la section utile du [README](README.md) |
| Moteur, interface et circulation des événements | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Accepter une extraction ou qualifier une version | [Protocole CLI](docs/CLI_TESTING_PROTOCOL.md) |
| Comprendre une correction de septembre et ses limites | [Suivi d'implémentation](docs/implementation-2026-09-07/PROGRESSION.md) ; les guides actifs et le code peuvent avoir évolué depuis |

Ne pas charger tous les audits historiques pour une correction locale, ni transformer leurs anciens résultats en état courant de la version.

## Invariants

- `ProcessingWorker` reste importable sans Qt ni torch ; l'IA se charge à la demande. Studio utilise `ProcessingController`, `ProcessingThread` et `ProcessingBridge` ; pas d'accès aux widgets depuis le moteur.
- Valider réglages et collisions avant d'écrire. Chaque exécution a son dossier ; préserver les médias originaux et les résultats existants. Préparer image et masque avant publication et indexer seulement les sorties confirmées. Deux fichiers ne constituent pas une transaction disque : un crash peut laisser un lot partiel, sans reprise automatique garantie.
- Propager les erreurs d'écriture, EXIF, masque et des futures ; compter les sorties confirmées. Annulation et fermeture doivent arrêter proprement les processus et travaux ; éviter les processus orphelins.
- L'aperçu suit géométrie, résolution, score et masque réels de l'export. Ne pas afficher une ellipse de démonstration, une estimation de temps ou un badge GPU comme preuve d'un résultat réel.
- Conserver les réglages utilisateur et modèles personnalisés. En sélection multiple, ne modifier que les champs édités. Un modèle personnalisé exige la confiance explicite prévue par l'application ; préserver l'isolation du cache Ultralytics.
- Les secondes reposent sur les horodatages décodés ; signaler le repli sur FPS. La date de fichier n'est pas une date de capture. Ne pas inventer altitude ou orientation optique depuis une trajectoire GPS ; conserver les limites d'interpolation et les conventions de coordonnées.
- COLMAP utilise l'index confirmé, des dossiers par caméra et les masques séparés ; préparer les rigs avant matching et un espace de reconstruction neuf.
- Garder les QSS dans le paquet, les outils de publication hors du wheel et les profils de dépendances propres aux plateformes. Un verrou macOS ne qualifie pas Windows/CUDA.

## Vérifier et terminer

Commandes de référence dans l'environnement du projet : `python -m pytest -q`, `python -m ruff check .`, `python scripts/check_release.py`. Pour Qt sans écran, utiliser `QT_QPA_PLATFORM=offscreen` selon CONTRIBUTING. Choisir les régressions concernées ; pour une livraison, suivre tous les contrôles prévus par CONTRIBUTING et le protocole d'acceptation. Ne pas déclarer une validation IA complète lorsque ses tests sont ignorés.

Rapporter le comportement obtenu et les limites effectivement observées. Tests de sources, roue installée, binaire distribué, GPU et médias réels sont des validations différentes. Préserver les tags et assets publiés ; suivre le circuit de version, branche et brouillon de release documenté. Un historique de préversion n'est pas une autorisation de publier une nouvelle version stable.
