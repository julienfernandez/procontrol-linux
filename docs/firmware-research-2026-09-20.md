# Open ProControl : exploration du firmware par le réseau

Date : 20 septembre 2026. Objectif utilisateur : comprendre le logiciel interne
de la Digidesign ProControl originale, améliorer son contrôle et préserver les
connaissances nécessaires à sa réutilisation durable. Cette recherche reste
ouverte : aucune modification du firmware ni extraction de la mémoire de la
console n'a été réalisée pendant cette étape.

## Résultat de cette étape

Le fichier officiel **`Procontrol.dll.rsr` de Pro Tools 10.3.10 Windows contient
deux images firmware Intel HEX**, nommées `comm` et `fader`, avec une ressource
de version `v1.37`. La console locale annonce également `1.37`. C'est une
correspondance de version, pas une comparaison octet par octet avec sa flash.

L'analyse statique identifie un canal de diagnostic dans la famille réseau
`f0 13 00 70`, un interpréteur de commandes de communication et un interpréteur
de faders. Le premier possède des commandes de lecture de mémoire. Le second
contient notamment lecture/écriture mémoire, seuils tactiles, gains de boucle,
amortissement, calibration et déplacement moteur. Leur accessibilité effective
et leurs effets sur cette console restent à vérifier individuellement.

Le [rapport JSON](firmware-research-2026-09-20.json) conserve les empreintes,
sources, offsets, segments et références aux trames. Il complète ce carnet ;
un champ `static_routes` désigne une analyse du fichier, pas un test matériel.

## 1. État réel et observation réseau

Au début de l'étude, les processus passerelle `584531`, pointeur `584534` et
Ardour `584535` étaient actifs. Console Online, Ardour répondant, huit pistes,
1 320 sorties feedback acquittées sur 1 320, zéro timeout. Ces PID et compteurs
sont un instantané historique. Aucun service n'a été arrêté ou redémarré par
cette recherche. D'autres tâches travaillaient simultanément sur ce studio.

Interface `enp0s25`, porteuse 10 Mbit/s half-duplex ; console
`00:a0:7e:a0:ad:9c`, hôte `3c:97:0e:1b:3a:00`. Commande utilisée :

```bash
sg wireshark -c 'PROCONTROL_CAPTURE_BACKEND=dumpcap bash tools/capture.sh enp0s25 firmware-recon-passive 60'
```

Capture clôturée :
`captures/20260920T203317Z-firmware-recon-passive-M6CB51/traffic.pcap`.

- 46 trames reçues, zéro perte rapportée par dumpcap, aucune troncature.
- 20 trames `0x885f` impliquent la console ; somme du corps concordante sur 20/20.
- Console → réseau : 8 annonces `e1` et 6 ACK `a0` ; hôte → console : 6 maintiens.
- Annonces `MAINUNIT / 1.37`, identiques quant au corps pendant cette capture.
- IPv4/IPv6 également présents sur le lien, **émis par le laptop**. Aucun paquet
  IP émis par la console dans cette fenêtre. Cela ne démontre pas l'absence
  absolue de toute pile IP dans son logiciel.
- Aucun geste contrôlé ni test moteur durant l'expérience. Les horodatages
  première/dernière trame sont 20:33:21.639908 / 20:34:12.469357 UTC ; une fenêtre
  de capture de 60 s ne contient pas nécessairement des paquets à ses deux bornes.

SHA-256 : `8be39435eaeb9da2e4f0a910059727c10a9b30c03cd63cdefa351bd362973c73`.

Un recensement hors ligne de **34 PCAP** existants relève **18 649 trames
émises par la console** : 8 669 `00`, 9 118 `a0`, 206 `e0`, 656 `e1`.
Les deux `traffic-us.pcap` corrigés précédemment remplacent leurs originaux à
horodatage erroné dans ce comptage. Le JSON énumère les fichiers et leurs SHA.
Ces durées et gestes hétérogènes ne constituent pas 34 essais indépendants.
Aucun transfert de firmware n'y a été identifié.

