# Audit de l'application 360Extractor

> **Version auditée :** 2.5.2 (commit `90f08f5`, branche `claude/application-audit-HCDJf`)
> **Date :** 2026-05-29
> **Périmètre :** audit applicatif complet (code `src/`, tests, dépendances, packaging, documentation, sécurité)
> **Nature :** rapport d'analyse — aucune modification du code applicatif n'a été effectuée.

---

## 1. Synthèse exécutive

360Extractor est une application Python de bureau (PySide6/Qt) qui extrait des
images perspectives (« rectilinéaires ») depuis des vidéos et images 360° en vue
de la photogrammétrie, avec suppression optionnelle d'objets/opérateurs par IA
(YOLO/ultralytics) et embarquement de métadonnées GPS issues de la télémétrie
(GPMF GoPro, CAMM Insta360, GPX, SRT). Le traitement exploite le GPU (CUDA/MPS)
quand disponible.

**État général : sain et fonctionnel, mais avec une dette technique notable.**
Le code est globalement lisible et bien découpé en couches (`core` / `ui` /
`utils`). La géométrie est testée. Les points de vigilance majeurs concernent la
**robustesse du cycle de vie des threads Qt**, la **gestion des ressources et des
erreurs** dans le pipeline de traitement, et l'**absence d'outillage qualité**
(CI, lint, packaging, couverture de test du cœur).

### Top risques

| # | Sévérité | Constat | Emplacement |
|---|----------|---------|-------------|
| 1 | 🔴 Critique | Fuite de handle vidéo en cas d'exception (`cap` jamais libéré) | `src/core/processor.py` |
| 2 | 🔴 Critique | Fermeture de la fenêtre pendant un traitement → thread Qt détruit en cours d'exécution (crash possible) | `src/ui/main_window.py:1239` |
| 3 | 🟠 Élevé | Dialogue « Success » affiché même quand des jobs ont échoué | `src/core/processor.py:48` + `src/ui/main_window.py:1158` |
| 4 | 🟠 Élevé | Aucune CI / lint / packaging ; cœur de traitement non testé | infrastructure |
| 5 | 🟠 Élevé | `torch`/`torchvision` non épinglés malgré une install CUDA fragile | `requirements.txt` |

**Note globale indicative : 6,5 / 10** — bon socle fonctionnel, robustesse et
industrialisation à renforcer.

---

## 2. Périmètre & méthode

### Arborescence
```
src/
  core/    processor, ai_model, ai_classes, analyzer, geometry,
           motion_detector, job, telemetry, settings_manager, version
  ui/      main_window (1240 l.), preview_widget, video_card, sidebar,
           log_panel, collapsible_section, toggle_switch, widgets, icons, styles.qss
  utils/   gpmf_parser, camm_parser, gpx_parser, srt_parser,
           image_utils, file_manager, logger
  main.py  (point d'entrée : modes GUI et CLI)
tests/     test_core.py, test_gpmf_parser.py
docs/      CLI.md, SETTINGS.md
```
~5070 lignes de Python dans `src/`.

### Stack
PySide6 (Qt6), OpenCV, NumPy, Ultralytics (YOLO26), PyTorch (CUDA/MPS), piexif,
defusedxml, tqdm.

### Méthode
Exploration multi-agents puis **recoupement manuel sur le code source réel** pour
chaque constat. Les constats non confirmés par la lecture du code ont été écartés
et sont listés en annexe (§12) par souci de transparence.

---

## 3. Bugs & robustesse

### 3.1 🔴 Fuite de handle vidéo en cas d'exception
**`src/core/processor.py:118, 129, 427-428`**

`cap = cv2.VideoCapture(...)` est ouvert (l.129) et libéré par `cap.release()`
seulement à la toute fin de `process_video` (l.427-428). La grande boucle de
traitement (l.238-425) n'est **pas** enveloppée dans un `try/finally`. Toute
exception levée dans la boucle (remap, IA, écriture I/O, télémétrie) remonte à
`run()` (l.56-62) sans jamais libérer `cap` → handle de fichier fuité, vidéo
verrouillée, impossibilité de la retraiter sans redémarrer.

**Recommandation :** envelopper le corps de `process_video` dans
`try: ... finally: if cap: cap.release()`.

