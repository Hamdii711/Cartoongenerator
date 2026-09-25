# Cartoon Generator

Générateur de dessins animés 2D "cutout" (façon South Park), scène par
scène, en faisant collaborer plusieurs IA :

- un **LLM** (OpenAI ou Gemini) écrit le scénario et le découpe en scènes ;
- un **provider image** (OpenAI ou Gemini) génère les personnages (une fois
  par projet, réutilisés comme cutouts sur toutes les scènes) et les
  décors ;
- du **code Python** (Pillow + MoviePy) compose chaque scène : personnage
  posé sur le décor, bouche qui alterne pendant qu'il "parle", petit
  mouvement de caméra, dialogue affiché en sous-titre (pas de voix) ;
- toutes les scènes sont assemblées en une **vidéo finale** (`final.mp4`).

Projet **indépendant** : aucun tool/plugin/skill, aucune dépendance à un
autre dépôt.

## Documentation

| Doc | Contenu |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Comment le pipeline est découpé et pourquoi, détail du rendu d'une scène, roadmap |
| [docs/CLI.md](docs/CLI.md) | Référence complète de chaque commande, flags, sortie JSON |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | `.env`, `config.yaml`, schémas `story.json` et `profile.json` |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Comment ajouter un nouveau backend LLM/image |
| [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) | Comment un agent IA pilote cet outil (contrat d'appel, exemple) |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Erreurs courantes et leur solution |

## Installation

```bash
cd cartoon_generator
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigne OPENAI_API_KEY et/ou GEMINI_API_KEY
```

## Organisation par projet

Tout ce qui concerne une histoire vit dans son propre dossier, rien n'est
partagé entre deux projets :

```
projects/<nom_projet>/
├── story.json              # titre, synopsis, scènes, dialogues
├── characters/<nom>/
│   ├── profile.json        # description physique, personnalité, rôle
│   ├── neutral.png
│   ├── talk.png
│   └── blink.png
├── backgrounds/scene_N.png
├── scenes/scene_N.mp4
└── final.mp4
```

Détail des schémas JSON : [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Utilisation rapide

Toutes les commandes impriment un JSON sur stdout en cas de succès, ou un
JSON d'erreur sur stderr + code de sortie non nul en cas d'échec — pensé
pour être appelé par un agent IA plutôt que par un humain (détails :
[docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md)).

```bash
# 1. Créer les personnages du projet (une fois, réutilisés sur toutes les scènes)
python main.py character add --project ep1 --name Randy \
  --description "homme adulte, cheveux bruns, pull orange" \
  --personality "naïf, impulsif, toujours au mauvais endroit" \
  --role "père de famille, personnage principal" \
  --provider openai

python main.py character add --project ep1 --name Stan \
  --description "jeune garçon, bonnet bleu et rouge" \
  --personality "raisonnable, un peu blasé" \
  --role "fils de Randy" \
  --provider openai

# 2. Générer le script (découpage en scènes + dialogues)
python main.py script generate --project ep1 \
  --theme "Randy essaie de réparer la voiture familiale et ça tourne mal" \
  --scenes 4 --provider gemini

# 3. Rendre chaque scène (génère les décors manquants + anime les persos)
python main.py render --project ep1 --image-provider openai

# 4. Assembler la vidéo finale
python main.py assemble --project ep1

# Ou tout en une commande (les personnages doivent déjà exister) :
python main.py generate --project ep1 \
  --theme "Randy essaie de réparer la voiture familiale et ça tourne mal" \
  --scenes 4 --llm-provider gemini --image-provider openai
```

Le résultat final est dans `projects/ep1/final.mp4`. Référence complète des
commandes : [docs/CLI.md](docs/CLI.md).

## Ajouter un provider

Le système est extensible par design : implémenter `LLMProvider` et/ou
`ImageProvider` (voir `providers/base.py`) dans un nouveau fichier sous
`providers/`, puis l'ajouter dans les registres `LLM_PROVIDERS` /
`IMAGE_PROVIDERS` de `providers/__init__.py`. Rien d'autre à changer. Guide
détaillé : [docs/PROVIDERS.md](docs/PROVIDERS.md).

## Tests

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

`tests/test_pipeline_smoke.py` fait tourner le pipeline complet
(personnage → script → rendu → assemblage) avec des providers factices,
sans aucun appel réseau.

## Limites actuelles

- Pas de voix/TTS : les dialogues sont affichés en sous-titres, la durée de
  chaque scène est estimée à partir de la longueur du texte. Piste
  d'extension documentée dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#roadmap-pistes-dextension-non-implémentées).
- La transparence des personnages générés par un provider qui ne supporte
  pas nativement l'alpha (ex: Gemini/Imagen) est obtenue en détourant un
  fond blanc uni — voir [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
  pour les cas limites.

## Licence

Pas de licence définie pour l'instant (dépôt privé de développement).