Trois corps d'annonce distincts apparaissent. Les différences concernent la
MAC hôte et l'octet 14 du corps (`63` puis `76` au premier démarrage). La
signification de cet octet n'est pas établie. Les captures initiales contiennent
aussi des messages `70 00` en ASCII ; par exemple la trame 25 du premier startup
contient `U`. **Un message console → hôte ne prouve pas qu'il faut le rejouer
dans l'autre sens.**

## 2. Sources constructeur et récupération des fichiers

Le manuel constructeur local, `work/track-monitor/procontrol-guide.pdf`, est
le **ProControl Guide 6.9**, 196 pages, auteur Digidesign Technical Publications.
Les pages imprimées 32 et 170 ont été rendues et inspectées visuellement.

- p. 10 : logiciel ProControl et mises à jour firmware livrés avec Pro Tools.
- p. 14 : transport Ethernet de type `0x885f`, coexistence avec TCP/IP.
- p. 32 : comparaison des versions et mise à jour via Pro Tools ; la mise à
  jour remet les réglages Utility à leur valeur d'usine.
- p. 35 : restauration usine et remise à jour par Pro Tools, décrites mais
  **non exécutées** ici.
- p. 170 : SYSTEM affiche les versions et informations matérielles/réseau ;
  tests Ethernet avec compteurs. Aucun test de bouclage lancé ici.

