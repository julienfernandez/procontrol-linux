# Diagnostic réseau et premières lectures mémoire sur ProControl

Le 20 septembre 2026, entre **20:52 et 20:56 UTC**, la ProControl originale
`00:a0:7e:a0:ad:9c` a répondu à des requêtes de diagnostic sur Ethernet
`0x885f`. La version retournée est **`COMv1.37`**. Deux acquisitions de chacun
des segments suivants concordent octet par octet entre elles et avec l'image
constructeur extraite précédemment :

| Zone réellement lue | Octets distincts | Répétitions | Résultat |
|---|---:|---:|---|
| `0x20000–0x20007` : vecteurs initiaux | 8 | 2 | `00 06 e2 d4 00 02 b6 02` |
| `0x2a3d0–0x2a4cf` : début du décodeur de commandes | 256 | 2 | 256/256 identiques au constructeur |

Cela établit l'accès au moniteur de communication et la lecture de ces
**264 octets distincts**. Ce n'est pas encore une sauvegarde complète de la
console, une preuve de restauration, ni une validation des commandes moteurs.
Le [rapport JSON](firmware-network-validation-2026-09-20.json) donne les cinq
expériences, les SHA complets, numéros de trames et résultats de comparaison.
L'[étude initiale](firmware-research-2026-09-20.md) documente l'origine des
adresses et du firmware officiel ; elle était uniquement statique et passive.

## Expérience et état du studio

L'outil `tools/firmware_probe.py` utilise les fonctions de session et le helper
Ethernet de la passerelle. Il prend **le même verrou `run/daemon.lock` avant
d'ouvrir une socket**. Un essai pendant que le démon était actif a été refusé ;
aucun dossier de sortie n'a été créé. Ce rejet a aussi un test automatisé.

La passerelle recevait alors une extension de mapping dans une autre tâche.
Ses modules chargés n'ont pas été modifiés pour cette recherche. Le choix
initial d'un RPC de diagnostic a donc été remplacé, pour ces premiers essais,
par une courte session exclusive : arrêt propre du démon, expérience,
fermeture des sockets, relance dans un bloc `finally`. Il n'y a pas eu deux
émetteurs Ethernet locaux simultanés.

Trois pauses ont servi à la version seule, aux deux lectures des vecteurs,
puis aux deux lectures du décodeur. Le pointeur et Ardour sont restés actifs.
L'outil n'envoie pas d'OSC et ne relaie pas de gestes vers le DAW pendant
l'expérience. Il entretient la session et acquitte les messages reçus.
La reprise normale du démon réinitialise ses retours comme lors de tout
redémarrage de la passerelle ; cela ne constitue pas un test moteur distinct.

Après le dernier essai : démon `613729`, console Online, Ardour répondant,
219 sorties acquittées sur 219, zéro timeout, aucune sortie en attente et
aucune erreur. Les PID Ardour `584535` et pointeur `609883` ont été conservés.
Ces chiffres décrivent cette vérification, pas l'état futur du studio.

## Messages effectivement échangés

Toutes les requêtes ci-dessous vont de l'hôte `3c:97:0e:1b:3a:00` à la console.
Les réponses viennent de la MAC de la console vers cet hôte. La session est
ouverte par `e2`, acquittée par `a0`, à partir d'une annonce `MAINUNIT / 1.37`.
Une requête diagnostic est une commande DigiNet `00`, nombre d'enveloppes `1`.

### Version

```text
requête : f0 13 00 70 00 56 f7
ASCII   :                 V
réponse : f0 13 00 70 00 43 4f 4d 76 31 2e 33 37 0a 0d f7
ASCII   :                 C  O  M  v  1  .  3  7 LF CR
```

Dans `live-version-1/traffic.pcap` : requête trame 4, ACK trame 5,
réponse diagnostic trame 6, ACK de l'hôte trame 7. Le délai requête/réponse
dans le PCAP est **4,169 ms**. Le journal de la première version de l'outil
annonçait 5,299 ms car il mesurait après l'envoi de l'ACK de réponse, incluant
la temporisation prévue de cet ACK. Ce ne sont pas des horodatages matériels.
La version a été interrogée à nouveau avant chacune des quatre lectures.

