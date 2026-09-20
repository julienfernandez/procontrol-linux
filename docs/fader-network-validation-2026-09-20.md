# Diagnostic des faders : réponse réelle et observation du relais

Le 20 septembre 2026, une requête Ethernet `f0 13 00 70 01 56 f7` a obtenu
**quatre réponses directes `FDRv1.37 LF CR`** de la ProControl locale.
Le premier essai, envoyé immédiatement après la connexion, avait seulement
reçu son ACK et a expiré sans réponse diagnostic. Cet échec est conservé.

L'audit indépendant de **21 PCAP clôturés, 1 036 trames**, confirme les réponses,
l'essai incomplet et **150 octets lus dans cinq champs RAM précisément
identifiés du processeur principal**. Il ne s'agit pas d'une lecture du programme
des faders. Aucun réglage moteur, calibration, téléchargement ou effacement
n'a été envoyé par ces expériences.

Le [rapport de preuves](fader-network-validation-2026-09-20.json) conserve
chaque capture, résultat, empreinte, adresse et mesure. Cette étape complète
l'[analyse statique du relais](fader-diagnostic-analysis-2026-09-20.md).

## Version attendue et réponse observée

Dans l'image constructeur `fader`, l'initialisation à `0x9af2–0x9b24` assemble
dix octets en RAM à `0x4412e` :

| Source de l'image | Octets copiés | Contenu |
|---|---:|---|
| `0xb0d6` | 3 | `FDR` |
| `0xb0da` | 5 | `v1.37` |
| `0xa8bc` | 2 | LF CR |

Ce contenu est celui fourni par le handler `V/v` à `0x9374`. La table de
branche a été vérifiée avec son index inversé : `V` et `v` arrivent bien à
ce handler. La réponse n'est pas déduite du seul nom de la ressource `fader`.

Sur le réseau, lors du dernier essai utilisant l'outil final :

```text
requête : f0 13 00 70 01 56 f7
réponse : f0 13 00 70 01 46 44 52 76 31 2e 33 37 0a 0d f7
contenu :                F  D  R  v  1  .  3  7  LF CR
```

Dans `live-fader-final-cli/traffic.pcap`, la requête est en trame 1,
l'ACK console en trame 2, la réponse en trame 3 et son ACK hôte en trame 4.
Le délai requête/réponse mesuré depuis le PCAP est **6,769 ms**.
Les quatre délais indépendants sont 7,145, 5,894, 5,847 et 6,769 ms.
Ce sont des mesures de capture Linux sur ce studio, pas une latence audio
ou une mesure du mouvement mécanique.

## Premier essai incomplet et changement de méthode

`live-fader-version-1` contient 20 trames. La requête est en trame 17 et son
ACK en trame 18 ; aucune réponse `70 01` n'arrive dans le délai de deux secondes.
Avant la connexion, treize répétitions d'une ancienne entrée console
`f0 13 00 60 01 00 01 02 f7` sont observées. Une dernière répétition, reçue
après la connexion, est acquittée. Le sens fonctionnel de cette entrée n'est
pas attribué par cette étude.

Le lecteur s'arrête sans retransmettre la requête et la passerelle est relancée.
La répétition prévue de cet essai n'est pas effectuée automatiquement.
La cause de l'absence de réponse reste **non établie** : l'ACK ne dit pas
jusqu'où la commande a progressé dans le logiciel des deux processeurs.

Les essais suivants vérifient d'abord `COMv1.37` dans la même session Ethernet.
L'observation détaillée des files série obtient une réponse ; deux échanges
`COM` puis `FDR` la reproduisent ; enfin la version finale de la commande CLI
réussit après une nouvelle prise de session exclusive. Cette préparation est
maintenant intégrée à `--target fader`. Ce succès ne démontre pas que le défaut
initial était uniquement un problème de délai ou de message en attente.

## Cinq champs RAM nommés, sans adresse libre

Les adresses suivantes viennent du code `comm 1.37`, déjà comparé octet par
octet au programme installé. Elles sont lues par le moniteur principal avec
`A<adresse>m`. `A` change son pointeur de lecture volatil ; aucun octet du
champ observé n'est écrit. Les registres MMIO restent exclus.

| Option `--read-state` | Adresse | Longueur | Objet observé |
|---|---|---:|---|
| `fader-version` | `0x5094a` | 10 | Version reçue et mémorisée par `comm` |
| `fader-version-valid` | `0x509c2` | 4 | Drapeau posé après réception d'une version validée |
| `fader-errors` | `0x509ba` | 4 | Compteur logiciel de rejets du parseur série |
| `fader-tx-ring` | `0x6c10e` | 24 | En-tête de la file d'émission vers les faders |
| `fader-rx-ring` | `0x6bf0e` | 24 | En-tête de la file de réception depuis les faders |

Une sélection nommée impose sa cible `comm`, son adresse, sa longueur et des
lectures unitaires. Elle refuse `--read-code`, une longueur ou un lot personnalisés,
ainsi que la cible `fader`. `--read-code` garde ses bornes des segments de code.
La version exacte `COMv1.37` est obligatoire avant chaque série de lectures RAM.

Les trois premiers champs ont été lus deux fois : version `FDRv1.37 LF CR`,
drapeau `00 00 00 01`, compteur `00 00 00 00`. Chaque paire concorde.
La valeur mémorisée ne suffisait pas à prouver une réponse à une nouvelle
requête ; les quatre réponses directes constituent une preuve séparée.

