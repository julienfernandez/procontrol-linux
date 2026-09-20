# Lire les petits champs fader et l'état de calibration

Préparation du 21 septembre 2026. **Essai matériel encore à exécuter après la
double acquisition du programme.** Les adresses proviennent de la
[cartographie statique](preservation-layout-2026-09-21.md). La première passe
du programme installé a depuis été [comparée au constructeur](fader-first-pass-2026-09-21.md),
mais aucune valeur des nouvelles zones n'est supposée connue.

## Quatre champs nommés, 270 octets par passe

| Champ | Adresse | Octets | Nature et portée |
|---|---|---:|---|
| `fader-boot-vectors` | `0x0000` | 8 | Vecteurs initiaux ; pas le bootstrap entier |
| `fader-application-checksum` | `0xfffe` | 2 | Mot stocké ; calcul du contrôle encore impossible sans tous les octets de la plage |
| `fader-touch-thresholds` | `0x44012` | 4 | Deux mots de seuil en RAM, en unités internes |
| `fader-calibration-state` | `0x4402a` | 256 | Huit structures de 32 octets, incluant des données calculées à l'exécution |

Le lecteur d'origine reste limité aux quatre segments de code. L'extension
requiert un nom de champ explicite ; elle n'ouvre pas une lecture libre de la
RAM ou des registres matériels. Un bloc ne dépasse pas 12 octets et reste
entièrement dans le champ choisi. Chaque bloc est suivi des huit lectures
de relâchement `d0–d7` déjà documentées : au maximum 465 octets série pour
488 octets utilisables dans la file RX.

Avant les données nouvelles, une acquisition dédiée vérifie les huit octets
de relâchement aux adresses connues et l'état neutre. Chaque bloc contrôle les
versions `COMv1.37` et `FDRv1.37`, le mode normal, le cache tactile, les
pointeurs et débordements RX, puis le retour neutre. Une modification du
tampon pendant la copie fait échouer le bloc ; le chemin de récupération
existant tente les relâchements documentés lorsqu'ils ont été vérifiés.

`U` règle le pointeur volatil du moniteur fader ; `Q/q` lit la mémoire. Le
contenu brut peut être interprété par le relais comme un faux événement
tactile, d'où la neutralisation par bloc. Il ne s'agit donc pas d'une lecture
sans aucun effet volatil. L'outil n'exécute ni `W`, ni `C` de calibration,
ni commande de moteur, de redémarrage ou de flash.

## Exécution dans le dépôt principal

La copie `work/preservation-read-stage` sert à la préparation. **Ne pas y
utiliser `--send`** : elle possède un autre chemin de runtime et de verrou.
Intégrer `research/preservation-reads` dans le dépôt principal après la fin
du collecteur actif et la conservation de ses sources, captures et audits.

```bash
# Aperçu : aucune socket ouverte et aucun service arrêté.
python3 tools/fader_preservation.py

# Depuis la racine du dépôt principal, avec un dossier inexistant.
python3 tools/fader_preservation.py --send \
  --output work/firmware-research-20260920/live-fader-preservation-1

# Audit des deux passes clôturées.
python3 tools/audit_fader_preservation.py \
  work/firmware-research-20260920/live-fader-preservation-1 \
  --output work/firmware-research-20260920/fader-preservation-audit-1.json
```

La gestion de la passerelle est partagée avec le
[lecteur des réglages comm](comm-preservation-procedure.md) : statut Online
frais, Ardour en attente, arrêt de passerelle, verrou exclusif avant sockets
et tentative de relance dans `finally`. Conserver le résultat de relance puis
vérifier le nouveau PID et Online ; ne pas conclure depuis le seul verrou.

Le plan prévoit **25 blocs par passe, deux passes, 540 octets de champs**,
en plus de la preuve initiale de relâchement. Il conserve chaque bloc et
chaque champ assemblé. Les captures sont auditées avant acceptation du bloc ;
un compteur de pertes non nul ou absent arrête la collecte. Il n'y a aucun
retry automatique. Un dossier interrompu conserve ses preuves et ne doit
pas être réutilisé comme sortie d'un nouvel essai.

