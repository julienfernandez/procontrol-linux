# Écoute IN / DISK depuis la ProControl

## Utilisation

Le bouton **MON/Ø**, à gauche des huit potards, ouvre une page d’écoute des
pistes. Leurs noms restent affichés en bas ; la ligne supérieure indique la
source d’écoute de chaque piste de la banque.

| Geste | Résultat |
|---|---|
| MON/Ø | Ouvre ou ferme la page de monitoring des huit tranches |
| ASSIGN/MUTE sous le potard d’une tranche | Bascule cette piste entre IN et DISK, sans devoir la sélectionner |
| SELECT d’une piste, puis INPUT | Force l’écoute de son entrée, indépendamment de son armement REC |
| SELECT d’une piste, puis OUTPUT | Force l’écoute de ce qui est enregistré sur la piste, mode DISK |
| DEFAULT, dans la page MON/Ø | Rend à Ardour le choix automatique de la source de la piste sélectionnée |
| PAN, MON/Ø ou ESCAPE | Quitte la page ; les valeurs de mixage réapparaissent |
| EQ, DYN ou INSERTS | Quitte la page de monitoring et reprend l’édition des greffons |
| Shift + MON/Ø | Conserve l’ancien raccourci de polarité de la piste sélectionnée |

INPUT et OUTPUT ouvrent aussi cette page lorsqu’elle est fermée. Les boutons
de tranche fonctionnent sur la banque visible, y compris après BANK. Les
bus, le master et les emplacements vides ne reçoivent aucune commande de
monitoring. SELECT, les faders, MUTE, SOLO et REC conservent leur rôle.
Les rotatifs de tranches et DSP ne modifient aucun paramètre caché pendant
que la page de monitoring est affichée.

**IN** écoute l’entrée de la piste, même sans armer REC. **DISK** écoute les
régions de la piste. **AUTO** laisse Ardour choisir suivant le transport et
ses réglages de monitoring. DEFAULT ne change pas le mode d’automation du
volume et n’est pas le bouton AUTO de chaque tranche.

Ces commandes pilotent le monitoring logiciel d’Ardour. Le monitoring direct
d’une interface audio est indépendant. Elles ne changent ni les ports audio
de la piste, ni le routage du master, ni l’armement d’enregistrement.

## Affichage et voyants

| Texte en haut de la tranche | Voyant ASSIGN/MUTE |
|---|---|
| IN | Allumé fixe |
| DISK | Éteint |
| AUTO | Clignotement lent : une seconde allumée, une seconde éteinte |
| Attente | Clignotement rapide : attente d’un état ou de la confirmation Ardour |
| IN+DISK | Allumé ; les deux sources ont été activées depuis Ardour |
| ERREUR | Confirmation absente après deux secondes ; affichage pendant trois secondes |
| -- | Pas de piste compatible à cet emplacement |

Les voyants globaux INPUT, OUTPUT et DEFAULT reflètent les retours confirmés
de la piste sélectionnée. MON/Ø allumé indique que cette page est ouverte.
`SELECT?` demande une sélection unique lorsque les raccourcis globaux ne
peuvent pas déterminer leur cible. Les boutons ASSIGN/MUTE restent utilisables
directement par tranche.

## Contrat logiciel

La paire OSC `/strip/monitor_input` et `/strip/monitor_disk` vaut respectivement
`1,0` pour IN, `0,1` pour DISK, `0,0` pour AUTO, `1,1` pour les deux sources.
Les retours de tranche utilisent le feedback OSC existant. Les lectures
ponctuelles placent l’identifiant absolu dans le chemin OSC, par exemple
`/strip/monitor_input/3`, pour que la réponse reste identifiable.

Chaque changement est **sérialisé** : suppression de la source indésirable,
attente de son retour, puis activation de la source demandée et attente de
son retour. Dans Ardour 9.8, les deux commandes OSC font une lecture-modification
du même masque `MonitorControl`, dont l’écriture est différée au cycle audio.
Deux écritures immédiates peuvent donc partir du même ancien masque et activer
accidentellement IN et DISK ensemble.

Une commande garde l’identifiant absolu de sa piste même lors d’un changement
de banque ou de page. Les appuis rapides remplacent la cible demandée sans
envoyer deux écritures concurrentes. SELECT suivi immédiatement d’INPUT vise
la nouvelle piste demandée, avant même le retour visuel de sélection. Une
sélection relative non confirmée ou devenue trop ancienne ne réutilise pas
l’ancienne piste. Déconnexion et changement de catalogue annulent les demandes
en attente. Aucun `/refresh` global ni sondage périodique du catalogue ajouté.

Les clignotements passent par la file de sorties existante, avec regroupement
des états et un seul ACK Ethernet en attente. L’état du module est exposé
dans `run/status.json`, sous `track_monitor`.

## Références et validation

- Le **ProControl Guide 6.9**, Digidesign, pages imprimées 78–80 et 99–100,
  décrit MON/Ø, la sélection du mode d’écoute et les boutons PRE/POST/ASSIGN
  des tranches : [guide du fabricant, copie PDF](https://procomms.weebly.com/uploads/2/5/7/2/25726309/procontrol_guide.pdf).
  Ici, MON/Ø ouvre directement la page, et la bascule principale est IN/DISK.
- Les adresses de boutons viennent de la
  [table ProControl de référence](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/procontrolmap.py) :
  zone globale 8, codes 09/0A/0B/07 ; code 04 dans chaque tranche 0–7.
  Les photographies de l’utilisateur et le PDF confirment les libellés,
  pas les octets Ethernet de ces nouveaux gestes.
- [Retours OSC Ardour](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/feedback-in-osc/)
  et [réglages de monitoring](https://manual.ardour.org/recording/monitoring/monitor-setup-in-ardour/).
  Sources locales Ardour 9.8 : `osc.cc`, `osc_route_observer.cc` et
  `libs/ardour/monitor_control.cc` pour la sérialisation des deux bits.
- 20 septembre 2026 : **223 tests logiciels réussis**, dont 19 nouveaux tests
  pour le monitoring, les courses de sélection/banque, les retours, les délais,
  les retries, les modes DSP et l’indépendance de REC.
- Installation locale et redémarrage de procontrol/pointer effectués. Ardour
  fait simultanément l’objet d’un diagnostic de gel jog/Link dans un autre
  fil : aucun transport, réglage Link ni état d’écoute de sa session de test
  n’a été modifié pour cette validation. L’essai auditif et la confirmation
  physique de ces touches/voyants restent à faire après ce diagnostic.

## Suite envisagée pour ASSIGN global

Le bouton ASSIGN global est réservé à une future page de **routage des ports** :
choisir INPUT ou OUTPUT, parcourir les ports au potard de la tranche et valider
avec son bouton ASSIGN/MUTE ; ESCAPE annulerait le choix. Cette page n’est pas
implémentée par cette modification. La distinction reste visible : la page
MON/Ø choisit ce qu’on écoute ; la future page ASSIGN choisira les connexions.
