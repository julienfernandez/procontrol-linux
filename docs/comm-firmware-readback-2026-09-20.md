# Lecture complète des segments du firmware de communication

Le 20 septembre 2026, de **21:10:24 à 21:15:33 UTC**, deux acquisitions
Ethernet ont lu les **63 768 octets** des quatre segments de l'image `comm`
1.37 sur la ProControl originale `00:a0:7e:a0:ad:9c`. Les deux acquisitions
concordent exactement entre elles et avec la ressource constructeur `CODE 26`
extraite de `Procontrol.dll.rsr`. Durée totale : **308,377 secondes**.

La reconstruction indépendante des octets depuis les **504 PCAP clôturés**
concorde également avec chacun des blocs, les huit fichiers de segments et
l'image officielle. Le [rapport de preuves](comm-firmware-readback-2026-09-20.json)
conserve les empreintes de chaque bloc/capture/résultat, les compteurs et les
sources des outils. Cette étape prolonge les
[premières lectures de 264 octets](firmware-network-validation-2026-09-20.md).

## Périmètre réel de la sauvegarde

| Adresses inclusives | Octets | SHA-256 identique pour les deux lectures et le constructeur |
|---|---:|---|
| `0x20000–0x20007` | 8 | `230e4cc0835ad1fbd6cac5b383d422b9f270ca2000d5072a428b9b035f235b03` |
| `0x20064–0x2007f` | 28 | `64e9a8906127c7ba897b21e6e2d87336c8957576d3d6ed13070a0043f8209074` |
| `0x20100–0x2010f` | 16 | `ab98bf58a7b2442d97c4c9c61d414a231ee743687c840983d9aa7ea0d2e07bf2` |
| `0x20400–0x2fce3` | 63 716 | `e2945b200be72745afb10a3bc68300b4dc3b5adba90b3a8157cec37f051e1af8` |

Le qualificatif **complète** porte sur la couverture des adresses présentes
dans cette image de mise à jour `comm`. Les trous entre ces segments ne sont
ni lus ni remplis artificiellement. La ROM de démarrage, la RAM, l'EEPROM,
la calibration propre à cette unité et le programme réellement installé dans
le processeur des faders ne sont pas sauvegardés par cette expérience. La
restauration matérielle n'a pas été essayée.

## Passage aux lectures par lots

La première méthode `A<adresse>m` lit un octet par requête. Pour acquérir
l'image entière en quelques minutes, `firmware_probe.py` accepte désormais
des lots de **1 à 16 octets**, toujours dans un seul des segments connus.
Le mode par défaut conserve la méthode unitaire ; `--batch-size 16` utilise
`A` suivi de huit chiffres hexadécimaux, puis autant de `M` majuscules que
d'octets à lire. Le handler `M` à `0x2252e` lit puis incrémente le pointeur.

Avant chaque lot, l'adresse absolue est redonnée. Le lot final est raccourci
à la borne du segment : l'incrément après le dernier octet ne provoque pas
une lecture de l'adresse suivante. Aucune retransmission automatique de
requête n'a été ajoutée. Les réponses doivent couvrir toutes les adresses
du lot, avec ACK, avant de passer au suivant. Les doublons sont reconnus
par leur séquence ; les données reçues sont assemblées par adresse.

Deux pilotes ont précédé l'acquisition complète :

| Pilote local | Lecture | Trames | Résultat |
|---|---|---:|---|
| `batch-vectors` | 8 octets à `0x20000`, lot de 8 | 17 | Identique à la lecture unitaire et au constructeur |
| `batch-dispatcher` | 256 octets à `0x2a3d0`, lots de 16 | 275 | Identique à la lecture unitaire et au constructeur |

Leur dossier est `work/firmware-research-20260920/`. SHA des PCAP :
`82d3b8bc09511181414f931413c42f2001f7ccd2c43c389fb21acac4567c2945`
et `91a23227b8d59364c5d64545e657d03d13da574780c8b44a9777729e242224a3`.
Les deux pilotes ont zéro perte socket et ont été reconstruits hors ligne.

La console regroupe plusieurs réponses diagnostic dans certaines trames.
Le décodeur reconnaît donc les tailles et structures de réponse, y compris
plusieurs enveloppes concaténées. Il ne découpe pas aveuglément sur `f7` :
cette valeur peut être le caractère brut d'un octet mémoire. La concordance
entre l'adresse, la valeur hexadécimale et le caractère brut reste obligatoire.

## Acquisition longue et vérification indépendante

`archive_comm_firmware.py` vérifie les SHA des quatre fichiers constructeur
avant toute socket, puis détient le verrou Ethernet unique pour les deux
passes. Il appelle le lecteur par blocs de 256 octets maximum. Chaque bloc
commence par une interrogation `COMv1.37` et possède son PCAP, son résultat
JSON et son fichier mémoire. Les maintiens de session restent actifs pendant
la lecture. Les fichiers de segment ne sont assemblés qu'après lecture de
tous leurs blocs. Une erreur laisse un manifeste explicitement incomplet.

`audit_comm_archive.py` reconstruit ensuite les octets depuis les PCAP avec
un parseur distinct de celui utilisé pendant l'acquisition. Il vérifie :

