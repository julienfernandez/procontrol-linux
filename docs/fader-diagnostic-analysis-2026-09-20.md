# Relais diagnostic vers le processeur des faders

**Étape suivante réalisée :** quatre réponses directes `FDRv1.37` ont été
capturées, après un premier essai incomplet. Voir la
[validation réseau et les snapshots du relais](fader-network-validation-2026-09-20.md).
Le présent rapport conserve les conclusions de l'étape statique.

Analyse statique du 20 septembre 2026, après la
[double lecture complète de `comm`](comm-firmware-readback-2026-09-20.md).
**Aucune requête `70 01`, aucun déplacement moteur ni aucune écriture de
calibration n'a été envoyé pendant cette étape.** Les services restent actifs.

Le chemin de réponse série vers Ethernet est retrouvé dans `comm 1.37`.
Son validateur refuse les octets nuls et ceux dont le bit 7 vaut 1 dans le
contenu d'une réponse. Cette restriction est importante : le lecteur mémoire
des faders inclut un caractère brut et pourrait donc produire des réponses
que ce relais rejette. L'accès mémoire complet des faders par cette voie
n'est pas établi.

Le [rapport JSON](fader-diagnostic-analysis-2026-09-20.json) identifie les
images analysées, les sorties locales de désassemblage et l'archive privée
complémentaire. Les adresses sont des adresses mémoire de l'image, pas des
offsets du resource fork. Elles ne sont valables que pour ces fichiers.

## Sources et méthode

- `Procontrol.dll.rsr`, SHA-256
  `0603a032f3abf4af6e266ba05486d186e031a5e2448da86d0aacc2b1e1eb1a53`.
- Segment `comm`, base `0x20400`, 63 716 octets, SHA-256
  `e2945b200be72745afb10a3bc68300b4dc3b5adba90b3a8157cec37f051e1af8`.
- Segment `fader`, base `0x8400`, 11 494 octets, SHA-256
  `2479230a850da18b33b1dcf7292dbb12af6421aceabc047b2ae07d5582f23e05`.

L'origine officielle et l'extraction des quatre segments de chaque image
sont décrites dans la [recherche initiale](firmware-research-2026-09-20.md).
L'image `comm` a été comparée à celle lue sur l'appareil ; le programme des
faders installé dans l'appareil n'a pas encore fait l'objet de cette comparaison.

Les chemins ont été relus avec GNU objdump m68k 2.42, mode `m68k:68020`.
Ce mode de décodage n'identifie pas à lui seul la référence du processeur.
Les tables de caractères et de branches sont traitées comme des données.

## Aller : Ethernet vers l'interpréteur des faders

| Image et adresse | Observation dans le code |
|---|---|
| `comm 0x2a63c–0x2a66c` | La famille `70` distingue les sélecteurs `00` et `01`. `00` alimente le moniteur principal ; `01` retire le sélecteur puis appelle `0x2ada0` avec les octets restants |
| `comm 0x2ada0` | Mise en file série dans `0x6c10e` et activation du bit 4 du masque d'interruptions via `0x80000715` |
| `fader 0xa40e–0xa430` | Réception série depuis le registre `0x8000071b`, puis mise en file dans `0x448f8` |
| `fader 0x91ec–0x91f8` | L'interpréteur `0x91c2` choisit le mode de réponse 1 lorsque son contexte est `0x448f8`, sinon le mode 0 |
| `fader 0x9374` | `V/v` fournit dix octets depuis `0x4412e`, avec la lettre de commande comme tag, à la routine de réponse `0x89ae` |

Ces éléments relient les interfaces logicielles attendues. Le câblage physique,
la réponse exacte de version et les conditions de fonctionnement de l'unité
réelle restent à confirmer par une expérience contrôlée.

L'interpréteur remet également l'octet `0x4400e` à zéro à `0x91e6` avant de
traiter une commande. Sa portée fonctionnelle n'est pas établie ici. Une
interrogation dite de lecture ne doit donc pas être décrite comme sans aucun
effet sur l'état volatil interne.

## Retour : réponse série vers Ethernet

Dans `fader`, `0x89ae` distingue trois modes de sortie : 0 vers `0xa2ea`,
1 vers la liaison encadrée, 2 vers les deux. La voie encadrée construit :

```text
00 <tag de commande> <longueur sur un octet> <contenu>
```

Elle pose le drapeau `0x44010`, enfile l'en-tête puis le contenu via `0xa332`,
puis efface le drapeau. `0xa332` utilise la file `0x44af8` ; la routine
`0xa11c` copie les octets. À `0xa436–0xa44a`, l'interruption retire les octets
de cette file et les écrit vers `0x8000071b`. Aucune transformation du bit 7
n'apparaît dans ces chemins relus.

Dans `comm`, le parseur série `0x23d00` utilise la file `0x6bf0e`.
Le chemin `0x23f60` examine un en-tête de trois octets. Sa table reconnaît
notamment les tags `V/v` et l'espace :

