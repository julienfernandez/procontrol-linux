# Compléter la préservation par les petits blocs comm

Procédure préparée le 21 septembre 2026, heure de Paris. **Les nouveaux champs
n'ont pas encore été lus sur la console.** Les logiciels sont testés avec des
captures synthétiques et attendent la fin de la double acquisition fader.
La [cartographie statique](preservation-layout-2026-09-21.md) explique la
provenance de chaque adresse ; les valeurs réelles restent inconnues.

## Périmètre et ordre

`tools/comm_preservation.py` effectue deux passes dans le même ordre, avec
un PCAP distinct par champ et une vérification `COMv1.37` avant chaque lecture :

| Champ | Adresse | Taille | Rôle et limite |
|---|---|---|---|
| `comm-boot-vectors` | `0x00000` | 8 | Deux mots de 32 bits ; le bootstrap complet reste absent |
| `comm-application-checksum` | `0x30000` | 2 | Mot de contrôle stocké ; la plage complète à sommer reste à acquérir |
| `comm-network-settings` | `0x34000` | 10 | Configuration réseau stockée, qui peut être invalide et remplacée au démarrage |
| `comm-utility-settings` | `0x3c000` | 88 | Bloc Utility persistant et son marqueur de version |
| `comm-utility-mirror` | `0x40000` | 88 | Instantané du miroir RAM, potentiellement différent de la flash |

Chaque passe lit **196 octets** ; les deux réunies produisent dix captures et
392 octets de données, sans compter les réponses de version. Les requêtes
restent limitées aux commandes `V`, `A` et `M` du moniteur **comm**.
La commande `A` règle son pointeur de diagnostic volatil. Aucune écriture
flash, retour usine, calibration ou commande de mouvement n'est utilisée.

## Exécution après la collecte en cours

La copie `work/preservation-read-stage` sert uniquement à préparer et tester
le logiciel. Ne pas y utiliser `--send` : son répertoire de runtime et son
verrou ne sont pas ceux de la passerelle principale. Intégrer la branche
`research/preservation-reads` dans le dépôt principal **après** la clôture,
l'audit et la conservation des sources de l'acquisition fader active.

Depuis la racine du dépôt principal, un aperçu n'ouvre aucune socket :

```bash
python3 tools/comm_preservation.py
```

Pour l'essai matériel, choisir un dossier inexistant :

```bash
python3 tools/comm_preservation.py --send \
  --output work/firmware-research-20260920/live-comm-preservation-1
```

Le précontrôle exige une passerelle réellement joignable par son PID, un statut
Online de moins de cinq secondes, Ardour en attente et aucun apprentissage ou
geste récent enregistré. Il n'est pas suffisant qu'un ancien fichier indique
`running: true` : le verrou peut appartenir à un autre lecteur de firmware.
Le collecteur arrête la passerelle, prend son verrou exclusif, puis ouvre les
sockets. Il tente sa relance dans `finally`, y compris après interruption.
Les journaux `restart.log` et `restart-result.json` en conservent le résultat ;
vérifier ensuite le nouveau PID, la fraîcheur et le statut Online réels.

Les champs sont conservés au fur et à mesure. Un échec de lecture ou des
pertes socket non nulles/inconnues arrête la séquence sans retry. Les fichiers
déjà produits restent présents et le manifeste indique l'inachèvement.
Ne pas réutiliser ce dossier pour une nouvelle tentative.

## Audit indépendant et interprétation

```bash
python3 tools/audit_comm_preservation.py \
  work/firmware-research-20260920/live-comm-preservation-1 \
  --output work/firmware-research-20260920/comm-preservation-audit-1.json
```

L'auditeur n'importe pas le collecteur. Il reconstruit les octets depuis les
PCAP, contrôle les bornes, versions, enveloppes, ACK et empreintes, puis
compare les résultats aux fichiers enregistrés et aux audits de chaque champ.
Il exige deux passes complètes, refuse les champs manquants ou répétés et les
captures réutilisées, non chronologiques ou chevauchantes. Le temps PCAP est
celui de l'hôte ; une correction de cette horloge peut donc nécessiter une
analyse séparée, sans réécriture des captures originales.

L'interprétation conserve les valeurs observées :

- Le bloc réseau est valide selon le programme si le mot final est non nul
  et correspond à la somme modulo 65 536 des huit premiers octets. Un échec de
  ce contrôle n'invalide pas la sauvegarde de ses octets ; il ne faut pas les
  remplacer par les constantes constructeur. La configuration effective du
  pilote Ethernet n'est pas prouvée par la seule lecture de la flash.
- Le marqueur Utility est comparé aux huit octets `v1.37` suivis de trois
  zéros. Les différences flash/RAM sont indiquées par offset sans leur
  attribuer une signification qui n'a pas encore été établie.
- L'égalité entre passes est donnée séparément pour chaque champ. Une RAM
  différente reste une observation conservée et non atomique. Si un champ
  persistant diffère, le rapport est tout de même écrit, puis le CLI renvoie
  un code d'échec pour appeler l'attention sur cette instabilité.
- La valeur du mot de contrôle du programme n'est pas annoncée vérifiée tant
  que sa plage complète de 65 536 octets n'a pas été acquise et sommée.

Ce complément ne constitue pas une sauvegarde intégrale : bootstrap,
identité matérielle complète, trous des images et autres composants restent
à étudier. Deux copies d'un bloc ne démontrent pas une procédure de restauration.

## Tests et conservation

Onze tests du collecteur et de l'auditeur couvrent deux passes reconstruites
depuis dix PCAP synthétiques, les lectures différentes, l'arrêt sans retry,
les pertes, la relance après échec de socket, un échec de relance, le statut
périmé, la falsification ou duplication de captures et les règles de décodage.
Les cinq tests des champs nommés vérifient en plus leurs bornes et le lecteur
sur un lien simulé. Ces tests ne remplacent pas l'essai matériel à venir.

Les rapports détaillés contiennent les réglages propres à l'unité et restent
dans les archives privées avec les PCAP, résultats, sources exactes et hashes.
Dans Git public, conserver la méthode, les outils, les conclusions choisies,
les empreintes des archives et les limites. Un checksum ou un marqueur invalide
doit être documenté comme résultat ; ne pas corriger silencieusement la preuve.
