# Lecture des faders : faux événements tactiles et retour à l'état neutre

Expériences du **21 septembre 2026, heure de Paris** (20 septembre à
22:10 UTC). Les octets `c0` et `d0` lus dans le programme fader provoquent
respectivement un événement de toucher et de relâchement dans le relais
`comm`. La paire ramène son cache tactile à zéro. Les huit octets `d0–d7`
ont été lus et vérifiés, puis un bloc de code de 12 octets a été récupéré
deux fois avec ces relâchements à sa suite. Les quatre essais aboutissent,
avec états avant/après et audit indépendant des PCAP.

Le [manifeste](fader-touch-recovery-2026-09-21.json) conserve les sources,
60 captures clôturées, 2 115 trames, empreintes et résultats. Ce rapport établit la méthode de
neutralisation dans ces essais. **Il ne prétend pas que le programme complet
des faders a déjà été acquis.** Le nouvel outil d'archive prépare deux passages
sur les quatre segments constructeur ; leur résultat doit être documenté
séparément après achèvement et vérification.

## Question et recherche d'une autre commande

La [lecture des vecteurs](fader-raw-readback-2026-09-20.md) a confirmé que les
octets refusés par le filtre restent lisibles dans RX. Elle a aussi montré
pourquoi une acquisition générale devait maîtriser l'état tactile du relais.

La table de commandes fader a été relue avec GNU objdump m68k 2.42 : table
de 52 offsets signés à `0x92ca`, caractères à `0x9332`, sélection à `0x92a2`.
Le parcours des caractères croît tandis que l'index des offsets décroît :
le caractère d'index `i` utilise l'entrée `51-i`. Le résultat concorde avec
les branches ciblées et l'aide embarquée à partir de `0x9812`.

| Commande | Chemin étudié et interprétation statique |
|---|---|
| `H/h` | `0x9366` → `0x9812`, aide embarquée |
| `V/v` | `0x9374`, version |
| `U/u` | `0x9750`, adresse du pointeur mémoire volatil |
| `Q` / `q` | `0x97ca` / `0x97da` → `0x90d8`, même format avec caractère brut |
| `W/w` | `0x9782`, écriture mémoire, non utilisée |
| `A/a`, `G/g`, `M/m` | Branche commune `0x94a2`, actions sur positions/vitesse ; ce ne sont pas les commandes mémoire de `comm` |
| `D/d` | Paramètre de l'asservissement, pas un dump hexadécimal |
| `B/b`, `C/c`, `S/s`, `X/x`, `:` | Redémarrage, calibration, arrêt de boucle, essais moteurs et téléchargement ; chemins non utilisés |

Aucune variante de lecture mémoire sans caractère brut n'a été trouvée dans
ce dispatch. Une aide connue sur un autre moniteur ne justifierait pas d'envoyer
`D`, `A` ou `M` à ce processeur. Les commandes ci-dessus ont été **analysées** ;
cette étape n'a pas essayé les commandes de moteur, calibration ou téléchargement.

## Méthode retenue

Le parseur `comm 0x23e70–0x23f5c` extrait le canal par `octet & 7`. En mode
zéro (`0x5095c`), `c0–cf` pose le mot tactile correspondant à 1 et `d0–df`
le remet à 0 dans le cache `0x508ea`. Il prépare aussi un événement réseau.
Ce sont des effets sur le **relais logiciel**, pas une action sur le capteur
physique. Les branches des modes 6 et 7 sont différentes : le pilote exige
le mode zéro avant et après chaque bloc.

Des commandes `U<adresse>q` permettent de lire ces caractères dans le code
constructeur. Les adresses de relâchement retenues sont :

| Canal logiciel | Octet | Adresse fader |
|---:|---|---|
| 0 | `d0` | `0x8455` |
| 1 | `d1` | `0x9d3a` |
| 2 | `d2` | `0x8c64` |
| 3 | `d3` | `0x849b` |
| 4 | `d4` | `0x8aa0` |
| 5 | `d5` | `0xa00f` |
| 6 | `d6` | `0x8883` |
| 7 | `d7` | `0x8941` |

La preuve initiale lit les huit adresses et exige les huit valeurs exactes,
un cache tactile neutre et un mode normal. Seulement ensuite, le pilote lit
`0x8459=c0` puis `0x8455=d0`. Enfin, les lectures de code ajoutent les huit
lectures de relâchement dans la même enveloppe Ethernet.

Un bloc maximal de 12 octets produit `5 + 21×12 = 257` octets série.
Les huit commandes unitaires de relâchement en produisent `8×26 = 208`.
Le total, **465 octets**, reste dans les 488 cases de données du tampon RX.
Les fenêtres RAM sont découpées à la fin du tampon et à 256 octets maximum.
Le compteur de débordements et le producteur sont contrôlés avant/après copie.

Les champs RAM nommés de `firmware_probe.py` acceptent désormais les lots
`A/M` de 1 à 16, déjà éprouvés pour le code `comm` et RX. Les adresses et
longueurs des champs restent fixes. Cela réduit la durée des snapshots ;
**ils restent non atomiques**. Les essais ci-dessous valident aussi ces lots
sur les en-têtes RX, le mode, le cache tactile et le compteur d'erreurs.

