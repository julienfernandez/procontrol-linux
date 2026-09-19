# Compteur musical et synchronisation MPC

20 septembre 2026.

## Compteur BARS / BEATS / TICKS

Le champ OSC `/position/bbt` d'Ardour 9.8 contient trois nombres, par exemple
`123|04|1500`. Ardour utilise **1920 ticks par temps** (`libs/temporal/temporal/types.h`).
L'ancien formatage appliquait `:03d` aux ticks : cette option fixe une largeur
minimale, pas maximale. À partir de 1000 ticks, la chaîne passait donc de huit
à neuf chiffres, puis `[-8:]` supprimait le chiffre de gauche. Cela déplaçait
les mesures et les temps par rapport aux points du compteur.

Le nouveau rendu convertit les ticks vers une résolution d'affichage de
**960 ticks par temps** : `ticks_console = ticks_Ardour // 2`. Les huit cases
restent toujours **3 mesures + 2 temps + 3 ticks** ; les séparateurs restent
dans l'octet de points `0x14`, indépendants des chiffres à sept segments.

| Position Ardour | Compteur console |
|---|---|
| `123|04|0999` | `123.04.499` |
| `123|04|1000` | `123.04.500` |
| `123|04|1919` | `123.04.959` |
| `124|01|0000` | `124.01.000` |

Un champ qui dépasse ses cases affiche des tirets, sans tronquer un autre
champ : la mesure 1000 affiche `---.01.000`. Une valeur OSC vide ou mal formée
efface les chiffres et les points. Le timecode SMPTE conserve son encodage
et ses points `0x2a`. Changer COUNTER MODE ne change ni tempo ni transport.

Validation logicielle : cinq nouveaux tests, dont les 1920 positions d'un
temps, le passage 999→1000 ticks, les changements de mesure, les dépassements,
les valeurs vides et les allers-retours SMPTE/BBT. **204 tests passent**.
Le correctif est installé après arrêt propre puis relance de la passerelle et
du pointeur. Ardour reste ouvert. Le rendu physique attend le retour utilisateur.

## Essai MIDI Clock / MMC — conservé pour diagnostic

La ProControl pilote le transport Ardour par OSC. Ardour produit ensuite
l'horloge MIDI et les commandes de transport destinées à la MPC. Ainsi, PLAY
dans Ardour et PLAY sur la console empruntent le même chemin.

Dans Ardour 9.8 :

- Conserver le transport **Internal**.
- Dans **Preferences → Transport → Generate**, activer **Enable Mclk generator**
  et **Send MMC commands**.
- Dans les connexions MIDI, raccorder **MIDI Clock out** et **MMC out** au port
  de lecture **MPC One USB Audio 16ch MIDI 1**.
- Sauvegarder le projet. Les deux connexions externes sont enregistrées dans
  la section `MIDIPorts` du fichier de session ; les deux options d'émission
  sont enregistrées dans la configuration Ardour.

Sur la MPC, **Menu → Preferences → MIDI/Sync** :

- Dans **INPUT PORTS**, le port **USB MIDI Port 1** est présent. Sur MPC 3.9.1,
  cette liste montre Global/Control/Track, sans case Sync. La photo utilisateur
  le confirme ; le champ `sync` partagé dans le fichier de réglages ne démontre
  donc pas un filtrage de la réception. Les cases Sync des sorties concernent
  uniquement l’émission et restent désactivées ici.
- **Sync Receive : MIDI Clock** ; **Receive MMC : activé**.
- **Sync Send : Off**, pas de retour d'horloge vers Ardour.
- Dans les réglages du métronome, **Count-In : Off** pour éviter un départ retardé.

Le port USB 1 est réservé ici à la synchro ; le port 2 conserve le trajet du
clavier Roland. Le Master audio reste raccordé à la Behringer.

Le tempo vient d'Ardour (120 BPM dans la session au moment de la configuration).
Le MIDI Clock est le choix adapté au suivi musical du tempo ; le MTC exprime
une position en heures/minutes/secondes/images. Aucun câble ni sortie audio
LTC n'est nécessaire dans ce montage. Ardour émet aussi Song Position Pointer
et Continue lors d'une reprise hors origine ; le suivi de ces messages et de
MMC Locate doit être vérifié sur la MPC, notamment après un déplacement du curseur.
Cette liaison ne constitue pas une horloge audio commune à l'échantillon près.

