# Éditer depuis la ProControl — Ardour 9.8

Les cinq touches PREVIOUS / ZOOM/SEL / NEXT / UP / DOWN sont maintenant
identifiées. Leur mode navigation/zoom et les impulsions lumineuses des
commandes ponctuelles sont décrits dans [le parcours d’essai](console-test-workflow.md).

## Première boucle, sans souris

1. Appuyer sur **WINDOWS / EDIT**, puis **SELECT** sur la tranche voulue.
2. Aller au début avec la touche retour au début, ou placer le curseur avec le **jog**.
3. Appuyer sur **IN** : c'est le début d'une nouvelle sélection.
4. Appuyer quatre fois sur **POST** pour avancer de quatre mesures, puis **OUT**.
5. Appuyer sur **LOOP PLAYBACK**. La plage devient la boucle et la lecture démarre.

Un deuxième appui sur LOOP PLAYBACK désactive la boucle. STOP arrête la lecture.
**SHIFT + LOOP PLAYBACK** bascule la boucle existante sans remplacer ses bornes.
Ardour est ici configuré avec son comportement normal « lecture en boucle ».
Si la préférence Ardour « Loop is a mode » est activée, LOOP active le mode et
il faut aussi PLAY pour démarrer le transport.

PRE/POST conservent la position relative dans la mesure. Pour une boucle exactement
sur les barres, partir du début d'une mesure. **GRID** choisit la grille à la mesure
et active l'aimantation ; **SHIFT + GRID** choisit le temps ; **ALT + GRID** désactive
l'aimantation. Le jog reste continu. **SHIFT + jog** le rend dix fois plus fin.
Laisser le curseur finir son déplacement avant IN/OUT ou une coupe : une commande
immédiatement accolée au dernier paquet de jog peut précéder la mise à jour du
curseur dans Ardour. Le test sans pause a reproduit cette limite ; aucune garantie
à l'échantillon près n'est revendiquée pour ce geste simultané.

## Touches d'édition

Les opérations agissent sur les pistes/régions sélectionnées dans Ardour. SELECT
sur une tranche choisit la piste. **SHIFT + EDIT TOOL / SELECT** sélectionne toutes
les pistes pour une édition commune. Vérifier la sélection visible avant de
supprimer ou déplacer plusieurs pistes.

| Touche | Appui simple | Avec SHIFT |
|---|---|---|
| WINDOWS / EDIT | Ouvrir l'éditeur et placer le point d'édition au curseur de lecture | Idem |
| WINDOWS / MIX | Ouvrir la console de mixage | Idem |
| WINDOWS / TRANS | Centrer l'éditeur sur le curseur | Idem |
| UNDO | Annuler | Rétablir |
| SAVE | Sauvegarder la session | Idem |
| IN | Commencer une nouvelle plage, avec une fin provisoire au même point | Déplacer le début de la boucle existante au curseur |
| OUT | Terminer la plage | Déplacer la fin de la boucle existante au curseur |
| PRE / POST | Reculer / avancer d'une mesure | Reculer / avancer de quatre mesures |
| CUT | Couper la sélection dans le presse-papiers | Idem |
| COPY | Copier la sélection | Répéter une fois juste après |
| PASTE | Coller au curseur | Répéter une fois juste après |
| DELETE | Supprimer la sélection | Idem |
| SEPARATE | Séparer aux bornes de la plage ; sans plage, couper au curseur | Couper au curseur sur les pistes sélectionnées, même avec une ancienne plage |
| CAPTURE | Définir la boucle depuis la sélection, sans démarrer | Retrouver la plage de la boucle existante |
| TRIM | Garder la partie des régions comprise dans la plage | Outil d'étirement temporel |
| SELECT (Edit Tool) | Outil de sélection d'une plage | Même outil, sur toutes les pistes |
| GRAB | Sélectionner les régions qui croisent la plage, outil objet | Ne sélectionner que les régions entièrement dans la plage |
| PENCIL | Outil de dessin d'Ardour | Idem |
| SHUFFLE | Mode Ripple d'Ardour : édition avec décalage du contenu suivant | Idem |
| SLIP | Mode Slide : édition sans refermer automatiquement les trous | Idem |
| SPOT | Caler le début du groupe de régions au curseur, décalages relatifs conservés | Caler la fin du groupe |
| GRID | Aimantation à la mesure | Aimantation au temps |
| AUDITION | Lire une fois la plage sélectionnée | Lire les régions sélectionnées |
| LOOP PLAYBACK | Boucler la sélection / désactiver la boucle déjà active | Basculer la boucle existante |
| LOOP REC | Définir les bornes punch depuis la sélection | Idem |
| NUDGE | Basculer les flèches BANK SELECT vers le déplacement des régions | Idem |