Les 24 octets d'en-tête des files sont décodés en six mots longs big-endian.
Les routines de file utilisent l'offset 0 pour le producteur, 8 pour le
consommateur, 12 pour la borne relative de fin, et 20 pour le compteur de
débordements. Les autres mots sont conservés sans leur attribuer un rôle
supplémentaire ici. Les lectures octet par octet ne sont **pas atomiques**.

## Une requête suivie à travers les files série

Dans `live-fader-route-1`, lecture des deux en-têtes et du compteur, une seule
requête `V`, puis relecture des en-têtes, du compteur et du cache version :

| Champ | Avant | Après | Différence observée |
|---|---|---|---:|
| Producteur et consommateur TX | `0x6c269` | `0x6c26a` | +1 octet |
| Producteur et consommateur RX | `0x6c0d6` | `0x6c0e3` | +13 octets |
| Compteur de rejets | 0 | 0 | 0 |
| Compteurs de débordements des deux files | 0 | 0 | 0 |

Le code de réception série `comm 0x2ae82–0x2aea4` alimente la file RX depuis
`0x8000071b`. À `0x2aeac–0x2aec2`, la file TX est vidée vers ce même registre.
Ces adresses MMIO sont **analysées dans le code**, pas lues sur l'appareil.

L'avance TX de 1 et RX de 13 est cohérente avec l'émission de `V` et une réponse
série `00 56 0a` suivie des dix octets de version. La réponse Ethernet de cette
expérience est aussi capturée. L'observation réunit donc un trajet logiciel,
des changements d'état RAM et un résultat réseau ; elle ne remplace pas une
capture électrique de la liaison interne.

## Outils, reproduction et restauration des services

`tools/firmware_probe.py --target fader` confirme désormais `COMv1.37`, conserve
cette étape dans `comm-version/`, puis envoie une seule interrogation `FDR`.
Le même verrou, les mêmes sockets et la même session sont gardés. Une erreur
sur `COM` interdit l'envoi vers les faders. Les réponses sont reconnues par
leur sélecteur ; une réponse `70 00` ne valide pas une requête `70 01`.
L'aperçu par défaut expose les deux requêtes sans ouvrir de socket.

```bash
# Aperçus sans réseau :
python3 tools/firmware_probe.py --target fader
python3 tools/firmware_probe.py --read-state fader-version

# Pendant une période compatible avec une suspension de la surface :
(
  ./procontrol stop || exit
  trap './procontrol start' EXIT
  python3 tools/firmware_probe.py --target fader --send \
    --output work/fader-version-new
)
./procontrol status

# Audits hors ligne des deux captures clôturées :
python3 tools/audit_firmware_probe.py work/fader-version-new/comm-version
python3 tools/audit_firmware_probe.py work/fader-version-new
```

L'auditeur reconstruit les requêtes, ACK, versions et délais sans importer
le parseur du lecteur. Pour les snapshots RAM, il réutilise la reconstruction
adressée de `audit_comm_archive.py` et compare PCAP, octets et fichiers conservés.
`matches_report: true` peut confirmer fidèlement un essai incomplet : seul
`observed_complete: true` indique que l'échange attendu a été observé.

Ardour était déjà fermé avant les essais ; aucun processus Ardour n'a été
arrêté ni relancé. Le mapping n'était pas en apprentissage et aucun geste récent
n'était signalé. Chaque arrêt du démon a été suivi d'une relance dans `finally`.
Le pointeur est resté actif. Au dernier contrôle : passerelle `629422`, Online,
sans erreur ; Ardour toujours attendu, comme avant les essais. Ces états sont
historiques et doivent être revérifiés à la reprise.

## Conservation, validation et limites

Les originaux sont dans `work/firmware-research-20260920/live-fader-*`.
Une archive privée complémentaire conserve les 21 PCAP, snapshots, rapports,
versions des sources et analyses statiques utilisées ; son nom, sa taille,
son manifeste et son SHA-256 sont dans le JSON associé. La copie reste sur
la même machine. Le Git public conserve outils, tests, méthode, conclusions
et empreintes, selon la [règle de conservation](retour-experience.md).

Archive `procontrol-fader-network-1.37-evidence.tar.gz` : **82 fichiers relus
et vérifiés après compression**, 86 939 octets, SHA-256
`1b3f449c0f95afac734995455f571cb43127741ec165c6da44d6fa123981b712`.
Les archives précédentes sont conservées séparément.

Validation locale du code final : **358 tests Python réussis en 79,513 s**,
compilation Python, inventaire des mappings en mode `--check` et contrôle
d'espaces Git réussis. Ces tests ne commandent pas les moteurs réels.

L'ajout du sélecteur a d'abord révélé en tests un masquage de variable : le nom
`target` servait déjà à l'adresse de lecture et devenait `None` à la transaction
de version. Les adresses locales ont été renommées `read_target` avant tout
essai sur le matériel. Les tests conservent les deux cibles, le refus des
lectures faders, les champs RAM imposés, l'ACK insuffisant, les mauvais sélecteurs,
le préalable `COM`, les octets bruts et l'audit de données altérées.

Le programme des faders n'a pas été lu. La restriction du relais aux contenus
sans NUL et sans bit 7 reste à résoudre pour une acquisition mémoire complète.
La carte de démarrage, les données persistantes, la calibration, la restauration
et l'optimisation physique des moteurs restent des objectifs ouverts.
