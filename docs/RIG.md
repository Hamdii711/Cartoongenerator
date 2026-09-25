# Personnage articulé (rig)

Depuis cette version, `character add` génère par défaut un **personnage
articulé** plutôt que 3 poses figées : le torse, la tête (3 variantes :
bouche fermée, bouche ouverte, yeux fermés), les 2 bras et les 2 jambes sont
générés comme des **pièces séparées**, puis animés en tournant chaque
membre autour de son articulation, comme un vrai pantin en papier découpé.

C'est ce qui permet un vrai mouvement de jambes à la marche et un léger
balancement au repos, au lieu d'un personnage plat qui glisse sur l'écran
ou flotte au-dessus du décor.

## Pourquoi ce changement

L'ancien système (`character add --flat` / `character import`) ne stockait
que 3 images du corps entier (`neutral`, `talk`, `blink`). Sans jambe
séparée, impossible de faire marcher le personnage autrement qu'en glissant
son corps entier d'un point à un autre — d'où le rendu "il flotte / pas de
mouvement de jambe / se déplace bizarrement" observé sur le premier test.

## Comment ça marche

### 1. Génération des pièces

`character add` (sans `--flat`) génère 8 images via le provider image :

| Pièce | Fichier | Convention de cadrage |
|---|---|---|
| Torse | `torso.png` | bord du haut = point d'attache du cou, bord du bas = point d'attache des hanches |
| Tête (neutre) | `head_neutral.png` | bord du bas = coupe du cou |
| Tête (parle) | `head_talk.png` | idem, bouche grande ouverte |
| Tête (cligne) | `head_blink.png` | idem, yeux fermés |
| Bras gauche/droit | `arm_left.png` / `arm_right.png` | bord du haut = épaule |
| Jambe gauche/droite | `leg_left.png` / `leg_right.png` | bord du haut = hanche |

Chaque image est détourée (fond blanc → transparence) exactement comme les
personnages plats. Le fichier `rig.json` dans le dossier du personnage
enregistre les chemins des pièces et les points d'attache.

### 2. Animation par rotation

À chaque frame, `pipeline/rig.py::LoadedRig.compose(...)` :
1. place le torse ;
2. fait pivoter chaque bras/jambe autour de son point d'attache (haut de
   l'image) d'un angle donné, puis le colle sur le point d'attache
   correspondant du torse (épaule/hanche) ;
3. colle la tête (variante neutre/parle/cligne) sur le point d'attache du
   cou.

Aucune coordonnée n'est devinée par l'IA : les points d'attache sont des
fractions fixes de la taille du torse (`SOCKETS` dans `pipeline/rig.py`),
et le point d'attache de chaque membre est toujours le haut de sa propre
image (`PART_ANCHOR`) — c'est la consigne donnée dans le prompt de
génération qui garantit cette convention.

### 3. Angles utilisés par le moteur de rendu

`pipeline/scene_renderer.py` calcule, à chaque instant `t` :
- **En marche** (première apparition du personnage dans l'épisode) :
  jambes en ciseaux (`walk_leg_angle`, sinusoïde déphasée de π entre les
  deux jambes), bras qui se balancent à l'inverse des jambes du même côté —
  contrôlé par `walk_swing_degrees` dans `config.yaml`.
- **Au repos** (personnage déjà en place) : léger balancement
  (`idle_sway_angle`) sur les bras, déphasé par personnage pour que tout le
  monde ne bouge pas en même temps — contrôlé par `idle_sway_degrees` /
  `idle_sway_period`.
- **Tête** : même logique qu'avant (`neutral`/`talk`/`blink` choisie par
  `_character_pose`), simplement appliquée à la bonne variante de tête du
  rig plutôt qu'à une image de corps entier.

## Utilisation

```bash
# Personnage articulé (par défaut)
python main.py character add --project ep1 --name Randy \
  --description "homme adulte, cheveux bruns, pull orange" \
  --personality "naïf, impulsif" --role "père de famille"

# Ancien mode plat (3 poses figées, pas de rig)
python main.py character add --project ep1 --name Randy --flat \
  --description "..." --personality "..." --role "..."
```

`render` détecte automatiquement si un personnage a un `rig.json` et
l'anime en conséquence — aucune option à passer côté `render`/`generate`.

## Limite connue : dérive de couleur entre pièces

Chaque pièce est générée par un appel séparé à l'IA image : le torse, un
bras, une jambe n'ont **aucune image de référence commune** au moment de
leur génération, seulement la même description texte. Une légère
différence de teinte de peau ou de couleur de vêtement entre deux pièces
est possible, même avec un prompt identique.

Si ça arrive :
- Retoucher la pièce concernée à la main (c'est un simple PNG dans
  `characters/<nom>/<piece>.png`) — le rendu relit les fichiers du disque,
  aucune régénération nécessaire ailleurs.
- Ou régénérer uniquement le personnage (`character add` à nouveau) et
  espérer une meilleure cohérence à l'essai suivant.

## `character import` reste en mode plat

Importer des images faites à la main (`character import`,
[docs/IMAGES_MANUELLES.md](IMAGES_MANUELLES.md)) ne peut pas produire un
rig : découper une image de personnage entier en pièces articulées
demanderait un outil de segmentation, hors du périmètre actuel. Un
personnage importé reste donc animé par glissement/swap de pose entière,
comme avant.
