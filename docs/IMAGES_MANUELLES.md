# Créer ses images à la main (ChatGPT, Gemini…)

Tu peux fabriquer personnages et décors toi-même dans ChatGPT ou Gemini,
puis les donner au programme : `character import` pour les personnages, et
un dépôt direct dans `projects/<projet>/backgrounds/` pour les décors.
Aucune clé API n'est nécessaire pour ces étapes.

## Personnage : 3 images, dans la même conversation

Fais les trois images **dans la même conversation**, la pose neutre en
premier, puis les deux variantes à partir d'elle. Sinon le personnage
change d'apparence d'une image à l'autre.

**1. Pose neutre.** Remplace `[DESCRIPTION]` :

```
Un seul personnage de dessin animé, en pied, centré, vu de face, debout dans une pose neutre, bouche fermée : [DESCRIPTION].
Style cutout 2D en papier découpé, dans l'esprit de South Park : formes simples, contours noirs épais, couleurs unies et plates, sans dégradé ni ombre.
Fond blanc pur uni, sans décor, sans objet, sans ombre au sol, sans texte. Format carré.
```

**2. Bouche ouverte :**

```
Exactement le même personnage, même pose, même cadrage, même taille et même position dans l'image, mêmes couleurs.
Seule différence : la bouche est grande ouverte, comme s'il parlait. Fond blanc pur uni.
```

**3. Yeux fermés :**

```
Exactement le même personnage, même pose, même cadrage, même taille et même position dans l'image, mêmes couleurs.
Seule différence : les yeux sont fermés, comme s'il clignait des yeux. Bouche fermée. Fond blanc pur uni.
```

Puis :

```bash
python main.py character import --project ep1 --name Yanis \
  --neutral neutre.png --talk bouche_ouverte.png --blink yeux_fermes.png \
  --personality "..." --role "..."
```

## Décor

```
Décor de dessin animé, sans aucun personnage : [LIEU].
Style cutout 2D en papier découpé, dans l'esprit de South Park : formes simples, contours noirs épais, couleurs unies et plates. Format paysage 16:9, sans texte.
```

Enregistre-le sous `projects/<projet>/backgrounds/scene_<id>.png`, où
`<id>` est le numéro de la scène dans `story.json`. Un même décor peut
servir à plusieurs scènes : copie-le sous chaque numéro. `render` ne
regénère jamais un décor déjà présent.

## Règles pour un bon résultat

- **Fond blanc pur et uni** derrière le personnage : il est retiré
  automatiquement.
- **Contours noirs continus** : le blanc à l'intérieur du personnage
  (t-shirt, yeux, baskets) est conservé tant qu'il est entouré d'un
  contour fermé.
- **Même cadrage sur les 3 poses** : sinon le personnage « saute » à
  l'écran quand il parle. Les marges vides autour du personnage sont
  recadrées automatiquement, de la même façon pour les 3 poses.
