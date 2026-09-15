# Ouverture de session ProControl : références et essai minimal

La demande utilisateur du 13 septembre 2026 autorise le passage au démon qui
établit une session Online. Les captures passives ont identifié la MAC cible,
MAINUNIT / 1.37, le transport 0x885f et la structure candidate de l'en-tête.
Ardour est installé (`/usr/bin/ardour`) ; son raccordement OSC vient ensuite.

## Succès externe vérifié

Le [dernier commentaire de l'issue #9](https://github.com/phunkyg/ReaControl24/issues/9#issuecomment-617918597)
confirme les échanges dans les deux sens après une correction de pipe, le
22 avril 2020. Le signalement initial n'est donc pas le bilan final du projet.
Le [journal de l'issue #8](https://github.com/phunkyg/ReaControl24/issues/8#issuecomment-575794718)
contient une séquence réseau lisible pour MAINUNIT version 1.37. C'est un journal
tiers, avec certaines lignes résumées, et non notre PCAP.

Références de code figées :
[ReaControl.py, DEV_OtherDevices b6268cbb](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/ReaControl.py),
[control24d.py, Release 2a963e9c](https://github.com/phunkyg/ReaControl24/blob/2a963e9c0c8beb52f7a1e39164c4e93c3580ec7d/control24d.py).
Les deux emploient la même ouverture et les mêmes principes de maintien.

## Séquence observée dans le journal tiers

| Étape | Sens | Champs / réponse |
|---|---|---|
| Annonce | Console → broadcast | e0, MAINUNIT, 1.37 |
| Online | Hôte → console | longueur 16, compteur envoyé 1, commande e2, 0 commande de corps |
| Initialisation horloge | Hôte → console | compteur 2, corps de 15 octets commençant f0 13 01 30 19 |
| ACK | Console → hôte | a0, compteur acquitté 1 puis 2 |
| Annonce de session | Console → broadcast | e1, MAC hôte dans le début du corps |
| Maintien | Hôte → console | corps 00, longueur 17, compteur suivant |
| ACK du maintien | Console → hôte | a0, compteur acquitté correspondant |

Le maintien est émis après 10 secondes sans envoi dans le code tiers.
L'ACK hôte reprend le compteur envoyé de la trame de données console, avec
compteur propre à zéro. Les annonces broadcast ne sont pas acquittées.

## Essai local

Par défaut, `tools/session_probe.py` réalise uniquement online e2, ACK a0 et keepalive 00.
Il attend une annonce e0 MAINUNIT de la MAC explicitement ciblée ; une annonce
e1 préalable fait interrompre l'essai afin de ne pas reprendre une session existante.
Le paquet d'initialisation d'horloge est omis dans ce premier essai : nous testons
si l'ouverture et le maintien seuls suffisent. Ce sous-ensemble est une hypothèse
expérimentale, pas la reproduction intégrale du daemon tiers.

Après l'essai de dix minutes, le maintien local a été rendu périodique toutes
les dix secondes, indépendamment des ACK : la cadence initiale pouvait être
repoussée indéfiniment par les gestes. Cette correction est testée hors ligne,
mais reste à valider sur la console ; voir le rapport Online avant un nouvel essai.

Sans `--send`, il affiche les paramètres et la trame online sans ouvrir de socket.
Avec `--send`, il ouvre deux sockets Ethernet, abandonne les droits root, écrit
un PCAP et un journal JSON, puis se termine après la durée active et une queue
d'écoute passive. La réception enregistre les sorties de la seconde socket via
PACKET_OUTGOING ; les tentatives d'envoi et les sorties effectivement observées
par le noyau restent comptées séparément. Les horodatages sont ceux de la
réception en espace utilisateur, pas des horodatages matériels.

```bash
python3 tools/session_probe.py --interface enp0s25 --mac 00:a0:7e:a0:ad:9c
# Essai actif demandé ; fenêtre système possible pour les sockets brutes.
pkexec /usr/bin/python3 "$PWD/tools/session_probe.py" --interface enp0s25 --mac 00:a0:7e:a0:ad:9c --duration 120 --observe-after 20 --send
```

Les droits dumpcap permettent la capture, mais ne donnent pas au processus Python
le droit initial d'ouvrir une socket brute. Le lancement ci-dessus ne modifie pas
les capacités de Python et ne change pas AppArmor.

Les premiers essais ont réussi : voir [Online et transport Ardour](online-2026-09-13.md).
L'option `--osc-port 3819` ajoute le pont de transport local ; le port de réponse
est en Auto. Le pont comprend maintenant aussi les quatre boutons de navigation
documentés dans le guide Ardour. L'option distincte `--clock-test`, demandée par
l'utilisateur, teste le compteur avec trois commandes bornées : voir
[displays.md](displays.md). Les essais peuvent durer jusqu'à 900 secondes, avec
un exemple de dix minutes dans [le guide Ardour](ardour.md).

Critères à relever : ACK de l'ouverture, annonces e1, ACK successifs de maintien,
événements unicast de boutons, absence de retries croissants, confirmation visuelle
de la disparition de Offline. Deux minutes réussies constituent un premier essai
de maintien ; une validation de longue durée et la reconnexion restent nécessaires.
