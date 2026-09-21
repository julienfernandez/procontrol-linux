# Pilote des lectures RX fader par lots de 16 et 32

**Essais réalisés le 21 septembre 2026 :** les
[deux campagnes matérielles et leur archive](fader-rx-benchmark-validation-2026-09-21.md)
confirment un gain sur le plan borné décrit ici. Les défauts restent inchangés.

Ce pilote étend la [mesure sur le code comm](preservation-fields-validation-2026-09-21.md)
aux fenêtres du tampon série RX. Huit essais suivent l'ordre
**16, 32, 32, 16, 16, 32, 32, 16**. Ils demandent tous les mêmes douze octets
fader à `0x8400`, déjà comparés au constructeur, suivis des huit relâchements
connus. La réponse série attendue reste limitée à 465 octets.

## Ce qui varie et ce qui reste contrôlé

Seule la taille des transactions de relecture des fenêtres RX varie.
La commande fader, le délai de stabilisation de 250 ms, les versions COM/FDR,
les contrôles de toucher, mode, producteur RX, débordements et les relâchements
restent inchangés. Le compteur de débordement diagnostic comm est lu avant
et après chaque bloc. Les huit relâchements sont vérifiés au début de la campagne.

L'option `experimental_rx_batch32` ne permet que des fenêtres de 1 à 256
octets dans les 488 positions connues du tampon comm, sans traverser sa fin.
Le collecteur fader n'accepte cette option que pour le plan exact
`0x8400, 12 octets` suivi des relâchements. La calibration, les autres champs
RAM et les archives de programme conservent leurs lots de 16 par défaut.

Chaque bloc est décodé indépendamment depuis ses PCAP. Les adresses, le flux
série complet, les deux représentations des octets et les tailles de lot
réellement transmises sont vérifiés. Une erreur arrête le pilote, conserve
les preuves et utilise la récupération de toucher existante si nécessaire.
Les statistiques de pertes doivent être connues et nulles.

## Exécuter

Depuis le dépôt principal, après clôture de toute autre acquisition :

```sh
python3 tools/fader_rx_benchmark.py
python3 tools/fader_rx_benchmark.py --send \
  --reference work/firmware-research-20260920/extracted/CODE-27-00008400.bin \
  --output work/firmware-research-20260920/fader-rx-benchmark-1
```

La référence complète est vérifiée par sa longueur et son SHA-256 avant
l'ouverture du réseau. Le programme contrôle la passerelle et le verrou,
arrête la passerelle, mène la campagne exclusive et la relance en sortie.
Ne pas exécuter `--send` depuis un worktree de préparation distinct du runtime.

## Interpréter les durées

Le manifeste conserve la durée totale de chaque bloc et la somme des durées
des seules fenêtres RX, ainsi que leurs longueurs. Le point de départ du
tampon peut changer entre blocs : le bouclage et le nombre de fenêtres
doivent accompagner la comparaison. Les médianes ne représentent ni une
mesure de latence physique des faders, ni un test d'endurance.

Les tests couvrent les bornes de fenêtre, les octets `00–ff` sur sockets,
une réponse manquante, le bouclage série, la récupération après écrasement,
le refus d'une fausse étiquette de lot 32, la preuve des relâchements et
l'arrêt sans répétition au premier débordement. Le résultat matériel doit
être conservé dans un rapport daté avant d'élargir ce mode à d'autres lectures.
