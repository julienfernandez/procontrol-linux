# Trackpad, clavier et pavé de touches

**Le déplacement du pointeur Linux dans les quatre directions est confirmé
par l'utilisateur le 13/09/2026.** Le démon Ethernet et le pont souris restent
en arrière-plan. Les clics et le clavier ALPHA / pavé sont maintenant raccordés et reçus par le test GTK.

## Utilisation sur ce laptop

```
./pointer start --gain 0.24
./pointer status
./pointer stop
```

Le pont fonctionne sans root sur la session XFCE/X11, à l'aide de l'extension
[XTEST](https://xorg.freedesktop.org/archive/X11R7.7/doc/libXtst/xtestlib.html).
Il nécessite procontrold actif et s'arrête si celui-ci s'arrête. Il n'émet aucun
paquet Ethernet. État : `run/pointer-status.json` ; erreurs :
`run/pointer-launcher.log`. `stop` ne coupe que la souris, pas le transport.

Gain utilisé actuellement : **0,24**, après un premier essai à 0,12 jugé trop
lent. Pour changer le gain, arrêter ce seul pont puis relancer avec `--gain`.
Sans cet argument, la valeur initiale du programme est 0,12. Un lancement
alors qu'il tourne retourne son état sans changer le gain. Les fractions sont
accumulées pour préserver les mouvements lents. Ce réglage est une sensibilité
constante, pas encore une courbe d'accélération selon la vitesse du doigt.

Le pont suit les nouvelles commandes unicast du journal de procontrold, ignore
les doublons et messages vieux de plus de 250 ms. Le déplacement ignore le jog ; les touches et clics passent par les événements décodés du démon. Il reprend
le nouveau fichier lors d'une rotation du journal. Un canal d'événements dédié
remplacera utilement ce suivi de journal ensuite. Cette première version ne
prend pas en charge Wayland. `/dev/uinput` existe mais ses droits restent
inchangés ; aucun périphérique uinput n'a été créé, evdev n'est pas installé.

## Encodage du déplacement

Format reçu : `f0 13 00 60 01 H X Y f7`. Dans ce corps de neuf octets,
H est à l'offset 5, X à 6 et Y à 7. Les coordonnées sont relatives et signées :

```
dx = signed8(((H & 0x03) << 6) | X)
dy = signed8(((H & 0x0c) << 4) | Y)
```

X positif = droite ; Y positif = bas. La capture contrôlée du 13/09 à 18:22 UTC
confirme `H & 0x20` = clic gauche, `H & 0x10` = clic droit ; zéro libère les boutons. L'empaquetage correspond à
celui du [pilote souris série Microsoft dans Linux](https://github.com/torvalds/linux/blob/master/drivers/input/mouse/sermouse.c),
fonction sermouse_process_ms. Cette correspondance n'établit pas que la liaison
interne de la console soit série ; nous observons son enveloppe Ethernet.
Le lecteur `tools/procontrol_pointer.py` vérifie longueur, famille et bits
autorisés sans remplacer la table tierce ni les octets originaux.

## Preuves locales

Chaque dossier sous captures contient PCAP original, SHA-256, notes, audit et
décodage par trame. Toutes ces captures dumpcap sont sans perte signalée.

| Expérience (préfixe UTC 20260913) | Trames de geste | Résultat |
|---|---|---|
| T173255Z-trackpad-horizontal-online-vgcJ0Q | 17–2866 ; jog 748–953 | Gestes mélangés signalés par l'utilisateur, conservés comme tels |
| T173709Z-trackpad-horizontal-only-HPVbyL | 8–636 puis 640–1256 | 315 X positifs à droite ; 309 X négatifs à gauche |
| T173936Z-trackpad-vertical-only-QHmmiK | 15–576 puis 580–1235 | Sommes Y -3867 vers le haut, +3397 vers le bas |
| T174437Z-trackpad-x11-live-vK4Upf | 13–3120, mouvements entre autres événements | 1 553 mouvements reçus, 1 101 déplacements X11 émis, quatre directions confirmées |

Le premier relevé mélangé contient aussi 103 événements `b0 5c ..`, étiquetés
`/track/29/reavpot` par ReaControl24. L'utilisateur a bougé le jog, mais il faut
encore isoler ses directions ; ce libellé ne désigne pas une 29e tranche.

Le pont souris démarre à 17:44:37 UTC, PID 58018, gain 0,12. L'utilisateur
confirme les quatre directions et signale une lenteur. Arrêt propre de ce seul
pont à 17:46:41, relance à 17:46:42 UTC, PID 58267, gain 0,24. Le démon
Ethernet PID 56762 n'a pas été interrompu. Utiliser status pour les PID actuels.
La nouvelle vitesse reste à apprécier par l'utilisateur.

## ALPHA, pavé et clics validés en entrée Linux

La séquence contrôlée ALPHA, A, B, Z, SHIFT+C, ALPHA, 1, 2, Entrée, clic gauche,
clic droit est confirmée par l'utilisateur. Capture :
`20260913T182202Z-alpha-keypad-controls-batch-ndOm88`, 112 trames, zéro perte,
SHA-256 `0939224b4f274f40ff634506ba26dfa159a6703233ebecde53c953b63a1d5fa9`.
ALPHA : trames 12/14 et 44/46 ; lettres et Shift : 16–39 ; pavé : 49–60 ;
clic gauche : 64/66 ; clic droit : 69/71. Les octets et actions sont rejoués
par `tests/fixtures/alpha-keypad-clicks.json`.

Format bouton : `90 numéro zone`, bit 0x40 de zone = appui. Matrix = zone 0x17 ;
ALPHA = numéro 0x21 ; A–Z = 1–26 ; SHIFT = 0x1b ; pavé = zone 0x1a.
Les photos confirment les autres inscriptions de la rangée ALPHA.

Le pont traduit les symboles avec le clavier X11 **fr/latin9** actif sur ce
laptop. Il ajoute les modificateurs nécessaires aux chiffres et symboles ;
il suit les touches qu'il a pressées pour les libérer à l'arrêt / déconnexion.
CAPS est géré localement ; l'interaction CAPS+SHIFT reste à affiner.

Le test réel [input-live-validation.json](input-live-validation.json) contient
39 appuis et 39 relâchements, des lettres minuscules et majuscules, les chiffres,
et deux clics gauche plus un clic droit dans la zone dédiée. Ce fichier
journalise uniquement les événements de notre fenêtre de test, ouverte à
18:35:18 UTC puis fermée par l'utilisateur. Les gestes reçus étaient plus
nombreux que la courte séquence proposée : conserver cette distinction.
Les événements console et X11 concordent à quelques millisecondes près pour
les clics ; ce n'est pas une mesure générale garantie de latence.

Relance du pont étendu : 18:34:48 UTC, gain 0,24. Il reste actif après la fermeture
de la fenêtre de test. L'utilisateur rapporte « ça semble fonctionner à merveille ».
