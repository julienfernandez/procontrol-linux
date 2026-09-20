# Premiers octets du firmware des faders récupérés via le tampon série

**Étape suivante :** le risque de faux toucher est ensuite
[observé puis neutralisé par des lectures de relâchement](fader-touch-recovery-2026-09-21.md).
Les conclusions ci-dessous décrivent la première étape, limitée aux vecteurs.

Le 20 septembre 2026, les **huit octets à `0x8000–0x8007`** ont été lus sur
la ProControl trois fois : `00 04 53 84 00 00 a4 70`. Ils correspondent aux
vecteurs du segment constructeur `CODE 27`. La troisième lecture traverse
la fin du tampon circulaire. Un premier essai avait déjà récupéré le seul
octet nul à `0x8000`.

L'audit indépendant reconstruit ces résultats depuis **55 PCAP clôturés,
3 500 trames**, sans importer le décodeur d'acquisition. Les empreintes,
trames de requête/réponse, états RAM et sources exactes sont dans le
[manifeste public](fader-raw-readback-2026-09-20.json). Il s'agit de **8 octets
distincts vérifiés**, pas d'une sauvegarde des 11 546 octets des segments
constructeur des faders, ni d'une restauration matérielle.

## Question et état initial

Le [diagnostic fader](fader-network-validation-2026-09-20.md) répond bien
`FDRv1.37`. Mais le [validateur du relais comm](fader-diagnostic-analysis-2026-09-20.md)
rejette les contenus comportant `00` ou un octet dont le bit 7 vaut 1.
Le lecteur mémoire fader inclut précisément le caractère brut entre
apostrophes, même si la représentation hexadécimale est imprimable.

Question : les octets refusés par le relais restent-ils récupérables dans
son tampon RAM de réception série, avant qu'ils soient remplacés ?

Passerelle Online, Ardour fermé/attendu, apprentissage désactivé, aucune
action récente enregistrée. Chaque session exclusive arrête la passerelle,
prend son verrou `run/daemon.lock` puis garantit sa relance dans `finally`.
Le service pointeur reste actif. Interface `enp0s25`, liaison 10 Mbit/s
half-duplex, EtherType `0x885f`, mêmes hôte et console que les essais précédents.

## Analyse statique qui rend l'essai possible

La consommation série `comm 0x2abbc` avance le pointeur consommateur mais
**n'efface pas les cases lues**. La mise en file `0x2ab76` écrit les nouvelles
données ; `0x2abfe` lit sans consommer. Le tampon conserve donc temporairement
une réponse, même lorsque le parseur la refuse.

La structure RX à `0x6bf0e` comporte six champs big-endian de quatre octets :

| Décalage | Champ utilisé dans cette recherche |
|---:|---|
| 0 | Pointeur producteur |
| 4 | Début des données : `0x6bf26` |
| 8 | Pointeur consommateur |
| 12 | Taille de l'allocation : 512 octets, en-tête compris |
| 16 | Champ non interprété, observé à zéro |
| 20 | Compteur de débordements |

L'espace de données compte **488 octets**, jusqu'à `0x6c10d` inclus.
Le bouclage revient à `0x6bf26`, pas au début de l'en-tête. Les valeurs et
les pointeurs observés sont compatibles avec ce chemin de code. Le segment
`comm` correspondant a déjà été comparé intégralement à celui de l'appareil.

La réponse série à `U00008000` vaut `00 20 02 0a 0d`. Chaque lecture ajoute
21 octets : `00 20 12`, puis le contenu de 18 octets
`<adresse sur 8 caractères>: <hex sur 2 caractères> '<octet brut>' LF CR`.
Un essai d'un octet doit donc produire 26 octets série ; huit lectures en
produisent 173. `q` lit sans incrément, `Q` lit puis avance le pointeur volatil.

## Procédure et contrôles

1. Vérifier `COMv1.37`, puis `FDRv1.37` dans la même session.
2. Lire l'état tactile `0x508ea` sur 16 octets, le mode `0x5095c` et l'en-tête RX.
   Exiger toucher nul, mode zéro et file vide. À partir du deuxième essai,
   relever aussi le compteur d'erreurs `0x509ba` avant et après.
