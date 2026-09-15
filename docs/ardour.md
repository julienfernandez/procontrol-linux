# Ardour sur ce laptop

Installation vérifiée le 13 septembre 2026 : paquet `ardour 1:8.4.0+ds1-2ubuntu8`,
commande `/usr/bin/ardour`, module `/usr/lib/ardour8/surfaces/libardour_osc.so`.
L'utilisateur a activé OSC dans l'application. L'écoute UDP 3819 et les retours
OSC sont vérifiés ; la configuration enregistrée sur disque peut être plus ancienne
que l'état de l'application ouverte. Le port de réponse reste en Auto, conformément
au choix utilisateur. Le pont configure son retour de section principale via OSC.

Le [manuel officiel](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-control/)
définit `/transport_play` et `/transport_stop`. Le futur adaptateur enverra ces
commandes après identification locale des événements ProControl. Il devra
gérer séparément le [feedback](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/feedback-in-osc/)
pour les LEDs, puis les faders et vumètres.

Activer OSC dans les préférences de surfaces de contrôle, puis vérifier le port
affiché dans les [réglages du protocole](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-setup-dialog/).
Utiliser un socket UDP local avec port de retour connu ; ne pas recopier
`ProControl.ReaperOSC` dans Ardour, son format concerne Reaper.

Ordre de validation : session Ethernet maintenue ; PLAY/STOP reconnus dans une
capture contrôlée ; session Ardour de test ; contrôle du transport via OSC ;
retour de l'état du transport vers les LEDs. Les changements de gain et la
motorisation des faders seront des essais distincts.

PLAY et STOP pilotent désormais le transport : confirmation visuelle utilisateur
et retours OSC correspondants reçus. Voir [les mesures](online-2026-09-13.md).
Le [comparatif OSC/Mackie](mackie-vs-osc.md) motive le choix actuel, notamment
pour conserver des niveaux numériques destinés aux grands vumètres.

La navigation est maintenant traduite à partir de la table ProControl :

| Touche de référence | OSC Ardour | Appui / relâchement observables |
|---|---|---|
| Go To Start | `/goto_start` | `90 06 5c` / `90 06 1c` |
| Go To End | `/goto_end` | `90 07 5c` / `90 07 1c` |
| Rewind | `/rewind` | `90 0d 5c` / `90 0d 1c` |
| Forward | `/ffwd` | `90 0e 5c` / `90 0e 1c` |

Comme PLAY/STOP, seul l'appui envoie un float OSC 1.0. Ardour 8.4 déclare ces
quatre callbacks et filtre les relâchements dans `PATH_CALLBACK`. Rewind et
Forward demandent les vitesses de recherche d'Ardour ; STOP les arrête. Ils
ne signifient pas encore « jog pendant le maintien du bouton ». Le jog, les
flèches et les modes de navigation seront mappés séparément. Sources :
[manuel transport OSC](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-control/),
[callbacks Ardour 8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.h).

Contrôle du backend réel le 13 septembre : les quatre corps de boutons passés
par `ArdourTransport` déclenchent leurs messages OSC. Depuis une position non
nulle, les deux commandes de borne déplacent le curseur à zéro dans cette
session ; `/rewind` donne une vitesse -1 et `/ffwd` une vitesse +1. La distinction
entre des bornes de session différentes reste à tester avec des marqueurs
début/fin distincts. Les nouveaux gestes physiques n'ont pas encore été testés
de bout en bout avec cette version du pont.

Preuves dans `ardour-navigation-check-v2.json`. Le premier essai automatique
(`ardour-navigation-check.json`) avait des préconditions inadéquates pour tester
le retour arrière depuis zéro. La restauration finale a dû attendre le retour
de vitesse nulle avant `/locate` : envoyer Stop et Locate à la suite pouvait
laisser un décalage d'un buffer. Le suivi enregistré confirme ensuite le retour
exact à **1718272 samples**, vitesse **0**, position et état initiaux.

Commande de démon de test, après vérification qu'aucun autre essai n'est actif :

```bash
pkexec /usr/bin/python3 "$PWD/tools/session_probe.py" --interface enp0s25 --mac 00:a0:7e:a0:ad:9c --duration 600 --observe-after 30 --osc-port 3819 --quiet --send
```

Les émissions sont limitées à dix minutes dans cet exemple. Le mode `--quiet`
conserve le journal complet sur disque ; le démon utilise le compte utilisateur
après ouverture des sockets brutes. Les relâchements et retransmissions reconnus
n'engendrent pas de deuxième commande de transport.
