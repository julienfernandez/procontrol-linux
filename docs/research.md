# Références examinées — 13 septembre 2026

Recherche web et inspection de sources GitHub, sans exécution des daemons tiers.
La recherche n'est pas exhaustive ; aucun résultat ne démontre à lui seul la
compatibilité complète avec la console présente. Les commits ci-dessous figent
les versions consultées.

| Projet / branche | Ce qui a été vérifié | Utilité et limite |
|---|---|---|
| [phasewalker18/ReaControl24](https://github.com/phasewalker18/ReaControl24) | Projet d'origine Control\|24, bridge vers Reaper OSC | Référence historique ; ne pas assimiler les modèles |
| [phunkyg/ReaControl24 — Release](https://github.com/phunkyg/ReaControl24/tree/2a963e9c0c8beb52f7a1e39164c4e93c3580ec7d) | Capture/injection pcap, en-tête Ethernet et session, mappings Control\|24 | Commit `2a963e9c0c8beb52f7a1e39164c4e93c3580ec7d`, 26/06/2020 ; Python 2 historique |
| [DEV_OtherDevices](https://github.com/phunkyg/ReaControl24/tree/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069) | Fichiers **spécifiques ProControl**, sélection de `MAINUNIT`, adaptations afficheurs/LEDs | Commit `b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069`, 14/02/2021 ; expérimental, unité principale |
| [DEV_OtherDevices_Py3](https://github.com/phunkyg/ReaControl24/tree/d0a4344603f3ba5900fa3128ad3795a35a059399) | Branche distincte avec commit « Run Python 2to3 script » | Commit `d0a4344603f3ba5900fa3128ad3795a35a059399`, 13/02/2021 ; conversion automatique, fonctionnement actuel non testé |
| [Davitekk/C24-Engine-Renewed](https://github.com/Davitekk/C24-Engine-Renewed/tree/94d7a3ba42726db8fd5da8151429cc7d28ea7b47) | Collection Python 3, Ethernet brut, HUI, outils de mapping/LEDs ; développée et testée sur macOS selon son README | Commit `94d7a3ba42726db8fd5da8151429cc7d28ea7b47`, 16/08/2026 ; **Control\|24**, pas preuve ProControl |
| [Davitekk/Control24-Engine](https://github.com/Davitekk/Control24-Engine) | Le dépôt actuel est un README pointant vers C24-Engine-Renewed | Suivre la collection ci-dessus |

## Éléments spécifiquement ProControl

- [Issue #5](https://github.com/phunkyg/ReaControl24/issues/5) : utilisateur rapportant
  faders, mute/solo et transport fonctionnels. Le problème de contact tactile
  initial est déclaré résolu après correction du code et ajout du mapping OSC
  [le 23 janvier 2019](https://github.com/phunkyg/ReaControl24/issues/5#issuecomment-456671130).
  C'est un retour d'usage externe, pas un test de notre kit.
- [Issue #8](https://github.com/phunkyg/ReaControl24/issues/8) : détection de
  `MAINUNIT` et firmware `1.37` dans un journal ; erreurs avec les extensions.
  Notre propre annonce a depuis confirmé cette même version. Un
  [journal inclus dans les commentaires](https://github.com/phunkyg/ReaControl24/issues/8#issuecomment-575794718)
  montre online e2, ACK a0, annonces e1 et keepalives acquittés.
- [Issue #9](https://github.com/phunkyg/ReaControl24/issues/9) : **lire jusqu'à la
  résolution**, pas seulement le problème initial de retour Offline. Après un
  [contournement fonctionnel avec control24d.py + procontrolosc.py](https://github.com/phunkyg/ReaControl24/issues/9#issuecomment-617555949),
  le développeur [corrige l'extrémité du pipe utilisée](https://github.com/phunkyg/ReaControl24/issues/9#issuecomment-617691997).
  L'utilisateur confirme [ReaControl.py fonctionnel dans les deux sens](https://github.com/phunkyg/ReaControl24/issues/9#issuecomment-617918597)
  le 22 avril 2020. Il existe donc un succès ProControl documenté ; les limites
  des mappings ne doivent pas être présentées comme une absence de session réseau.
- [PR #10](https://github.com/phunkyg/ReaControl24/pull/10) : correction de
  l'octet de famille `f0 13 01` vers `f0 13 00` pour plusieurs sorties ProControl.
- [Issue #12](https://github.com/phunkyg/ReaControl24/issues/12) et sa
  [pièce jointe texte](https://github.com/phunkyg/ReaControl24/files/4520019/Ptewlscapture.txt) :
  extraits d'hexadump attribués à une capture Pro Tools/ProControl, avec EtherType
  `0x885f` et adressage de la deuxième rangée d'afficheurs. Le fichier consulté
  est un **extrait texte de 4 123 octets**, pas un PCAP complet ni une capture locale.
- [Issue #22](https://github.com/phunkyg/ReaControl24/issues/22) : disparition du
  texte des afficheurs après rafraîchissement. La présence d'un mapping ne signifie
  donc pas que tous les comportements ont été résolus.

Fichiers à relire lors de l'analyse des premières trames :
[ReaControl.py](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/ReaControl.py),
[ReaCommon.py](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/ReaCommon.py),
[procontrolosc.py](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/procontrolosc.py),
[procontrolmap.py](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/procontrolmap.py).

## Autres références

[V-Control Pro de Neyrinck](https://docs.neyrinck.com/v-control-pro/pro-control/)
documente la prise en charge ProControl. Cela montre une solution existante ;
ce manuel n'est pas une spécification libre du protocole.

[Le manuel OSC d'Ardour](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/)
documente contrôle et feedback. Le futur adaptateur doit respecter ce schéma,
et non supposer que `ProControl.ReaperOSC` est directement utilisable dans Ardour.

La branche ReaControl24 examinée est GPLv3 ou ultérieure dans ses en-têtes de
code. Le démon de test local reprend maintenant les choix documentés de session
dans une implémentation minimale Python 3, également GPL-3.0-or-later. Voir
[la référence de session](session-reference.md). Aucun daemon tiers n'a été exécuté.

À la demande explicite de l'utilisateur, la table ProControl est maintenant
réutilisée directement dans le kit, licence et provenance conservées. Le
parcours et les conversions de référence sont adaptés en Python 3 ; voir
[l'intégration réalisée](reacontrol-integration.md).