3. Envoyer une seule enveloppe `70 01`, contenant `U` + adresse et `q` ou les
   huit `Q`. Attendre l'ACK puis conserver une fenêtre de réception de 0,5 s.
   Aucun renvoi automatique de cette commande en cas d'échec.
4. Relire l'en-tête RX. Exiger une avancée producteur de 26 ou 173 modulo 488
   et aucun nouveau débordement. Lire les cases conservées via les commandes
   `A/M` du processeur **comm**, en fenêtres bornées et lots de 16 au maximum.
5. Relire l'en-tête RX une troisième fois : producteur et compteur de
   débordements doivent être stables pendant la copie. Reconstruire le flux
   série et vérifier adresse, valeur hexadécimale et caractère brut.
6. Obtenir une nouvelle réponse `FDRv1.37`, puis vérifier que toucher et mode
   sont inchangés. Préserver les rapports d'échec et de récupération si besoin.

Les snapshots RAM sont **non atomiques**. Ces contrôles rendent les quatre
essais cohérents ; ils ne garantissent pas une acquisition sous mouvement
continu ou en présence d'un flux série imprévu. Un ACK seul ne valide aucun
octet du firmware.

## Résultats observés sur l'appareil

Heures UTC, offsets producteur relatifs à `0x6bf26` :

| Essai local | Début UTC | Octets mémoire | Producteur avant → après | Fenêtres série | Erreurs avant → après |
|---|---|---:|---|---|---|
| `live-fader-raw-zero-1` | 21:52:18 | 1 | 9 → 35 | 26 | Non relevées |
| `live-fader-raw-vectors-1` | 21:57:15 | 8 | 61 → 234 | 173 | 5 → 30 |
| `live-fader-raw-vectors-2` | 21:57:20 | 8 | 260 → 433 | 173 | 30 → 55 |
| `live-fader-raw-vectors-3` | 21:57:24 | 8 | 459 → 144 | 29 + 144 | 55 → 80 |

- Les trois lectures de huit octets ont le SHA-256
  `0b94948d9565a02762f1a6b7f83c5cf28908ea1bf882cdc5800eb57e0fdd8b2d`,
  identique au segment constructeur `CODE-27-00008000.bin`.
- Le flux série de 173 octets a le même SHA-256 lors des trois lectures :
  `1dedaab0995a79d306f1be144809651c8b9c0f2cd9573dfb05f777f314574470`.
- Les 55 rapports de socket indiquent zéro perte ; le compteur de débordements
  RX reste zéro. Cela concerne ces captures bornées.
- Dans chaque PCAP `request/traffic.pcap` des essais de huit octets, la trame 1
  porte la requête, la 2 son ACK. Les réponses console → hôte sont : trame 3,
  LF CR de `U` ; trames 5, 7 et 9, lectures `0x8001=04`, `0x8002=53`, `0x8007=70`.
  Les cinq autres réponses mémoire n'arrivent pas sous leur forme diagnostic
  Ethernet. Les octets bruts de **toutes** les réponses se retrouvent dans RX.
- Le premier essai nul ne transmet que LF CR de `U` en trame 3. Son consommateur
  est deux octets derrière le producteur après lecture ; une réponse de version
  est obtenue ensuite. Les essais complets suivants commencent avec une file vide.
- Le compteur d'erreurs augmente de **25 par lecture de huit octets**. Le rejet
  et la reprise du parseur peuvent compter plusieurs erreurs pour une seule
  réponse ; ce compteur ne mesure pas un nombre de paquets perdus. Le premier
  essai n'avait pas ces snapshots : la valeur 5 observée ensuite ne suffit pas
  à lui attribuer rétrospectivement un delta mesuré.

## Limite importante avant une lecture complète

Le refus d'une réponse ne signifie pas que tous ses octets sont ignorés.
Le parseur peut ensuite réexaminer le caractère brut comme un événement série.
Analyse statique `comm 0x23e70–0x23f5c` : les valeurs `c0–cf` peuvent inscrire
un toucher, et `d0–df` un relâchement, dans `0x508ea + 2 × (octet & 7)`.
En mode zéro, ce chemin prépare un événement destiné à l'hôte via `0x2b8a6` ;
les modes 6 et 7 ont d'autres branches liées aux faders. **Ce risque est déduit
du code ; aucun essai sur ces valeurs n'a été effectué dans cette campagne.**

