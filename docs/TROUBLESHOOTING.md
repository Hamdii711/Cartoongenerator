# Dépannage

## `Missing OPENAI_API_KEY` / `Missing GEMINI_API_KEY`

La clé n'est pas dans `.env` (ou pas dans l'environnement shell). Vérifie :

```bash
cat cartoon_generator/.env   # doit contenir la ligne OPENAI_API_KEY=sk-...
```

Le fichier `.env` doit être à la racine de `cartoon_generator/`, pas ailleurs.

## `Project '...' has no characters yet`

`script generate` (ou `generate`) a été appelé avant tout `character add`
sur ce projet. Crée au moins un personnage d'abord :

```bash
python main.py character add --project ep1 --name Randy --description "..."
```

## `Expected N scenes, got M`

Le LLM n'a pas respecté le nombre de scènes demandé. C'est une erreur de
validation volontaire (`pipeline/script_writer.py`) plutôt que de laisser
passer un script incohérent. Relance `script generate` - c'est en général
un aléa du modèle, pas un bug systématique. Si ça se reproduit souvent avec
un provider donné, essaie l'autre (`--provider`).

## `Scene N has a line from unknown speaker '...'`

Le LLM a fait parler un personnage qui n'existe pas dans le projet. Même
cause/remède que ci-dessus - relancer `script generate` suffit en général.

## `No rendered scenes found for project '...' - run render first`

`assemble` a été appelé avant `render`, ou `render` a échoué avant de
produire le moindre clip. Vérifie `projects/<nom>/scenes/` - s'il est vide,
relance `render`.

## Le personnage généré a un halo blanc / bord visible

C'est une limite connue du détourage automatique
(`pipeline/character_studio.py::_key_white_to_alpha`) : il transforme les
pixels proches du blanc en transparence, ce qui peut laisser un léger liseré
sur un contour anti-aliasé. Deux options :
- Ajuster `threshold`/`soft_range` dans `_key_white_to_alpha` si le problème
  est systématique.
- Retoucher l'image générée à la main (elle reste un simple PNG dans
  `characters/<nom>/`) avant de lancer `render`.

## Une partie blanche du personnage devient transparente

Le détourage ne retire que le blanc relié au bord de l'image, donc un
t-shirt blanc ou le blanc des yeux sont normalement conservés. Si une zone
blanche disparaît quand même, c'est que son contour noir a une petite
ouverture qui la relie au fond. Corrige l'image (referme le contour) ou
régénère-la en demandant des « contours noirs épais et continus ».

## Erreur MoviePy / ffmpeg au moment de l'export

Le projet dépend de `imageio-ffmpeg`, qui embarque son propre binaire
ffmpeg - pas besoin d'installer ffmpeg séparément sur le système. Si
l'erreur persiste :

```bash
pip install --force-reinstall imageio-ffmpeg
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```

et vérifie que le chemin affiché existe et est exécutable.

## Rendu très lent

La résolution (`resolution` dans `config.yaml`) et la durée totale (nombre
de scènes × longueur des dialogues) sont les deux leviers principaux. Pour
itérer rapidement pendant le développement d'un épisode, baisse
temporairement `resolution` (ex: `[640, 360]`) et remonte-la pour le rendu
final.

## Voir la trace complète d'une erreur

Ajoute `--debug` à la commande - voir `CLI.md`.

## Lancer les tests

```bash
cd cartoon_generator
source venv/bin/activate
python -m pytest tests/ -q
```

Le test `tests/test_pipeline_smoke.py` ne fait aucun appel réseau (il utilise
des providers factices) - s'il échoue, le problème vient du pipeline
Pillow/MoviePy lui-même, pas d'une API externe.