- `V/v` mène à `0x23fce` : dix octets vers `0x5094a`, validation via
  `0x23bbe`, mise à 1 de `0x509c2`, puis comparaison des versions via `0x23c98`.
- L'espace mène à `0x240d0` : longueur prise dans l'en-tête, même validateur.
- `0x23bbe` appelle `0x21fce` avec le sélecteur **1** après validation et copie.
  Le constructeur `0x21fce` produit `f0 13 00 70 01 <contenu> f7`.

Le tag et la longueur série ne sont donc pas recopiés comme tels dans ce
contenu Ethernet. Une réponse `70 01` est distincte du contexte principal
`70 00` déjà essayé sur l'appareil.

## Filtre des réponses et correction d'interprétation

Le validateur `comm 0x23bbe` attend un paquet complet de `3 + longueur`
octets, au maximum 126, et vérifie la concordance de la longueur. Entre
`0x23c0a` et `0x23c24`, pour chaque octet du contenu :

```text
octet == 0                   -> rejet
(octet & 0x80) == 0x80        -> rejet
sinon                        -> continuer
```

Les valeurs admissibles par ce test vont donc de **`0x01` à `0x7f`**.
La branche `bne` à `0x23c1e` saute la mise à zéro du drapeau de validité
lorsque le bit 7 est absent. Les routines `0x2abfe` (lecture sans consommation),
`0x2abbc` (consommation) et `0x2a8d2` (copie) n'enlèvent pas ce bit.

La première lecture de travail avait inversé cette condition et envisagé
un bit 7 imposé, puis supprimé par une routine de copie. La relecture des
branches et des copies réfute cette interprétation. Elle est conservée ici
pour éviter de construire un futur décodeur autour d'un encodage inexistant
dans les chemins examinés. Aucun essai matériel n'a utilisé cette hypothèse.

## Lecture mémoire : syntaxe différente et limite à éprouver

| Commande dans `fader` | Handler | Observation statique |
|---|---|---|
| `U` + huit chiffres hexadécimaux | `0x9750` | Positionne le pointeur volatil `0x44026`, puis réponse LF CR avec tag espace |
| `Q` | `0x97ca` | Appelle `0x90d8`, puis incrémente le pointeur |
| `q` | `0x97da` | Appelle `0x90d8` sans incrément |
| `W/w` | `0x9782` | Écriture d'octet ; commande non utilisée |

`0x90d8` formate adresse, valeur hexadécimale, caractère brut entre apostrophes,
LF CR. L'octet mémoire est lu à `0x910a` pour l'hexadécimal, puis à `0x9122`
pour le caractère. Le contenu est transmis avec un tag espace via `0x89ae`.

**Déduction statique :** si le caractère brut vaut `00` ou `80–ff`, ce contenu
rencontre le filtre de rejet de `comm`, même si son champ hexadécimal est
lisible. Cela pourrait expliquer une absence de réponse Ethernet sans que
la commande de lecture soit absente du processeur des faders. La réaction
complète à ce rejet et la remise en synchronisation ne sont pas validées ici.
Un timeout ne devrait donc pas entraîner des retries aveugles.

Les syntaxes `A/M/m` du processeur principal et `U/Q/q` des faders ne sont
pas interchangeables. Aucun outil réseau publié n'est étendu aux faders dans
cette étape. Les contrôles de version, de bornes et de caractère brut du
lecteur `comm` restent propres à son contexte.

## Reproduire et reprendre

Après extraction avec `tools/inspect_firmware.py`, exemples hors ligne :

```bash
m68k-linux-gnu-objdump -D -b binary -m m68k:68020 \
  --adjust-vma=0x20400 --start-address=0x23bbe --stop-address=0x23c98 \
  work/procontrol-firmware-1.37/CODE-26-00020400.bin
m68k-linux-gnu-objdump -D -b binary -m m68k:68020 \
  --adjust-vma=0x8400 --start-address=0x90d8 --stop-address=0x9152 \
  work/procontrol-firmware-1.37/CODE-27-00008400.bin
```

Les sorties de travail complètes et leurs sources sont conservées dans
`work/firmware-research-20260920/` et dans le complément privé
`procontrol-fader-static-1.37-evidence.tar.gz`, sous le dossier de préservation
décrit dans la [mémoire technique](retour-experience.md#ce-que-lon-conserve-et-où).
Le JSON associé donne son SHA-256, son manifeste de fichiers et les commandes
de reproduction des vues. Cette archive a été relue après compression ;
elle reste sur le même disque et ne constitue pas une sauvegarde indépendante.

La prochaine expérience utile est une interrogation bornée de version,
avec verrou exclusif, capture, timeout, validation du sélecteur de réponse
et reprise des services. Il faudra établir la version réellement installée
avant toute lecture d'adresse issue du fichier constructeur. La couverture
mémoire, les réglages volatils/persistants, la calibration et la restauration
restent des étapes séparées.
