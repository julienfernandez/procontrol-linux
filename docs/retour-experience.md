# Mémoire technique du projet Open ProControl

Ce document est le point d'entrée du retour d'expérience conservé dans Git.
Il répond à la demande de conserver les découvertes, les erreurs, les méthodes
et les preuves dans le projet lui-même, pour permettre sa reprise et sa
transmission. État consolidé le **21 septembre 2026**.

Les rapports datés font foi pour leurs expériences respectives. Un ancien PID,
nombre de tests ou réglage décrit un instantané. Pour connaître le fonctionnement
actuel, consulter la [carte fonctionnelle](control-map.md), les
[guides](README.md) et l'état réel des services.

## État de l'exploration interne

| Sujet | Acquis et niveau de preuve | Source à reprendre |
|---|---|---|
| Firmware constructeur | Deux ressources `comm` et `fader` 1.37 extraites, contrôlées et reproductibles ; analyse statique | [Origine, extraction et adresses](firmware-research-2026-09-20.md), [empreintes](firmware-research-2026-09-20.json) |
| Diagnostic du processeur principal | Version `COMv1.37` et premières lectures confirmées sur la console, avec captures et répétitions | [Cinq expériences réseau](firmware-network-validation-2026-09-20.md), [preuves](firmware-network-validation-2026-09-20.json) |
| Programme de communication installé | 65 536 octets couverts par deux acquisitions cumulatives, segments et compléments audités depuis 514 PCAP ; les deux images sont identiques et leur somme correspond au mot stocké `0xda49` | [Plage complète du programme](comm-application-complete-2026-09-21.md), [manifeste de preuves](comm-application-complete-2026-09-21.json) |
| Relais vers le processeur des faders | Quatre réponses directes `FDRv1.37` ; cache et files série lus dans la RAM de `comm`. Premier essai incomplet conservé ; cette étape précédait l'acquisition du programme | [Validation réseau](fader-network-validation-2026-09-20.md), [preuves](fader-network-validation-2026-09-20.json), [analyse statique](fader-diagnostic-analysis-2026-09-20.md) |
| Premiers octets installés des faders | Huit octets de vecteurs `0x8000–0x8007` lus trois fois via les données conservées dans RX, identiques au constructeur ; audit de 55 PCAP, bouclage réel inclus. Étape désormais complétée par la première passe entière | [Lecture brute et effets du filtre](fader-raw-readback-2026-09-20.md), [empreintes et résultats](fader-raw-readback-2026-09-20.json) |
| Effets tactiles des lectures fader | Paire `c0/d0` observée sur le réseau, huit lectures `d0–d7` vérifiées et cache tactile neutre après deux lectures d'un bloc de code ; méthode ensuite appliquée aux 1 928 blocs de la double acquisition complète | [Neutralisation et table de commandes](fader-touch-recovery-2026-09-21.md), [preuves](fader-touch-recovery-2026-09-21.json) |
| Programme fader installé | Deux passes de 11 546 octets identiques au constructeur et entre elles ; 30 584 captures auditées, pertes socket nulles. Archive privée complète vérifiée | [Double acquisition entière](fader-firmware-readback-2026-09-21.md), [empreintes et couverture](fader-firmware-readback-2026-09-21.json) |
| Démarrage et réglages persistants | Deux lectures des vecteurs, contrôles et petits blocs comm/fader réalisées ; réglages persistants identiques, un octet RAM variable conservé. La somme complète comm est vérifiée ; celle du fader reste à établir | [Lectures réelles et écart RAM](preservation-fields-validation-2026-09-21.md), [audits et empreintes](preservation-fields-validation-2026-09-21.json) |
| Sauvegarde restaurable de toute l'unité | Encore ouverte : bootstrap complet, trous mémoire, autres réglages éventuels et restauration matérielle restent à établir | [Périmètre exact de la conservation](comm-firmware-readback-2026-09-20.md#périmètre-réel-de-la-sauvegarde) |
| Accélération des lectures RX | Deux pilotes de huit blocs connus : environ 24 % de temps en moins par bloc avec des lots de 32 ; octets conformes, aucun débordement observé, touchers neutres. Défaut 16 conservé ; aucune endurance ni latence musicale établie | [Conditions, mesures et restitution des preuves](fader-rx-benchmark-validation-2026-09-21.md), [manifeste](fader-rx-benchmark-validation-2026-09-21.json) |