### Adresse absolue puis lecture sans incrément

Chaque octet est demandé par une enveloppe contenant `A` suivi de huit
chiffres hexadécimaux, puis `m` minuscule. Exemple pour `0x20000` :

```text
requête : f0 13 00 70 00 41 30 30 30 32 30 30 30 30 6d f7
ASCII   :                 A  0  0  0  2  0  0  0  0  m
réponse A : f0 13 00 70 00 0a 0d f7
réponse m : f0 13 00 70 00 30 30 30 32 30 30 30 30 3a 20 30 30 20 27 00 27 0a 0d f7
contenu m : 00020000: 00 '<octet NUL>' LF CR
```

Dans `live-vectors-1` : requête trame 8, ACK 9, réponse `LF CR` à `A` en
trame 10, octet adressé en trame 12 ; chaque réponse est acquittée. Le `LF CR`
intermédiaire est cohérent avec le handler à `0x22484`, qui écrit le pointeur
volatil du moniteur à `0x5007a`, puis émet deux caractères. **Cet accusé de
commande n'est pas une valeur lue.** Le handler de `m` à `0x22546` lit la
mémoire sans incrémenter le pointeur. L'outil redonne l'adresse pour chaque
octet ; une réponse absente ou répétée ne peut décaler les adresses suivantes.

Le format expose l'octet deux fois : en hexadécimal et comme caractère brut.
La seconde copie peut être NUL, un saut de ligne, un octet avec bit de poids
fort, voire `f7`. Un découpage « MIDI sept bits » ou par lignes serait faux.
Le lecteur exige l'adresse attendue et la concordance des deux représentations.
Il conserve le corps complet, hors remplissage Ethernet, avant de l'interpréter.

Une future intégration au démon devra intercepter cette enveloppe complète
avant le mapping des gestes : le découpeur historique `split_commands` est
une heuristique fondée sur les octets de statut, incompatible avec les octets
arbitraires de ces réponses mémoire. Ce chemin séparé évitera d'interpréter
un octet de programme comme un geste destiné à Ardour ou au pointeur.

## Résultats et intégrité

| Expérience locale | Trames PCAP | Requêtes diagnostic | Octets lus | Réponses répétées |
|---|---:|---:|---:|---:|
| `live-version-1` | 7 | 1 | 0 | 0 |
| `live-vectors-1` | 55 | 9 | 8 | 0 |
| `live-vectors-2` | 55 | 9 | 8 | 0 |
| `live-dispatcher-1` | 1 546 | 257 | 256 | 1 |
| `live-dispatcher-2` | 1 545 | 257 | 256 | 1 |

Les **3 208 trames** ont un en-tête de longueur valide et une somme de corps
concordante. Le compteur noyau de pertes de la socket est zéro dans chacun
des cinq essais. Les doublons des deux grandes lectures, trames 918 et 696,
ont été acquittés et reconnus par leur séquence ; ils ne comptent pas comme
des octets supplémentaires. Leur présence est conservée, sans en déduire une
cause de perte ou un défaut matériel. Les 533 requêtes représentent cinq
versions et 528 lectures d'octet.

SHA-256 commun aux deux acquisitions de chaque zone :

- Vecteurs : `230e4cc0835ad1fbd6cac5b383d422b9f270ca2000d5072a428b9b035f235b03`.
- Décodeur : `80fb0f68362a8ffac1baa0589df74a4e3da1cafd4d305bd872ab1cab42a76c87`.

Les valeurs ont aussi été reconstruites **hors ligne depuis les PCAP**,
indépendamment du fichier `memory.bin` produit pendant l'essai. Adresse,
valeur hexadécimale et caractère brut concordent sur les 528 lectures. Les
264 adresses distinctes correspondent aux segments de la ressource `CODE 26`
officielle déjà extraite. La correspondance de version est ainsi complétée
par une correspondance binaire limitée à ces deux zones.

