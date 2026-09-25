# Ajouter un provider

Le projet ne code en dur aucun backend IA : `pipeline/` et `main.py` ne
parlent qu'aux interfaces abstraites `LLMProvider` et `ImageProvider`
définies dans `providers/base.py`. Ajouter un nouveau provider ne demande
donc **aucune modification** en dehors du dossier `providers/`.

## 1. Interfaces à implémenter

```python
class LLMProvider(ABC):
    def generate_script(self, theme: str, num_scenes: int, characters: list[dict]) -> dict:
        """Doit renvoyer un dict conforme au schéma story.json (voir docs/CONFIGURATION.md)."""

class ImageProvider(ABC):
    def generate_image(self, prompt: str, transparent_bg: bool = False, size: str = "1024x1024") -> bytes:
        """Doit renvoyer des octets PNG."""
```

Une classe peut implémenter les deux (voir `OpenAIProvider`,
`GeminiProvider`) ou une seule (rien n'empêche un provider "LLM only" ou
"image only").

## 2. Exemple minimal : un nouveau provider LLM

`providers/monprovider_provider.py` :

```python
import json
from typing import Any, Dict, List

from .base import LLMProvider
from .prompts import SCRIPT_SYSTEM_PROMPT, build_user_prompt
from config import get_api_key


class MonProviderProvider(LLMProvider):
    name = "monprovider"

    def __init__(self, model: str = "mon-modele"):
        self.api_key = get_api_key("MONPROVIDER_API_KEY")
        self.model = model

    def generate_script(self, theme: str, num_scenes: int, characters: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = SCRIPT_SYSTEM_PROMPT + "\n\n" + build_user_prompt(theme, num_scenes, characters)
        # ... appeler l'API du provider avec `prompt`, récupérer une réponse texte JSON ...
        raw_json_text = call_mon_api(prompt)
        return json.loads(raw_json_text)
```

Utilise `providers/prompts.py` (`SCRIPT_SYSTEM_PROMPT`, `build_user_prompt`,
`build_character_prompt`, `build_background_prompt`) pour rester cohérent
avec les autres providers plutôt que de réécrire tes propres prompts - le
contrat de sortie (`story.json`) est le même pour tout le monde.

## 3. Enregistrement

Dans `providers/__init__.py`, ajoute une ligne :

```python
from .monprovider_provider import MonProviderProvider

LLM_PROVIDERS = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "monprovider": MonProviderProvider,   # <-- nouvelle ligne
}
```

(idem dans `IMAGE_PROVIDERS` si le provider gère aussi les images).

## 4. Clé API

Ajoute la variable dans `.env.example` :

```
MONPROVIDER_API_KEY=
```

`config.get_api_key("MONPROVIDER_API_KEY")` lève une erreur claire si la clé
est absente - pas besoin de gérer ce cas toi-même dans le provider.

## 5. Utilisation

```bash
python main.py script generate --project ep1 --theme "..." --scenes 4 --provider monprovider
python main.py character add --project ep1 --name Randy --description "..." --provider monprovider
```

Ou en le mettant par défaut dans `config.yaml` :

```yaml
default_llm_provider: monprovider
```

## Bonnes pratiques

- **Ne jamais coder en dur une clé API** dans le fichier provider - toujours
  passer par `config.get_api_key(...)`.
- **Respecter le contrat de sortie.** `generate_script` doit renvoyer
  exactement le nombre de scènes demandé, avec des `speaker` qui
  correspondent aux noms de personnages fournis - `pipeline/script_writer.py`
  valide ça et lève une erreur explicite sinon.
- **`generate_image` doit renvoyer des octets PNG valides.** Si le backend
  ne supporte pas nativement la transparence (`transparent_bg=True`),
  demande un fond blanc uni dans le prompt (voir `GeminiProvider`) -
  `pipeline/character_studio.py` se charge de détourer le blanc en
  transparence automatiquement si l'image renvoyée est totalement opaque.
- **Ne pas modifier `pipeline/` ou `main.py`** pour faire fonctionner un
  provider. Si l'interface actuelle ne suffit pas (paramètre manquant,
  etc.), c'est le signe qu'il faut élargir `providers/base.py` de façon
  générique (nouveau paramètre optionnel avec valeur par défaut), pas
  ajouter un cas spécial ailleurs dans le code.
