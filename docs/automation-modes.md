# AUTO de chaque voie : modes d’automation du fader

Implémenté le 15 septembre 2026 pour Ardour9.8 et ProControl originale.

## Utilisation

AUTO contrôle l’automation du gain/fader de sa propre voie, sans changer la
sélection du projet. Un appui avance ; relâcher avant le suivant. Le maintien
n’effectue qu’un changement. Shift + AUTO recule dans le même cycle.

| Ordre | Mode Ardour | Voyant ProControl | Effet |
| --- | --- | --- | --- |
| 0 | Manual | tous éteints | Réglage manuel ; la courbe de gain n’est pas lue |
| 1 | Play | RD | Lecture de l’automation enregistrée |
| 2 | Write | WR | Écriture des valeurs du fader pendant la lecture |
| 3 | Touch | TC | Écriture pendant le toucher, puis reprise de la courbe |
| 4 | Latch | LT | Écriture après toucher, maintenue jusqu’à l’arrêt |

Le voyant TM reste éteint : le mode Trim de ProControl n’est pas un sixième
état d’automation du gain dans Ardour. Le trim de gain Ardour est un contrôle
indépendant ; il ne doit pas être confondu avec Manual. Les voyants indiquent
le mode choisi, pas la présence d’un enregistrement audio. REC/RDY reste séparé.
Les contacts tactiles des faders transmettent déjà gain/touch 1 puis0.

Les boutons de la zone AUTOMATION continuent à cibler le contrôle choisi par
VOL/PAN/MUTE/TRIM. AUTO par voie et ses lampes suivent spécifiquement le fader.
Le retour des changements faits à la souris utilise le même état OSC que les
changements faits depuis AUTO. Aucune requête périodique de catalogue ajoutée.

## Défaut corrigé

L’ancien AUTO lisait /strip/gain/automation et revenait souvent à Play. Avec
notre gainmode2, Ardour9.8 émet l’état sous /strip/fader/automation : cette réponse
est désormais normalisée dans le cache commun du gain. L’affichage des lampes
et la remise en place des états après banque/reconnexion sont implémentés.

Les appuis rapides conservent la dernière demande encore en attente pour
calculer le mode suivant. Les acquittements intermédiaires ne font pas repartir
le cycle en arrière. Cette anticipation expire après1s ; les lampes affichent
uniquement le mode reçu d’Ardour. Sans état connu ou catalogue valide, AUTO
attend les retours au lieu de supposer un mode initial. Une modification externe
hors des demandes en attente devient immédiatement prioritaire.

## Protocole et références

Bouton : 90 05 (zone|40) pressé, 90 05 zone relâché ; zones00..07.
Lampes : F0 13 00 20 zone bits F7. Bits RD04, TM08, LT10, TC20, WR40.
ProCautomode adapte l’octet2 de _ReaAutomode de01 à00 pour ProControl.

OSC émis : /strip/gain/automation ii [SSID,mode], mode0..4. Le SSID est remappé
selon la banque ; les lampes utilisent toujours la position physique0..7.
Les valeurs internes AutoState d’Ardour sont des bits : ne pas les confondre
avec les indices OSC0..4. Lampes des tranches vides/déconnectées effacées.

Sources primaires vérifiées :
- Ardour9.8 libs/surfaces/osc/osc.cc, OSC::set_automation (cinq modes0..4).
- Ardour9.8 libs/surfaces/osc/osc_route_observer.cc, gain_automation (aliasfader).
- Ardour9.8 gtk2_ardour/gain_meter.cc, menu Manual/Play/Write/Touch/Latch.
- vendor/reacontrol24/procontrolosc.py, ProCautomode ; ReaCommon.py, _ReaAutomode.
- https://github.com/Ardour/ardour/blob/9.8/libs/surfaces/osc/osc.cc
- https://manual.ardour.org/mixing/automation/automation-states/
- https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/automation/

La page OSC historique liste0..3 ; Latch4 est vérifié dans le code9.8 installé.
La photo utilisateur confirme les inscriptions WR/TC/LT/TM/RD ; les codes
proviennent du driver ProControl de référence, pas d’une déduction de la photo.

## Validation

165 tests réussis, dont15 scénarios dédiés : aliasgainmode2, cycle, Shift,
appuis rapides, double trame/maintien/relâchement, mode inconnu, réponse externe,
expiration, banque, Master, restauration/reconnexion, données invalides,
confirmation des lampes et compatibilité avec édition EQ.

Preuves de déploiement et validation physique : automation-validation.json.
Capture mixte Ethernet/OSC : captures/automation-modes-20260915/live.pcapng.


Validation physique reçue : « Oui, les cinq états correspondent ».
Capture clôturée :20appuis sur voies2/3,20commandes,21retours et21sorties
lampes toutes acquittées. Appui→émission lampe médiane3.8835ms, max5.112ms ;
mesure réseau, pas capteur optique. dumpcap signale1paquet flushed à la clôture
sur chaque interface ; PCAPNG original et dérivé conservés avec SHA256.
Ardour peut passer automatiquement de Write à Touch à l’arrêt de lecture ;
les voyants suivent aussi ce changement renvoyé par le DAW.
