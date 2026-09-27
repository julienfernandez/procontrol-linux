# Submix MPC dans la vue Master — 26 septembre 2026

## Résultat et limite

La touche MASTER FADERS présente maintenant le Master Ardour en première
position, puis les bus audio et MIDI dans leur ordre de présentation. Les
banques restent limitées à huit voies physiques ; les commandes ciblent les
identifiants absolus du catalogue OSC. Un nouvel appui revient à la vue normale.

La session studio contient un bus stéréo `MPC SUB 1`. Il reçoit la piste
`MPC 11-12`, qui porte déjà le Submix 1 utilisé par les deux batteries du projet
MPC. Le bus alimente le Master. Le gain de la piste réceptrice a été transféré
au bus, puis la piste mise à gain unité, afin de conserver le niveau précédent
et de rendre le fader de la vue Master directement utile. Ce contrôle agit
sur le retour audio dans Ardour ; il ne modifie pas le fader interne de la MPC.
Aucun compresseur ni autre greffon n'a été ajouté ou activé.

La séparation demandée des quatorze pistes musicales sur quatorze paires
indépendantes **n'est pas active**. Une copie XPJ a été préparée et contrôlée,
mais la liaison matérielle reste à **16 canaux / 8 paires stéréo**. La session
Ardour dispose de seize pistes stéréo nommées jusqu'à `MPC 31-32` ; leurs noms
ne prouvent pas l'existence de trente-deux canaux USB.

## Refus matériel des 32 canaux

MPC One, application 3.9.1.2, noyau
`6.18.26-az01-2026-04-30-rt4`. L'option MPC « 32 inputs/outputs » était cochée.
La configuration temporaire UAC2 avec `p_chmask=c_chmask=4294967295` a été
refusée à l'attachement au contrôleur :

```
Error: unsupported playback channels mask
failed to start codex_mpc_audio: -22
```

Le pilote offre `p_chmask/c_chmask`, mais pas `p_channels/c_channels`.
Le [code Linux du pilote UAC2](https://github.com/torvalds/linux/blob/master/drivers/usb/gadget/function/f_uac2.c)
limite ce masque à `0x07ffffff`. Les bits réservés ne permettent donc pas de
déclarer trente-deux canaux en mettant simplement tous les bits à un.

Le script ne tente plus cette valeur invalide : la branche 32 canaux exige
les attributs de compte explicite du pilote. Cette branche n'a pas pu être
validée sur le noyau installé. Le nettoyage gère aussi un gadget créé mais
non attaché, et conserve le code d'échec initial. Aucun noyau, module ou
firmware n'a été remplacé.

## Incident et restauration

À 09:19:52 UTC, pendant le changement USB vers Internal dans les préférences,
l'application MPC a négocié son périphérique interne puis s'est arrêtée avec
`SIGSEGV` (journal systemd à 09:19:53). Le service l'a relancée. Cette observation
ne démontre pas la cause interne du plantage. Elle précède l'essai du gadget
32 canaux, refusé ensuite par le noyau.

La suite de la reconfiguration a été faite application arrêtée. Après le refus
32 canaux, le gadget 16 canaux a été recréé, les deux flux de maintien PipeWire
remis en service et le projet original restauré à l'identique. Les PCM de la
MPC ont été relus RUNNING dans les deux sens : S16_LE, 44 100 Hz, 16 canaux,
période 128, tampon 768. Trois relevés supplémentaires après rechargement du projet montrent les
deux PCM RUNNING avec les mêmes temps de déclenchement. Le projet a été
rechargé dans l'application ; son mixeur montre les pistes attendues. Ces
relevés ne sont pas un test d'endurance ni une écoute.

## Préservation et preuves

Les données musicales restent hors du dépôt public dans
`../mpc-routing-20260926/`. La copie locale complète du projet contient 53
fichiers, 98 439 407 octets utiles. L'archive tar fait 98 484 736 octets,
SHA-256 `b337a0858bfdee5329e2d07f7f104a88ae3deb1a1fdf486d65ef8b6d33670781`.
Les 51 fichiers du dossier de samples ont aussi été relus et hachés sur la
MPC, puis comparés au manifeste extrait de cette archive : tous identiques.
Il s'agit d'une copie sur le laptop, pas d'une archive sur support indépendant.

Le XPJ sauvegardé par l'utilisateur et finalement restauré a pour SHA-256
`e183a50efad32ad9c227cb0cd57f28b323149191c5a34cbfd2b4f4ec331e4fa9`.
La version préparée pour 14 paires a pour SHA-256
`461d6802a499817055a313d757a42f859d6bd2a3fa2191b664d9db3466b4b4c7`.
La comparaison JSON intégrale prouve que seuls `destination` et
`audioRouteSubIndex` des quatorze pistes changent ; six séquences, samples,
effets, niveaux et autres champs sont identiques. Cette version reste locale.
Une copie `.before-routing-20260926.bak` du XPJ est aussi conservée sur la carte.

Les entrées `audioRoute` sont au niveau des pistes du projet MPC3 : les mêmes
pistes sont partagées par ses six séquences. Les overrides de pads n'ont pas
été modifiés.

Validation logicielle : 55 tests ciblés réussis (catalogue/routage stéréo,
affichage, départs, automation et monitoring). Le nouveau test couvre un
Master situé après les bus dans le catalogue, le débordement sur une deuxième
banque, le ciblage des faders et le retour à la vue normale. Le catalogue OSC
réel expose le nouveau bus avec deux entrées et deux sorties. Les connexions
stéréo sont enregistrées dans la session. La confirmation physique des
libellés et du fader a été demandée ; elle reste à distinguer de ces preuves.

## Suite nécessaire

Pour activer les quatorze sorties stéréo et séparer aussi les deux batteries,
il faut d'abord un pilote gadget UAC2 capable d'annoncer 32 canaux discrets.
Après validation de ce transport : raccorder toutes les entrées Ardour,
charger la copie XPJ préparée, envoyer les deux pistes batterie distinctes
vers `MPC SUB 1`, puis contrôler chaque paire et les effets de sortie MPC.
Les inserts placés sur la sortie MPC 1/2 traitent cette sortie, pas toutes les
sorties séparées ; ce point doit être pris en compte à l'écoute du nouveau mix.