### 3.2 🔴 Fermeture de fenêtre pendant un traitement
**`src/ui/main_window.py:1239-1241`**

```python
def closeEvent(self, event):
    self.settings_manager.save_settings()
    super().closeEvent(event)
```

`closeEvent` ne demande pas l'arrêt du worker (`self.worker.stop()`) ni n'attend
le thread (`self.thread.quit(); self.thread.wait()`). Si l'utilisateur ferme la
fenêtre pendant un traitement, le `QThread` est encore actif au moment de la
destruction → erreur Qt « QThread: Destroyed while thread is still running » et
thread orphelin qui continue à écrire des fichiers.

**Recommandation :** dans `closeEvent`, si `self.is_processing`, appeler
`worker.stop()`, `thread.quit()`, `thread.wait(timeout)` avant `super().closeEvent`.

### 3.3 🟠 « Success » affiché même après des erreurs
**`src/core/processor.py:48-64` + `src/ui/main_window.py:1112, 1158-1167`**

Dans `ProcessingWorker.run`, une exception sur un job émet `error_occurred` puis
la boucle **continue** et finit par émettre `finished` (l.64). Côté UI,
`finished` est relié à `processing_finished` (l.1112) qui affiche un
`QMessageBox.information(... "Batch processing completed successfully.")`
(l.1162). Conséquence : après une erreur, l'utilisateur voit d'abord le dialogue
critique, puis un dialogue « Succès ». De plus `processing_error` appelle
`worker.stop()` (l.1169), ce qui interrompt les jobs restants tout en laissant le
flux aboutir à « Succès ».

Par ailleurs, il n'existe pas de signal d'**erreur par job** : la `VideoCard`
fautive ne passe pas à un statut « Failed » (elle reste « Processing »).

**Recommandation :** suivre l'état d'échec dans le worker, ajouter un signal
`job_error(index, message)`, et conditionner le message final (succès / terminé
avec erreurs / annulé).

### 3.4 🟠 `shutdown(wait=False)` à l'arrêt → écritures tronquées
**`src/core/processor.py:46`**

`stop()` appelle `self.io_pool.shutdown(wait=False)`, ce qui annule les tâches
d'écriture d'images en attente. Combiné à l'attente par-frame (l.422-423), le
risque est limité mais une image peut rester partiellement écrite à l'annulation.

**Recommandation :** documenter le comportement d'annulation et préférer un arrêt
coopératif laissant se terminer la frame courante.

### 3.5 🟠 Boucle de traitement si `fps == 0`
**`src/core/processor.py:144, 253`**

Si OpenCV rapporte `fps == 0` (vidéo à conteneur défectueux), l'intervalle en
secondes devient `interval = max(1, 0) = 1`. Le calcul de timestamp est protégé
(`frame_idx / fps if fps > 0 else 0`, l.253), donc pas de division par zéro ; en
revanche la cadence d'extraction demandée n'est pas respectée (chaque frame est
traitée). À surveiller.

### 3.6 🟠 Validation GPS absente
**`src/core/telemetry.py:202-236` + parsers `utils/*_parser.py`**

`get_gps_at_time` interpole lat/lon/alt sans bornage (l.232-236) et suppose les
échantillons triés par timestamp (utilise `bisect`, l.213). Les parsers GPMF /
CAMM / GPX ne valident pas les plages (`-90 ≤ lat ≤ 90`, `-180 ≤ lon ≤ 180`) ni
l'absence de NaN/Inf. Des coordonnées aberrantes peuvent être embarquées dans
l'EXIF (`embed_exif`, l.238).

**Recommandation :** valider/borner les coordonnées à l'extraction et garantir le
tri temporel des échantillons.

### 3.7 🟡 Parsing CAMM par interpolation linéaire
**`src/utils/camm_parser.py`** — les timestamps sont reconstruits par répartition
uniforme (ou repli 5 Hz si durée inconnue). Hypothèse fragile si la cadence
d'échantillonnage réelle est irrégulière → léger désalignement GPS/image.