Les lectures de 256 octets ont un délai médian PCAP de 4,532 et 4,630 ms par
octet ; maxima 36,855 et 37,587 ms. L'intervalle minimal entre requêtes dépasse
23 ms. Ces mesures décrivent un studio au repos et incluent la réception dans
le processus Linux ; elles ne mesurent ni la latence audio ni les performances
en charge. Les sockets de capture enregistrent les émissions de l'outil et
les trames provenant de la console ; ce n'est pas une capture de tout le lien.

## Outil reproductible

L'outil refuse par construction les adresses hors des quatre segments connus
de `comm 1.37`, un passage dans un trou d'adressage, et plus de 256 octets par
invocation. Il vérifie la réponse exacte `COMv1.37 LF CR` avant toute lecture.
Il attend à la fois l'ACK et la réponse adressée, avec une seule requête en
vol, au maximum 50 Hz, sans répétition automatique d'une requête expirée.
Une version différente, une déconnexion ou une transaction incomplète arrête
l'expérience. Un fichier `memory.bin` n'est publié que pour une lecture complète.
La version finale enregistre aussi l'empreinte de son propre fichier source.

```bash
# Aperçu sans ouvrir de socket :
python3 tools/firmware_probe.py --read-code 0x20000 --length 8

# Tests sans matériel ni privilège Ethernet :
python3 -m unittest discover -s tests -p test_firmware_probe.py -v

# Session exclusive, dans un nouveau dossier ; relance même si le test échoue :
(
  ./procontrol stop || exit
  trap './procontrol start' EXIT
  python3 tools/firmware_probe.py --send --read-code 0x20000 --length 8 \
    --output work/firmware-vectors-new
)
./procontrol status
```

Ne pas lancer cette session pendant l'apprentissage du mapping ou une prise
audio nécessitant la surface. Le helper non root installé est utilisé ;
aucune nouvelle capability, modification système ou configuration IP requise.
Les tests couvrent exclusion mutuelle, ACK seul insuffisant, version incorrecte,
boucle réelle via sockets locales, réponse intermédiaire de `A`, doublons,
octets huit bits, cohérence des lectures et bornes des régions accessibles.

Validation finale avant publication, sur la base `90b0850` : **334 tests
Python réussis en 80,199 s**, dont neuf tests de cet outil ; compilation Python,
inventaire des mappings en mode `--check` et contrôle d'espaces Git réussis.
Après les captures, la version finale ajoute l'empreinte du script, la
conservation du rapport si les statistiques socket sont indisponibles et
l'arrêt sur une annonce Offline entre deux requêtes. Ce dernier cas est
testé par sockets locales ; aucune coupure physique n'a été provoquée.

Les fichiers bruts sont sous `work/firmware-research-20260920/live-*` : PCAP,
résultats JSON, petits dumps, audit indépendant et états avant/après du démon.
Les sources exactes des itérations utilisées sont conservées localement ;
leurs empreintes sont dans le rapport. Ces données constructeur restent hors
du Git public. Le code, les tests, les résultats et les procédures sont versionnés.

## Ce qui reste à établir

- Lecture complète et double vérification des segments du firmware `comm` ;
  l'outil actuel fournit les premières acquisitions bornées, pas ce dump complet.
- Carte du démarrage, de la flash, de la RAM et de l'EEPROM : aucun balayage
  d'adresses inconnues ou de registres MMIO n'a été effectué.
- Chemin de diagnostic `70 01` vers le processeur des faders, réponse de version
  et distinction paramètres volatils/calibration persistante.
- Sauvegarde restaurable de l'état propre à cette unité, puis expérience de
  restauration explicitement préparée. La lecture seule ne prouve pas la restauration.
- Optimisation de paramètres moteurs sur mesures physiques contrôlées, avec
  valeur de départ récupérable. Aucun de ces réglages n'a été modifié ici.

Les commandes `W/w`, effacement, téléchargement, redémarrage et calibration
n'ont pas été envoyées. `A` change uniquement le pointeur de diagnostic utilisé
pour la lecture ; l'expérience ne réécrit pas les octets du programme.
