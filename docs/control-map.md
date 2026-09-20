# Carte fonctionnelle ProControl → Ardour / Linux

État du 20 septembre 2026. Cette carte décrit le code actuel, adapté à Ardour 9.8.
Elle ne signifie pas que chaque bouton a été essayé physiquement. Les libellés
sont ceux de la console ; les codes proviennent de la table ProControl tierce
et des captures référencées dans les guides.

## Édition et transport

Le [guide d’édition](console-editing.md) détaille les combinaisons et la sélection
à éditer. Pour une boucle : **WINDOWS EDIT → SELECT de tranche → IN → POST × 4
→ OUT → LOOP PLAYBACK**. Après un déplacement au jog, laisser la position
s’afficher avant de poser IN ou OUT : le curseur d’Ardour est asynchrone.

| Bouton | Fonction actuelle |
|---|---|
| PLAY / STOP, retour début / fin, REW / FF | Transport Ardour |
| Jog | Déplacement du curseur ; SHIFT affine le jog normal ; SCRUB / SHUTTLE changent son mode |
| WINDOWS EDIT / MIX | Éditeur principal avec point d’édition au curseur / mixeur |
| IN / OUT | Début d’une nouvelle sélection / fin ; SHIFT déplace les bornes de boucle ; CTRL bascule le punch |
| PRE / POST | Reculer / avancer d’une mesure ; SHIFT quatre mesures ; CTRL rejoint les bornes de sélection |
| LOOP PLAYBACK | Affecter la sélection à la boucle et la lancer ; SHIFT conserve les bornes existantes |
| CAPTURE | Affecter la sélection à la boucle ; SHIFT rappelle la sélection de boucle |
| LOOP REC | Affecter la sélection au punch ; ne lance pas l’enregistrement |
| CUT / COPY / PASTE / DELETE | Couper / copier / coller / supprimer la sélection ; SHIFT + COPY ou PASTE duplique |
| SEPARATE | Séparer la plage ou couper au curseur ; SHIFT coupe au curseur les objets des pistes sélectionnées |
| TRIM / SELECT / GRAB / PENCIL | Rogner / sélectionner une plage / sélectionner ses régions / dessiner ; variantes dans le guide |
| SHUFFLE / SLIP | Mode ripple / slide |
| SPOT | Caler le début du groupe de régions au curseur ; SHIFT cale la fin |
| GRID | Grille mesure ; SHIFT temps ; ALT désactive l’accrochage |
| NUDGE puis flèches BANK | Déplacer les régions sélectionnées selon le pas Nudge d’Ardour ; hors NUDGE, changer de banque |
| AUDITION | Lire la sélection ; SHIFT lit les régions sélectionnées |
| UNDO / SAVE | Annuler / sauvegarder ; SHIFT + UNDO rétablit |
| F1 / F2 / F3 / F4 | Rafraîchir / ajouter un marqueur / précédent / suivant ; SHIFT + F3/F4 zoome |
| COUNTER MODE | SMPTE ↔ mesures/temps ; ne change pas la synchronisation |

Avec la préférence Ardour « Loop is a mode », LOOP active le mode ; PLAY démarre
la lecture. Les cinq touches autour de ZOOM/SEL sont maintenant identifiées par quinze
appuis/relâchements réels. Centre éteint : UP/DOWN changent de voie et
PREVIOUS/NEXT déplacent le curseur aux limites des régions. Centre allumé :
zoom horizontal et hauteur des pistes. Voir [les essais et voyants](console-test-workflow.md).

## Tranches, écoute et DSP

| Contrôle | Fonction actuelle |
|---|---|
| Huit faders et contact tactile | Gain normalisé, toucher, retour moteur protégé pendant la manipulation |
| SELECT / MUTE / SOLO / REC RDY | Sélection, mute, solo et armement de la piste de la banque |
| AUTO | Manual / Play / Write / Touch / Latch pour l’automation du gain |
| Encodeurs de tranche | Pan par défaut, départ choisi ou paramètres du mode DSP actif |
| MON/Ø | Page d’écoute ; SHIFT conserve la polarité |
| ASSIGN/MUTE en page d’écoute | IN ↔ DISK par tranche, indépendamment de REC |
| INPUT / OUTPUT | Forcer IN / DISK sur la piste sélectionnée ; DEFAULT rend la main à AUTO en page d’écoute |
| EQ IN/EDIT / DYN IN/EDIT | Ouvrir l’EQ / compresseur adapté ; le créer s’il manque avec l’extension Ardour fournie |
| INS/SEND par voie | Navigateur DSP ciblé sur cette voie, comme INSERTS/PARAM |
| INSERTS/PARAM | Navigateur chaîne / bibliothèque ; huit effets proposés, sans catalogue VST général |
| Huit rotatifs DSP et boutons associés | Naviguer, ouvrir un effet, sélectionner et régler les paramètres selon le mode |
| PAGES / MASTER BYPASS / ESCAPE | Pages de paramètres / bypass / sortie du mode DSP |
| CHANNEL MATRIX | Sélection, mute, solo, armement selon le mode ; banques A–D |
| MASTER FADERS | Vue master puis retour aux pistes |

Guides : [écoute IN/DISK](track-monitoring.md), [bibliothèque DSP](curated-plugins.md),
[EQ et compresseur](eq-plugin-workflow.md), [Chaleur, Tube et Tape](warm-tape-plugins.md),
[automation](automation-modes.md). Les modifications de plugins exigent les patches
natifs et des descripteurs compatibles ; voir [la reconstruction](../native/README.md).

## Linux, affichage et retours

Trackpad et clics pilotent X11 ; ALPHA transforme la Channel Matrix en clavier.
Le pavé numérique envoie des caractères à l’application active. Les touches et
clics sont libérés lors d’une perte de connexion. Le pont souris attend puis
reprend automatiquement après un redémarrage du daemon, sans rejouer les anciens
gestes. Voir [clavier/souris](keyboard-mouse.md).

Noms, valeurs, LEDs, compteur, anneaux de pan, moteurs et vumètres suivent OSC.
Le hook Lua fournit les niveaux stéréo ; les colonnes master utilisent les
adresses calibrées dans les réglages locaux. Un ACK confirme la réception d’une
trame, pas l’atteinte mécanique d’un fader ni son rendu visuel.

Le jog et les moteurs sont regroupés à 50 Hz ; une seule trame attend son ACK,
avec échéance de 100 ms et reprise bornée à partir de l’état actuel. Les keepalive
restent indépendants. Voir [l’ordonnancement](jog-motor-scheduling.md) et le
[correctif Ardour jog/JACK/Link](jog-link-stability-2026-09-20.md).

## Ce que l’inventaire ne prouve pas

[L’inventaire généré](mapping-backlog.md) inspecte neuf contextes logiciels ; son
[JSON](mapping-coverage.json) détaille les actions. Une touche reconnue peut
changer un mode local ou être volontairement consommée sans action. Les commandes
absentes de la table, encodeurs et contrôles audio analogiques ont une validation
séparée. Les grandes banques, l’endurance, l’écoute synchronisée MPC et tous les
gestes physiques ne sont pas couverts par les tests unitaires.

Les anciens états restent dans les [rapports datés](README.md) et l’historique Git.
