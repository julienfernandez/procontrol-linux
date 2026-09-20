# Pilote de débit du diagnostic comm : lots de 16 et 32 octets

Cette préparation est désormais complétée par le [pilote matériel et ses mesures](preservation-fields-validation-2026-09-21.md#pilote-comm--résultat-des-lots-de-16-et-32).

Préparation du **21 septembre 2026**. Analyse statique et tests logiciels ;
aucun résultat matériel à 32 octets n'est acquis à ce stade. La double lecture
du code fader reste menée avec ses sources figées et ses lots de 16 octets.

## Pourquoi mesurer

Sur la première passe fader, les lectures des données RX ont occupé
1 224,920364 s sur 2 514,394782 s cumulées dans les blocs, soit 48,7163 %.
Ce coût motive un pilote de transactions comm plus grandes. Il ne justifie
pas de réduire arbitrairement le délai de stabilisation série de 250 ms.
Les durées proviennent des manifests de l'acquisition, sans mesure de
latence physique des faders ou d'Ardour.

## Ce que montre le code constructeur

Source : segment `CODE-26-00020400.bin`, 63 716 octets, SHA-256
`e2945b200be72745afb10a3bc68300b4dc3b5adba90b3a8157cec37f051e1af8`.
Ce segment comm a déjà été lu deux fois dans la console et comparé au
constructeur ; voir la [double lecture comm](comm-firmware-readback-2026-09-20.md).

| Chemin étudié | Observation statique |
|---|---|
| `0x2a63c` → `0x2ab76` | Le sélecteur diagnostic comm `00` transmet les commandes à la file dont l'en-tête est à `0x6b50a`. |
| `0x2a6bc` → `0x2a898` | Initialisation avec une allocation de 512 octets, dont 24 octets d'en-tête. |
| `0x2ab94–0x2abaa` | Le producteur revient au début des 488 positions ; un emplacement reste réservé pour distinguer plein et vide. Maximum de 487 octets non consommés. |
| `0x2aba2` | L'échec d'insertion incrémente le compteur 32 bits à en-tête + 20, soit `0x6b51e`. |
| `0x2a6dc` | Assemblage SysEx dans le tampon à `0x6b70b`, avec compteur à `0x6b90c`. Aucune borne explicite repérée dans la boucle examinée ; la distance entre symboles ne prouve pas seule la taille d'allocation. |
| `0x21fce` puis `0x2b1c8` | Les réponses mémoire sont enveloppées et soumises séparément à la chaîne d'émission. La capacité totale de la file de sortie n'est pas établie ici. |

La commande `A` + huit chiffres d'adresse + 32 `M` occupe 41 octets,
47 avec l'enveloppe SysEx. Son ajustement dans la file d'entrée ne prouve
pas que les 32 réponses seront correctement transmises : le pilote doit
le vérifier. Les 488 positions restent le module du tampon circulaire ;
la réserve d'un emplacement ne doit pas le remplacer par 487 dans le lecteur RX.

Fenêtres de désassemblage conservées localement dans
`work/firmware-research-20260920/comm-batch32-static.txt`, SHA-256
`983532b159982985c171311405ebdfccad4330c9be95d173bb62b02ec724465d`,
avec leur provenance et leurs empreintes dans `comm-batch32-static.json`.
Les fichiers constructeur et leur désassemblage restent hors du Git public.

## Plan exécutable

`tools/comm_batch_benchmark.py` lit le même bloc de 256 octets à `0x2a3d0`
selon l'ordre **16, 32, 32, 16, 16, 32, 32, 16**. Chaque essai comprend :

1. Lecture du compteur `comm-diagnostic-overflows` et audit indépendant.
2. Version `COMv1.37`, lecture du code, audit des requêtes/ACK/réponses,
   reconstruction des 256 octets et comparaison au constructeur.
3. Seconde lecture du compteur : valeur inchangée requise.

Les 24 captures attendues sont distinctes. Aucune répétition automatique.
Une réponse manquante, des représentations hexadécimale/brute différentes,
un octet non conforme, une taille de lot inattendue, des pertes socket
ou un changement du compteur arrêtent le pilote et conservent l'échec.
Un compte de pertes inconnu est également refusé.

Le lecteur courant reste limité à 1–16 octets. L'option
`--experimental-batch32` n'autorise que ce bloc exact, avec cible comm,
longueur 256 et lot 32 ; les champs nommés et la RAM RX ne sont pas étendus.
Les médianes portent sur la durée totale de chaque lecture de code, version
préalable incluse, sans les deux contrôles de compteur. Quatre répétitions
par taille constituent un pilote, pas une mesure d'endurance ni une preuve
de latence interactive.

Depuis le dépôt principal, après clôture et préservation de l'acquisition
précédente, vérifier d'abord l'aperçu :

```sh
python3 tools/comm_batch_benchmark.py
```

Puis, pendant une période de test autorisée, avec un nouveau dossier :

```sh
python3 tools/comm_batch_benchmark.py --send \
  --reference work/firmware-research-20260920/extracted/CODE-26-00020400.bin \
  --output work/firmware-research-20260920/comm-batch-benchmark-1
```

Le programme exige une passerelle Online récente, Ardour fermé et aucun
geste récent ; il arrête la passerelle, prend son verrou exclusif et la
relance en sortie, y compris après une erreur. Ne pas le lancer depuis
le worktree de préparation, dont le verrou serait différent.

## Vérification logicielle et suite

Les tests sur sockets simulées couvrent tous les octets `00–ff`, les réponses
désordonnées, les doublons et une réponse manquante avec lot 32. Le parseur
indépendant vérifie le PCAP obtenu et refuse un lot 32 annoncé comme 16.
Les tests du pilote reconstruisent ses 24 captures, puis injectent séparément
un débordement, une référence différente et des pertes pour vérifier l'arrêt
et la conservation des preuves. Ces tests n'ouvrent pas le réseau matériel.

La suite locale complète de cette préparation passe : **440 tests en
102,783 secondes**, aucun ignoré. Compilation syntaxique, inventaire généré
en mode `--check` et contrôle du diff passent également. Journal local :
`work/firmware-research-20260920/batch32-stage-tests.log`.

Après le pilote réel, conserver ses résultats datés avant toute extension
aux lectures RX. Le code fader, le démarrage et les champs de préservation
gardent leurs propres campagnes et leurs propres limites de preuve.
