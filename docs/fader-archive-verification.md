# Vérifier une archive fader et ses blocs déjà terminés

L'[acquisition fader](fader-touch-recovery-2026-09-21.md) audite chaque bloc
avant de l'inscrire dans son manifeste. Le nouvel outil
[audit_fader_archive.py](../tools/audit_fader_archive.py) relit l'ensemble des
captures référencées et vérifie aussi la couverture des segments, l'ordre des
blocs, la séparation chronologique des passages et les fichiers assemblés.
Il n'importe aucune fonction d'acquisition et n'ouvre aucune socket.

**Validation datée du 21 septembre 2026 :** l'instantané du collecteur à
22:30:09 UTC le 20 septembre (00:30:09 à Paris) contient 187 blocs, soit
2 224 octets de code. Ils ont été reconstruits depuis 2 980 PCAP clôturés et
130 566 trames. Les octets concordent avec le constructeur, et tous les
compteurs de pertes socket enregistrés valent zéro. L'acquisition globale
était toujours en cours : **ce résultat est un préfixe vérifié du premier
passage, pas une archive complète ni deux passages validés**.

Le [manifeste de cette validation](fader-archive-audit-2026-09-21.json) conserve
les empreintes, les tests, les instantanés et les emplacements des preuves.

## Contrôles supplémentaires à l'échelle de l'archive

- La preuve préalable des huit lectures `d0–d7` est auditée depuis ses PCAP.
- Chaque passage contient exactement les blocs attendus, sans adresse absente,
  répétée, déplacée ni située dans un trou entre segments. Une déclaration
  `complete` ne suffit pas à prouver cette couverture.
- Pour chaque bloc, l'audit série est recalculé, puis comparé à son résultat
  conservé. Les huit valeurs de relâchement sont vérifiées et retirées des
  octets de programme reconstruits.
- Chaque `code.bin` et chaque segment assemblé sont comparés aux octets
  reconstruits depuis les captures, avant leur comparaison au constructeur.
- Les requêtes des blocs successifs doivent venir après la dernière capture
  du bloc précédent. Copier les captures du premier passage dans le dossier
  du second ne produit pas une deuxième acquisition valide. Ces timestamps
  proviennent de l'horloge logicielle de capture locale.
- Les deux passages d'une archive achevée sont comparés octet par octet.
  Une seule acquisition ou un second passage incomplet n'obtiennent pas cette
  validation. Les pertes socket et compteurs manquants sont relevés séparément.

Les quatre plages sont `0x8000–0x8007`, `0x8064–0x807f`, `0x8100–0x810f` et
`0x8400–0xb0e5`, soit **11 546 octets par passage**. La vérification ne remplit
pas artificiellement les trous et ne les assimile pas à du firmware sauvegardé.

## Vérification finale, après l'acquisition

Depuis la racine du dépôt, avec des chemins de sortie nouveaux :

```bash
python3 tools/audit_fader_archive.py work/archive-fader \
  --reference work/firmware-research-20260920/extracted \
  --output work/audit-fader-final.json \
  --reconstruct work/fader-reconstruit
```

Par défaut, le programme refuse une archive annoncée incomplète. Les références
constructeur sont contrôlées par taille et SHA-256. L'outil conserve à côté du
rapport le manifeste exact utilisé, ici `audit-fader-final.manifest.json`.
Les fichiers reconstruits restent dans le dossier privé choisi ; ils ne
doivent pas être ajoutés au dépôt public.

## Contrôle pendant une acquisition longue

Le collecteur inscrit un bloc dans son manifeste seulement après avoir fermé
ses captures et terminé son audit. Le remplacement du manifeste est atomique.
L'option suivante fige ce manifeste et inspecte uniquement les blocs déjà
référencés. Elle ne parcourt pas les autres dossiers, y compris celui du bloc
actuellement en cours d'écriture :

```bash
python3 tools/audit_fader_archive.py work/archive-fader \
  --completed-prefix \
  --reference work/firmware-research-20260920/extracted \
  --output work/audit-prefixe.json \
  --reconstruct work/fader-prefixe-reconstruit
```

Une archive inachevée conserve `complete_archive: false`,
`completed_prefix_only: true` et `passes_equal: null`. Un segment incomplet
est nommé avec le suffixe `.partial.bin`. Le code de sortie zéro signifie que
le périmètre effectivement audité concorde avec la référence ; il ne transforme
pas un préfixe en acquisition complète.

### Retour d'expérience : figer aussi le manifeste

Un hash de `manifest.json` seul est insuffisant pour reproduire un audit de
préfixe : le collecteur remplace ce fichier après chaque bloc. Le premier
prototype conservait le hash sans copier l'instantané. Cet instantané a été
reconstitué et son identité exacte vérifiée par ce hash. La version publiée
copie désormais les octets du manifeste **avant** l'audit, dans un fichier
distinct, et travaille sur cette copie figée. Les deux rapports historiques
et leurs instantanés sont conservés séparément.

## Essais du vérificateur et premiers résultats

Les **21 tests ciblés des auditeurs fader passent en 1,993 s**. Ils comprennent
des archives synthétiques à deux passages, une archive interrompue, un dossier
de capture en cours volontairement invalide, une capture réutilisée, des blocs
absents ou dupliqués, des fichiers falsifiés et la conservation exacte du
manifeste. Les modules utilisés par l'acquisition en cours n'ont pas été modifiés.

Deux audits successifs ont porté sur des instantanés distincts :

| Instantané UTC | Blocs terminés | Octets de code | PCAP | Trames | Résultat |
|---|---:|---:|---:|---:|---|
| 22:27:53, le 20 septembre | 135 | 1 600 | 2 164 | 94 430 | Préfixe conforme, pertes déclarées nulles |
| 22:30:09, le 20 septembre | 187 | 2 224 | 2 980 | 130 566 | Préfixe conforme, pertes déclarées nulles |

Le deuxième reconstruit entièrement les trois petits segments (8, 28 et
16 octets) et les 2 172 premiers octets du segment à `0x8400`. Ses captures
proviennent toujours du **premier passage** de la campagne.

Le complément privé de validation contient les outils, tests, rapports,
instantanés et fichiers reconstruits. Il **n'embarque pas les PCAP** du
collecteur encore actif : ils restent dans
`work/firmware-research-20260920/live-fader-code-archive-1/`, et leur regroupement
doit être fait après la clôture de la campagne. Les deux dossiers restent sur
la même machine. Une empreinte ne remplace pas une capture perdue.

La validation complète exigera encore le deuxième passage achevé, cet audit
final, la conservation des captures et des images, et la vérification de la
reprise des services. Elle ne prouvera pas à elle seule une restauration
matérielle de la console, ni la sauvegarde de son bootstrap ou de sa calibration.
