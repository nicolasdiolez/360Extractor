# Validations et preuves conservées

Audit du 7 septembre 2026, commit `eef3edac24f4334180955848679137c123fa3e66`. [Rapport](RAPPORT.md) · [Plan](PLAN.md) · [Inventaire](INVENTAIRE.md).

Les résultats ci-dessous décrivent les essais effectués pendant l’audit. Les sondes montrent le comportement actuel, y compris ses défauts ; elles ne constituent pas des tests d’acceptation pour une version corrigée.

## Environnement et préservation

Les essais applicatifs ont utilisé `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`, sur macOS 26.6.2 arm64. Python 3.14.6, disponible par défaut, ne possède pas les dépendances de l’application. Les versions requises et présentes sont dans [dependencies.json](dependencies.json).

Coverage, mypy et les outils de construction supplémentaires ont été installés dans `/private/tmp/360-audit-tools-20260907`. La construction a utilisé une copie des fichiers suivis dans `/private/tmp/360-audit-build-20260907`. Les essais de médias et d’erreurs d’écriture ont utilisé des fichiers temporaires. Le rendu Qt est offscreen. Aucun média de l’utilisateur n’a été traité, aucun correctif du produit n’a été appliqué.

La comparaison finale des 78 empreintes SHA-256 avec l’état initial ne détecte aucune modification : [integrity-check.json](integrity-check.json). Le dossier de rapport est le seul ajout au projet visible dans Git.

## Version et état distant

La vérification a combiné l’interrogation directe des têtes et tags (`git ls-remote --heads --tags origin`), les comparaisons de commits/contenu et les réponses de l’API GitHub pour les branches, PR, releases et exécutions CI. Les résultats sont détaillés dans la section 1 du rapport. Ces consultations ne créent ni branche, ni commit, ni publication.

La branche Studio locale et distante pointe vers `eef3eda`. Elle contient tous les changements de main, avec 21 commits supplémentaires. Dev possède un commit de merge non ancêtre de Studio, mais aucun changement de fichier supplémentaire à intégrer depuis leur ancêtre commun. Aucun PR ouvert ni branche plus avancée en contenu n’a été identifié dans le périmètre examiné.

## Résultats d’exécution