### 3.8 🟡 `except Exception:` silencieux
**`src/core/telemetry.py:246`** — le repli en cas d'échec de `piexif.load` ne
journalise rien ; un problème de permission/disque devient invisible.
**`src/main.py:65`** — repli large `except Exception` (acceptable car
log + `sys.exit`, mais masque le type d'erreur).

---

## 4. Sécurité

> Contexte : application **locale mono-utilisateur**, ce qui réduit la surface
> d'attaque réelle. Les points ci-dessous restent de bonnes pratiques.

### 4.1 ✅ Bonnes pratiques constatées
- **XML sécurisé** : `gpx_parser.py` utilise `defusedxml` (protection XXE /
  Billion Laughs).
- **Pas d'injection shell** : `ffprobe` est invoqué via une **liste**
  d'arguments (pas de `shell=True`) dans `telemetry.py`.
- **Pas de désérialisation dangereuse** : la configuration utilise `json`
  (aucun `pickle`, `eval`, `exec`).

### 4.2 🟡 Path traversal sur le nommage personnalisé
**`src/core/processor.py:66-74, 392-404`**

En mode de nommage `custom`, `generate_filename` substitue les variables du motif
sans neutraliser les séquences `../`, puis `os.path.join(output_dir, save_name)`
(l.403-404) n'est pas vérifié comme restant à l'intérieur de `output_dir`. Un
motif tel que `../../{filename}` écrirait hors du dossier prévu.

**Recommandation :** nettoyer les composants de chemin (`os.path.basename`),
puis vérifier `os.path.realpath(full_save_path).startswith(os.path.realpath(output_dir))`.

### 4.3 🟡 Pas de limite de taille sur la config JSON
**`src/main.py:59-61`** — `json.load` sans contrôle de taille (impact négligeable
en usage local).

---

## 5. Performance

### 5.1 🟡 Copie complète de frame en mode adaptatif
**`src/core/processor.py:285`** — `last_extracted_frame = frame.copy()` copie
l'image couleur pleine résolution à chaque frame retenue, uniquement pour le
calcul de mouvement. Une version réduite/niveau de gris suffirait et diviserait
fortement l'empreinte mémoire.

### 5.2 🟡 Aucune annulation/limitation des workers de preview
**`src/ui/preview_widget.py:240-257`** — chaque changement de réglage lance un
`PreviewWorker` ; les workers précédents ne sont pas annulés. En déplaçant
rapidement un curseur, plusieurs décodages vidéo concurrents sont lancés (CPU
gaspillé). Les signaux Qt étant sérialisés sur le thread UI, il n'y a pas de
corruption d'état, mais le « dernier arrivé » gagne sans débounce.

**Recommandation :** ajouter un debounce (QTimer) et/ou annuler le worker en cours.

### 5.3 🟢 `import` à l'intérieur de `process_video`
**`src/core/processor.py:169`** — `from core.ai_classes import ...` est exécuté à
chaque appel de traitement vidéo. À remonter en tête de module.

---

## 6. Architecture & qualité de code

### 6.1 🟠 `main_window.py` — objet « dieu » (1240 lignes)
**`src/ui/main_window.py`** concentre : construction du layout et splitters,
gestion de la file de jobs, cycle de vie des threads de traitement et d'analyse,
synchronisation UI↔settings (~15 callbacks), raccourcis clavier. Cela viole le
principe de responsabilité unique, complique les tests et augmente le risque de
régression.

**Recommandation (non bloquante) :** extraire `JobQueueManager`,
`SettingsController` et `ProcessingOrchestrator` ; `MainWindow` devient un
orchestrateur léger.

### 6.2 🟠 Duplication et code mort dans `ai_model.py`
**`src/core/ai_model.py:75-153` (`process_image`) vs `155-226` (`process_batch`)** —
la logique de construction/inversion/feathering du masque est quasi identique. Le
pipeline (`processor.py:355`) n'appelle que `process_batch` : **`process_image`
semble être du code mort**.

**Recommandation :** extraire une méthode privée `_build_mask(...)` et supprimer
`process_image` s'il est inutilisé.

### 6.3 🟡 Logique CLI confuse autour de `--ai`
**`src/main.py:79-90`** — `get_arg` contient une branche spéciale `if arg_name ==
'ai' and val is False` alors qu'aucun argument `--ai` n'est défini dans le parser
(l.40-49). Code mort / source de confusion.

### 6.4 🟡 Incohérences de valeurs par défaut
- `layout_mode` : défaut `'ring'` (`settings_manager.py:13`) vs `'adaptive'`
  (`processor.py:151`).
- **Preview ≠ Export** : `preview_widget.py:86` appelle
  `generate_views(cam_count, pitch_offset)` **sans** `layout_mode`, alors que
  l'export le passe (`processor.py:214`). La prévisualisation peut donc ne pas
  refléter le layout réellement exporté.

### 6.5 🟡 Journalisation hétérogène
- `print()` au lieu du `logger` : `settings_manager.py:72,84`, `video_card.py:78`.
- Mélange `traceback.print_exc()` + `logger`/signal : `processor.py:60-62`
  (préférer `logger.error(..., exc_info=True)`).

### 6.6 🟢 Qualité générale
- Annotations de type partielles (présentes dans `telemetry.py`/`ai_model.py`,
  rares dans `processor.py`/`main_window.py`).
- Constantes « magiques » sous forme de chaînes (`'Skip Frame'`, `'ring'`,
  `'realityscan'`, identifiants de page UI) → candidates à des `Enum`.
- Fonction très longue : `process_video` (`processor.py:76-431`, ~356 lignes).

---

## 7. Tests & couverture

**Framework :** `unittest`. **Lancement :** `python -m unittest discover -s tests`
(ou `pytest tests/`).

**Couvert :**
- `tests/test_core.py` — `GeometryProcessor` (génération de vues ring/cube/
  fibonacci, matrice de rotation, formes des maps), `ImageUtils.calculate_blur_score`,
  `gpx_parser`, modèle `Job`, singleton `SettingsManager`.
- `tests/test_gpmf_parser.py` — parsing GPMF.

**Non couvert (parties critiques) :**
- `core/processor.py` (430 l. — cœur du pipeline) : **aucun test**.
- `core/ai_model.py`, `core/telemetry.py`, `core/motion_detector.py`,
  `core/analyzer.py`.
- `utils/camm_parser.py`, `utils/srt_parser.py`.
- Toute la couche **UI**.

**Fragilité d'isolation :** `TestSettingsManager` (`test_core.py:231-266`) opère
sur le **singleton** réel et celui-ci lit le vrai fichier
`~/.application360/config.json`. Les tests peuvent donc dépendre de
l'environnement et se polluer mutuellement (l'état du singleton persiste entre
tests).

