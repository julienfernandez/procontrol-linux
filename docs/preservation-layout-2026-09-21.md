# Démarrage, réglages persistants et calibration : cartographie statique

Analyse du **21 septembre 2026, heure de Paris**, sur les images constructeur
`comm` et `fader` 1.37. Aucun nouvel accès à la console n'a été effectué pour
cette étude : la double acquisition des faders occupait toujours le réseau.
Le [manifeste](preservation-layout-2026-09-21.json) identifie les fichiers,
les adresses étudiées, la référence constructeur et l'archive privée.

**Résultat :** l'image de mise à jour omet plusieurs zones utiles à une
restauration. Le code `comm` lit un bloc réseau de 10 octets à `0x34000`,
charge 88 octets de réglages depuis `0x3c000`, et contrôle une somme de
programme conservée à `0x30000`. Le code fader consulte une somme à `0xfffe`.
Le contenu réel de ces zones reste à acquérir ; ce rapport ne les sauvegarde pas.

## Carte déduite du démarrage

Les deux points d'entrée (`comm: 0x2b602`, `fader: 0xa470`) établissent
`DFC = 7`, puis écrivent `0x80000001` à `0x3ff00` avec `MOVES`.
Cette séquence concorde avec le registre MBAR du
[manuel MC68340 publié par NXP](https://www.nxp.com/docs/en/data-sheet/MC68340UM.pdf),
§3.4.3 et §4.3.1. Les registres internes sont ainsi placés à `0x80000000`.
Les paires masque/base aux offsets `0x40/0x44` et `0x48/0x4c` concordent
également avec ses sélecteurs mémoire (§4.3.4, pages imprimées 4-30 à 4-32).

Les bits de masque d'adresse `AM31–AM8` déterminent la plage sélectionnée ;
les huit bits bas portent d'autres attributs. Le décodage ci-dessous porte
sur les valeurs écrites par le programme, pas sur une mesure des puces :

| Processeur / sélecteur | Masque écrit | Base écrite | Plage configurée, inclusive | Interprétation issue du code |
|---|---|---|---|---|
| comm / CS0 | `0x0003fffe` | `0x00000001` | `0x00000–0x3ffff` | Espace des images et de la flash |
| comm / CS1 | `0x0003fff1` | `0x00040001` | `0x40000–0x7ffff` | RAM, également parcourue par le test de démarrage |
| fader / CS0 | `0x0000fffe` | `0x00000001` | `0x0000–0xffff` | Espace du démarrage et du programme, nommé EEPROM dans les messages |
| fader / CS1 | `0x00007ff1` | `0x00040001` | `0x40000–0x47fff` | RAM, également parcourue par le test de démarrage |

Il s'agit d'une architecture **compatible avec ce modèle de registres**.
Le marquage physique et la variante exacte des processeurs restent inconnus.
Une plage de sélection ne prouve ni la capacité physique du composant raccordé,
ni l'absence d'alias, ni le contenu de tous ses octets. Elle ne devient pas une
autorisation de lecture de registres matériels ou de balayage arbitraire.

## Le démarrage manque encore aux archives

Les commandes de redémarrage sautent à `0x400` : routines `comm: 0x22084`
et `fader: 0x9152`. Elles n'ont pas été exécutées. Les images récupérées ne
contiennent aucune donnée à cette adresse.

Les routines d'inspection du démarrage (`comm: 0x21b84`, `fader: 0x846e`)
utilisent une somme des octets modulo 65 536. Les helpers `0x2a9ca` et
`0xa0fe` avancent bien d'**un octet**, malgré leur résultat sur 16 bits.

| Opération visible dans le code | comm | fader |
|---|---|---|
| Plage sommée pour le démarrage | `0x00000–0x0ffff` | `0x0000–0x3fff` |
| Plage sommée pour le programme téléchargé | `0x20000–0x2ffff` | `0x8000–0xbfff` |
| Mot de contrôle du programme | `0x30000–0x30001` | `0xfffe–0xffff` |

Les plages sommées incluent des adresses absentes des ressources Intel HEX.
Il serait donc incorrect de calculer une preuve de restauration en remplissant
ces trous par des zéros ou `ff` supposés. La couverture de l'image de mise à
jour et la couverture des zones contrôlées au démarrage sont différentes.
La référence « Bootstrap Version » trouvée dans le programme ne prouve pas
que le bootstrap réellement installé possède la même version.

## Deux blocs persistants de communication

### Réseau : 10 octets à `0x34000`

`0x2058a` copie 10 octets depuis la flash dans un tampon. Le mot big-endian
à l'offset 8 doit être non nul et égal à la somme modulo 65 536 des huit
premiers octets. `0x2054e` est le chemin d'écriture correspondant ; il a été
étudié hors ligne, sans être appelé.

Le code d'initialisation à `0x297a6` utilise ce bloc, ou une valeur par défaut
si son contrôle échoue. Les six premiers octets alimentent la configuration
d'adresse Ethernet, et les deux suivants le type de protocole. Les constantes
par défaut à `0x2ec58` sont `00:a0:7e:a0:00:00` et `0x885f`. Les deux derniers
octets de l'adresse par défaut peuvent être dérivés d'un identifiant matériel
par `0x24c6e`. **Ces constantes ne sont pas les valeurs lues sur notre unité.**

`0x24c6e` réalise une transaction série sur le bit 0 du port à `0x80000011`,
émet `0x33`, reçoit huit octets, les vérifie puis restitue six octets.
Le composant physique et son identifiant complet restent à établir. Le bloc
flash réseau ne constitue donc pas, à lui seul, une sauvegarde de cette identité.

### Réglages Utility : 88 octets à `0x3c000`

`0x20536` copie `0x58` octets vers le miroir RAM `0x40000–0x40057`.
`0x2050c` effectue la sauvegarde inverse après effacement du secteur ; aucune
de ces opérations persistantes n'a été déclenchée par cette étude.

L'initialisation à `0x26d8c` prépare les valeurs par défaut, puis compare les
huit premiers octets du miroir avec ceux de la flash avant de charger le bloc.
Le marqueur préparé est `v1.37` suivi de trois zéros. Des chemins du menu Utility,
dont le retour aux valeurs d'usine, utilisent la sauvegarde `0x2050c`.
La signification de chaque champ n'est pas encore entièrement cartographiée.
Le miroir RAM est susceptible de diverger du bloc sauvegardé : conserver les
deux séparément lors d'une future observation.

## Calibration des faders : un état calculé en RAM

L'initialisation `0x8f10` prépare huit structures de 32 octets à partir de
`0x4402a`. Le démarrage appelle ensuite `0x8dfc` depuis `0x9b3c`. Cette routine
effectue une calibration et écrit les résultats dans ces structures, notamment
une échelle à l'offset `0x00`, une étendue à `0x10` et un indicateur à `0x1b`.
Le périmètre des huit structures est `0x4402a–0x44129`.

Ce chemin étaye une calibration reconstruite à l'exécution. Il ne prouve pas
l'absence de toute autre donnée de calibration persistante dans le matériel.
Une future copie RAM devra être datée et qualifiée d'instantané volatil.
Aucune nouvelle calibration ni modification de gain moteur n'a été exécutée.

Autre piège de lecture : les seuils initialisés à 89 et 115 aux adresses
`0x44012` et `0x44014` ne sont pas directement des pourcentages. Les handlers
`0x951c` et `0x9534` convertissent leur argument par multiplication par 128,
puis division par 100. Les unités doivent être vérifiées avant toute exposition
d'un réglage dans Open ProControl.

## Prochaine observation discriminante

Après la clôture et l'audit de la double acquisition en cours, commencer par
des lectures bornées du contexte `comm` : vecteurs `0x00000–0x00007`, mot de
contrôle `0x30000–0x30001`, bloc réseau de 10 octets, bloc Utility de 88 octets
et son miroir RAM. Répéter, capturer et auditer les transactions avant toute
extension. Les outils actuels n'autorisent pas encore ces nouvelles plages.

L'extension est préparée séparément au commit `cab0e24`, sur la branche
`research/preservation-reads`. Cinq tests spécifiques et 21 tests du lecteur
passent sur cette copie : bornes exactes, lecture simulée de l'adresse zéro,
bloc de 88 octets, aperçu sans socket, audit indépendant et rejet de captures
incohérentes. Cette validation est logicielle ; aucun de ces champs nouveaux
n'a encore été interrogé sur la console.

La copie est `work/preservation-read-stage`. **Ne pas y lancer `--send`** :
son chemin de runtime et son verrou seraient ceux de la copie. Après la fin
du collecteur actif et la vérification des sources, intégrer ce commit dans
le dépôt principal, puis effectuer les essais depuis sa racine avec son
verrou habituel et une reprise de passerelle garantie.

La [procédure préparée de double lecture des petits blocs](comm-preservation-procedure.md)
automatise ensuite les cinq champs et leur audit indépendant, tout en conservant
les contenus invalides ou différents comme observations. Sa présence ne signifie
pas que l'essai matériel a déjà eu lieu.

L'étude des faders devra ensuite distinguer image de démarrage, contrôle de
programme et instantané de calibration, tout en conservant les huit lectures
de relâchement par bloc. Aucun de ces travaux n'est déclaré acquis ici.
La [procédure fader préparée](fader-preservation-procedure.md) couvre désormais
les vecteurs du bootstrap, le mot de contrôle, les seuils et les huit structures
RAM. Ses tests restent distincts de l'observation matérielle à venir.

## Reproduire l'analyse et conserver les preuves

Extraire les images selon la [procédure constructeur](firmware-research-2026-09-20.md#6-reproduire-la-récupération-et-lanalyse),
vérifier leurs SHA-256, puis lire les fenêtres indiquées dans le manifeste :

```bash
m68k-linux-gnu-objdump -D -b binary -m m68k:68020 \
  --adjust-vma=0x20400 --start-address=0x2050c --stop-address=0x20650 \
  work/firmware-research-20260920/extracted/CODE-26-00020400.bin
```

Pour `fader`, employer la base `0x8400` et `CODE-27-00008400.bin`.
Le mode de désassemblage ne suffit pas à identifier le processeur. Un parcours
linéaire traduit aussi les chaînes et tables en fausses instructions : suivre
les appels, les branches et les arguments avant d'attribuer une fonction.

Le complément privé contient les images étudiées, fenêtres de désassemblage,
manuel NXP, pages de registres rendues, données d'analyse et script de
constitution. Son inventaire et ses empreintes sont dans le manifeste public.
Il ne contient aucune nouvelle capture de console. La copie vérifiée reste
sur la même machine, dans `~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`.
