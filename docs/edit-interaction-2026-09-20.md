# Édition et retours d’état — 20 septembre 2026

## Ce que les gestes montrent

La séquence annoncée est retrouvée dans les journaux permanents entre
19:24:31 et 19:25:24 UTC. La fenêtre PCAP précédente était déjà fermée :
ces observations proviennent des journaux, pas d’une nouvelle capture PCAP.

Trois appuis et trois relâchements pour CUT, COPY, PASTE, DELETE, SEPARATE,
CAPTURE, AUDITION, PRE, IN, OUT et POST ; un LOOP REC ; trois QUICK PUNCH ;
deux LOOP PLAYBACK et deux EX TRANS, suivis de deux STOP. Les commandes
attendues sont transmises. Les six fonctions CUT à CAPTURE reçoivent chacune
trois allumages et trois extinctions de voyant. Ces messages ne prouvent pas
la visibilité des lampes sur cette unité.

CUT/DELETE sans cible et SEPARATE au curseur ont été reproduits sur une copie
Ardour Dummy : absence de région/plage sélectionnée → aucune coupe/suppression ;
SEPARATE divise au curseur sur la piste sélectionnée. Avec IN/OUT, coupe,
suppression, copie, collage et annulation fonctionnent. Ne pas confondre le
curseur de lecture, la piste sélectionnée et la sélection à éditer.

## Parcours depuis la console

1. WINDOWS / EDIT puis SELECT sur la tranche.
2. Placer le curseur avec le jog et presser IN.
3. Déplacer le curseur, par exemple POST une mesure, puis OUT.
4. DELETE retire ce passage ; CUT le retire et le copie ; COPY le copie.
5. Pour coller : placer le curseur, puis PASTE. UNDO annule, SHIFT + UNDO rétablit.

Pour traiter des régions entières : IN/OUT autour, GRAB, puis édition.
GRAB réactive l’outil plage avant de lire les bornes, même après avoir utilisé
l’outil objet. SEPARATE signifie « diviser », CUT signifie « couper la sélection
vers le presse-papiers ». Aucune sélection automatique plus large n’est ajoutée
à CUT ou DELETE.

## Voyants

| Commande / état | Retour |
|---|---|
| CUT, COPY, PASTE, DELETE, SEPARATE, CAPTURE, AUDITION, PRE, POST, UNDO, SAVE | Flash 350 ms à l’envoi |
| IN sans fin distincte | Clignotement lent, 0,5 s allumé / 0,5 s éteint |
| IN puis OUT à une autre position | IN et OUT fixes |
| CUT, DELETE, UNDO/REDO, GRAB, reconnexion | Effacement du guide local IN/OUT |
| EX TRANS et ON LINE | Fixes lorsque la synchro externe d’Ardour est confirmée active |
| QUICK PUNCH | Fixe si punch-in et punch-out actifs ; lent si un seul des deux est actif |
| REC transport armé sans enregistrement effectif | Clignotement lent |
| REC pendant l’enregistrement effectif d’une piste armée | Fixe |
| LOOP PLAYBACK | État de boucle renvoyé par Ardour |
| LOOP REC | Flash à la définition des bornes de punch ; n’arme pas les pistes |

Le guide IN/OUT décrit les gestes envoyés depuis la console. Il ne prétend pas
suivre toutes les sélections réalisées à la souris. Une position immobile reste
valide ; après perte OSC, les positions et états sont invalidés. IN et OUT au
même point restent une plage incomplète. Un retour arrière est accepté.
Les boutons EX TRANS/QUICK PUNCH maintenus ou retransmis ne basculent qu’une fois.

## Lecture des états Ardour

Le sixième patch natif ajoute `/procontrol/transport/state`, lecture seule,
sans création ni reconstruction d’observateur OSC. Réponse entière : version 1,
synchro externe, punch-in, punch-out, boucle, état REC (0 désactivé / 1 armé /
2 enregistrement), présence d’une piste armée. La requête normale est limitée
à quatre par seconde ; sans réponse elle retombe à une toutes les cinq secondes.
Après deux secondes sans réponse, les indications détaillées deviennent inconnues
et leurs voyants sont éteints. Un appui seul n’invente pas l’état de synchro.

Le retour `/position/samples` est également activé pour le guide IN/OUT. Les
flashes gardent la file Ethernet à un ACK en vol et la reprise existante.
Aucun thread ou délai bloquant n’a été ajouté au démon.

## Vérification

256 tests Python passent (60,773 s), dont six nouveaux cas de guide, états
confirmés, temporisation, perte de connexion et maintien. Les tests d’édition
sont rejoués dans Ardour 9.8 avec moteur Dummy sur OSC3901, écran Xvfb séparé.
Le nouvel OSC est interrogé dans cette instance pour punch, synchro externe,
REC armé, enregistrement réel puis arrêt. Le projet musical original ne sert
pas aux découpes ni à l’enregistrement de test.

[Résultats structurés](edit-interaction-validation-2026-09-20.json).
Le rendu physique des nouvelles lampes reste à confirmer sur la console.

Les six patches s’appliquent dans l’ordre sur la base officielle ; les neuf
fichiers obtenus sont identiques au build. Mise en service après sauvegarde et
fermeture propre d’Ardour : module installé identique au module testé, passerelle
Online, Ardour répondant, pointeur actif, statut transport confirmé et 243/243 ACK
sans timeout à la vérification initiale.
