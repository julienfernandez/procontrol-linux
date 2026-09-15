# Capturer la ProControl sous Linux

**Mise à jour du 13/09/2026 :** les captures dumpcap depuis Codex sont testées,
sans sudo, avec arrêt natif par durée et zéro perte signalée. Wireshark est
installé et moi appartient au groupe wireshark. L'app déjà ouverte conserve ses
anciens groupes : les exemples emploient `sg` pour activer cette appartenance.
Voir [workspace-linux.md](workspace-linux.md). Le signal d'ouverture à attendre
est `File: -`. AppArmor empêche le profil `chatgpt` d'arrêter tcpdump par signal ;
le script refuse cette combinaison et aucune politique AppArmor n'a été changée.

## 1. Liaison et outils

Préférer `ProControl — câble Ethernet — enp0s25`, avec Internet sur le Wi-Fi.
Un switch acceptant le 10 Mbit/s convient aussi pour observer les annonces et
les communications adressées au laptop. Ne pas forcer vitesse/duplex tant que
la porteuse est présente. Si elle est absente, vérifier câble, alimentation,
compatibilité 10BASE-T et auto-MDI-X ; un matériel ancien peut nécessiter un
câble croisé en liaison directe.

```bash
ip -brief link
ip -brief address
ip -statistics link show dev enp0s25
cat /sys/class/net/enp0s25/carrier
cat /sys/class/net/enp0s25/speed
cat /sys/class/net/enp0s25/duplex
sg wireshark -c 'dumpcap --version'
```

L'absence d'adresse IP n'empêche pas la capture Ethernet. Un ping n'est pas le
test de référence pour ce protocole. Ne pas sélectionner `any` : sous Linux,
cela produit généralement du « Linux cooked capture » plutôt que les en-têtes
Ethernet originaux. Le lecteur fourni refuse ces linktypes.

Pour l'observation de démarrage, ne lancer aucun bridge ni ancien daemon.
Wireshark/dumpcap et Python sont déjà installés sur ce laptop. TShark est
facultatif ; aucune installation supplémentaire n'est nécessaire au kit.

## 2. Première capture sans filtre

Dans le dossier `procontrol-linux`, console éteinte :

```bash
sg wireshark -c 'PROCONTROL_CAPTURE_BACKEND=dumpcap bash tools/capture.sh enp0s25 startup 90'
```

**Attendre « File: - »**, puis allumer la console sans toucher aux commandes.
Noter l'heure de l'allumage,
de « Welcome to ProControl » et de `Offline` dans `notes.md`. Le script s'arrête
après 90 secondes ; Ctrl+C permet aussi de l'arrêter. Une extinction volontaire
et un nouvel essai constituent une nouvelle expérience, pas une suite du premier
fichier. Si le délai est trop court, refaire une capture de 180 secondes.

Commande brute équivalente pour une capture manuelle, depuis ce dossier :

```bash
# Choisir un nom neuf : une redirection > écrase un fichier existant.
sg wireshark -c 'dumpcap -q -P -i enp0s25 -s 0 -B 4 -a duration:90 -w -' > captures/startup-manuel.pcap
```

