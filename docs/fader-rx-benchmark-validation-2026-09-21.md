# Lecture des fenêtres RX fader : deux pilotes réels 16/32

Le **21 septembre 2026**, deux campagnes de huit blocs ont comparé les lots
de 16 et 32 octets pour relire le tampon RX contenant les réponses fader.
La seconde campagne, après la fin des tests logiciels, mesure **23,7 % de temps
en moins par bloc** : médiane de **2,615 s à 1,996 s**. Les seules lectures RX
passent de **1,282 s à 0,661 s**, soit **48,5 % de temps en moins**.
Les octets attendus sont tous identiques à la référence, sans perte socket
enregistrée ni débordement observé.

Le [manifeste public](fader-rx-benchmark-validation-2026-09-21.json) conserve
chaque mesure, les fenêtres effectivement lues, les dates et les empreintes.
La [procédure](fader-rx-benchmark.md) décrit le périmètre volontairement borné.

## Conditions et résultats

Chaque campagne suit `16, 32, 32, 16, 16, 32, 32, 16`, soit quatre blocs par
taille. Un bloc demande les douze octets connus à `0x8400` et huit octets de
relâchement, aux mêmes adresses dans tous les essais. Les réponses produisent
465 octets série. Seule la taille des lots de relecture RX change : les
contrôles restent à 16, la stabilisation à 250 ms et le plan fader identique.
La preuve initiale des huit relâchements et les lectures du compteur comm
encadrant chaque bloc sont exclues des médianes de bloc ci-dessous.

| Campagne | Heure UTC | PCAP / trames | Médiane bloc, lots 16 → 32 | Médiane RX, lots 16 → 32 |
|---|---|---|---|---|
| 1, avec tests logiciels en parallèle | 00:11:37,687–00:12:02,887 | 159 / 6 079 | 2,609722 → 1,988625 s | 1,281899 → 0,662942 s |
| 2, après leur fin vérifiée | 00:13:37,542–00:14:01,610 | 158 / 5 915 | 2,615368 → 1,995907 s | 1,282446 → 0,660659 s |

Le second relevé confirme le premier sur ce scénario court. L'absence de
tests logiciels concurrents a été contrôlée avant son lancement ; l'ordinateur
n'était pas pour autant isolé de tous ses services. Les longueurs des trois
fenêtres de chaque bloc varient avec la position dans le tampon circulaire.
Leur somme reste 465 et le manifeste conserve chaque découpage : par exemple,
`170 + 256 + 39` puis `167 + 256 + 42` au début de la seconde campagne.
Les durées ne sont ni une mesure de latence tactile ou audio, ni une garantie
de gain identique sur une longue collecte.

## Vérification des échanges et des effets

L'audit indépendant reprend les **317 PCAP et 11 994 trames** des deux
campagnes : unicité des captures, ordre chronologique des blocs et des contrôles,
ACK, adresses, tailles de lots réellement transmises, réponses série complètes
et comparaison des octets. Il vérifie aussi les empreintes des manifestes et
des audits, puis recalcule les médianes depuis les durées enregistrées.

Les statistiques de pertes socket sont connues et nulles. Le compteur de
débordement diagnostic comm vaut zéro avant et après chacun des seize blocs.
Les contrôles RX montrent un producteur stable pendant la copie et aucun
nouveau débordement. Chaque fin de bloc confirme huit états tactiles neutres
et le mode normal `0`. Les deux collecteurs sont terminés, sans erreur, et
leurs relances de passerelle retournent zéro. Les processus de la passerelle
et du pointeur ont été vérifiés après la dernière campagne, console Online.

## Sources, tests et conservation

Le code testé et exécuté correspond au commit `6eddde4`. Ses empreintes ont
été revérifiées après les deux campagnes. **450 tests locaux passent en
104,745 s**, aucun ignoré ; la compilation Python et le contrôle non modifiant
de l'inventaire des commandes passent également. Les tests couvrent notamment
les bornes RX, les valeurs `00–ff`, une réponse absente, le bouclage, la
récupération, une fausse étiquette de taille et l'arrêt au débordement.

L'archive privée `procontrol-fader-rx-benchmarks.tar.gz` contient les deux
campagnes, les références, les audits, les sources via bundle Git, les journaux
de tests et l'état final des services. Ses **1 008 membres** sont vérifiés,
pour **2 303 517 octets**. SHA-256 :

```text
142e973fd3cb72c3274b140060099fdba803b8974bf349187797917d36f16efe
```

La copie dans `~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`
a été extraite dans un dossier neuf. Son bundle a été cloné au commit exact ;
les deux audits, exécutés depuis ces sources restaurées, reproduisent les
rapports initiaux à l'exception de leur date de vérification. Il s'agit d'une
restitution des preuves hors ligne, sur le même ordinateur, sans essai de
réinstallation du firmware. Les PCAP et binaires constructeur restent privés ;
les outils, tests, méthodes et empreintes sont conservés dans Git public.

## Décision et prochaine étape

Le mode 32 reste expérimental et limité au plan connu `0x8400 + 12 octets`,
suivi des relâchements. Les lecteurs ordinaires conservent leur défaut 16.
Avant une extension à des adresses ou plans différents, élargir la validation
de façon bornée, avec les mêmes contrôles et l'arrêt à la première anomalie.
Les quatre intervalles manquants du programme fader et les bootstraps restent
à lire. Aucun gain musical, aucune endurance et aucune restauration matérielle
ne sont affirmés à partir de ces seize petits blocs.
