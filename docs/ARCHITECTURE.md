# Architecture

## Vue d'ensemble

```
                 ┌─────────────────┐
   thème  ─────▶ │   LLMProvider    │ ─────▶ story.json (scènes + dialogues)
                 │ (openai/gemini)  │
                 └─────────────────┘

                 ┌─────────────────┐
 description ───▶│  ImageProvider   │ ─────▶ characters/<nom>/{neutral,talk,blink}.png
 personnage      │ (openai/gemini)  │        backgrounds/scene_N.png
                 └─────────────────┘

  story.json  +  character assets  +  backgrounds
        │
        ▼
 ┌────────────────────┐
 │  scene_renderer.py  │  Pillow (composite frame par frame) + MoviePy (encodage)
 │  - timing des lignes (sans TTS, estimé au nb de caractères)
 │  - bouche qui alterne pendant qu'un perso parle
 │  - clignement occasionnel des persos qui ne parlent pas
 │  - mouvement de caméra (Ken Burns : zoom/pan) sur le décor
 │  - sous-titres incrustés
 └────────────────────┘
        │  scenes/scene_N.mp4 (un clip par scène)
        ▼
 ┌────────────────────┐
 │ video_assembler.py  │  concatène les clips + fondu entre scènes
 └────────────────────┘
        │
        ▼
    projects/<nom>/final.mp4
```

## Pourquoi ce découpage

- **`providers/`** est la seule couche qui parle à une API externe. Tout le
  reste du code (pipeline, CLI) ne connaît que les interfaces
  `LLMProvider` / `ImageProvider` (`providers/base.py`), jamais un SDK
  concret. C'est ce qui permet d'ajouter un nouveau backend sans toucher au
  reste du projet (voir `PROVIDERS.md`).
- **`pipeline/`** contient toute la logique métier, indépendante de
  l'interface (CLI aujourd'hui, pourrait être un appel de fonction Python
  direct demain). Chaque module correspond à une étape du pipeline et peut
  être testé isolément avec un provider factice (voir `tests/test_pipeline_smoke.py`).
- **`main.py`** est une fine couche CLI au-dessus de `pipeline/` : elle ne
  fait qu'analyser les arguments, appeler le pipeline, et sérialiser le
  résultat en JSON. Elle ne contient aucune logique métier.
- **`projects/<nom>/`** est la seule notion de "état" persistant. Il n'y a
  pas de base de données : le système de fichiers EST l'état, ce qui rend
  chaque étape inspectable/éditable à la main entre deux commandes (ex:
  remplacer un `backgrounds/scene_3.png` généré par un autre avant de
  lancer `render`).

## Pourquoi pas de vraie génération vidéo IA frame-par-frame

Le style demandé (South Park) est un style **cutout 2D**, pas de l'animation
fluide. Payer une API vidéo IA par scène serait plus lent, plus cher, et
donnerait un mouvement moins contrôlable que composer nous-mêmes des images
fixes réutilisables (personnages) avec du code. Le seul appel IA "coûteux"
par scène est la génération du décor (une image fixe) ; le personnage n'est
généré qu'une fois par projet, pas par scène.

## Pourquoi pas de TTS pour l'instant

Décision explicite du projet (voir la section Roadmap ci-dessous pour la
piste d'extension). Sans audio, la durée d'affichage de chaque réplique est
estimée à partir de sa longueur (`chars_per_second` dans `config.py`), et le
dialogue est affiché en incrustation texte plutôt que synchronisé sur une
piste audio.

## Rendu d'une scène, en détail (`pipeline/scene_renderer.py`)

1. **Timeline** (`_build_timeline`) : convertit la liste de répliques d'une
   scène en fenêtres temporelles `(début, fin, personnage, texte)`, avec un
   petit padding en entrée/sortie de scène.
2. **Caméra** (`_make_background_frame_fn`) : le décor est suréchantillonné
   (`oversample`) puis, à chaque instant `t`, on recadre une fenêtre dont la
   taille/position dépend du type de caméra (`static`, `zoom_in`,
   `zoom_out`, `pan_left`, `pan_right`) et de la progression `t/duration`.
   Ça donne un mouvement de caméra simple sans avoir à générer plusieurs
   images.
3. **Pose du personnage** (`_character_pose`) : le personnage qui parle
   alterne `talk.png`/`neutral.png` toutes les `mouth_flap_interval`
   secondes ; les autres clignent (`blink.png`) sur un cycle déterministe
   propre à chaque nom (déphasé pour que tout le monde ne cligne pas en
   même temps).
4. **Placement** (`_character_position`) : les personnages présents dans la
   scène sont répartis en slots horizontaux égaux, avec une petite
   animation d'entrée en glissade au début de la scène.
5. **Frame finale** : tout est composité avec `Image.alpha_composite` dans
   une seule fonction `make_frame(t)` passée à un `moviepy.VideoClip` — pas
   de `CompositeVideoClip`/masques moviepy, pour rester simple et robuste
   aux différences de version de MoviePy.
6. **Encodage** : `clip.write_videofile(...)` avec `imageio-ffmpeg` (pas
   besoin d'un ffmpeg système installé séparément).

## Roadmap (pistes d'extension, non implémentées)

- **Voix (TTS) + synchro labiale.** Inspiré du projet
  [Synctoon](https://github.com/Automate-Animation/synctoon) (GPL-3.0,
  observé pour son architecture, pas repris tel quel) : un `AudioProvider`
  (ElevenLabs, OpenAI TTS, ...) génère l'audio de chaque ligne, un outil de
  phonétisation/alignement (ex: `g2p-en`, ou l'alignement natif renvoyé par
  certains TTS) donne le timing réel des mots, et un jeu de visèmes bouche
  (`talk_a.png`, `talk_o.png`, ...) remplace l'alternance simpliste
  actuelle. Suivrait le même pattern provider que `LLMProvider`/`ImageProvider`.
- **État intermédiaire éditable.** Synctoon expose un CSV "une ligne = un
  frame" entre le LLM et le rendu, permettant une correction manuelle avant
  rendu. On pourrait faire l'équivalent en exposant/validant `story.json`
  comme point d'édition manuelle (déjà possible aujourd'hui en éditant le
  fichier à la main entre `script generate` et `render`), et à terme un
  format par-scène plus fin (caméra, timing) si le besoin de contrôle fin
  se confirme.
- **Cache de rendu par combinaison.** Si le volume de scènes augmente,
  mémoïser les frames déjà rendues pour une combinaison (personnage, pose,
  position) identique, comme le fait Synctoon, éviterait de tout
  recalculer après un simple changement de texte.
- **Réutilisation de décors entre scènes similaires** au lieu d'en générer
  un par scène systématiquement.