**Exécution observée (env. vierge) :** sans dépendances installées,
`test_core.py` échoue dès l'import (`ModuleNotFoundError: numpy`) ; seul
`test_gpmf_parser.py` s'exécute (2/2 OK). En l'absence de CI, cette dépendance
d'environnement n'est pas détectée automatiquement.

**Recommandation :** ajouter des tests sur le pipeline (avec une petite vidéo de
fixture), les parsers CAMM/SRT, et isoler `SettingsManager` via un chemin de
config temporaire (`tmp_path` / réinitialisation du singleton).

---

## 8. Dépendances & packaging

**`requirements.txt`**
```
PySide6>=6.5.0
opencv-python>=4.8.0
numpy>=1.24.0
ultralytics>=8.4.14
tqdm>=4.66.0
piexif>=1.1.3
defusedxml>=0.7.1
```

- 🟠 **`torch`/`torchvision` absents** du fichier alors qu'ils sont indispensables
  (IA) et que le README décrit une installation CUDA délicate (risque de
  downgrade CPU silencieux). L'install n'est donc pas reproductible depuis
  `requirements.txt` seul.
- 🟡 **Bornes uniquement minimales** (`>=`), pas de fichier de lock → builds non
  déterministes (notamment NumPy 2.x / OpenCV / ultralytics).
- 🟡 **Pas de `pyproject.toml`/`setup.py`** : pas d'installation en paquet, pas
  d'entry point console (`360extractor = ...`).
- 🟡 **Aucune CI** (`.github/workflows` absent), aucun lint/type-check configuré
  (flake8/ruff/mypy), aucun `pre-commit`.

**Recommandations :** ajouter `pyproject.toml` (métadonnées + dépendances +
entry point), une CI GitHub Actions (tests + ruff + mypy), et documenter/épingler
l'installation de PyTorch (extra index CUDA) ou la déplacer dans un
`requirements-gpu.txt` dédié.