Sources : [générateurs Ardour](https://manual.ardour.org/synchronization/timecode-generators-and-slaves/),
[réglages des ports MIDI MPC](https://support.akaipro.com/en/support/solutions/articles/69000804431-akai-pro-mpc-series-configuring-midi-ports-for-multi-midi-control),
[transport MMC MPC](https://support.akaipro.com/en/support/solutions/articles/69000868287-akai-pro-mpc%E3%82%B7%E3%83%AA%E3%83%BC%E3%82%BA%EF%BD%9Cmpc%E3%81%A8%E5%A4%96%E9%83%A8%E6%A9%9F%E5%99%A8%E3%81%AE%E6%8E%A5%E7%B6%9A),
[retard causé par Count-In](https://support.akaipro.com/en/support/solutions/articles/69000875260-mpc-standalone-why-does-my-mpc-play-one-bar-late-when-receiving-external-midi-clock-).

### Résultat du diagnostic MIDI

La réception USB a été mesurée **sur la MPC**, en s'abonnant au même port ALSA
`f_midi-0` que l'application MPC, sans débrancher celle-ci : **196 ticks en
4,06 secondes**, soit **120,07 BPM** à 24 ticks par noire. Start, Stop, Continue,
Song Position Pointer et MMC Play/Stop/Locate ont également été observés.
Cela prouve l'arrivée des messages ; cela ne prouve pas leur utilisation par
le séquenceur. L'utilisateur voit encore 128 BPM et ne constate pas de changement
du rythme. La synchronisation MIDI de bout en bout reste donc non résolue.

## Pont Ableton Link

Le code d'Ardour 9.8 installé ne possède pas de transport maître Ableton Link.
Le pont optionnel `native/ardour_link.cc` utilise la bibliothèque officielle
[Ableton Link](https://github.com/Ableton/link), au commit
`902aef95bf94af49746fdda5369b42cdcfa1e6d2` (GPL-2.0-or-later).
`jack_link` de rncbc a été étudié ; son fonctionnement reprend la maîtrise
de la timebase JACK. Ici, **Ardour conserve sa propre carte de tempo** : notre
client JACK lit uniquement le transport et la timebase, sans les remplacer.

Trajet actif : **ProControl → OSC → Ardour → JACK → Link → réseau local → MPC**.
Le pont utilise les fonctions Link prévues pour le thread audio : tempo, phase
musicale, début et fin de lecture. Il n'ouvre aucun port audio, ne modifie aucune
connexion de piste, et ne produit aucune trame du protocole ProControl.
Il fonctionne dans un processus séparé du contrôleur Ethernet.

### Installation et service

Prérequis Linux : compilateur C++17, Git, en-têtes et bibliothèque JACK,
service utilisateur systemd. Le SDK reste dans `work/`, les exécutables dans
`build/`, les états locaux dans `run/` ; aucun n'est versionné.

```sh
./link build
# Avec PipeWire, utiliser exactement la bibliothèque JACK employée par Ardour :
./link install --jack-library /chemin/vers/pipewire-0.3/jack
./link start
./link status
./link stop
```

Avec un serveur JACK natif, `./link install` suffit. `build --sdk CHEMIN`
accepte un checkout propre du SDK à la révision indiquée. Le remplacement du
binaire est atomique ; relancer le service après une reconstruction.
Le service `procontrol-link.service` redémarre après une panne. `start` est
idempotent ; un verrou interdit un second pont sur le même fichier d'état.
L'installation ne l'active pas automatiquement à l'ouverture de session.

### Réglages pour l'essai

Dans Ardour : sélectionner **JACK comme source de synchronisation**, activer
la synchronisation externe, et laisser **JACK Time Master** activé pour publier
la carte de tempo d'Ardour. Le générateur MIDI Clock et l'envoi MMC doivent être
désactivés pour cet essai ; les deux connexions vers la synchro USB MPC sont
retirées. Le port du clavier et les connexions audio restent disponibles.
Ces réglages ont été sauvegardés dans le projet après une fermeture normale
et un redémarrage d'Ardour. Le Master reste envoyé vers la Behringer.

Sur la MPC :

1. **Menu → Preferences → MIDI/Sync → Sync Receive : Ableton Link**.
2. Activer **Start/Stop Sync** si cette option est présente.
3. Désactiver **Receive MMC** ; laisser Sync Send désactivé.
4. Garder la MPC et le PC sur le même réseau local. Ici, le câble USB reste
   chargé de l'audio ; Link passe par le réseau local.

La [procédure Akai](https://support.akaipro.com/en/support/solutions/articles/69000814493-akai-pro-mpc-series-force-ableton-link-setup-and-tutorial)
montre aussi le choix Link dans le champ Sync du menu principal. Une barre de
progression Link apparaît lorsque la liaison est établie.

`./link status` doit afficher `running: true`, `enabled: true`, un `tempo`
correspondant à Ardour et **au moins un `peers`** quand la MPC participe.
Un processus actif avec `peers: 0` ne prouve aucune connexion à la MPC.
`enabled: false` indique que le pont attend une timebase JACK valide.

### Portée et vérification

Ce premier mode transmet **le tempo et les gestes de transport d'Ardour vers
Link**. Régler le tempo dans Ardour ; une modification du tempo Link depuis un
autre appareil est ramenée à celui d'Ardour. Les boutons de la MPC ne pilotent
pas Ardour en retour. Rejoindre le réseau Link ne déclenche pas, à lui seul,
la lecture : faire STOP puis PLAY dans Ardour une fois les participants présents.

Link partage le tempo et la phase ; il ne transmet pas la position absolue
d'un morceau, ni la sélection d'une séquence MPC. Un déplacement du curseur
recale la phase musicale, pas un numéro de mesure dans l'arrangement MPC.
Il ne constitue pas une horloge audio commune à l'échantillon près.

Le client recale la phase à PLAY, après un déplacement ou une boucle, un
changement de mesure ou l'arrivée d'un participant. Il corrige un écart de phase
supérieur à 10 ms, avec une cadence limitée (phase de démarrage distincte).
`phase_error_ms` mesure l'écart avant une éventuelle correction ; les courts
transitoires de départ ne sont pas une mesure de dérive en régime établi.

Validation : compilation, réception réelle par **un second client Link local**,
transmission de 120 BPM, retour à 120 après une demande distante de 137 BPM,
PLAY/STOP et cycle du service. Les essais utilisent une session en 4/4 ; les
autres métriques, la précision audio, les changements continus de tempo et
l'endurance restent à valider. **La MPC est maintenant un participant Link confirmé**. Une capture réseau
de 12 secondes contient 52 annonces de la MPC : toutes indiquent 120 BPM,
et leur état passe STOP → PLAY → STOP pendant un essai OSC depuis Ardour.
Les réglages MPC indiquent Link et Start/Stop Sync activés. Le suivi audible
et le rendu de l’écran attendent encore la confirmation utilisateur.
Le [rapport de validation](counter-link-validation-2026-09-20.json) distingue
les états du protocole, les tests logiciels et ces vérifications physiques.
