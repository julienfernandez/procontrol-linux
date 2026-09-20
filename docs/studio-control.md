# Centre de contrôle du studio USB

Le panneau **Studio USB**, sur `http://127.0.0.1:8765`, supervise la chaîne
MPC HAKAI → USB → PipeWire → Ardour → Behringer. Il est indépendant de la
boucle temps réel de la console. Fermer l’onglet ne coupe pas la supervision :
le service `settings` reste en arrière-plan avec la Gateway.

## Utilisation

- **Vérifier maintenant** demande un nouveau diagnostic en lecture.
- **Remettre en service** prépare l’interface USB, le pont MIDI et les deux
  maintiens audio. Si la session studio configurée est réellement active dans
  Ardour, ses 16 entrées et la sortie Master Behringer sont raccordées.
- **Rétablir le routage studio** réapplique uniquement ces connexions, dans
  cette même session. Le bouton est indisponible pour un autre projet.
- **Reprendre automatiquement** conserve le choix sur ce PC. Une MPC joignable
  dont le gadget, le filtre audio, le pont MIDI ou les maintiens sont absents
  déclenche une remise en service. Une MPC injoignable reste en observation.
- **Journaux et diagnostic** affiche les derniers événements, la sortie de la
  dernière opération et les logs de maintien. Le bouton de téléchargement
  exporte un JSON contenant aussi le diagnostic détaillé.

Après un reboot réel de la MPC, sélectionner **Preferences → Audio Device →
UAC2_Gadget 0** sur son écran reste nécessaire. Le panneau le signale. Il ne
relance pas l’application MPC, ne ferme pas Ardour et ne force ni lecture,
ni enregistrement, ni IN/DISK/MUTE. Pour entendre une entrée, vérifier IN et
MUTE sur la piste. Les modes d’écoute connus de la Gateway sont affichés ; un
mode inconnu reste indiqué comme tel.

## Ce que signifient les états

Chaque observation vérifie le réseau, le contrôleur USB et son état configured,
la visibilité du gadget dans le processus MPC, les deux PCM ouverts **par le
PID de l’application MPC**, le pont ALSA MIDI, les vrais liens PipeWire (16
canaux actifs par maintien), les 16 entrées Ardour et Master L/R vers la
Behringer. Les cartes ALSA sont retrouvées par leur identifiant, pas par un
numéro card2 supposé permanent.

Un PCM ouvert par un programme de test ne signifie pas que la MPC a sélectionné
l’interface. Un PID de maintien vivant ne signifie pas que ses canaux sont
raccordés. Les deux cas ont leurs tests de régression.

La période et le tampon affichés sont lus dans `hw_params`, pas déduits de la
consigne HAKAI. Les changements de `trigger_time` sont comptés depuis le début
de la supervision pour le même boot/PID MPC. Ce sont des reprises **observées**,
pas un compteur exhaustif d’XRUN : une sélection manuelle peut les provoquer,
et plusieurs reprises entre deux observations peuvent échapper au compteur.
Elles ne déclenchent pas une reconfiguration automatique.

Les diagnostics ont une date ; après 30 s sans nouvelle mesure, les voyants
passent en état ancien. Les connexions vérifiées ne prouvent pas une écoute sans
parasite ou une stabilité longue durée.

## Architecture et garde-fous

- `tools/studio_control.py` : worker du service web, diagnostic toutes les
  dix secondes après la mesure précédente, jobs sérialisés, journal borné.
- `integrations/mpc_usb/` : préparation et routage USB désormais versionnés
  dans le dépôt Gateway. Le lanceur historique local pointe vers ces sources.
- `GET /api/studio`, `GET /api/studio/logs`,
  `POST /api/studio/action` : API locale avec les mêmes contrôles Host/Origin
  que les réglages. Actions autorisées : check, recover, route, automatic.
  Aucun chemin, hôte ou texte de commande n’est accepté via HTTP.
- Un verrou de supervision empêche deux workers concurrents. Le verrou
  `studio.lock` existant sérialise aussi les appels du lanceur Ardour.
- Nouvelle tentative au plus tôt 60 s après une opération réussie ; après
  échec, 120 puis 240 puis 300 s. Les opérations ont un délai maximal de 150 s
  par commande. Un arrêt du service termine le groupe de processus local en
  cours et publie un résultat d’échec, plutôt que de laisser un travail orphelin.
- La session et la fraîcheur de l’état Gateway sont revérifiées après prepare
  et avant route. Aucun routage imposé à un autre projet.
- Les données de diagnostic/SSH, projets, captures, dépendances binaires et
  réglages personnels ne sont pas publiés sur GitHub.

## Installation locale

Créer `studio.json` à la racine (ignoré par Git) à partir de
[`studio.example.json`](../studio.example.json). `data_root` désigne le dossier
local contenant `run/known_hosts` et les dépendances déjà installées :

- `tools/vendor/alsa-utils-armhf/usr/bin/aconnect` ;
- `tools/vendor/coreutils-armhf/bin/dd` ;
- `tools/vendor/pipewire-jack/usr/lib/x86_64-linux-gnu/pipewire-0.3/jack/libjack.so.0`.

Ces binaires externes ne sont pas inclus dans le dépôt. SSH doit être configuré
localement avec une clé et une clé d’hôte validée. Aucun mot de passe n’est
stocké dans la configuration. La session est un **dossier** Ardour ; le lanceur
utilise son fichier `.ardour` de même nom.

Les commandes manuelles utilisent ces variables :

```sh
export MPC_STUDIO_ROOT=/chemin/vers/mpc-one-usb-audio
export MPC_HOST=adresse-de-la-mpc
export MPC_STUDIO_SESSION=/chemin/vers/session/session.ardour
python3 integrations/mpc_usb/studio.py prepare
```

Puis `./settings stop` et `./settings start` chargent la supervision. Elle ne
change pas les réglages de la console. Le raccourci normal ProControl démarre
ce service. La reprise nécessite que la Gateway soit lancée : aucune modification
du firmware ou installation de service au démarrage de la MPC n’est faite.

Le contournement du filtre Audio Device reste spécifique au binaire MPC 3.9.1
identifié par SHA-256 dans `mpc_audio_visibility.py`. Il modifie un octet en RAM
après contrôle des instructions et relecture ; une autre version est refusée.
Le tampon HAKAI est préparé uniquement pour l’empreinte de bibliothèque connue.

## Validation du 20 septembre 2026

Le reboot réel signalé par l’utilisateur avait effacé le gadget configfs et le
script `/tmp`. Remise en service réussie, puis sélection utilisateur observée :
les deux PCM du processus MPC sont RUNNING, S16_LE, 16 canaux, 44,1 kHz,
période 128, tampon **768 réellement appliqué**. Les deux maintiens ont 16/16
liens ; Master possède deux connexions Behringer et aucune autre destination.

Le parcours navigateur réel a vérifié refresh, remise en service, journaux,
téléchargement et activation de la reprise automatique. Deux préparations
idempotentes ont conservé les temps de démarrage des PCM et le processus Ardour.
Le panneau a été vérifié en 1440×1100 et 390×844, sans erreur JavaScript ni
débordement horizontal. Les cas de panne sont testés par simulation ; aucun
nouveau reboot matériel n’a été imposé au projet ouvert pour tester l’automate.