La concordance des deux passes `comm` et des deux passes fader donne une
base pour interpréter leurs segments de code. Elle ne valide pas les autres
mémoires ou une restauration matérielle. Les paramètres
moteurs et la calibration n'ont pas été modifiés pendant ces recherches.

## Enseignements à conserver

### Observer les échanges et identifier la preuve

- Mesurer séparément les lectures RX et la durée du bloc complet : presque
  doubler la vitesse d'une phase ne divise pas par deux toute la collecte.
  Conserver les tailles de fenêtres et les tâches concurrentes ; le premier
  pilote RX chevauchait les tests logiciels, le second a été répété après
  leur fin. Voir les [deux campagnes RX](fader-rx-benchmark-validation-2026-09-21.md).

- Une RAM peut varier entre deux lectures réussies : conserver les deux snapshots et
  localiser l’écart. Sur les huit structures fader, un octet a changé alors que
  les champs de calibration décodés sont identiques ; cela ne constitue ni
  une perte réseau ni une preuve de mauvaise calibration. Voir les
  [lectures matérielles de préservation](preservation-fields-validation-2026-09-21.md).
- Une allocation de file de 512 octets inclut 24 octets d'en-tête ; ses
  488 positions n'acceptent que 487 octets non consommés, un emplacement
  distinguant plein et vide. Vérifier le compteur de débordement et les
  réponses réelles avant d'augmenter un lot. Voir le
  [pilote comm 16/32 et ses limites](comm-batch-benchmark.md).
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
- Un parseur qui refuse une réponse peut laisser ses octets dans un tampon
  circulaire. La consommation avance les pointeurs sans forcément effacer les
  données. Vérifier les bornes, le bouclage et la stabilité du producteur pendant
  la copie ; ne pas appeler un snapshot RAM non atomique une image figée.
- Une commande de lecture peut modifier des pointeurs volatils et des compteurs,
  voire produire des événements mal interprétés. Pour les faders, distinguer
  valeurs récupérées, erreurs du filtre et état tactile. Le premier pilote reste
  borné aux vecteurs ; le nouveau lecteur ajoute des relâchements vérifiés à
  chaque bloc. Voir la [lecture brute](fader-raw-readback-2026-09-20.md) et la
  [neutralisation des faux touchers](fader-touch-recovery-2026-09-21.md).
