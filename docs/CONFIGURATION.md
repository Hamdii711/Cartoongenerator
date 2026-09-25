# Configuration

Deux fichiers, deux rôles bien séparés :

| Fichier | Contenu | Exemple |
|---|---|---|
| `.env` | **Secrets uniquement** (clés API) | `OPENAI_API_KEY=sk-...` |
| `config.yaml` | Tout le reste (comportement, timing, résolution) | `default_llm_provider: gemini` |

`config.yaml` est optionnel : sans lui, les valeurs de
`config.py::DEFAULT_CONFIG` s'appliquent.

## `.env`

Copie `.env.example` vers `.env` et renseigne les clés dont tu as besoin :

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```

Une clé manquante ne fait échouer que les commandes qui en ont besoin -
inutile de renseigner les deux si tu n'utilises qu'un seul provider.

## `config.yaml`

Crée ce fichier à la racine de `cartoon_generator/` (à côté de `main.py`)
pour changer les valeurs par défaut :

```yaml
default_llm_provider: gemini      # provider utilisé si --provider n'est pas précisé
default_image_provider: openai

fps: 24
resolution: [1280, 720]           # [largeur, hauteur] en pixels

min_line_seconds: 2.0             # durée minimale d'affichage d'une réplique
chars_per_second: 15.0            # vitesse de lecture estimée, pour calculer la durée d'une réplique
scene_intro_pad: 0.4              # marge (s) avant la première réplique d'une scène
scene_outro_pad: 0.4              # marge (s) après la dernière réplique d'une scène

mouth_flap_interval: 0.2          # intervalle (s) d'alternance bouche ouverte/fermée pendant qu'un perso parle
blink_interval: 4.0               # un personnage inactif cligne environ toutes les N secondes
blink_duration: 0.15              # durée (s) d'un clignement

scene_transition_fade: 0.3        # durée (s) du fondu entrant/sortant entre scènes lors de l'assemblage final
```

Tu n'as besoin de spécifier que les clés que tu veux changer - le reste
garde sa valeur par défaut (fusion avec `DEFAULT_CONFIG`).

## Schéma `story.json`

Généré par `script generate`, lu par `render`. Éditable à la main entre les
deux étapes si tu veux ajuster un dialogue ou une description de décor sans
tout regénérer.

```json
{
  "title": "Titre de l'épisode",
  "synopsis": "Résumé en 2-3 phrases.",
  "characters": ["Randy", "Stan"],
  "scenes": [
    {
      "id": 1,
      "background_desc": "cuisine années 90, style cutout plat",
      "camera": "static",
      "lines": [
        {"speaker": "Randy", "text": "Bon, je vais réparer cette voiture moi-même."},
        {"speaker": "Stan", "text": "Papa, tu dis toujours ça..."}
      ]
    }
  ]
}
```

Champs :
- `id` : entier séquentiel à partir de 1 - sert de nom de fichier pour le
  décor (`backgrounds/scene_<id>.png`) et le clip rendu
  (`scenes/scene_<id>.mp4`).
- `camera` : une valeur parmi `static`, `zoom_in`, `zoom_out`, `pan_left`,
  `pan_right`.
- `lines[].speaker` : doit correspondre exactement à un nom de personnage
  du projet (`characters/<nom>/`) - `script_writer.py` rejette une scène
  qui référence un speaker inconnu.

## Schéma `characters/<nom>/profile.json`

Généré par `character add`. Sert à la fois de mémo humain et de contexte
injecté au LLM lors de `script generate`, pour que les dialogues générés
restent cohérents avec chaque personnage.

```json
{
  "name": "Randy",
  "physical_description": "homme adulte, cheveux bruns, pull orange",
  "personality": "naïf, impulsif, toujours au mauvais endroit au mauvais moment",
  "role": "père de famille, personnage principal"
}
```

## Résolution des chemins

Tous les chemins de projet sont résolus via
`config.get_project_dir(project_name)`, qui pointe toujours vers
`cartoon_generator/projects/<project_name>/`, quel que soit le répertoire
courant depuis lequel `main.py` est lancé.
