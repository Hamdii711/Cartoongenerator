# Intégration avec un agent IA

Ce projet n'a **pas d'interface humaine** (pas de CLI interactive, pas
d'interface web) : il est conçu pour être piloté par un agent (le tien) qui
lance des commandes et parse leur sortie JSON.

## Contrat d'appel

- Chaque commande est un process séparé (`python main.py <sous-commande> ...`).
- **Succès** : un seul objet JSON sur stdout, code de sortie `0`.
- **Échec** : un objet JSON `{"status": "error", "message": "..."}` sur
  stderr, code de sortie non-nul.
- Aucun prompt interactif, aucune confirmation - une commande soit
  s'exécute et retourne, soit échoue immédiatement.
- Toutes les commandes sont **idempotentes ou explicites sur ce qu'elles
  écrasent** : `character add` régénère toujours les 3 images d'un
  personnage s'il est réappelé avec le même nom (donc ne le rappelle pas
  sans besoin) ; `render` ne regénère pas un décor déjà présent sur disque.

## Exemple d'appel depuis un agent (pseudo-code)

```python
import json, subprocess

def run(cmd: list[str]) -> dict:
    result = subprocess.run(
        ["python", "main.py", *cmd],
        cwd="cartoon_generator",
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(json.loads(result.stderr)["message"])
    return json.loads(result.stdout)

# 1. Personnages (une fois par projet)
run(["character", "add", "--project", "ep1", "--name", "Randy",
     "--description", "homme adulte, cheveux bruns, pull orange",
     "--personality", "naïf, impulsif", "--role", "personnage principal"])

# 2. Pipeline complet
result = run(["generate", "--project", "ep1",
              "--theme", "Randy répare la voiture et ça tourne mal",
              "--scenes", "4"])
print(result["output"])  # chemin du final.mp4
```

## Ordre de dépendance entre commandes

```
character add (≥1 fois)
      │
      ▼
script generate  ──▶  story.json
      │
      ▼
render            ──▶  backgrounds/*.png + scenes/*.mp4
      │
      ▼
assemble          ──▶  final.mp4
```

`generate` fait `script generate` + `render` + `assemble` d'un coup, mais
suppose que les personnages existent déjà - un agent qui construit un
épisode de zéro doit d'abord appeler `character add` pour chaque personnage
du casting.

## Ce que l'agent doit décider lui-même

Ce projet ne prend aucune décision créative à la place de l'appelant :
- Le **thème**, le **nombre de scènes**, la **description/personnalité**
  de chaque personnage sont des paramètres d'entrée - c'est à l'agent (ou à
  l'utilisateur qu'il représente) de les fournir.
- Le choix du **provider** (`--provider`, `--llm-provider`,
  `--image-provider`) peut être omis pour utiliser les valeurs par défaut
  de `config.yaml`, ou précisé explicitement si l'agent veut comparer
  plusieurs backends.

## Lire le résultat

- `final.mp4` est un fichier vidéo standard (H.264) - à transmettre tel
  quel à l'utilisateur (pas de traitement supplémentaire nécessaire).
- En cas d'échec à une étape intermédiaire (ex: `render` échoue après que
  `script generate` a réussi), `story.json` reste sur disque : relancer
  `render` seul (pas besoin de refaire `script generate`) une fois le
  problème corrigé (ex: clé API ajoutée).