## Interpréter sans transformer l'instantané

L'auditeur reconstruit les octets depuis les PCAP, recontrôle les relâchements,
les limites, le préalable, l'ordre chronologique, la couverture et les
fichiers assemblés. Il compare les deux passes champ par champ. Une capture
copiée du premier passage vers le second ne passe pas ces contrôles.

Les structures sont interprétées suivant les accès visibles dans les routines
`0x8f10` et `0x8dfc`, sans inventer une validation mécanique :

| Offset dans chaque structure | Lecture conservée | Limite |
|---|---|---|
| `0x00`, 4 octets | Mot d'échelle calculé, valeur brute | Pas une mesure de force ni un réglage utilisateur |
| `0x10`, 2 octets | Étendue interprétée en entier signé | Unités internes, pas des millimètres |
| `0x1b`, 1 octet | Indicateur de validité brut | La valeur ne remplace pas un test physique du fader |

Le rapport n'affirme pas que la calibration a été déclenchée ou physiquement
validée. Il conserve l'empreinte de chaque structure entière et les huit
valeurs brutes de l'indicateur, y compris une valeur autre que zéro ou un.

Les mots aux adresses `0x44012` et `0x44014` sont lus comme valeurs internes
signées. Les valeurs par défaut 89 et 115 ne sont pas affichées comme 89 %
et 115 % : les handlers du moniteur appliquent un facteur 128/100 à leurs
arguments. La lecture de RAM ne change pas ces seuils.

Les 256 octets sont acquis en plusieurs blocs ; même les octets d'un mot
peuvent être lus à des instants distincts. Ce n'est **pas un instantané
atomique**. Une différence RAM entre passes est conservée, sans conclure à
une erreur de transmission ou écraser la première valeur. Une divergence
des vecteurs ou du mot de contrôle est signalée séparément et donne un code
de sortie non nul à l'auditeur, après écriture du rapport détaillé.

L'analyse du formateur de réponse `0x90d8` montre une limite supplémentaire :
`0x910a` lit la valeur destinée à l'hexadécimal, puis `0x9122` relit l'adresse
pour le caractère brut. Ces deux accès sont distincts. Une modification de
RAM entre eux peut donc produire deux représentations différentes au sein
d'une même réponse. Ce cas n'a pas encore été observé sur les nouvelles zones.
Les parseurs exigent leur concordance et conservent la capture en cas d'échec ;
ne pas remplacer l'une des valeurs par l'autre ni conclure automatiquement à
une corruption ou une perte réseau.

## Vérifications et conservation

Les tests spécifiques vérifient les limites et l'option de champ explicite,
les relâchements, les caractères de contrôle et octets de poids fort, le
bouclage RX, la récupération et le refus d'un toucher actif. Les tests du
collecteur reconstruisent deux passes synthétiques et éprouvent la preuve
préalable, les pertes, les lectures RAM différentes, les captures dupliquées,
un champ falsifié et le choix du bon collecteur sous la gestion commune du
verrou et de la relance.

Cette validation est logicielle. Lors de l'essai réel, conserver les captures,
les données, les sources exactes, les états avant/après et les journaux dans
l'archive privée, avec empreintes et conclusions dans Git. L'égalité de deux
instantanés ne prouve ni une sauvegarde permanente de la calibration, ni une
restauration de la console.

Le [relevé de préparation](fader-preservation-preparation-2026-09-21.json)
conserve les empreintes des sources et des essais. Les 15 nouveaux tests passent
en 17,167 secondes. Les auditeurs étendus ont aussi relu les **15 376 PCAP et
675 735 trames réels** de l'archive restaurée de première passe : le résultat
est identique à l'audit d'origine, hormis le nom de son manifeste figé. Cette
compatibilité des anciennes preuves ne valide pas les nouvelles zones matérielles.
