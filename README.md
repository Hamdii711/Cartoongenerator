# Cartoon Generator

Générateur de dessins animés 2D "cutout" (façon South Park), scène par
scène, en faisant collaborer plusieurs IA :

- un **LLM** (OpenAI ou Gemini) écrit le scénario et le découpe en scènes ;
- un **provider image** (OpenAI ou Gemini) génère les personnages (une fois,
  réutilisés comme cutouts sur toutes les scènes) et les décors ;
- du **code Python** (Pillow + MoviePy) compose chaque scène : personnage
  posé sur le décor, bouche qui alterne pendant qu'il "parle", petit
  mouvement de caméra, dialogue affiché en sous-titre (pas de voix) ;
- toutes les scènes sont assemblées en une **vidéo finale** (`final.mp4`).

Projet **indépendant** de hermes-agent : aucun tool/plugin/skill, aucune
dépendance au reste du dépôt.

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

## Utilisation (CLI, sortie JSON)

Toutes les commandes impriment un JSON sur stdout en cas de succès, ou un
JSON d'erreur sur stderr + code de sortie non nul en cas d'échec — pensé
pour être appelé par un agent IA plutôt que par un humain.

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

Le résultat final est dans `projects/ep1/final.mp4`.

## Ajouter un provider

Le système est extensible par design : implémenter `LLMProvider` et/ou
`ImageProvider` (voir `providers/base.py`) dans un nouveau fichier sous
`providers/`, puis l'ajouter dans les registres `LLM_PROVIDERS` /
`IMAGE_PROVIDERS` de `providers/__init__.py`. Rien d'autre à changer.

## Configuration

- `.env` : clés API uniquement (secrets).
- `config.yaml` (optionnel, à la racine de `cartoon_generator/`) : provider
  par défaut, résolution, fps, timing des lignes de dialogue, etc. Voir
  `config.py::DEFAULT_CONFIG` pour la liste des clés.

## Limites actuelles

- Pas de voix/TTS : les dialogues sont affichés en sous-titres, la durée de
  chaque scène est estimée à partir de la longueur du texte.
- La transparence des personnages générés par un provider qui ne supporte
  pas nativement l'alpha (ex: Gemini/Imagen) est obtenue en détourant un
  fond blanc uni (`pipeline/character_studio.py::_key_white_to_alpha`) —
  fonctionne bien tant que le personnage n'a pas de grandes zones blanches.
