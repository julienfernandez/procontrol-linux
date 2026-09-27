# CHANNEL MATRIX : première tranche en solo/mute et suivi d'EQ

## Signalement et limites de l'observation

Le 27 septembre au soir, l'utilisateur décrit une première tranche qui passe en
solo ou mute lors de passages entre groupes de huit. Il précise utiliser les
touches **CHANNEL MATRIX**, avec un changement audible, et signale également un
comportement étrange lors du changement de piste avec un EQ ouvert. Il ne peut
pas refaire l'essai physique pendant cette intervention. Le détail visuel du
second symptôme n'a pas encore été précisé.

Ardour 9.8 PID 272570 reste ouvert sur `studio-mpc-usb-jette-toi`. La passerelle
initiale PID 249952 et le pointeur PID 249955 sont vivants ; le descripteur 3 de
la passerelle détient son verrou. La base Git est
`16d50ca2299695ec96968e5ef4d248c7ccc076c3`, avec de nombreuses modifications locales
antérieures conservées. Les preuves privées et copies avant intervention sont
dans `work/bank-solo-20260927/`.

## Ce que les journaux établissent

Les journaux tournants conservés montrent, à 19:23:20 UTC, les touches de mode
MUTE (`90 25 57`), SOLO (`90 26 57`), puis REC (`90 27 57`). À 19:23:22, les
touches 1 puis 9 produisent bien des actions `matrix recenable` : ce sont des
sélections de groupe **et** des actions sur les pistes, selon le mode mémorisé.
À 19:23:29, SELECT (`90 24 57`) restaure la sélection simple. Les passages vers
1/9 ensuite enregistrés sont en mode SELECT. Les événements solo de tranche
observés à 19:23:34 et 19:25:12 suivent le code physique `90 07 40`.

Ces traces ne prouvent donc pas que l'incident décrit s'est produit en mode
SOLO/MUTE. Les anciens journaux n'enregistraient ni les retours solo/mute ni les
arguments OSC après conversion entre tranche physique et piste absolue.

Le modèle logiciel reproduit le mécanisme : en mode SOLO/MUTE persistant,
1 → 9 → 17 → 25 applique ce mode aux premières pistes des groupes. En SELECT,
56 changements successifs envoient uniquement `/strip/select`, sans modifier
le cache de mixage. Appuyer sur **SELECT de CHANNEL MATRIX** remet les touches
numérotées en sélection simple. Les flèches BANK, hors NUDGE, changent de groupe
sans cette action de matrice.

La capture passive de 180 secondes est une trace de repos, pas une reproduction :
65 161 trames, 61 Ethernet et 65 100 loopback ; aucun appui de console ni écriture
solo/mute/armement. Dumpcap signale zéro perte Ethernet et un paquet loopback
évacué à la clôture. SHA-256 PCAPNG :
`6f758dfae150956763101f22f49cc97f126eaf862b7a8795ab76f8abd779734b`.

## Défaut distinct corrigé dans le suivi de fenêtre

Le suiveur conservait la fenêtre native de l'ancienne piste pendant l'attente
des descripteurs de la nouvelle. La fenêtre restait donc manipulable alors que
la console avait déjà changé de cible. Le correctif ferme cette ancienne
fenêtre dès qu'une autre identité de piste est demandée et que la nouvelle
n'est pas encore prête. Les rafraîchissements de la même piste gardent leur
fenêtre ; si la nouvelle cible est déjà prête, elle remplace directement l'autre.

Deux tests de transition échouent avec l'ancien suiveur et passent avec le
correctif. Ils vérifient également qu'une confirmation tardive de l'ancienne
fenêtre ne la rétablit pas. Cela confirme le défaut de transition logiciel,
pas son identité avec tous les symptômes rapportés par l'utilisateur.

## Journal de diagnostic durable

`run/control-audit.jsonl` conserve désormais les contextes avant/après,
mode MATRIX, banque de huit, piste et identité persistante, état de l'éditeur,
actions interprétées et cibles OSC absolues. Les retours solo/mute/armement ne
sont consignés que lorsqu'ils changent ; l'état initial reste distinct par
`previous: null`. Les ouvertures/fermetures de fenêtre et écritures de paramètres
sont aussi conservées. Un échec d'envoi indique `sent: null` plutôt qu'une fausse
absence de transmission partielle.

Ce journal est borné à quatre fichiers de 2 Mio et séparé des vumètres et des
sondages de transport. Le statut expose aussi `matrix_mode` et `matrix_bank`.
Le diagnostic ne change aucune règle de sélection, aucun solo/mute ni paramètre
audio. Les fichiers de session et les captures restent privés.

## Déploiement et vérifications

À 20:05 UTC, arrêt contrôlé du pointeur puis de la passerelle, remplacement des
deux modules préparés (`plugin_window.py`, `procontrold.py`), puis relance des
deux services. Aucun deuxième émetteur Ethernet concurrent. Passerelle PID
276957, pointeur PID 276960 ; console Online, Ardour répond, 220/220 retours
acquittés et aucun timeout au contrôle. Le mode MATRIX est SELECT et la banque
affichée revient à 1. Ardour garde le PID 272570 et le fichier de session garde
son SHA-256. Le transport Juju reste en 32×32 avec Master stéréo Behringer.

Validation locale : **517 tests Python réussis**, tests JavaScript de vumètres
et de polling réussis, inventaire généré à jour, syntaxe des modules préparés
vérifiée. Les deux cas nouveaux de fenêtre échouaient avant le correctif et
passent après. Le journal dédié est effectivement ouvert par le nouveau
processus et contient les états de mixage reçus à la connexion.

La validation physique du symptôme intermittent reste à faire lorsque
l'utilisateur pourra reprendre ses gestes. Le correctif de fenêtre et les
preuves de routage ne doivent pas être présentés comme une résolution prouvée
du premier signalement solo/mute.
