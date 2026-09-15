# Réutilisation directe de la branche ProControl

La demande utilisateur est de s'appuyer franchement sur le code GitHub qui
fonctionne déjà. La table `procontrolmap.py` du commit
`b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069` est donc conservée **sans modification**
dans `vendor/reacontrol24`, avec les mentions PhaseWalker et la licence GPLv3 ou
ultérieure. [Provenance et empreintes](../vendor/reacontrol24/README.md).

Le module `tools/procontrol_mapping.py` adapte en Python 3 le parcours de cette
table, le découpage des commandes et la conversion des valeurs de fader du
[ReaCommon.py de référence](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/ReaCommon.py).
Les boutons, contacts et noms viennent de la table d'origine. Le pont OSC
utilise désormais ses adresses Play/Stop ; leur correspondance physique est
déjà confirmée par nos essais. Les autres mappings sont disponibles pour
l'analyse, sans encore déclencher de nouvelles actions dans Ardour.

Le daemon enregistre ce décodage dans chaque événement entrant de commande et
indique le commit de référence dans les métadonnées. Les émissions restent
online, ACK et maintien ; les sorties faders, LEDs et vumètres ne sont pas encore
activées. Les messages inconnus restent conservés avec leurs octets.

## Application à la capture existante

Capture : `20260913T163251Z-online-probe-9g3d1oq0/traffic.pcap`, SHA-256
`e1e84c6b7a3fc69b2ec2cda2aa3d5024bbe1e24bdd3d118fe724e9b06fe49388`.
Le rapport `reference-decoding.json` adjacent contient les numéros des trames,
horodatages et octets de chaque événement : **204 correspondances dans la
table**, 175 événements sans correspondance, aucun événement classé malformé
par ce décodeur. Ces nombres incluent les messages broadcast de commande.

| Interprétation issue de ReaControl | Nombre | Observation complémentaire |
|---|---:|---|
| Mouvement de fader, canal 1 | 81 | Valeurs brutes de 0 à 610, échelle candidate 10 bits |
| Contact de fader, canal 1 | 14 | Pressions et relâchements selon le bit de la table |
| Encodeur, canal 1 | 36 | Identification de classe ; pas encore de conversion de pan Ardour |
| Mouvement de fader, canaux 2 / 3 | 3 / 13 | Valeurs brutes nulles dans cet essai |
| PLAY / STOP | 2 / 4 | Inclut appui et relâchement ; gestes contrôlés déjà documentés |

Les manipulations libres ne permettent pas de valider physiquement chaque
nom. Certaines commandes de zone DSP aboutissent même à `track/23/...` dans
la table : ce résultat est conservé comme libellé de référence, **pas comme
preuve d'une vingt-troisième tranche physique**. La famille `f0 13 00 60 ...`
reste sans correspondance. Réutiliser cette base accélère l'analyse tout en
laissant ses lacunes visibles.

```bash
python3 tools/decode_procontrol.py captures/20260913T163251Z-online-probe-9g3d1oq0/traffic.pcap --mac 00:a0:7e:a0:ad:9c
# --json NOUVEAU_FICHIER.json conserve aussi le détail, sans écraser un rapport.
```

Le découpage multiplexé reste l'heuristique du projet tiers, pas une grammaire
complète démontrée. Le transport actif continue d'accepter uniquement un bouton
PLAY/STOP complet par corps. Une valeur brute de fader ne se transpose pas
automatiquement en gain Ardour : la courbe, le contact et les échos doivent
encore être testés ensemble avant d'activer la motorisation.

## Maintien et prochaines parties à reprendre

Le principe historique des maintiens et ACK a été relu dans `DeviceSession`.
La version utilisée repousse bien son horloge d'envoi lors des ACK. Notre petit
daemon n'envoie pas encore les retours continus de LED/fader du client complet ;
il doit garder une cadence de maintien indépendante pendant les gestes.
[Chronologie, correction et limites de validation](online-2026-09-13.md).

La suite peut reprendre `_ReaFader` pour les échanges bidirectionnels et le
contact, `ReaButtonLed` pour les retours de boutons, `ProCscribstrip` pour les
afficheurs et `ProCvumeter` pour les niveaux. Leur adaptation vers les adresses
OSC d'Ardour reste nécessaire : le client d'origine parle à Reaper. La classe
commune des vumètres comporte des réserves d'adressage ProControl ; elle servira
de base aux essais d'un canal à la fois.

Validation logicielle de l'intégration : **36 tests réussis**, dont conservation
de l'empreinte du mapping, vecteurs PLAY/STOP, contact/solo des huit tranches,
bornes et signature des faders, découpage et préservation des inconnus ; test
UDP local du pont Ardour également réussi.