| Vérification | Résultat observé | Preuve et limite |
|---|---|---|
| Suite complète | 108 tests + 20 sous-tests réussis en 24,80 s, puis `QThread: Destroyed while thread '' is still running`, sortie 134 | Sortie observée dans la session d’audit ; le journal intégral de ce premier lancement n’a pas été conservé dans un fichier. Il ne s’agit pas d’une suite verte. |
| Suite sans Studio | 100 tests + 20 sous-tests réussis, sortie 0 | [core-tests.txt](core-tests.txt) ; ne couvre pas le cycle de vie GUI. |
| Couverture de cette suite partielle | 28 % sur tout le paquet ; processor 69 %, télémétrie 43 %, géométrie 100 % des instructions | [coverage.txt](coverage.txt) ; GUI exclue de l’exécution mais incluse dans le dénominateur, pas de couverture des branches, pas de preuve de justesse physique exhaustive. |
| Ruff sur src/tests/scripts | 2 imports inutilisés, sortie non nulle | [ruff.txt](ruff.txt). |
| Mypy configuré | 21 erreurs, 7 fichiers | [mypy.txt](mypy.txt) ; inclut des défauts d’annotation. |
| Mypy avec corps non annotés | 81 erreurs, 15 fichiers | [mypy-expanded.txt](mypy-expanded.txt) ; met notamment en évidence les contrats de lancement cassés. |
| Garde de release | Cohérence formelle validée pour 3.3.0 | Sortie observée en session ; ne constitue pas une validation du produit. |
| pip check | Aucune dépendance incompatible annoncée | Sortie observée en session ; ne vérifie ni sécurité ni GPU. |
| Construction du paquet wheel | Réussite après ajout de wheel aux outils temporaires | [wheel-build.txt](wheel-build.txt) ; premier essai arrêté faute d’outil wheel, sans modification de l’environnement global. |
| Ressources de la wheel | 42 entrées, aucun QSS, aucun poids PT | [wheel-inspection.json](wheel-inspection.json) ; pas de build complet PyInstaller. |
| Sondes fonctionnelles ciblées | Échecs GUI, faux succès d’écriture, collision, réglages perdus, formats GPS, logs et aperçu | [probe-results.json](probe-results.json), [probes.txt](probes.txt), [probes.py](probes.py). |
| IA | Panne de modèle simulée, masque binaire, chargement réel du modèle local et inférence CPU minimale réussie | [ai-probes.json](ai-probes.json) ; image uniforme 64 × 64, sans évaluation de précision. Le temps inclut les opérations de cette sonde et n’est pas une mesure de débit. |
| CLI et filtrage | Extraction flat réelle réussie ; deuxième scan récursif reprend les sorties ; une vue uniforme conservée par le flou intelligent | [extra-probes.json](extra-probes.json). |
| Géométrie | Temps et mémoire à 512, 1024 et 2048 pixels | [geometry-benchmark.json](geometry-benchmark.json) ; un seul échantillon par taille, source 8192 × 4096, pas de benchmark statistique. Le cas extrême 64 × 8192² est une estimation analytique, jamais alloué. |
| Dépendances OSV | 42 paquets interrogés ; 8 signalés ; 35 avis GHSA distincts | [osv-results.json](osv-results.json), [osv-advisories.json](osv-advisories.json) ; environnement installé, pas d’exploit exécuté, alias non additionnés. |
| Anciennes applications locales | Deux familles de bundles, versions 0.0.0 et 3.3.0 | [local-artifacts.json](local-artifacts.json) ; aucun lien de provenance démontré avec Studio. |
| Rendu réel Studio | Fenêtre 1520 × 920, options avancées ouvertes | [studio-audit.png](studio-audit.png) ; Qt offscreen, pas de recette native de tous les écrans et plateformes. |

Les sondes IA complémentaires, CLI et mémoire ont été exécutées dans la session avec des entrées synthétiques ; leurs résultats JSON sont conservés, leurs commandes ad hoc complètes ne sont pas toutes emballées en scripts autonomes. Le script `probes.py` conserve les reproductions principales. Aucun résultat absent n’a été reconstruit sous la forme d’un faux journal brut.

## Commandes pour les vérifications principales

À lancer depuis la racine du dépôt, dans un environnement isolé disposant des dépendances applicatives et des outils de développement. Les commandes suivantes sont des indications de reproduction. Le premier lancement complet peut encore provoquer le crash Qt documenté.

```sh
QT_QPA_PLATFORM=offscreen python -m pytest -q
QT_QPA_PLATFORM=offscreen python -m coverage run --source=src/extractor360 -m pytest -q --ignore=tests/test_studio_ui.py
python -m coverage report
ruff check src tests scripts
python -m mypy src/extractor360
python -m mypy --check-untyped-defs src/extractor360
python scripts/check_release.py
python -m pip check
python docs/audit-2026-09-07/probes.py
```

Le script de sondes remplace ses JSON et sa capture dans ce dossier. Les tests existants ne sont pas tous isolés de la configuration personnelle ; leur isolation est une correction demandée dans le plan. Les sondes d’audit imposent quant à elles une configuration temporaire.

## Navigation dans les preuves

- [inventory.json](inventory.json) : chemins, tailles et empreintes des 78 fichiers au début de l’audit.
- [INVENTAIRE.md](INVENTAIRE.md) : rôle, profondeur d’examen et limites pour chacun de ces fichiers, liens vers le commit exact.
- [source-index.txt](source-index.txt) : index de repérage des principales classes, fonctions et zones sensibles.
- [RAPPORT.md](RAPPORT.md) : 37 constats, références de code, conséquences, corrections et limites.
- [PLAN.md](PLAN.md) : huit lots, dépendances, charges, critères d’acceptation et portes de livraison.