`-s 0` conserve les paquets avec la limite maximale par défaut ; `-P` choisit
le PCAP classique et `-w -` l'écrit sur stdout, ouvert par le shell utilisateur.
Le script ajoute noms uniques, contexte, journal des statistiques et SHA-256.
Référence : [manuel dumpcap](https://www.wireshark.org/docs/man-pages/dumpcap.html),
également disponible localement via `man dumpcap`.

Ne pas filtrer par IP, UDP, OUI ou EtherType lors de cette première observation.
Le préfixe MAC `00:a0:7e` et `0x885f` sont des indices, pas des identifiants uniques.

## 3. Une manipulation par fichier

Après le démarrage, garder les conditions de connexion et l'état de la console
identiques. Temps ci-dessous : approximatifs, depuis « File: - » ; noter
les temps réellement observés. Séparer pression et relâchement dans les notes.
Dans la session actuelle, entourer chaque commande du tableau avec
`sg wireshark -c 'COMMANDE'`. Pour une manipulation coordonnée par le chat,
préférer 60 à 120 secondes et confirmer que le geste a eu lieu avant l'heure
de fin annoncée. Une réponse au chat tardive n'horodate pas le geste physique.

| Expérience | Commande | Scénario sur 30 s |
|---|---|---|
| Témoin | `bash tools/capture.sh enp0s25 idle 30` | Ne rien toucher |
| PLAY | `bash tools/capture.sh enp0s25 play 30` | 10 s repos ; presser PLAY 1 s ; relâcher ; repos |
| STOP | `bash tools/capture.sh enp0s25 stop 30` | Même scénario pour STOP |
| Contact | `bash tools/capture.sh enp0s25 fader1-touch 30` | À 10 s, toucher le fader 1 pendant 2 s sans le bouger |
| Fader 1 montée | `bash tools/capture.sh enp0s25 fader1-up 30` | Le placer en bas avant capture ; à 10 s, monter doucement jusqu'en haut en 5 s, puis relâcher |
| Fader 1 descente | `bash tools/capture.sh enp0s25 fader1-down 30` | Même chose, haut vers bas |

Répéter un même essai trois fois avant d'affirmer une correspondance. La course
physique 0–100 % ne signifie ni 0–100 % de gain audio, ni une échelle en dB connue.
Ne pas mélanger commandes ordinaires et diagnostics internes dans une expérience.

**Aucun changement de trame pendant PLAY ne prouve pas une panne.** La console
peut n'émettre les événements qu'après une ouverture de session. Une écoute
passive n'envoie ni ouverture de session ni ACK et ne supprimera donc pas `Offline`.

## 4. Première lecture

```bash
python3 tools/inspect_pcap.py captures/DOSSIER-EXPERIENCE/traffic.pcap --show 20 --hex-bytes 192
tcpdump -nn -e -tttt -XX -r captures/DOSSIER-EXPERIENCE/traffic.pcap
```

Vérifier d'abord les pertes dans `dumpcap.log` (ou `tcpdump.log`), puis les MAC, EtherTypes,
longueurs, chaînes ASCII, périodicités et sens des échanges. Comparer `idle` et
`play` à durée comparable ; la différence de deux paquets isolés peut simplement
être un compteur ou un timestamp. Le lecteur résume tout le fichier même si
seules les premières trames sont affichées.

Filtres **d'affichage Wireshark**, après identification :

```text
eth.type == 0x885f
eth.addr == aa:bb:cc:dd:ee:ff
```

Remplacer la MAC d'exemple par celle observée, corroborée par le câble dédié,
le comportement à l'allumage ou l'identification matérielle. Le filtre MAC du
lecteur est hors ligne, dans les deux sens :

```bash
python3 tools/inspect_pcap.py captures/DOSSIER-EXPERIENCE/traffic.pcap --mac aa:bb:cc:dd:ee:ff
```

Après clôture de la capture, confronter le schéma candidat aux octets :

```bash
python3 tools/audit_diginet.py captures/DOSSIER-EXPERIENCE/traffic.pcap --mac 00:a0:7e:a0:ad:9c --json captures/DOSSIER-EXPERIENCE/diginet-audit.json
```

Le JSON conserve SHA-256, numéros de trame, horodatages et champs candidats.
Le nom de sortie doit être neuf. Une correspondance arithmétique n'établit pas
à elle seule que le matériel vérifie un checksum, ni la fonction d'une commande.

Pour un PCAPNG externe : `editcap -F pcap entree.pcapng sortie.pcap` si editcap
est installé. Pour plusieurs interfaces/linktypes, les séparer dans Wireshark
avant conversion. Garder l'original intact.

## 5. Si la session hôte manque

Si seules des annonces se répètent, les confronter aux indices de
[protocol.md](protocol.md). Une capture avec un Pro Tools ancien compatible ou
un hôte compatible déjà disponible peut établir la vraie séquence de connexion.
Commencer avant l'activation du périphérique côté hôte et inclure initialisation,
repos et reconnexion dans des essais distincts.

**Un troisième ordinateur sur un switch ordinaire ne voit pas nécessairement
les échanges unicast ProControl ↔ hôte.** Le mode promiscuous du laptop ne suffit
pas : capturer sur l'hôte, utiliser un TAP approprié ou un port miroir/SPAN dans
les deux sens. Un hub Ethernet réellement partagé est différent d'un switch.
Ne pas ajouter de bridge logiciel à ce stade ; il modifierait le montage étudié.

Le jalon « hors de Offline » devra être vérifié par affichage physique ET par
une session stable dans la capture, puis par les événements de commandes. Une
simple disparition temporaire du texte ne suffit pas.
