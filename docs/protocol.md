# Carnet du protocole

## Statut des preuves

**Rapport utilisateur** : ProControl originale fonctionnelle aux diagnostics,
affichage « Welcome to ProControl » puis `Offline` sans Pro Tools. Cela valide
le contexte matériel déclaré, pas le protocole réseau.

**Observation locale du 13/09/2026** : `enp0s25` a une porteuse à 10 Mbit/s
half-duplex. La première capture contient 13 trames `0x885f` depuis
`00:a0:7e:a0:ad:9c`, dont 7 annonces `MAINUNIT` / `1.37`.
Voir [le relevé sourcé des observations locales](observations-2026-09-13.md).
**Online obtenu** : ouverture e2 acquittée, maintiens successifs acquittés,
annonces e1 et disparition de Offline confirmée par l'utilisateur. Un premier
couple PLAY pressé/relâché est capturé. Voir [les preuves actives](online-2026-09-13.md).

**Source tierce** désigne du code ou une capture d'un autre utilisateur.
**Hypothèse locale** désigne une interprétation qui attend une expérience.
Chaque nouvelle conclusion doit citer PCAP + SHA-256 + numéros des trames,
direction, état de la console et nombre de répétitions.

## Transport : références et première confirmation locale

Le [daemon expérimental ReaControl](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/ReaControl.py)
emploie Ethernet II `0x885f`, reconnaît le préfixe MAC `00:a0:7e`, et sélectionne
le client ProControl lorsque l'annonce contient `MAINUNIT`. Le
[texte de capture de l'issue #12](https://github.com/phunkyg/ReaControl24/files/4520019/Ptewlscapture.txt)
montre également `88 5f` aux octets 12–13 de trames attribuées à une ProControl.
L'EtherType et l'OUI ne distinguent pas à eux seuls tous les appareils Digidesign.

`inspect_pcap.py` traite seulement Ethernet/VLAN et conserve le payload brut.
L'outil séparé `audit_diginet.py` applique explicitement le schéma candidat
ci-dessous, en conservant les champs comme hypothèses et les preuves par trame.

## Structure candidate issue de ReaControl24

Offsets décimaux depuis le début d'une trame Ethernet **sans VLAN**, sans
préambule Ethernet. Champ entier multi-octets en big-endian dans ce code.

| Offset | Octets | Nom du code tiers / interprétation candidate |
|---:|---:|---|
| 0 | 6 | MAC destination |
| 6 | 6 | MAC source |
| 12 | 2 | EtherType `0x885f` |
| 14 | 2 | `numbytes` : code émetteur = 16 + taille des commandes |
| 16 | 2 | `unknown1` / `parity` tiers ; somme du corps sur nos 191 trames passives, checksum additif candidat |
| 18 | 4 | `sendcounter` ; le code l'incrémente selon le nombre de commandes |
| 22 | 4 | `cmdcounter` ; utilisé pour les accusés de réception |
| 26 | 2 | `retry` |
| 28 | 1 | `c24cmd` ; constantes tierces `0xa0` ACK, `0xe2` online |
| 29 | 1 | `numcommands` |
| 30 | variable | Commandes / données / éventuel remplissage Ethernet |

Le commentaire « Length 14 » de `C24Header` dans le code tiers est incohérent :
ses champs totalisent **16 octets**. Les deux en-têtes totalisent donc 30 octets.
Un tag VLAN décale les offsets applicatifs de 4 octets supplémentaires par tag.
Il faut distinguer longueur logique, longueur capturée, longueur sur le lien et
remplissage ; les données après l'en-tête ne sont pas nécessairement toutes des
commandes. Une trame physique minimale peut contenir du padding.

Dans la structure d'annonce tierce `C24BcastData`, le payload contient 15 octets
non nommés, puis deux champs de 9 octets, version et nom de périphérique. Il
s'agit d'un schéma candidat à confronter aux annonces brutes de notre console.

## Connexion et entretien de session

Le code tiers attend une annonce, adresse la MAC détectée, envoie `online`
(`0xe2`), puis une initialisation d'afficheur. Il gère ensuite ACK, compteurs,
retries et keepalive. Ces choix donnent une **liste d'éléments à observer**,
complétée désormais par un journal ProControl tiers montrant les ACK et une
confirmation de fonctionnement dans les deux sens. L'utilisateur a demandé
le passage à l'essai actif ; voir [session-reference.md](session-reference.md).

L'initialisation partagée de `DeviceSession.init_device` conserve un payload
commençant par `f0 13 01`, alors que plusieurs sorties ProControl emploient
`f0 13 00`. Il serait prématuré de rejouer ce code tel quel. Relever les messages
dans chaque sens, l'ordre, les délais, la retransmission et le retour éventuel
de `Offline`. Le petit essai actif préparé omet l'initialisation d'horloge et
a établi la session avec online et keepalive seuls. Les événements PLAY sont
ensuite reçus et acquittés. Cela valide ce sous-ensemble pour les premiers
essais locaux, sans établir encore la récupération après toutes les déconnexions.

## Commandes et sorties : pistes ProControl

Dans les extraits ProControl, certaines séquences ressemblent au MIDI
(`90`, `b0`, `f0 … f7`), mais cela ne suffit pas à établir un transport MIDI
standard ou RTP-MIDI. Plusieurs commandes peuvent être concaténées dans une trame.

| Fonction | Indice externe | Ce qui reste à vérifier ici |
|---|---|---|
| Fader | `_ReaFader` commun, échelle de 10 bits dans ReaCommon ; ProCfader l'utilise | Encodage, bornes, contact distinct du mouvement, motorisation et échos |
| Boutons / transport | `procontrolmap.py` et retour d'usage de l'issue #5 | Pression, relâchement, modes et modifiers |
| Afficheurs | `f0 13 00 40` ; adresses `00..07` et `20..27` dans l'issue #12 | Rangée, longueur, charset, effacement, rafraîchissement |
| LEDs / anneaux / compteur | Classes dédiées qui remplacent le troisième octet par `00` | Adresses exactes, états, clignotement et modes |
| Vumètres | `ProCvumeter` adapte la famille ; modèle de commande `f0 13 00 10 canal a b f7` | Correspondance avec chaque grand vumètre, bits/segments, crêtes et cadence |

Références : [classes ProControl](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/procontrolosc.py),
[classes communes](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/ReaCommon.py),
[afficheurs observés par un utilisateur](https://github.com/phunkyg/ReaControl24/issues/12).

Pour les vumètres, `ReaVumeter` contient lui-même une réserve sur l'adressage
des bus ProControl. Le fait que les diagnostics éclairent tous les segments ne
prouve ni le nombre de niveaux adressables ni leur correspondance aux octets.
Prévoir, avec un hôte compatible ou une session minimale validée, silence puis
niveaux fixes distincts sur **un seul canal à la fois**, noter le routage et
comparer les retours hôte → console. Mesurer aussi extinction, crête et cadence.

## Registre local à remplir

| Proposition | Preuve PCAP / trame / sens | État |
|---|---|---|
| MAC de cette ProControl | Capture `20260913T152134Z-startup-1wddjZ`, trame 12, console → broadcast | `00:a0:7e:a0:ad:9c` observée |
| EtherType de cette ProControl | Même fichier, 13 trames dont la 12 | `0x885f` observé |
| Identification / version de l'annonce | Même fichier, trames 12, 17, 20, 22, 26, 36, 46 | `MAINUNIT` / `1.37` annoncés |
| Ouverture et entretien de session | online-probe-y9kcm0yu, trames 2–4 et maintiens 6–41 ; rapport actif | Deux minutes acquittées, puis second essai de trois minutes |
| PLAY | play-online-DX00Sr, trames 12 et 14, console → laptop | 90 10 5c / 90 10 1c, premier geste contrôlé |
| STOP | stop-ardour-JhZItB, trames 58 et 60, console → laptop | 90 0f 5c / 90 0f 1c ; arrêt d'Ardour confirmé |
| Fader 1 et contact | online-probe-s89y2fd9, mouvements trames 504–801 ; contact 501/795 et 797/803 | Course 0–1023 décodée ; motorisation/gain non vérifiés |
| Trackpad X/Y | trackpad-horizontal-only-HPVbyL et trackpad-vertical-only-QHmmiK ; puis trackpad-x11-live-vK4Upf | Quatre directions et pointeur Linux confirmés ; voir keyboard-mouse.md |
| Commandes des grands vumètres | Un canal / niveau par expérience | Non vérifié |

## Mise à jour : mapping étendu validé le 13/09 à partir de 18:34 UTC

Cette section actualise les limites historiques ci-dessus. Les afficheurs des
tranches, le compteur et le jog sont désormais confirmés par l'utilisateur.
ALPHA et le pavé produisent des événements clavier X11 réels, et les deux clics
arrivent dans une fenêtre GTK. Voir [control-map.md](control-map.md),
[keyboard-mouse.md](keyboard-mouse.md) et [displays.md](displays.md) pour les
sources, captures, SHA-256, octets et trames.

La zone bouton 0x17 est CHANNEL MATRIX, 0x15 DSP et 0x16 monitor. Le parcours
historique de la table tiers les classait abusivement comme des tranches ;
notre adaptateur corrige ce point. Le jog `b0 5c valeur` utilise un delta
`valeur - 64`, envoyé à `/jog` ; son action sur Ardour est maintenant confirmée.
La souris utilise en plus H & 0x20 pour gauche, H & 0x10 pour droite, relâchés
à zéro. Les premiers essais isolés et les octets bruts sont préservés.

La capture de démarrage du mapping étendu contient 509 trames, zéro perte,
418/418 checksums candidats concordants ; 80 sorties feedback et 21 maintiens
acquittés ; cadence de maintien maximale 10,048248 s, aucune annonce e0 après
l'ouverture. Les quatre e0 présents précèdent le lancement du nouveau démon.
Les événements fader, jog et clics postérieurs à la clôture sont documentés
comme journal du démon, pas comme trames présentes dans ce PCAP.