- La concordance des octets lus, la couverture de toutes les adresses prévues
  et deux acquisitions distinctes sont trois propriétés à vérifier séparément.
  Un préfixe conforme n'est pas une archive complète. Figer et conserver les
  octets du manifeste utilisé pendant une campagne longue : son hash seul ne
  suffit pas lorsque le collecteur remplace ce fichier après chaque bloc.
  Voir le [vérificateur d'archive fader](fader-archive-verification.md).

Sources : [protocole](protocol.md), [captures Linux](capture-linux.md),
[afficheurs](displays.md), [premières lectures mémoire](firmware-network-validation-2026-09-20.md).

### Garder un seul propriétaire du réseau

- Un seul émetteur Ethernet détient le verrou du démon. Les outils autonomes
  d'acquisition prennent ce même verrou avant d'ouvrir leurs sockets.
- Un fichier `status.json` ancien ne prouve pas qu'un processus tourne. Vérifier
  PID, verrou, fraîcheur, état Online, réponse Ardour et erreurs avant et après
  intervention. Les changements de documentation ne nécessitent pas d'arrêt.
- Après transmission du verrou au démon, `/proc/locks` peut encore afficher
  le PID du lanceur terminé. Vérifier le descripteur et son `fdinfo` dans le
  processus actif avant de conclure à un verrou abandonné ; voir
  [l'observation et sa méthode de vérification](fader-archive-verification.md#identifier-le-processus-qui-détient-le-réseau).
- Le verrou partagé peut appartenir au lecteur de firmware. Dans cet état,
  `running: true` ne désigne pas nécessairement le démon, et l'inventaire
  historique des processus de capture peut omettre le lecteur Python.
  Identifier le propriétaire réel avant toute relance ; voir le
  [relevé et la procédure de surveillance](fader-archive-verification.md#identifier-le-processus-qui-détient-le-réseau).
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
| Première requête fader acquittée sans réponse | Conserver l'échec ; vérifier ensuite `COM` dans la même session. Succès reproduit, cause initiale encore ouverte | [Diagnostic réel des faders](fader-network-validation-2026-09-20.md) |
| Lecture fader contenant `00` ou un bit 7 positionné | Réponse directe filtrée, mais octets conservés dans RX et lus via `comm`. Ne pas multiplier les retries ; le compteur d'erreurs ne compte pas des paquets perdus | [Expérience et limite tactile](fader-raw-readback-2026-09-20.md) |
| Supposer qu'un moniteur possède les commandes habituelles de dump | Relire la table et l'aide du processeur exact : `D` règle un paramètre et `A/M` agissent sur les faders ; seule la famille `U/Q/q` sert ici aux lectures | [Commandes et preuve tactile](fader-touch-recovery-2026-09-21.md) |
| Audit d'un préfixe avec seulement le hash du manifeste évolutif | Conserver une copie exacte avant la lecture des preuves ; le premier instantané a été récupéré et vérifié par son hash, puis le CLI corrigé | [Instantanés et couverture](fader-archive-verification.md) |
| Assimiler image de mise à jour et contenu restaurable | Les sommes du démarrage portent aussi sur des trous absents d'Intel HEX ; des réglages et mots de contrôle résident hors image. Ne pas inventer leur remplissage | [Carte de préservation](preservation-layout-2026-09-21.md) |
| Lire une valeur brute comme un pourcentage | Les seuils fader passent par un facteur 128/100 ; identifier la conversion et les unités avant de proposer un réglage | [État de calibration et seuils](preservation-layout-2026-09-21.md#calibration-des-faders--un-état-calculé-en-ram) |
| Assimiler une réponse mémoire à une lecture atomique | Le formateur fader lit séparément la valeur hexadécimale et le caractère brut ; une modification intermédiaire de RAM peut les faire diverger. Conserver et refuser la réponse incohérente sans inventer une perte réseau | [Deux accès mémoire par réponse](fader-preservation-progress-2026-09-21.md#une-réponse-fader-peut-contenir-deux-lectures-de-ram) |
| Optimiser seulement le délai visible | La relecture RX représente 48,72 % du temps des blocs du premier passage, contre 9,72 % pour la requête et son attente. Mesurer toutes les étapes, y compris le préalable comm imbriqué | [Mesures et limites de la comparaison](fader-preservation-progress-2026-09-21.md#mesurer-avant-daccélérer-les-acquisitions-suivantes) |

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
Les étapes suivantes ajoutent des archives distinctes pour les versions réseau
et la lecture des vecteurs fader, ainsi que de nouveaux bundles identifiés par
leur commit. Leurs rapports datés donnent les inventaires et empreintes.
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

Le [rapport du 26 septembre 2026](studio-32-tracks-2026-09-26.md) décrit
la réorganisation du projet par défaut en 16 pistes stéréo MPC nommées
MPC 01-02 à MPC 31-32, suivies de Behringer et MIDI, sans modification des
effets existants. Ces 32 canaux nommés dans le projet ne doivent pas être
confondus avec la liaison USB MPC, observée à 16 canaux dans chaque sens.
Les huit nouvelles paires gardent leurs entrées libres ; copie du projet et
vérifications SHA-256 locales.

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

## 26 septembre 2026 — Submix en vue Master, refus UAC2 à 32 canaux

La vue MASTER FADERS inclut maintenant les bus, après le Master. Le bus
stéréo `MPC SUB 1` reçoit le retour USB 11/12 déjà utilisé par les batteries.
Les 14 sorties stéréo MPC sont préparées mais non activées : le noyau refuse
le masque 32 bits et n'expose pas les attributs de compte explicite. Après un
SIGSEGV de l'application pendant USB → Internal, la liaison 16 canaux et le
XPJ original ont été restaurés. Voir le [rapport et les limites de validation](mpc-submix-master-2026-09-26.md).

## 26 septembre 2026 — Arrêts, reprises et réponses lentes

Un fichier récent ne suffit pas à prouver la présence du worker : vérifier
aussi son verrou avant d'autoriser un routage ou d'afficher des niveaux. Une
reprise automatique en attente doit pouvoir être annulée et doit revérifier
le défaut avant de démarrer. Un gadget créé sans câble connecté appelle une
attente explicite, pas une boucle de préparation. Enfin, un cache partagé
doit dater la fin de sa réponse lente pour ne pas faire patienter chaque
client derrière une nouvelle requête identique. Voir les
[corrections et mesures de la passerelle](gateway-stability-2026-09-26.md).

Le coredump du même jour a révélé un problème natif différent : déconnecter
un signal ne retire pas automatiquement ses callbacks déjà en attente.
Les observateurs OSC utilisent maintenant l'invalidation PBD par génération.
Voir le [rapport natif, les témoins négatifs et les limites de charge](osc-callback-lifetime-2026-09-26.md).
Les erreurs USB voisines ne suffisent pas à établir la cause de ce SIGSEGV.

## 27 septembre 2026 — Graphe, vumètre interne et effets vocaux

Un `pw-dump` invalide ne doit pas être traduit en disparition du matériel :
lecture sans couleurs, validation structurelle et reprises bornées sont
désormais communes au backend et à la supervision. Le port de mesure Ardour
peut apparaître après le processus ; attendre puis vérifier les seuls liens
PCI internes concernés a retiré quatre connexions sans toucher les pistes.
La sortie Behringer a néanmoins produit des resynchronisations pendant la
nouvelle passe : la disparition des messages d'entrée interne ne valide pas
tous les chemins audio. Voir le [rapport daté](studio-vocal-pump-2026-09-27.md).

Les transitions d'horodatage PCM conservent maintenant direction et identité
du processus ; leur compteur n'est pas un compteur de crashs. Le journal de
santé de la passerelle survit à la rotation rapide des traces OSC/Ethernet.
Six profils et presets voix/pumping portent le catalogue à quatorze choix,
avec capacité native 3 et contrôle du contexte vocodeur Surge. Descripteurs,
insertion, non-duplication, fenêtres et réouverture ont été testés ; la
validation auditive et le routage kick/voix restent distincts et en attente.

Deux précautions reproductibles : l'auto-connexion Ardour des nouveaux bus
est différée, donc vérifier leurs destinations exclusives après stabilisation ;
les références Lua aux processeurs à sidechain doivent être libérées avant
de fermer leur session de test. Un coredump du harnais isolé a révélé ce
second cas. Ne pas l'effacer du bilan parce que le processus graphique a
survécu. Trois processus de test ont rencontré cette même famille de pile.
Le preset B.Shapr sauvegardait bien sa courbe, mais son interface
ne recevait les points qu'après activation du DSP.

Le test de signal a aussi révélé deux liaisons muettes malgré leur présence
dans le graphe : les départs internes créés à −inf et les broches sidechain
LV2 LSP non reliées au port externe. Départs à gain unité et mapping explicite
du détecteur ont été ajoutés au constructeur de chaînes ; le mapping LSP est
aussi dans l'insertion native. Mesure isolée après correction : 3,78 dB de
réduction ; couper le modulateur du vocodeur fait perdre 38,81 dB de sortie.
La sauvegarde et la réouverture conservent les broches. Ces mesures ne règlent
pas automatiquement le seuil sur la vraie basse et le vrai kick.

## 27 septembre 2026 — USB 32 canaux : capacité réelle et blocage noyau MPC

Le signalement « 15–16 dernière paire audible » concorde avec les deux PCM
MPC, les descripteurs USB PC et les ports PipeWire : 16 canaux réels, malgré
32 entrées nommées dans Ardour. Le pilote UAC2 est intégré au noyau MPC et
son image installée confirme le refus des masques au-delà de `0x07ffffff` ;
l'option locale `named_channels=0` n'annule pas ce contrôle.

Le backend et la supervision Linux Mint traitent désormais 16/32 canaux et
affichent séparément capacité réelle, entrées attendues et liens raccordés.
Le contrôle préalable refuse une demande 32 sans les attributs nécessaires
du pilote MPC, avant toute écriture. 65 tests ciblés, puis relecture du graphe
réel ; seule la supervision web a redémarré, audio et projet préservés.
**Le transport 32×32 reste non déployé** : le pilote MPC compatible manque.
Voir [preuves, modifications et suite](mpc-usb-32-production-2026-09-27.md).

## 27 septembre 2026 — Neuvième afficheur DSP : Channel / Group

L'ancien test `0x0d..0x14` / `0x2d..0x34` omettait le neuvième afficheur.
Le firmware COMv1.37 archivé accepte les indices DSP **13 à 21 inclus** ;
son chemin texte ignore le bit de ligne pour cette zone. `0x15` et `0x35`
désignent donc le neuvième tampon. En revanche `0x08` / `0x28` sont ignorés.
L'essai négatif `0x28` est confirmé par l'utilisateur malgré 48 ACK.
L'utilisateur confirme aussi le bon fonctionnement matériel de Channel / Group
en test LED / Vegas ; cela ne confirme pas encore notre commande réseau.

Le retour de contexte à `0x35` est installé : piste, mode/bande/page, attente,
ajout en cours, erreur. 63 tests ciblés passent ; Ardour et le fichier de
session sont restés inchangés lors de la relance des trois services.
L’utilisateur confirme ensuite `MPC01-02` au bon endroit : sortie réseau
physiquement validée. Réverb/Delay sur bus et
nouveau mode de départs sur les rotatifs DSP ne sont pas encore implémentés.
Voir [méthode, firmware, captures et limites](channel-group-2026-09-27.md).


## 27 septembre 2026 — zone DSP complète et vumètres web rapides

Suite à la confirmation utilisateur « MPC01-02 ou le nom sélectionné », le neuvième
LCD est utilisé pour modes / pages / attente / A/B. La passe suivante complète CREATE,
SELECT, ENABLE, SUSPEND, INFO, COMPARE et l’éditeur des départs existants de la piste.
Les huit rangées DSP sont incluses dans l’inventaire (310 entrées, 280 reconnues dans
au moins un contexte ; sorties et commandes analogiques ne sont pas de faux boutons
numériques). Aucun nouveau bus d’effet n’a été créé dans la session ouverte.

Le web reprend un thème sombre sobre ; les vumètres quittent le polling général
pour un flux compact indépendant. Mesure réelle avec trois clients : 24,86–24,88 Hz,
422 octets médians ; la source Lua reste à environ 10 Hz. La fluidité du dessin ne
constitue pas une augmentation de la fréquence des mesures audio. Expiration,
cache partagé, pause des onglets masqués et absence de données synthétiques en
production sont vérifiés. Suite générale 508 tests, tests ciblés de revue 21 et
JavaScript réussis. Ardour 173019 et fichier de session conservés ; console Online,
220/220 ACK sans timeout après le dernier redémarrage des seuls services Gateway.

Détails, limites et archives : [rapport de cette passe](console-complete-2026-09-27.md).

## 27 septembre 2026 — Juju Driver, SD temporaire et retrait USB

Le transport USB 32×32 est confirmé par 32 signatures distinctes dans chaque sens,
puis par la musique réelle sur 17–18 après redémarrage. La préférence MPC de
stockage temporaire restait sans effet : vérifier les descripteurs ouverts et le
périphérique du dossier, pas seulement le XML ou le choix visible. Un montage du
dossier SD identifié par UUID fournit maintenant 29,4 Gio temporaires disponibles.
Ne jamais masquer un dossier interne contenant encore une récupération.

Sur HAKAI, les liens d'activation dans l'overlay tardif `/etc` ne suffisent pas au
démarrage initial. Les dépendances précoces dans `/usr/lib/systemd/system` et le
montage de la SD avant MPC sont vérifiés par redémarrage logiciel. BusyBox `blkid`
ne reconnaît pas ici exFAT ; les propriétés udev identifient type et UUID.

Le retrait USB a révélé un autre défaut : Ardour 9.8 convertissait un nom JACK
nul en chaîne. Le callback corrigé est testé avec l'ancienne exception comme
témoin, compilé dans le backend et chargé après récupération de la session.
L'absence de redémarrage de l'application ne prouve pas une continuité audio ;
les changements d'ouverture PCM et l'écoute restent des observations distinctes.
Voir [preuves, sauvegardes et limites](juju-driver-deployment-2026-09-27.md).

## 27 septembre 2026 — sélection MATRIX et fenêtre d'EQ

Un changement de groupe par les touches 1/9/17/25 de CHANNEL MATRIX applique
aussi son mode persistant SELECT/MUTE/SOLO/REC. Le modèle reproduit l'activation
de la première piste dans ces modes, mais les journaux disponibles ne suffisent
pas à attribuer l'incident utilisateur à ce mécanisme. Conserver désormais la
trame d'entrée, le mode, la banque, la cible absolue après routage et le retour
de mixage dans un journal dédié, sans le bruit des sondages de transport.

Le suivi d'EQ conservait une ancienne fenêtre manipulable pendant l'attente des
descripteurs de la nouvelle piste. Fermer cette fenêtre si l'identité cible
change ; conserver les rafraîchissements ordinaires sur la même identité.
L'ancien code échoue aux deux tests de transition, le nouveau les passe.
L'utilisateur indisponible pour l'essai, la capture de repos n'est pas une
validation physique. [Méthode et limites](matrix-selection-2026-09-27.md).