Source publique retrouvée :
[Avid, Pro Tools 10.3.10 Info & Downloads](https://kb.avid.com/pkb/articles/download/Pro-Tools-10-3-10-Downloads),
publication du 4 février 2015. Le lien Windows mène à
[l'archive officielle](https://akmedia.digidesign.com/support/compressed/Pro_Tools_10_3_10_Win_84130.zip).
Il s'agit d'un installateur complet ; il n'a pas été exécuté.

L'archive contient des fichiers directement accessibles dans le ZIP, et pas
seulement un gros cabinet d'installation. Des requêtes HTTP Range ont permis
de récupérer son répertoire central et seulement les trois membres utiles.
Taille totale annoncée : 1 905 248 238 octets ; 12 681 entrées ; répertoire
central à l'offset 1 903 261 004, longueur 1 987 212 octets. Environ 2,3 Mo sont
nécessaires au téléchargeur reproductible, au lieu de récupérer toute l'archive.

| Fichier, sous `DAE/Controllers` | Taille extraite | SHA-256 |
|---|---:|---|
| `Procontrol.dll` | 602 112 | `222cad7e7abcf3f8f91bffc6ff9f3ea87ac2ee990328e93a20bda6770f43a903` |
| `Procontrol.dll.rsr` | 181 758 | `0603a032f3abf4af6e266ba05486d186e031a5e2448da86d0aacc2b1e1eb1a53` |
| `Procontrol_M.dll` | 356 352 | `c05dc43a0e944bd1dae6e2ed9a04edb2ba8dcda2e40b61d772fb951a99baa4db` |

Les trois tailles et CRC32 du ZIP concordent. Les DLL sont du code Windows x86
pour l'hôte ; les images embarquées sont dans le **resource fork `.rsr`**.
Ne pas confondre l'architecture des DLL avec celle de la console.

## 3. Images extraites et intégrité

Le resource fork a sa zone de données à l'offset 256, longueur 181 401,
sa table à 181 657, longueur 101. Les noms viennent de cette table, pas d'une
attribution supposée après analyse du contenu.

| Ressource | Nom | Offset fichier | Octets Intel HEX | Enregistrements valides | Octets adressés |
|---|---|---:|---:|---:|---:|
| `CODE 26` | `comm` | 269 | 153 522 | 1 998 / 1 998 | 63 768 |
| `CODE 27` | `fader` | 153 795 | 27 862 | 366 / 366 | 11 546 |
| `TEXT 24` | `version` | 260 | — | — | 5 (`v1.37`) |

Les images contiennent des trous d'adressage. L'extracteur préserve **quatre
segments séparés par image**, sans inventer les octets absents :

- `comm` : `0x20000–0x20007`, `0x20064–0x2007f`,
  `0x20100–0x2010f`, `0x20400–0x2fce3`.
- `fader` : `0x8000–0x8007`, `0x8064–0x807f`,
  `0x8100–0x810f`, `0x8400–0xb0e5`.

Les deux premiers mots longs big-endian sont compatibles avec des vecteurs
68k : pile/PC `0x6e2d4 / 0x2b602` pour `comm`, `0x45384 / 0xa470` pour `fader`.
Le code aux deux PC initialise la pile, SR, DFC et VBR de manière cohérente.
Analyse avec Capstone 5.0 et contre-vérification de chemins ciblés avec GNU
objdump m68k 2.42. **Famille Motorola 68k étayée ; référence physique exacte du
processeur non déterminée.** Le mode de désassemblage 68020 est un choix d'outil.

Les champs de départ Intel HEX type 03 valent zéro : ils sont conservés comme
métadonnées et ne remplacent pas les vecteurs observés. Référence du format :
[documentation Intel HEX de Keil](https://www.keil.com/support/docs/1584/_hlp_hexfile.htm).

Ces images constituent une sauvegarde des **fichiers de mise à jour récupérés**,
pas une sauvegarde intégrale de la console : ROM de démarrage, EEPROM, réglages,
calibration et état effectivement installé ne sont pas extraits.

## 4. Chemins internes retrouvés dans `comm`

Adresses ci-dessous relatives à l'espace mémoire décrit par Intel HEX, pas à
l'offset brut du `.rsr`. Elles concernent exclusivement l'image identifiée par
les SHA ci-dessus.

1. La boucle à `0x2972e` appelle le traitement Ethernet `0x2b48e`, puis passe
   les données reçues à `0x2a6dc`.
2. L'assembleur de commandes `0x2a6dc` détecte `f0…f7` et appelle `0x2a3d0`.
3. `0x2a3d0` vérifie la longueur, l'identifiant `13 00`, puis le sous-groupe.
   La table à `0x2a424` contient les branches `00` à `70`. L'entrée `60`
   aboutit directement au retour ; cela concerne ce dispatcher, pas toute
   interprétation possible de l'octet 60 ailleurs.
4. `70` mène à `0x2a63c`. Sélecteur `00` : les octets suivants entrent dans le
   tampon circulaire `0x6b50a`. Sélecteur `01` : appel `0x2ada0`, file de
   transmission série `0x6c10e`, vidée vers les registres autour de `0x8000071b`.
5. La boucle principale `0x26c78` fait traiter `0x6b50a` par l'interpréteur
   `0x22090`. Celui-ci est aussi utilisé pour une entrée série locale.
6. Les réponses du contexte réseau passent par `0x22032` puis `0x21fce`, qui
   construit une enveloppe `f0 13 00 70 00 … f7` et la remet à `0x2b1c8`.

Cette continuité statique étaye un **canal réseau de diagnostic**. Elle ne
prouve pas encore une réponse de l'appareil réel à une requête nouvellement émise.

| Commande ASCII dans le contexte `comm` | Handler | Lecture statique |
|---|---|---|
| `V` / `v` | `0x22192` | Renvoie 10 octets depuis `0x51dc4` via la voie de réponse courante |
| `A` / `a` + 8 chiffres hexadécimaux | `0x22484` | Fixe le pointeur mémoire à `0x5007a` ; consomme 9 caractères |
| `M` | `0x2252e` | Lecture via `0x21f52`, puis incrément du pointeur |
| `m` | `0x22546` | Même lecture sans incrément |
| `W` / `w` + 2 chiffres hexadécimaux | `0x224b8` / `0x224f4` | Écriture d'un octet, avec / sans incrément |
| `B` / `b` | `0x22318` | Chemin de redémarrage à `0x400` |
| `:` | `0x2232a` | Interpréteur de téléchargement ; le préfixe `:::` mène à l'effacement |

`0x21f52` formate adresse, valeur hexadécimale et caractère, en lisant deux fois
l'adresse pointée. Ce détail exclut une lecture aveugle de registres matériels :
une lecture MMIO peut avoir un effet. Une première lecture devra cibler une
adresse de code connue, après validation de version et du framing de réponse.
Le canal de diagnostic transporte aussi des opérations persistantes : aucun
balayage de commandes ni essai de flash ne fait partie de la validation réalisée.

## 5. Chemins retrouvés dans `fader`

L'interpréteur à `0x91c2` distingue les messages moteurs binaires et une table
de commandes ASCII (`0x92ca`, caractères à `0x9332`). La ressource contient un
menu d'aide décrivant les fonctions ; les handlers mémoire ont aussi été lus :

- `H` : aide ; `V` : version ; handlers `0x9366` et `0x9374`.
- `U` + 8 chiffres hexadécimaux : pointeur à `0x44026`, handler `0x9750`.
- `Q` / `q` : lecture avec / sans incrément, `0x97ca` / `0x97da`.
- `W` / `w` : écriture, `0x9782`.
- Le menu mentionne vitesse moteur, consigne de position, seuils de contact
  et relâchement, gains d'asservissement, amortissement et essais cycliques.

Le relais `70 01` de `comm` est un candidat sérieux pour rejoindre cette voie
série, mais le chemin complet, les conditions de mode et la remontée des
réponses doivent encore être vérifiés. **Ne pas utiliser la syntaxe `U/Q` de
`fader` sur le contexte `comm`, dont la syntaxe mémoire est `A/M`.**

## 6. Reproduire la récupération et l'analyse

Depuis la racine du projet, dans des dossiers nouveaux :

```bash
python3 tools/fetch_procontrol_personality.py work/procontrol-personality-10.3.10
python3 tools/inspect_firmware.py \
  work/procontrol-personality-10.3.10/Procontrol.dll.rsr \
  --extract work/procontrol-firmware-1.37
python3 -m unittest discover -s tests -p test_inspect_firmware.py -v
```

Le téléchargeur n'utilise que le HTTPS public d'Avid, vérifie la réponse 206,
les bornes Content-Range, le répertoire ZIP, les noms, les tailles, CRC32 et
SHA-256 fixés. Il refuse un fichier différent et un dossier destination existant.
L'extracteur utilise la bibliothèque standard Python ; aucune socket ni API
de console. Il valide les bornes du resource fork, les noms de ressources,
les types HEX, chaque longueur et checksum, EOF et les chevauchements.
Le manifest contient les segments, leurs SHA et les chaînes avec adresses.
Sept tests utilisent des données synthétiques, dont un exemple HEX indépendant.

La récupération des trois fichiers a été **refaite avec le script versionné** :
les trois SHA concordent avec l'extraction initiale. L'extraction a été faite
sur les fichiers réels, pas seulement sur les fixtures de tests.

Validation avant commit : **297 tests Python réussis en 54,468 s**, dans une
copie exportée de `22e3bc3` augmentée uniquement des six fichiers de cette
recherche. Les sept tests firmware sont inclus. Compilation Python, inventaire
des mappings en mode `--check` et contrôle d'espaces Git réussis. Cela valide
le logiciel et la reproductibilité hors ligne, pas l'accès diagnostic matériel.

Pour le désassemblage, outils consultés :
[Capstone, interface Python](https://www.capstone-engine.org/lang_python.html) et
GNU binutils m68k 2.42, paquet Ubuntu extrait localement sans installation système.
Exemple avec un objdump m68k disponible :

```bash
m68k-linux-gnu-objdump -D -b binary -m m68k:68020 \
  --adjust-vma=0x20400 --start-address=0x2a3d0 --stop-address=0x2a424 \
  work/procontrol-firmware-1.37/CODE-26-00020400.bin
```

Les données embarquées et tables ne sont pas des instructions. Un désassemblage
linéaire intégral ne constitue pas une cartographie fiable de toutes les fonctions.

## 7. Retours d'expérience pratiques

- Les recherches « ProControl firmware » ramènent beaucoup d'autres marques
  (RTI/AVPro, ABB, etc.). Toujours vérifier Digidesign et le modèle original.
- Les anciennes pages `archive.digidesign.com` ont renvoyé HTTP 403 dans cet
  environnement. Le lien Avid 10.3.10 et son CDN ont permis la récupération.
- Certaines tentatives urllib ont répondu 403 ou expiré après réception des
  en-têtes ; curl avec des plages explicites a fonctionné. Le script conserve
  la validation de plage pour ne pas télécharger silencieusement 1,9 Go.
- La première plage manuelle s'arrêtait trop tôt dans `Procontrol_M.dll` :
  zlib a rejeté le flux tronqué. La plage complète a ensuite permis CRC et SHA.
  Aucune donnée partielle n'a servi à une conclusion sur cette DLL.
- Le Python système n'avait ni pip ni ensurepip. Capstone et pefile ont été
  placés sous `work/` avec le Python fourni par l'environnement. Les deux
  outils versionnés n'en dépendent pas.
- Capstone affiche mal certains index m68k complexes (registre `invalid`,
  facteur d'échelle manquant). GNU objdump a confirmé l'indexation ×2 de la
  table SysEx et résout les adresses PC-relatives ; ne pas lire les tables
  de branchement depuis la seule sortie textuelle Capstone.
- L'objdump du paquet extrait exige son répertoire de bibliothèques dans
  `LD_LIBRARY_PATH`. Aucun changement global de bibliothèque n'a été effectué.
- Les outils ajoutés ne sont importés par aucun service du studio. Leur travail
  hors ligne évite un second émetteur Ethernet et une interruption concurrente.

## 8. Conservation et prochaines expériences

**Dans Git** : ce carnet, le rapport de preuves avec SHA, les deux outils,
leurs tests synthétiques, leurs références et les résultats de validation.
Les binaires constructeur, le manuel et les désassemblages complets restent
sous `work/firmware-research-20260920/` ; les PCAP sous `captures/`, conformément
aux exclusions du projet. Ils ne sont pas placés sous la licence GPL du code.
Les commandes ci-dessus permettent de reproduire l'acquisition et l'extraction.
La disponibilité durable du CDN n'est pas garantie : les copies locales
conservées doivent rejoindre une sauvegarde privée indépendante.

Prochaines étapes, **non exécutées** :

1. Préparer une requête de version `70 00` strictement bornée via l'émetteur
   unique de la passerelle, avec capture, timeout et distinction ACK/réponse.
   Le RPC actuel de la passerelle ne propose pas d'émission diagnostic brute.
2. Vérifier la réponse version ; ensuite lire quelques octets d'une zone de
   code connue avec `A/M`, comparer aux images officielles, répéter et hacher.
   Pas de lecture de MMIO ni d'écriture firmware pour cette expérience.
3. Établir la carte ROM/flash/RAM/EEPROM et sauvegarder ce qui est lisible,
   avec deux acquisitions concordantes et les trous explicitement représentés.
4. Vérifier séparément le relais vers les faders, les paramètres accessibles
   et leur portée RAM/persistante ; chaque réglage exige une mesure contrôlée
   et une valeur initiale récupérable avant optimisation.

L'objectif de maîtrise et de préservation reste actif. Cette étape fournit
les images d'origine et une voie de diagnostic étayée par leur code ; elle ne
prouve encore ni accès mémoire sur la console, ni restauration, ni longévité.
