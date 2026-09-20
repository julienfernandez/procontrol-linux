# Mémoire technique du projet Open ProControl

Ce document est le point d'entrée du retour d'expérience conservé dans Git.
Il répond à la demande de conserver les découvertes, les erreurs, les méthodes
et les preuves dans le projet lui-même, pour permettre sa reprise et sa
transmission. État consolidé le **20 septembre 2026**.

Les rapports datés font foi pour leurs expériences respectives. Un ancien PID,
nombre de tests ou réglage décrit un instantané. Pour connaître le fonctionnement
actuel, consulter la [carte fonctionnelle](control-map.md), les
[guides](README.md) et l'état réel des services.

## État de l'exploration interne

| Sujet | Acquis et niveau de preuve | Source à reprendre |
|---|---|---|
| Firmware constructeur | Deux ressources `comm` et `fader` 1.37 extraites, contrôlées et reproductibles ; analyse statique | [Origine, extraction et adresses](firmware-research-2026-09-20.md), [empreintes](firmware-research-2026-09-20.json) |
| Diagnostic du processeur principal | Version `COMv1.37` et premières lectures confirmées sur la console, avec captures et répétitions | [Cinq expériences réseau](firmware-network-validation-2026-09-20.md), [preuves](firmware-network-validation-2026-09-20.json) |
| Programme de communication installé | Les 63 768 octets adressés par l'image `comm` ont été lus deux fois et comparés au constructeur ; audit indépendant des 504 PCAP | [Lecture complète](comm-firmware-readback-2026-09-20.md), [manifeste de preuves](comm-firmware-readback-2026-09-20.json) |
| Relais vers le processeur des faders | Chemins aller/retour retrouvés dans le code ; filtre des réponses identifié ; aucune nouvelle requête `70 01` envoyée dans cette étude | [Analyse des faders](fader-diagnostic-analysis-2026-09-20.md), [provenance](fader-diagnostic-analysis-2026-09-20.json) |
| Sauvegarde restaurable de toute l'unité | Encore ouverte : démarrage, trous mémoire, EEPROM, calibration, programme installé des faders et restauration matérielle restent à établir | [Périmètre exact de la conservation](comm-firmware-readback-2026-09-20.md#périmètre-réel-de-la-sauvegarde) |

La concordance du programme `comm` donne une base solide pour interpréter ce
code. Elle ne valide pas automatiquement les autres mémoires ni l'image
effectivement installée dans le processeur des faders. Les paramètres moteurs
et la calibration n'ont pas été modifiés pendant ces recherches.

## Enseignements à conserver

### Observer les échanges et identifier la preuve

- Un ACK confirme une transaction réseau, pas l'allumage d'un afficheur, la
  sensation d'un fader ou un résultat audio. Garder séparées capture, réponse
  applicative, confirmation physique, validation logicielle et endurance.
- Une table Control|24, un commentaire de code ou une photo ne suffisent pas à
  attribuer un code à la ProControl originale. Documenter le modèle, la source
  exacte, le sens des trames et les gestes contrôlés.
- Analyser les PCAP après clôture, conserver leurs SHA-256, numéros de trames,
  statistiques de pertes et écarts au scénario. Une confirmation dans le chat
  n'est pas l'heure du geste. Les anciens PCAP avec horodatage corrigé gardent
  leur original et une explication du dérivé.
- L'octet brut d'une réponse mémoire `comm` peut être `00`, `80` ou `f7`.
  Découper par lignes, par statut MIDI ou au premier `f7` détruit l'information.
  Le lecteur spécialisé vérifie le format complet, l'adresse et les deux
  représentations de la valeur.

Sources : [protocole](protocol.md), [captures Linux](capture-linux.md),
[afficheurs](displays.md), [premières lectures mémoire](firmware-network-validation-2026-09-20.md).

### Garder un seul propriétaire du réseau

- Un seul émetteur Ethernet détient le verrou du démon. Les outils autonomes
  d'acquisition prennent ce même verrou avant d'ouvrir leurs sockets.
- Un fichier `status.json` ancien ne prouve pas qu'un processus tourne. Vérifier
  PID, verrou, fraîcheur, état Online, réponse Ardour et erreurs avant et après
  intervention. Les changements de documentation ne nécessitent pas d'arrêt.
- Une expérience exclusive suspend le relais des gestes vers Ardour. La mener
  pendant une période compatible et garantir la relance normale même en cas
  d'échec. Ne pas confondre la fin d'un outil avec la reprise de tous les services.
- Les maintiens de session sont indépendants des ACK de sorties. Une reprise
  renvoie les états actuels ; elle ne rejoue pas d'anciennes positions moteur.

Sources : [session](session-reference.md), [helper sans root](rootless-launch.md),
[reprise des retours](feedback-recovery.md), [ordonnancement](jog-motor-scheduling.md),
[reprise du pointeur](pointer-recovery-2026-09-20.md).

### Relier les défauts à leur vraie chaîne de données