**CTRL + PRE/POST** rejoint le début/la fin de la plage. **CTRL + IN/OUT** conserve
les bascules punch-in/punch-out. LOOP REC prépare les bornes ; l'armement des pistes,
le punch et l'enregistrement restent des commandes distinctes.

NUDGE allumé : les flèches BANK SELECT décalent les régions sélectionnées selon
la distance Nudge réglée dans Ardour. Cette distance n'est pas forcément une
mesure (le réglage courant peut être de plusieurs secondes). NUDGE éteint : les
flèches changent de banque. Dans le navigateur de plugins, elles gardent leur
fonction de navigation ; WINDOWS / EDIT permet d'en sortir.

## Trois gestes utiles

- **Retirer un passage** : SELECT de la piste → IN → déplacement → OUT → DELETE.
  SLIP laisse un trou ; SHUFFLE utilise le mode Ripple choisi dans Ardour.
- **Répéter quatre mesures** : IN → SHIFT + POST → OUT → SHIFT + COPY.
  Chaque nouvel appui répète à la suite ; UNDO annule la dernière répétition.
- **Déplacer/caler un morceau** : IN/OUT autour du passage → SEPARATE → GRAB →
  placer le curseur avec le jog → SPOT. GRAB prend les régions qui croisent la
  plage ; SHIFT + GRAB convient pour exclure celles qui dépassent les bornes.

Le point d'édition passe explicitement à **Playhead**, donc les touches d'édition
ne suivent plus la dernière position de la souris sur une autre forme d'onde.
Le trackpad et les boutons de souris de la console restent utilisables pour les
outils graphiques, notamment le dessin et l'étirement temporel.

## Zoom et navigation

SHIFT + F1 cadre toute la session ; SHIFT + F2 cadre la sélection ;
SHIFT + F3/F4 dézoome/zoome. La croix PREVIOUS / ZOOM/SEL / NEXT / UP / DOWN
est aussi raccordée depuis sa capture physique du 20 septembre.

ZOOM/SEL éteint : UP/DOWN sélectionnent la voie précédente/suivante ;
PREVIOUS/NEXT placent le curseur à la limite de région précédente/suivante.
ZOOM/SEL allumé : UP/DOWN changent la hauteur des pistes sélectionnées ;
PREVIOUS/NEXT règlent le zoom horizontal. SHIFT + centre cadre la sélection,
ALT + centre cadre la session. [Procédure et retour lumineux](console-test-workflow.md).

## Implémentation et validation

`tools/console_editing.py` centralise les actions. Ardour 9.8 a déplacé les actions
communes dans le groupe explicite `EditorEditing` : les anciens `Editor/editor-cut`,
`Editor/undo` et `MouseMode/set-mouse-mode-*` ne conviennent plus. Même `/undo`
natif appelait encore l'ancien groupe ; la passerelle utilise maintenant
`/access_action EditorEditing/undo`. SAVE passe par `Common/Save`.

Les actions GUI de construction puis lecture de boucle sont envoyées dans cet
ordre. Ajouter une commande Roll entre les deux a été testé puis écarté : ses
événements asynchrones empêchaient le bouclage. IN remet d'abord la fin au curseur
avant le début, afin de ne pas créer une sélection jusqu'à l'infini.
Les répétitions Ethernet et les appuis maintenus ne répètent pas les éditions.

Essais réels dans une **copie jetable** de session, Ardour 9.8, moteur Dummy,
écran Xvfb séparé et OSC 3901 : positions des régions et bornes vérifiées dans
les sauvegardes XML ; lecture et rebouclage vérifiés par retours OSC. Le projet
musical actif n'a pas servi aux découpes de test. Voir
[le rapport](console-editing-validation-2026-09-20.json).
Ces tests valident les commandes logicielles ; les touches physiques n'ont pas
toutes été actionnées et l'écoute audio n'a pas été évaluée.
