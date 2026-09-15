# Choix pour ProControl : OSC d'abord avec Ardour

Comparaison du 13 septembre 2026, fondée sur le manuel officiel d'Ardour,
le code Ardour **8.4** correspondant à la version installée, les profils locaux,
et nos premiers essais de transport. Recommandation : garder OSC pour exploiter
la ProControl dans Ardour ; prévoir un adaptateur Mackie optionnel si un autre
DAW le justifie. Aucun réglage Mackie n'a été activé par le kit.

## Ce que signifie la liste Mackie

La liste représente des appareils et variantes utilisant la famille Mackie/Logic
Control, avec des profils de disposition. Le manuel précise que Mackie Control
et Mackie Control Pro emploient le même protocole. « Universal Pro » ne transforme
donc pas une ProControl Digidesign en appareil compatible en choisissant cette ligne.
Il faudrait que notre démon émule Mackie sur des ports MIDI virtuels, tout en
conservant la couche Ethernet Digidesign que nous venons de valider.
[Appareils et profils](https://manual.ardour.org/using-control-surfaces/mackie-control-protocol/devices-not-listed/),
[connexions MIDI](https://manual.ardour.org/using-control-surfaces/devices-using-mackielogic-control-protocol/).

Les fichiers installés `mc.device` et `mcpro.device` décrivent notamment huit
tranches, fader master, jog, affichage temporel et contact des faders. La longueur
du catalogue ne mesure pas le nombre de fonctions que notre console pourra exploiter.

## Comparaison appliquée à nos besoins

| Besoin | OSC avec Ardour | Mackie dans Ardour 8.4 | Conséquence pour nous |
|---|---|---|---|
| Transport, boutons, LEDs | Commandes et retours d'état ; PLAY/STOP déjà testés | Commandes, LEDs et affectations existantes | Les deux conviennent ; la conversion vers la ProControl reste à coder |
| Faders motorisés et contact | Position, gain et événements touch disponibles | Faders haute résolution et contact pris en charge | Aucun avantage décisif de Mackie ; vérifier résolution physique et échos de notre console |
| Noms et rangées d'afficheurs | Noms, valeurs, paramètres disponibles séparément | Format d'affichage MCU ; noms abrégés à six caractères dans le chemin standard | OSC laisse notre démon décider du contenu de chaque rangée |
| **Grands vumètres** | Niveaux numériques, notamment en dB, plus choix de retour | Chemin standard ramené à **13 segments**, surcharge séparée | **Avantage OSC** pour choisir nous-mêmes les seuils et l'échelle de la ProControl |
| Jog / shuttle / navigation | Modes jog, shuttle, marqueurs, scroll et banque | Gestion intégrée à la surface Mackie | Les deux fournissent une base ; le comportement exact reste à tester |
| Ergonomie et fonctions de mixage | Mapping sur mesure à développer | Organisation existante autour des touches et modes MCU | Mackie fait gagner des conventions ; OSC s'adapte mieux à une disposition particulière |
| Autres DAW | Les adresses OSC d'Ardour ne sont pas universelles | Un adaptateur MCU peut servir à d'autres DAW compatibles | Avantage Mackie si l'objectif devient une large compatibilité entre DAW |

Sources pour les fonctions OSC :
[contrôles et banques](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-control/),
[retours faders, noms, niveaux et paramètres](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/feedback-in-osc/),
[contact et automation](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/automation/),
[jog et shuttle](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/jog-modes/).

Le point des 13 segments provient de `Meter::send_update` dans le
[code Ardour 8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/mackie/meter.cc).
Ce n'est pas une limite attribuée à tous les appareils, extensions propriétaires
ou implémentations futures de Mackie. Le
[code des faders](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/mackie/fader.cc)
utilise un message de pitch bend sur 14 bits : Mackie ne doit pas être assimilé
à un simple contrôleur MIDI CC de 7 bits. Le
[code d'affichage des tranches](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/mackie/strip.cc)
montre le formatage et l'abréviation des noms avant leur émission.

Le manuel [SSL Nucleus](https://manual.ardour.org/using-control-surfaces/mackie-control-protocol/ssl-nucleus/)
montre d'ailleurs que Mackie sait gérer des vumètres séparés : le problème pour
nous n'est pas leur existence, mais la granularité du niveau disponible et les
choix d'affichage déjà effectués par le backend.

## Décision de développement

Conserver la session Ethernet et le modèle des contrôles indépendants de
l'adaptateur DAW. OSC est l'adaptateur prioritaire pour Ardour. Si un besoin
concret de compatibilité MCU apparaît, ajouter une sortie MIDI Mackie à cette
même base, plutôt que réécrire le protocole de la console.

Le futur mapping des vumètres doit encore mesurer les adresses, segments,
seuils, canaux et cadence acceptés par la ProControl. Le fait qu'OSC fournisse
des nombres en dB ne valide pas à lui seul cet affichage matériel. De même,
il faut tester les modes d'automation et le retour des paramètres réellement
utiles ; aucune comparaison de listes ne prouve une prise en charge exhaustive.
