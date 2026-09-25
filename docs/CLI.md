# Référence CLI

Toutes les commandes sont sous `python main.py <commande> [...]`, exécutées
depuis le dossier `cartoon_generator/` (avec le venv activé).

**Contrat d'entrée/sortie** (pensé pour être appelé par un agent, pas un
humain) :
- Succès → un unique objet JSON sur **stdout**, code de sortie `0`.
- Échec → un objet JSON `{"status": "error", "message": "..."}` sur
  **stderr**, code de sortie `1`.
- Aucune commande n'est interactive (pas de prompt, pas de confirmation).

---

## `character add`

Génère les 3 assets d'un personnage (`neutral.png`, `talk.png`,
`blink.png`) et sauvegarde sa fiche (`profile.json`).

```bash
python main.py character add \
  --project ep1 \
  --name Randy \
  --description "homme adulte, cheveux bruns, pull orange" \
  --personality "naïf, impulsif, toujours au mauvais endroit" \
  --role "père de famille, personnage principal" \
  --provider openai
```

| Flag | Requis | Description |
|---|---|---|
| `--project` | oui | Nom du projet (dossier sous `projects/`) |
| `--name` | oui | Nom du personnage (nom du dossier sous `characters/`) |
| `--description` | oui | Description physique, utilisée dans le prompt image |
| `--personality` | non | Traits de caractère (influence aussi le script généré ensuite) |
| `--role` | non | Rôle dans l'histoire |
| `--provider` | non | Provider image (`openai`, `gemini`, ...) - défaut : `default_image_provider` de `config.yaml` |

Sortie :
```json
{"status": "ok", "name": "Randy", "dir": "projects/ep1/characters/Randy", "paths": {"neutral": "...", "talk": "...", "blink": "..."}, "profile": {...}}
```

---

## `character import`

Crée un personnage à partir d'images **que tu as déjà** (faites à la main
dans ChatGPT, Gemini, etc.) : aucun appel API, aucune clé nécessaire.
Prompts conseillés pour générer ces images : [IMAGES_MANUELLES.md](IMAGES_MANUELLES.md).

```bash
python main.py character import \
  --project ep1 \
  --name Yanis \
  --neutral images/yanis_neutre.png \
  --talk images/yanis_bouche_ouverte.png \
  --blink images/yanis_yeux_fermes.png \
  --description "jeune homme, t-shirt blanc, short noir" \
  --personality "sûr de lui, persuadé d'être un grand chef" \
  --role "personnage principal"
```

| Flag | Requis | Description |
|---|---|---|
| `--project` | oui | Nom du projet |
| `--name` | oui | Nom du personnage |
| `--neutral` | oui | Image : pose neutre, bouche fermée |
| `--talk` | non | Image : bouche ouverte (défaut : reprend `--neutral`, donc pas d'animation de bouche) |
| `--blink` | non | Image : yeux fermés (défaut : reprend `--neutral`, donc pas de clignement) |
| `--description`, `--personality`, `--role` | non | Fiche du personnage, utilisée par le LLM pour écrire les dialogues |

Les images sur fond blanc uni sont détourées automatiquement. Seul le blanc
**relié au bord de l'image** est retiré : un t-shirt blanc ou le blanc des
yeux, entourés d'un contour noir, sont conservés.

---

## `script generate`

Génère `story.json` : le titre, le synopsis et le découpage en scènes avec
dialogues, à partir d'un thème et de la fiche de chaque personnage du
projet.

```bash
python main.py script generate \
  --project ep1 \
  --theme "Randy essaie de réparer la voiture familiale et ça tourne mal" \
  --scenes 4 \
  --characters Randy,Stan \
  --provider gemini
```

| Flag | Requis | Description |
|---|---|---|
| `--project` | oui | Nom du projet |
| `--theme` | oui | Thème/pitch de l'épisode |
| `--scenes` | oui | Nombre de scènes à générer |
| `--characters` | non | Liste de noms séparés par des virgules - défaut : tous les personnages déjà créés dans le projet |
| `--provider` | non | Provider LLM - défaut : `default_llm_provider` de `config.yaml` |

Sortie : le `story.json` généré (voir `CONFIGURATION.md` pour le schéma).

Erreurs possibles : projet sans aucun personnage créé, réponse du LLM avec
un nombre de scènes différent de celui demandé, ou une réplique attribuée à
un personnage inconnu - dans tous les cas, message d'erreur explicite, rien
n'est écrit sur disque.

---

## `render`

Génère les décors manquants (idempotent - un décor déjà présent n'est pas
regénéré) puis rend chaque scène de `story.json` en clip vidéo. Si tous les
décors existent déjà (par exemple faits à la main et déposés dans
`backgrounds/scene_<id>.png`), aucun provider image n'est appelé et aucune
clé API n'est nécessaire.

```bash
python main.py render --project ep1 --image-provider openai
```

| Flag | Requis | Description |
|---|---|---|
| `--project` | oui | Nom du projet (doit déjà avoir un `story.json`) |
| `--image-provider` | non | Provider image pour les décors - défaut : `default_image_provider` |

Sortie :
```json
{"status": "ok", "project": "ep1", "scenes": ["projects/ep1/scenes/scene_1.mp4", "projects/ep1/scenes/scene_2.mp4", ...]}
```

Astuce : tu peux remplacer un `projects/ep1/backgrounds/scene_2.png` généré
par un autre fichier PNG avant de relancer `render` - il ne sera pas
regénéré tant qu'il existe.

---

## `assemble`

Concatène les clips de `scenes/` (dans l'ordre de leur `id`) avec un fondu
entre chaque scène, en `final.mp4`.

```bash
python main.py assemble --project ep1
```

| Flag | Requis | Description |
|---|---|---|
| `--project` | oui | Nom du projet (doit déjà avoir des scènes rendues) |

Sortie :
```json
{"status": "ok", "project": "ep1", "output": "projects/ep1/final.mp4"}
```

---

## `generate` (pipeline complet)

Enchaîne `script generate` → `render` → `assemble` en une seule commande.
**Les personnages doivent déjà exister** dans le projet (créés au préalable
via `character add`) - cette commande ne les génère pas automatiquement.

```bash
python main.py generate \
  --project ep1 \
  --theme "Randy essaie de réparer la voiture familiale et ça tourne mal" \
  --scenes 4 \
  --characters Randy,Stan \
  --llm-provider gemini \
  --image-provider openai
```

| Flag | Requis | Description |
|---|---|---|
| `--project` | oui | Nom du projet |
| `--theme` | oui | Thème/pitch de l'épisode |
| `--scenes` | oui | Nombre de scènes |
| `--characters` | non | Défaut : tous les personnages du projet |
| `--llm-provider` | non | Défaut : `default_llm_provider` |
| `--image-provider` | non | Défaut : `default_image_provider` |

Sortie :
```json
{"status": "ok", "project": "ep1", "title": "...", "scenes": ["...mp4", ...], "output": "projects/ep1/final.mp4"}
```

---

## Débogage

Ajoute `--debug` n'importe où dans la ligne de commande pour obtenir la
trace Python complète sur stderr en plus du message d'erreur JSON :

```bash
python main.py render --project ep1 --debug
```
