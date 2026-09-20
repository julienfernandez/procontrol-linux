# Programme fader installé : première passe complète

Rapport historique, complété par la [double acquisition finale](fader-firmware-readback-2026-09-21.md).
Les mentions de seconde passe en cours décrivent l’instantané ci-dessous.

Le 21 septembre 2026 à Paris, les **11 546 octets des quatre segments connus**
du programme fader 1.37 ont été lus sur la console et reconstruits depuis leurs
captures Ethernet. Ils correspondent octet par octet aux ressources constructeur.
La seconde passe est en cours ; l'égalité de deux acquisitions complètes reste
à vérifier. Ce résultat ne couvre ni le bootstrap, ni les trous entre segments,
ni les réglages ou la calibration de l'unité.

Le [manifeste public](fader-first-pass-2026-09-21.json) conserve le périmètre,
les empreintes et l'identité de l'archive privée. Les rapports des
[premiers préfixes](fader-archive-verification.md) restent valables pour leurs
instantanés antérieurs ; ce rapport les complète.

## Observation et audit

Le collecteur lancé au commit `5c4959d` a terminé ses 964 blocs du premier
passage. La première requête de bloc date du 20 septembre à 22:21:57,680931 UTC,
la dernière capture de bloc à 23:04:24,436404 UTC. Cela représente environ
42 minutes et 27 secondes pour cette passe, avec les contrôles intermédiaires
et huit lectures de relâchement par bloc.

L'audit indépendant a figé le manifeste actualisé à **23:04:37,152058 UTC**
(01:04:37 à Paris). Il comprend la première passe complète et cinq blocs déjà
clôturés de la seconde, soit 48 octets supplémentaires. Au total, ce périmètre
audité comprend **969 blocs, 11 594 octets de programme, 15 376 PCAP et
675 735 trames**, avec la preuve initiale des relâchements. Tous les compteurs
de pertes socket enregistrés valent zéro.

| Plage fader, inclusive | Octets, première passe | Résultat |
|---|---:|---|
| `0x8000–0x8007` | 8 | Reconstruit et identique au constructeur |
| `0x8064–0x807f` | 28 | Reconstruit et identique au constructeur |
| `0x8100–0x810f` | 16 | Reconstruit et identique au constructeur |
| `0x8400–0xb0e5` | 11 494 | Reconstruit et identique au constructeur |

Le vérificateur a relu les transactions, les réponses série reconstituées
depuis la RAM de `comm`, les adresses et les valeurs de chaque bloc. Il a
comparé les résultats aux audits enregistrés, aux fichiers `code.bin`, aux
segments assemblés, puis aux quatre références constructeur. Les états
tactiles et le mode normal sont vérifiés avant et après chaque bloc, selon la
[méthode de neutralisation documentée](fader-touch-recovery-2026-09-21.md).

Le résultat global reste `complete_archive: false`,
`completed_prefix_only: true`, `passes_equal: null`. Ces valeurs sont
correctes même lorsque le premier passage est entier : la campagne prévoit
deux passages. Les cinq blocs du second ne prouvent pas encore sa totalité.

## Conserver pendant que la seconde passe continue

L'audit n'a lu que les répertoires de blocs référencés par son manifeste figé.
L'archive privée suit la même règle : captures originales de ces blocs et de
la preuve initiale, résultats, audits, première passe assemblée, fichiers
reconstruits et références constructeur. Le manifeste exact, les sources
liées au lancement et un bundle Git complet sont également conservés.
Le dossier du bloc actif et les journaux encore en écriture en sont exclus.

L’archive `procontrol-fader-first-pass-evidence.tar.gz` contient 47 132 membres, tous relus et vérifiés. Sa copie est vérifiée dans
`~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`.
Les deux exemplaires restent sur la même machine. SHA-256 de l’archive :

```text
49e09556f1a3102302d7011e3128b6ce8610c65cfeed86895c41f9ebdc3da7d3
```

L’archive copiée a ensuite été extraite dans un dossier neuf. Le même audit
indépendant a reconstruit les octets depuis ces captures restaurées et produit
exactement les mêmes résultats, à l’exception du nom du fichier de manifeste.
Cette vérification, terminée à 23:08:30 UTC, éprouve la restitution des preuves
hors ligne ; elle ne constitue pas un flashage ou une restauration matérielle.

L'observation de 23:05:00 UTC confirme que le lecteur PID 641580 détient
`run/daemon.lock`. La passerelle est arrêtée pour cette collecte ; le pointeur
PID 622060 reste actif. Les sept sources enregistrées au lancement n'ont pas
changé. La relance de passerelle est prévue par le collecteur après la seconde
passe ; elle n'est pas encore déclarée effectuée dans ce rapport.

## Suite préparée

La branche
[`research/preservation-reads`, commit `080ef2e`](https://github.com/julienfernandez/procontrol-linux/tree/080ef2e6ff31ccb7d996bd4e19e010eaed88ebc7)
contient la double lecture des cinq petits blocs `comm` : vecteurs du bootstrap,
contrôle du programme, réseau, Utility et miroir RAM. Sa
[procédure](https://github.com/julienfernandez/procontrol-linux/blob/080ef2e6ff31ccb7d996bd4e19e010eaed88ebc7/docs/comm-preservation-procedure.md)
précise les bornes, l'arrêt/reprise de passerelle et l'audit indépendant.
Cette préparation reste séparée des sources chargées par la collecte active.

La [CI de cette préparation](https://github.com/julienfernandez/procontrol-linux/actions/runs/35543360943)
a réussi : **418 tests en 59,012 secondes, un test ignoré**, ainsi que les
contrôles de syntaxe, d'inventaire et les compilations natives. Onze nouveaux
tests portent sur le collecteur et l'auditeur des réglages ; les données
matérielles de ces cinq champs restent à acquérir.

Après la seconde passe : audit final, comparaison des deux acquisitions,
conservation de toutes leurs captures, vérification de reprise des services,
puis intégration et essai des lecteurs de réglages depuis le dépôt principal.
Le résultat présent ne démontre ni mouvement moteur, ni endurance prolongée,
ni restauration matérielle à partir d'une sauvegarde.