- MAC émetteur/destinataire, EtherType, longueur et somme de chaque corps ;
- seules les requêtes de version, d'adresse et de lecture prévues apparaissent ;
- aucune adresse demandée hors bloc, aucun chevauchement de requêtes ;
- ACK des requêtes, version, adresses, nombre d'enveloppes DigiNet et octets ;
- doublons de réponse identiques et cohérence hexadécimal/caractère brut ;
- concordance PCAP → blocs → segments, puis comparaison au constructeur ;
- concordance des empreintes avec le manifeste enregistré lors de l'acquisition.

Les **127 536 octets lus au total** sont validés par ce second parcours.
L'audit dénombre 135 165 trames, 504 demandes/réponses de version,
7 974 lots mémoire et 136 014 enveloppes de réponse uniques.
Il y a **11 trames de réponse répétées**, conservées puis dédupliquées,
et zéro perte rapportée par les sockets. Une répétition ne démontre pas à
elle seule une perte physique ; sa cause n'a pas été attribuée.

Avant le lancement, Ardour indiquait une vitesse de transport nulle, aucun
apprentissage de mapping n'était actif. Le démon de passerelle a été arrêté
proprement, puis relancé dans un bloc `finally` après fermeture des sockets
d'acquisition. Ardour et le pointeur n'ont pas été arrêtés. Pendant la lecture,
le lecteur acquitte les messages mais ne relaie pas de gestes vers le DAW.

À la reprise : démon `621064`, console Online, Ardour répondant, 219 sorties
acquittées sur 219, zéro timeout et aucune erreur. Les données sont un
instantané de ce contrôle ; elles ne prouvent pas l'endurance ni la sensation
physique des faders. Aucun essai moteur ou changement de calibration ici.

## Reproduction

```bash
# Acquérir les fichiers officiels et les extraire, dans des dossiers nouveaux :
python3 tools/fetch_procontrol_personality.py work/personality-new
python3 tools/inspect_firmware.py work/personality-new/Procontrol.dll.rsr \
  --extract work/firmware-new

# Aperçu du plan, sans réseau : 252 blocs par passe, deux passes.
python3 tools/archive_comm_firmware.py

# Pendant une période où la surface peut être suspendue :
(
  ./procontrol stop || exit
  trap './procontrol start' EXIT
  python3 tools/archive_comm_firmware.py --send \
    --reference work/firmware-new --output work/comm-readback-new
)
./procontrol status

# Vérification indépendante sans réseau, une fois l'acquisition terminée :
python3 tools/audit_comm_archive.py work/comm-readback-new \
  --reference work/firmware-new --output work/comm-readback-new/audit.json
```

La MAC et l'interface peuvent être précisées sur l'outil d'acquisition ;
donner également `--host` et `--peer` à l'auditeur pour un autre couple hôte/console.
Un dossier de sortie existant est refusé. Une acquisition interrompue conserve
ses blocs et son statut d'échec ; elle n'est pas automatiquement fusionnée
avec une nouvelle lecture. En cas de différence binaire, les octets réellement
lus sont conservés et la comparaison échoue : ils ne sont pas remplacés par
les octets de référence.

## Conservation et tests

Les captures et les deux ensembles de segments sont conservés dans
`work/firmware-research-20260920/comm-full-double-1`. Une archive privée,
hors du dossier de travail, a été créée dans :

```text
~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/
  procontrol-comm-1.37-evidence.tar.gz
  FILE-MANIFEST.json
  SHA256SUMS
  README.md
```

Elle contient également les fichiers constructeur, les images extraites,
les sources utilisées et l'audit indépendant. **1 546 fichiers ont été relus
et vérifiés après compression**. Taille 6 119 682 octets ; SHA-256 :
`03c35d6a5ed914202a986871a21218f5d04aa94cf5a966878743d8453cbc52bd`.
Cette copie reste sur la même machine ; un autre support est nécessaire pour
une conservation indépendante du disque local. Les données constructeur et
les captures brutes ne sont pas publiées dans le Git public.

Sur la base `100b5bc`, **345 tests Python passent en 80,352 s**. Compilation
Python, inventaire des mappings en mode `--check` et contrôle d'espaces Git
réussis. Les nouveaux cas vérifient les lots incomplets, les bornes, les
réponses concaténées avec caractères bruts, les doublons tardifs, les deux
passes et le refus de valider des captures altérées ou incomplètes.

Un test de lots supposait initialement que l'ACK d'un doublon tardif précédait
toujours la requête suivante. Cette hypothèse d'ordonnancement était fausse :
le faux appareil garde désormais la requête déjà reçue pendant qu'il attend
l'ACK. Le lecteur réel n'a pas été modifié pour imposer ce faux ordre.

## Suite de la recherche

La lecture de l'image `comm` est maintenant établie sur toutes ses adresses
connues. Restent le chemin vers le processeur des faders, la cartographie du
démarrage et des mémoires persistantes, la sauvegarde des réglages propres à
la console et une procédure de restauration matériellement éprouvée. Les
optimisations moteurs demanderont des valeurs de départ récupérables et des
mesures physiques contrôlées. Aucun de ces points n'est déclaré résolu par
la concordance de l'image de communication.