Les huit octets choisis dans les vecteurs ne contiennent pas ces octets. Le pilote impose cette
petite plage, le mode zéro et un état tactile neutre ; il ne donne pas une
commande libre de lecture de toute la mémoire fader. Étendre sa plage exige
d'abord d'établir une méthode qui maîtrise les effets du parseur sur les états
et démontre leur récupération. Aucun mécanisme de neutralisation n'est livré.

Les commandes `A/U` modifient des pointeurs volatils ; les commandes `M/Q`
les incrémentent. Le compteur d'erreurs change aussi. Cette recherche n'est
donc pas « sans changement d'état ». Aucune commande d'écriture de firmware,
d'effacement, de calibration ou de réglage moteur n'est utilisée.

## Outils, audit et reproduction

- [fader_readback.py](../tools/fader_readback.py) : aperçu par défaut, plage
  `0x8000–0x8007`, préalables, lecture conservée et contrôles avant/après.
- [firmware_probe.py](../tools/firmware_probe.py) : deux nouveaux états nommés,
  et fenêtres bornées du tampon RX `comm` (`--read-ring-offset`).
- [audit_fader_readback.py](../tools/audit_fader_readback.py) : reconstruction
  depuis les PCAP RAM, décodage série distinct, validation des fichiers et
  manifestes. Il réutilise les lecteurs PCAP/DigiNet et l'auditeur `comm`,
  **pas** le parseur série ni les fonctions d'acquisition du pilote fader.

Depuis la racine du dépôt, aperçu sans ouvrir de socket :

```bash
python3 tools/fader_readback.py --length 8
```

Exemple d'acquisition **exclusive**, uniquement dans les conditions de cette
expérience, avec un nouveau dossier et la console 1.37 correspondante :

```bash
(
  ./procontrol stop || exit
  trap './procontrol start' EXIT
  python3 tools/fader_readback.py --length 8 --send \
    --output work/nouvel-essai-vecteurs-fader
)
./procontrol status
./pointer status
```

L'outil ne gère pas l'arrêt/relance de la passerelle à la place de cet encadrement.
Il prend le verrou avant toute émission. Audit hors ligne après clôture :

```bash
python3 tools/audit_fader_readback.py work/nouvel-essai-vecteurs-fader \
  --reference work/firmware-research-20260920/extracted/CODE-27-00008000.bin
```

La référence provient de l'[extraction documentée](firmware-research-2026-09-20.md).
Sans `--reference`, l'audit vérifie la cohérence des captures et fichiers, sans
affirmer une comparaison constructeur. Les tests synthétiques couvrent octet
nul, bit 7, `f7`, bouclage, modification du tampon pendant la copie, préalables,
ACK manquant et falsification des fichiers ou manifestes. Aucun dump constructeur
complet n'est utilisé comme fixture publique.

## Conservation, validation et état final

Les sources réellement utilisées pour le premier essai sont préservées
séparément de celles des trois répétitions ; l'ajout des snapshots d'erreurs
entre ces étapes reste identifiable par les empreintes. Les originaux ne sont
pas remplacés lors de l'amélioration de l'auditeur.

Les preuves privées sont regroupées dans
`procontrol-fader-raw-vectors-1.37-evidence.tar.gz`, sous
`~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`.
L'archive et chaque membre sont relus et vérifiés ; le manifeste public contient
taille, SHA-256, inventaire, provenance et résultats de validation. Ce dossier
reste sur **la même machine**. Un support indépendant reste à prévoir.

À la reprise vérifiée : passerelle PID 633654 Online, 204/204 sorties initiales
acquittées, aucun timeout ni erreur ; pointeur PID 622060 inchangé, raccordé
au nouveau démon. Ardour reste fermé/attendu. Ce sont des observations de service
datées, pas une nouvelle confirmation physique des moteurs ou de l'audio.

**374 tests passent** localement en 80,976 s ; compilation Python, inventaire
généré en mode `--check` et contrôle des espaces passent aussi. Le manifeste
conserve les empreintes des sorties. La prochaine question matérielle est la maîtrise des effets du
parseur pour les autres valeurs, avant toute acquisition complète des faders.
