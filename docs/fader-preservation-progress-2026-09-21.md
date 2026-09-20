# Préparation des prochains relevés et durée de la collecte fader

État du 21 septembre 2026, après la première passe fader complète. La seconde
acquisition continue avec ses sources inchangées. Les nouveaux lecteurs sont
préparés et testés dans une copie distincte ; aucune des nouvelles zones décrites
ici n'a encore été lue sur la console.

## Lecteurs préparés et vérifiés

La branche
[`research/preservation-reads`, révision `2549e65`](https://github.com/julienfernandez/procontrol-linux/tree/2549e65a507a296a45ad5ef8cb059b20dd3702bb)
conserve deux procédures :

- [Petits blocs comm](https://github.com/julienfernandez/procontrol-linux/blob/2549e65a507a296a45ad5ef8cb059b20dd3702bb/docs/comm-preservation-procedure.md) :
  vecteurs du bootstrap, mot de contrôle du programme, réseau, réglages Utility
  et miroir RAM ; 196 octets par passe.
- [Petits champs fader](https://github.com/julienfernandez/procontrol-linux/blob/2549e65a507a296a45ad5ef8cb059b20dd3702bb/docs/fader-preservation-procedure.md) :
  vecteurs du bootstrap, mot de contrôle, deux seuils tactiles et huit structures
  de calibration en RAM ; 270 octets par passe, en 25 blocs avec relâchements.

Chaque procédure prévoit deux passes, une preuve réseau conservée et un audit
indépendant. Les lecteurs différencient le contenu stocké, le contenu volatil,
la concordance entre passes et la validité éventuelle d'un enregistrement.
Une valeur invalide ou différente est conservée, sans remplacement par un défaut.

La [CI sur la révision exacte](https://github.com/julienfernandez/procontrol-linux/actions/runs/35544429893)
réussit : **433 tests en 77,912 secondes, un test ignoré**, plus les vérifications
de syntaxe, de l'inventaire et les compilations natives. Les 15 nouveaux tests
fader passent localement en 17,167 secondes. Les auditeurs étendus ont aussi
réanalysé les **15 376 PCAP et 675 735 trames** de l'archive réelle restaurée de
première passe : résultat identique à l'audit initial, hormis le nom du manifeste.
Cette vérification conserve la compatibilité des preuves antérieures ; elle
ne remplace pas les essais des nouveaux champs sur le matériel.

La copie de préparation reste `work/preservation-read-stage`. Ne pas y lancer
`--send`, car ses chemins de runtime et de verrou sont distincts. Après la
clôture, l'audit et l'archivage de la double acquisition, intégrer la branche
dans le dépôt principal et y exécuter les procédures avec son verrou unique.

## Une réponse fader peut contenir deux lectures de RAM

L'analyse du formateur à `0x90d8` a identifié deux accès mémoire : `0x910a`
charge la valeur pour l'hexadécimal, puis `0x9122` relit l'adresse pour le
caractère brut. Les opcodes ont été vérifiés dans l'image constructeur dont
les segments correspondent à la première passe acquise sur la console.

Une RAM modifiée entre ces deux accès peut donc produire des représentations
divergentes dans une même réponse. **Cette divergence n'a pas encore été
observée sur les nouveaux champs.** Les parseurs exigent déjà leur concordance
et conservent la capture en cas d'échec. Ce résultat ne doit pas être interprété
automatiquement comme une perte réseau, ni corrigé en choisissant une des valeurs.

Les structures de calibration sont également acquises octet par octet, en
plusieurs blocs. Même deux valeurs brutes égales ne démontrent pas un instantané
atomique ou une calibration physique réussie. Aucun nouvel étalonnage n'a été
déclenché pour cette préparation.

## Mesurer avant d'accélérer les acquisitions suivantes

Les horodatages des résultats des **964 blocs clôturés du premier passage**
ont été relus depuis le manifeste figé. La durée entre le début du premier
bloc et la fin du dernier est de **2 546,807 secondes**, soit environ
42 minutes et 27 secondes. La médiane par bloc est de **2 615,233 ms**,
le 95e centile de **2 634,899 ms**. Ces mesures décrivent le lecteur de firmware
avec ses contrôles, pas la latence des faders ou d'Ardour en usage normal.

| Phase | Temps cumulé | Part du temps dans les blocs |
|---|---:|---:|
| Copie des fenêtres RX via le moniteur comm | 1 224,920 s | 48,72 % |
| Toucher, mode et erreurs, avant/après | 494,384 s | 19,66 % |
| En-têtes RX avant, après et à la fin | 357,583 s | 14,22 % |
| Requête fader et attente configurée | 244,373 s | 9,72 % |
| Versions, y compris le préalable comm imbriqué | 164,939 s | 6,56 % |
| Reste à l'intérieur des blocs | 28,196 s | 1,12 % |

Les espaces entre blocs représentent encore **32,412 secondes** sur le passage.
Le délai de réception configuré à 250 ms ne constitue donc pas l'essentiel
de la durée. La première cible d'une future expérience d'accélération est la
relecture RX, avec contrôle des limites des réponses et du comportement réel
des lots. Aucun gain de vitesse ni lot élargi n'est déclaré validé ici.

La méthode additionne `finished_utc - started_utc` de chaque résultat de sonde,
en incluant `versions/comm-version` une seule fois. Le premier calcul exploratoire
omettait ce préalable imbriqué ; il est conservé séparément, et le rapport final
`fader-first-pass-step-timing-2.json` corrige ce décompte. Les timestamps sont
ceux de l'hôte : ces durées ne mesurent ni le temps CPU seul, ni la latence UART
physique, ni une comparaison avant/après sous une charge identique.

## Conservation

Le [manifeste de cette étape](fader-preservation-progress-2026-09-21.json)
relie sources, essais, CI, analyse statique, profils de temps et archive privée.
`procontrol-fader-preservation-preparation.tar.gz` contient 27 membres,
tous relus et vérifiés, avec une copie vérifiée dans
`~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`.

Il ne duplique pas les PCAP : ceux utilisés pour la régression restent dans
l'[archive vérifiée de première passe](fader-first-pass-2026-09-21.md).
Le nouveau paquet conserve leur identité et les résultats de relecture.
Les copies restent sur la même machine. Les preuves nouvelles attendues sont
la seconde passe complète et les lectures matérielles des champs préparés.