- Pour le jog et le compteur, suivre position audible, JACK/Link, OSC et rendu
  console. Une divergence ne s'explique pas automatiquement par un mode
  d'affichage mal choisi. Les correctifs et leurs limites sont dans le
  [rapport jog / pool d'événements](jog-link-stability-2026-09-20.md).
- Un crash Ardour nécessite sa trace et la version du code natif. Un allocateur
  ASan préchargé ne rend pas un module instrumenté. Conserver le patch, son ordre
  d'application, les sources et les contrôles de reconstruction ; voir
  [stabilité OSC](stability-2026-09-17.md) et [reconstruction native](../native/README.md).
- Le retour moteur pendant le toucher doit respecter la position physique
  observée. La validation utilisateur du correctif a une valeur distincte
  des ACK ; voir [écho tactile](fader-echo-2026-09-14.md).
- Un inventaire d'actions ne compte pas les boutons physiquement validés.
  Examiner chaque mode et distinguer entrée consommée et action produite ; voir
  [revue du mapping](review-2026-09-20.md) et [inventaire](mapping-backlog.md).
- Conserver le besoin musical exprimé avec son état de livraison : EQ/DYN
  ouvrent et, avec l'extension fournie, créent le processeur adapté ; la
  [bibliothèque DSP](curated-plugins.md) reste une sélection de huit effets.
  Les essais sur les descripteurs ne prouvent pas à eux seuls le rendu physique.

### Apprendre aussi des impasses

| Problème rencontré | Correction ou enseignement | Détail conservé |
|---|---|---|
| Pages anciennes indisponibles, téléchargement partiel tronqué | Récupération HTTP Range avec bornes, CRC et SHA fixés ; aucune conclusion depuis un membre ZIP incomplet | [Recherche initiale, §7](firmware-research-2026-09-20.md#7-retours-dexpérience-pratiques) |
| Désassemblage Capstone ambigu sur certains index m68k | Contre-vérifier les chemins ciblés avec GNU objdump ; distinguer tables et instructions | [Méthode statique](firmware-research-2026-09-20.md#6-reproduire-la-récupération-et-lanalyse) |
| Délai version annoncé après l'ACK de réponse | Utiliser les timestamps requête/réponse du PCAP et nommer la mesure | [Validation réseau](firmware-network-validation-2026-09-20.md) |
| Réponses diagnostic concaténées et doublons tardifs | Parser les enveloppes entières, dédupliquer par séquence et conserver les répétitions dans les preuves | [Lecture par lots et audit](comm-firmware-readback-2026-09-20.md) |
| Faux appareil de test supposant un ordre ACK/requête | Corriger le modèle du test ; ne pas imposer au protocole réel un ordre non observé | [Retour d'expérience des tests](comm-firmware-readback-2026-09-20.md#conservation-et-tests) |
| Clone d'un bundle sans HEAD distant | Donner explicitement `--branch main` ; vérifier le commit après restauration | [Reprise Git hors ligne](comm-firmware-readback-2026-09-20.md#conservation-et-tests) |
| Première lecture inversée d'une branche du filtre série des faders | Le filtre rejette le bit 7 positionné ; il ne le requiert pas. Relire les deux branches avant d'inventer un encodage | [Correction et conséquence](fader-diagnostic-analysis-2026-09-20.md#filtre-des-réponses-et-correction-dinterprétation) |

## Ce que l'on conserve et où

**Dans Git public** : code, tests, fixtures minimales, protocoles observés,
procédures, rapports datés, résultats négatifs, provenance, empreintes, limites
et prochains contrôles. Les références constructeur ne deviennent pas GPL
parce qu'elles servent à cette recherche.

**Dans les archives locales séparées** : fichiers constructeur, désassemblages
complets, PCAP bruts, sessions et sauvegardes propres au studio. Les rapports
versionnés indiquent comment les identifier, les vérifier et, lorsque c'est
possible, les reproduire. Une empreinte identifie une preuve ; elle ne remplace
pas le fichier. Les exclusions de `.gitignore` restent en place.

Le dossier de conservation utilisé le 20 septembre est :

```text
~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/
```

Il contient l'archive privée des preuves `comm`, son manifeste, un bundle Git
au commit `b9172cb` et le complément d'analyse des faders décrit dans son rapport.
Le bundle `b9172cb` reste un instantané : il n'inclut pas les ajouts ultérieurs.
Pour préserver une nouvelle révision du dépôt après commit :

```bash
# Choisir un nom nouveau ; conserver les instantanés précédents.
git bundle create /chemin/vers/un-support/open-procontrol-REVISION.bundle main
git bundle verify /chemin/vers/un-support/open-procontrol-REVISION.bundle
git clone --branch main /chemin/vers/un-support/open-procontrol-REVISION.bundle /chemin/nouveau-clone
git -C /chemin/nouveau-clone rev-parse HEAD
```

Les copies vérifiées à ce jour restent sur la même machine. La copie sur un
support indépendant et une restauration matérielle restent à réaliser.

## Règle de continuité

Pour chaque nouvelle expérience ou correction :

1. Ouvrir un rapport daté à partir de la [fiche d'expérience](experiment-template.md).
   Indiquer la question, l'état initial, les versions et la méthode avant les résultats.
2. Conserver les commandes utiles, références, adresses, captures ou sorties
   pertinentes avec leurs empreintes. Inclure les essais interrompus et les
   hypothèses abandonnées lorsqu'ils évitent de répéter une erreur.
3. Nommer le niveau de preuve de chaque conclusion, l'état final des services,
   les limites et la prochaine expérience discriminante. Ne pas transformer une
   hypothèse remplacée en observation historique.
4. Lier le rapport depuis l'[index](README.md) et actualiser ce document lorsque
   l'état des connaissances change. Ajouter un renvoi dans les rapports anciens
   pour signaler la suite, sans réécrire leurs résultats.
5. Versionner outils, tests et documentation ensemble, vérifier le diff destiné
   à la publication, puis conserver le commit et le résultat CI dans l'historique
   de publication. Éviter une affirmation « validé » sans préciser ce qui l'a été.

Cette règle s'applique aussi lorsque l'expérience échoue ou reste incomplète.
Le dépôt doit permettre à une autre personne de reprendre le travail sans
reconstituer la conversation.
