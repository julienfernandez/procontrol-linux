# Réglages conservés, état fader et pilote de débit

Le **21 septembre 2026**, après la double acquisition complète du programme
fader, trois campagnes ont été exécutées depuis le commit `aec3535`.
Les champs comm et fader ont chacun été lus deux fois ; le pilote comm
a comparé quatre lectures par lots de 16 et quatre par lots de 32.
Chaque campagne a été auditée depuis ses captures, puis la passerelle relancée.

Le [manifeste public](preservation-fields-validation-2026-09-21.json) conserve
les bornes, empreintes, comptes, comparaisons et limites. Les contenus complets
des réglages et snapshots RAM restent dans l'archive privée.

## Les cinq blocs comm

Les deux passes totalisent **392 octets**, **10 PCAP** et **467 trames**,
sans perte socket enregistrée. Les cinq blocs sont identiques entre les passes.

| Champ | Adresse | Octets par passe | Observation |
|---|---|---:|---|
| Vecteurs du bootstrap | `0x00000` | 8 | Vecteur de reset à `0x400` ; contenu répété à l'identique |
| Mot de contrôle du programme | `0x30000` | 2 | Valeur stockée `0xda49` ; somme complète encore non vérifiée |
| Réseau | `0x34000` | 10 | Structure et somme interne cohérentes ; type stocké `0x885f` |
| Utility persistant | `0x3c000` | 88 | Marqueur `v1.37` présent |
| Miroir Utility en RAM | `0x40000` | 88 | Identique au bloc persistant et entre les deux passes |

La conformité du bloc réseau n'établit pas seule comment tous ses paramètres
sont employés par le pilote actif. L'égalité des deux copies Utility décrit
ces instantanés. Aucun octet invalide n'aurait été remplacé par une valeur
par défaut ; le lecteur conserve les octets reçus.
Méthode : [procédure comm](comm-preservation-procedure.md).

## Les quatre blocs fader

Les deux passes totalisent **540 octets**, **50 blocs de données**,
**801 PCAP** et **33 999 trames**, avec la preuve initiale des relâchements.
Aucune perte socket n'est enregistrée. Les vecteurs du bootstrap, le mot
de contrôle et les seuils sont identiques entre les passes.

| Champ | Adresse | Octets par passe | Observation |
|---|---|---:|---|
| Vecteurs du bootstrap | `0x00000` | 8 | Vecteur de reset à `0x400` |
| Mot de contrôle du programme | `0xfffe` | 2 | Valeur stockée `0x52a3` ; somme complète encore non vérifiée |
| Seuils tactiles | `0x44012` | 4 | Valeurs brutes signées 89 et 115 ; ce ne sont pas des pourcentages |
| Huit structures d'état | `0x4402a` | 256 | Un octet diffère entre les snapshots ; les champs de calibration décodés sont identiques |

L'écart de RAM se situe à **`0x4403d`**, soit l'offset `0x13` de la première
structure : `0x83` dans la première passe, `0x82` dans la seconde. Sa cause
n'est pas établie. Les deux snapshots complets sont conservés ; aucun n'est
présenté comme une image atomique ou remplacé par l'autre.

Pour chaque tranche, les champs d'échelle, d'étendue et le drapeau actuellement
décodés sont identiques entre les passes. Les huit drapeaux valent 1. Cela
constate l'état logiciel lu ; cela ne valide pas physiquement la calibration,
la course, le toucher ou le comportement moteur. Aucune calibration n'a été
lancée et aucun réglage persistant n'a été écrit.

La divergence hexadécimal/brut envisagée dans l'analyse statique du formateur
n'a pas été observée dans ces lectures. Un changement entre deux snapshots
entiers est distinct d'une réponse incohérente au cours d'une seule lecture.
Méthode : [procédure fader](fader-preservation-procedure.md).

## Pilote comm : résultat des lots de 16 et 32

Le bloc vérifié `0x2a3d0–0x2a4cf` a été lu selon l'ordre
**16, 32, 32, 16, 16, 32, 32, 16**. Les huit acquisitions correspondent
aux mêmes 256 octets constructeur. Le compteur de débordement à `0x6b51e`
vaut zéro avant et après chaque essai. L'audit de **24 PCAP** et **2 037 trames**
retrouve chaque adresse, les tailles de lot attendues et aucune perte socket.

| Lot | Quatre durées de lecture, en ms | Médiane |
|---|---|---:|
| 16 | 654,403 ; 664,358 ; 654,474 ; 656,709 | 655,592 ms |
| 32 | 311,559 ; 309,366 ; 320,031 ; 319,657 | 315,608 ms |

Le rapport des médianes est **2,077**, soit environ **51,9 % de temps en moins**
sur ce bloc. La durée mesurée inclut la version comm préalable, mais exclut
les lectures du compteur avant et après. Ce petit essai ne mesure ni endurance,
ni latence physique ou audio. Il ne valide pas encore les lots de 32 dans
le lecteur de RAM RX : le comportement par défaut reste limité à 16.

La [préparation du pilote](comm-batch-benchmark.md) conserve le raisonnement
statique, les bornes de la commande et les tests qui ont précédé l'essai.
La suite locale passait 440 tests ; la
[CI de préparation](https://github.com/julienfernandez/procontrol-linux/actions/runs/35545370426)
passe également 440 tests en 77,928 s, un ignoré, avec compilations natives.

## Conservation et suite

L'archive `procontrol-field-campaigns-evidence.tar.gz` contient les trois
campagnes terminées, les audits, références, sources via bundle Git et
journaux de validation. Ses **2 587 membres** ont été vérifiés ; sa taille
est de **3 453 361 octets**, SHA-256 :

```text
50bb1d6703905d421f4c452509bfd6440affb1a182abf477b2a5cfab7810e169
```

La copie est vérifiée dans
`~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`, sur le même
ordinateur. Les captures et valeurs complètes restent hors du Git public.
La copie a ensuite été extraite dans un dossier neuf ; son bundle Git a été
cloné au commit `aec3535`. Les trois audits exécutés depuis cette copie
retrouvent les mêmes résultats, en dehors de l’heure du nouvel audit du pilote.
À **23:54:37 UTC**, la passerelle PID 666560 et le pointeur PID 622060
ont un état Online frais ; les trois redémarrages ont un code de sortie zéro.

Les deux mots de contrôle des programmes sont désormais conservés, mais
les [intervalles manquants](application-preservation-gaps-2026-09-21.md)
doivent encore être lus pour recalculer les sommes complètes. La prochaine
optimisation est un essai borné de lecture RX par lots de 32, avec comparaison
des octets, stabilité du producteur et contrôle des débordements. Une sauvegarde
restaurable de toute l'unité et une restauration matérielle restent à établir.