## Observations réseau

| Essai | Début UTC | Valeurs demandées | Erreurs avant → après | Résultat |
|---|---|---|---|---|
| `live-fader-release-proof-1` | 22:10:20 | Huit relâchements | 80 → 112 | `d0 d1 d2 d3 d4 d5 d6 d7` reconstruits |
| `live-fader-touch-pair-1` | 22:10:24 | Toucher puis relâchement du canal 0 | 112 → 120 | `c0 d0`, cache final nul |
| `live-fader-neutralized-code-1` | 22:10:25 | `0x8450–0x845b` puis huit relâchements | 120 → 174 | Code conforme à la référence |
| `live-fader-neutralized-code-2` | 22:10:28 | Même plan | 174 → 228 | Résultat identique |

Dans le PCAP `request/traffic.pcap` de la paire, les trames console → hôte
**5 et 9** contiennent `90 09 40` puis `90 09 00`. Aucun geste humain n'a été
requis pour produire ces événements. Dans les deux essais de code, les trames
11, 15 et 19 contiennent un relâchement canal 0, un relâchement canal 7 et un
toucher canal 0 ; les trames 27, 31, 35, 39, 43, 47, 51 et 55 portent les huit
relâchements ajoutés. Les doublons éventuels doivent être distingués par leur
séquence, pas comptés comme de nouveaux gestes.

Les deux lectures du bloc restituent :
`00 04 40 00 4e d0 4c df 38 c0 4e 74`. Le producteur avance de 465 modulo 488,
avec bouclage réel dans les deux cas ; le consommateur reste deux octets derrière
jusqu'à l'interrogation de version suivante. Les préalables du bloc suivant
exigent à nouveau une file vide. Toucher nul et mode zéro sont vérifiés après
chacun des quatre essais. Les compteurs de pertes socket et de débordements RX
restent nuls dans leurs rapports.

Une réponse diagnostic principale `f0 13 00 70 00 55 f7` apparaît également
en trame 7 de la première preuve de relâchement. Son origine n'est pas établie.
Elle est conservée dans l'audit et ne sert pas de preuve d'une lecture fader.
Les essais suivants ne reproduisent pas cette réponse dans leur capture de
requête. Ne pas effacer cet écart ni lui attribuer une cause sans preuve.

## Acquisition complète préparée

- [fader_serial_probe.py](../tools/fader_serial_probe.py) construit les plans,
  vérifie le flux conservé dans RX et l'état avant/après. Il garde une seule
  requête en attente et ne la réémet pas automatiquement.
- [audit_fader_serial.py](../tools/audit_fader_serial.py) reconstruit les octets
  depuis les PCAP RAM et vérifie chaque relâchement avec son propre parseur.
- [fader_archive.py](../tools/fader_archive.py) impose les quatre références
  constructeur par taille et SHA-256. Il prévoit **964 blocs par passage**,
  soit 11 546 octets, avec deux passages par défaut. Chaque bloc est audité
  immédiatement et comparé à la référence. Les résultats partiels sont
  conservés avant tout arrêt ; une divergence stoppe la campagne.

L'aperçu ne touche ni le réseau ni les services :

```bash
python3 tools/fader_archive.py
```

Acquisition complète, à réserver à la console 1.37 concernée et à une période
de repos, sans Ardour actif ni manipulation de la surface :

```bash
python3 tools/fader_archive.py --send \
  --reference work/firmware-research-20260920/extracted \
  --output work/nouvelle-archive-fader
```

Cette commande vérifie l'état réel de la passerelle, l'arrête, prend son verrou,
puis la relance dans `finally`. Le pointeur reste actif et attend la reprise.
Les captures et un manifeste actualisé permettent de suivre les blocs validés.
Après interruption ou erreur, examiner le manifeste et la récupération ; ne
pas relancer aveuglément. `SIGTERM` et Ctrl+C suivent le chemin de récupération.

Les mesures de ces petits essais suggèrent environ 84 minutes pour deux
passages au même rythme ; c'est une estimation, pas une durée d'acquisition
complète mesurée. Aucun résultat complet n'est revendiqué par cette préparation.

## Conservation et portée

Le manifeste public identifie l'archive privée des quatre essais, les outils
utilisés, les désassemblages pertinents, les tests et l'état des services après
relance. Les copies restent sur la même machine. Les programmes constructeur
et PCAP bruts restent hors Git public ; outils, conclusions et empreintes y sont.

La suite locale passe **394 tests en 80,220 s**, dont les contrôles de plage,
de bouclage, de récupération, d'audit et d'arrêt sur divergence. Compilation
Python, inventaire du mapping en mode `--check` et contrôle du diff passent.
Après les essais : passerelle PID 637686 Online, pointeur PID 622060 raccordé
au même démon, aucun défaut déclaré ; Ardour reste fermé/attendu.

La réussite concerne les octets, les événements réseau et le cache tactile du
relais. Ce n'est ni une validation de mouvement moteur, ni une mesure d'audio,
ni une sauvegarde restaurable de toute la console. Bootstrap, calibration,
EEPROM, trous mémoire et restauration matérielle restent des sujets distincts.
