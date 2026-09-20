# Souris ProControl : reprise après redémarrage de la passerelle

## Diagnostic du 20 septembre 2026

La ProControl était Online et Ardour répondait, mais aucun processus
`pointer_x11.py` ne tournait. Le dernier statut du pont (PID 386049) indiquait
`running: false`, `Démon Ethernet arrêté`, à 23:31:09 UTC le 19 septembre.
La passerelle avait été relancée à 23:31:14 UTC pendant les essais du jog,
sans relance du pont souris. Le code quittait volontairement dès que le verrou
de la passerelle était libéré. Le clavier ALPHA et les clics utilisent ce même
pont et étaient donc également indisponibles.

## Correction déployée

`tools/pointer_x11.py` attend maintenant le retour de la passerelle. Il
conserve son verrou, son processus, sa connexion X11 et le gain configuré.
L'état indique `waiting_daemon` pendant la coupure. Les touches et boutons
maintenus sont libérés ; aucun geste n'est injecté tant que la console n'est
pas Online. Un changement de processus remet à zéro les fractions de
mouvement, les doublons et les commandes en attente, puis reprend à la fin du
journal actuel. Les anciens gestes ne sont pas rejoués.

Une absence temporaire du journal au lancement ou pendant une rotation
n'entraîne plus d'arrêt. La limite de fraîcheur de 250 ms reste appliquée.
La commande explicite `./pointer stop` fonctionne aussi pendant l'attente.

## Validation

- L'ancien worker quitte avec le code 0 lorsque le faux démon perd son verrou :
  le test de reprise reproduit bien l'arrêt involontaire pour l'utilisateur.
- Sept tests ciblés passent : captures des quatre directions, format,
  doublons/fraîcheur, fractions, arrêt/reprise du démon avec boutons maintenus,
  rotation avec journal absent, création tardive du journal. Les tests du cycle
  de vie utilisent un vrai sous-processus, les vrais verrous et le lecteur de
  journal ; l'injection X11 y est remplacée par un enregistreur isolé.
- Essai sur la passerelle réelle : PID 456287 arrêté, état `waiting_daemon`
  observé, puis PID 456495 Online et Ardour répondant. Le pont a conservé le
  **même PID 456069** avant, pendant et après cette coupure.
- `./pointer start` répété conserve ce PID. Gain **0,58**, configuration
  révision 10, aucune erreur du pont. Ardour est resté ouvert, PID 390473.
- Suite complète : **226 tests réussis en 38,793 secondes** ; contrôle
  `git diff --check` sans erreur.

Les preuves locales sont conservées dans
`run/pointer-recovery-20260920T065225Z/` : ancien module, état initial,
échec attendu de l'ancien worker et états complets du redémarrage réel.
Le premier script de contrôle a mal interprété la sortie texte de `stop`
comme du JSON ; son bloc de restauration a relancé la passerelle, puis le
contrôle corrigé a été entièrement rejoué avec succès.

Après la demande d'essai, le pont a reçu 362 commandes de déplacement de la
console et émis 349 mouvements X11 ; la position interrogée est passée de
(736, 330) à (277, 61), sans erreur. Aucun clic n'a été relevé dans cette
fenêtre. Preuve : `physical-input-observed.json` dans le même dossier local.
La confirmation visuelle de l'utilisateur et l'essai des clics restent en
attente ; les compteurs logiciels ne remplacent pas ce constat.