---

## 9. Documentation & cohérence

- ✅ Versions cohérentes : `core/version.py` (2.5.2), `README.md`, `CHANGELOG.md`
  concordent.
- ✅ Documentation présente et utile : `README.md`, `ARCHITECTURE.md`,
  `CHANGELOG.md`, `docs/CLI.md`, `docs/SETTINGS.md`.
- ✅ `.gitignore` exclut bien les modèles `.pt` (auto-téléchargés) et les fichiers
  de dev internes.
- 🟡 Le modèle est codé en dur (`yolo26n-seg.pt`, `processor.py:39`) ; à exposer
  en configuration et à documenter (taille/variante du modèle).

---

## 10. Tableau récapitulatif par sévérité

| Sévérité | Constat | Référence |
|----------|---------|-----------|
| 🔴 Critique | Fuite de handle vidéo (pas de `try/finally`) | §3.1 `processor.py:427` |
| 🔴 Critique | `closeEvent` n'arrête pas le worker → crash QThread | §3.2 `main_window.py:1239` |
| 🟠 Élevé | « Success » après erreurs ; pas de statut d'échec par job | §3.3 |
| 🟠 Élevé | `torch`/`torchvision` non gérés ; pas de packaging/CI/lint | §8 |
| 🟠 Élevé | Cœur de traitement non testé | §7 |
| 🟠 Moyen | `shutdown(wait=False)` → écriture tronquée | §3.4 |
| 🟠 Moyen | Validation GPS absente (bornes, tri) | §3.6 |
| 🟠 Moyen | God object `main_window.py` | §6.1 |
| 🟠 Moyen | Duplication + code mort `ai_model.process_image` | §6.2 |
| 🟡 Faible | Path traversal nommage custom | §4.2 |
| 🟡 Faible | Preview ignore `layout_mode` ; défaut `ring`/`adaptive` | §6.4 |
| 🟡 Faible | Pas de debounce des previews ; copie frame coûteuse | §5.1, §5.2 |
| 🟡 Faible | `except` silencieux, `print` vs logger, `import` en boucle | §3.8, §6.5, §5.3 |
| 🟢 Info | Type hints partiels, chaînes magiques, fonction longue | §6.6 |

---

## 11. Recommandations priorisées (roadmap)

**Lot 1 — Robustesse (rapide, fort impact)**
1. `try/finally` autour de `process_video` pour libérer `cap` (§3.1).
2. Arrêt propre des workers dans `closeEvent` (§3.2).
3. Message final conditionnel + signal `job_error` + statut « Failed » sur la carte (§3.3).

**Lot 2 — Qualité des résultats**
4. Validation/bornage GPS et tri temporel (§3.6).
5. Cohérence preview/export (`layout_mode`) et défauts unifiés (§6.4).
6. Confinement des chemins de sortie en mode custom (§4.2).

**Lot 3 — Industrialisation**
7. `pyproject.toml` + entry point + gestion de PyTorch (§8).
8. CI GitHub Actions : tests + ruff + mypy (§8).
9. Tests du pipeline, des parsers CAMM/SRT, isolation `SettingsManager` (§7).

**Lot 4 — Dette structurelle (fond)**
10. Découpe de `main_window.py` (§6.1) ; factorisation `_build_mask` et suppression de `process_image` mort (§6.2) ; logging homogène (§6.5).

---

## 12. Annexe — faux positifs écartés (transparence méthodologique)

Constats remontés lors de l'exploration mais **invalidés** après lecture du code :

- **Division par zéro dans le calcul d'ETA** : déjà protégée par
  `processor.py:261` (`if frame_idx > 0 and elapsed > 0`).
- **Crash `frame.shape` si frame `None` dans la preview** : protégé par le garde
  `if not ret: return` en `preview_widget.py:49-51` (et `cap.release()` appelé
  avant).
- **`AttributeError` sur `res.masks`** : géré par `ai_model.py:189`
  (`if has_detection and res.masks:`), avec repli masque plein.
- **« Signal mismatch » du `ThumbnailWorker` provoquant un crash** : connecter un
  `Signal(QPixmap)` à un slot sans argument (`quit()`) est valide en Qt — l'argument
  surnuméraire est simplement ignoré.

---

*Fin du rapport.*
