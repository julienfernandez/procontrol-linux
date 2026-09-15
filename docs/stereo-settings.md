# SELECT, stéréo et réglages locaux — 13 septembre 2026

## Changements installés

SELECT envoie désormais `/strip/select <SSID> 0`, conformément au traitement
OSC d'Ardour 8.4. La sélection des tranches et de CHANNEL MATRIX utilise le
même chemin. L'allumage SELECT reste piloté par le retour réel d'Ardour.

Le catalogue OSC contient toutes les pistes, bus, VCA et le master ; les banques
de huit sont calculées localement, bornées au catalogue. Les commandes, noms,
LEDs, faders et vumètres partagent la même correspondance. Une banque ne change
pas pendant un contact de fader. Une identité incertaine suspend le routage.

Le hook `ardour/procontrol_stereo.lua` est installé dans
`~/.config/ardour8/scripts/` et activé dans Ardour sous le nom
**ProControl Stereo Meters**. Toutes les 100 ms, il lit MeterPeak séparément
pour chaque canal audio et transmet les niveaux en UDP local sur 3820.
L'OSC standard reste sur 3819. Aucun routage audio n'est modifié par le hook.
Les métadonnées associent chemin de session, ID de route, nom, type et ordre.
Le pont recoupe le catalogue OSC ; il éteint les niveaux périmés après une seconde.

Les vumètres de tranche utilisent les adresses 0–7 à gauche et 32–39 à droite.
L'adressage droit est issu de ReaControl24 ; sa réussite physique sur cette
console doit encore être confirmée. Une piste mono laisse sa colonne droite éteinte.
Les niveaux OSC agrégés ne remplacent plus les niveaux indépendants.

## Réglages

Ouvrir **http://127.0.0.1:8765**. La page propose la sensibilité souris et jog,
et six affectations source/canal pour les grands vumètres. Le master gauche
et droit est présélectionné pour 1 et 2 ; 3 à 6 sont désactivés.

`settings.json` est enregistré atomiquement. L'application aux services actifs
passe par leurs sockets locaux ; les services relisent les réglages au démarrage.
La fermeture du navigateur ne les arrête pas. Le serveur écoute uniquement sur
la boucle locale, rejette les origines étrangères et ne possède pas de socket Ethernet.

Commandes depuis la racine du projet :

```sh
./procontrol start   # authentification Linux locale pour ouvrir Ethernet
./pointer start
./settings start
./procontrol status
./pointer status
./settings status
```

Ce sont des processus détachés ; aucun démarrage automatique au boot n'est installé.

## Calibration des six grandes colonnes

Les adresses physiques ne sont pas encore identifiées. Les entrées
`meter_addresses` restent `null` : les niveaux master sont disponibles mais
ne sont pas envoyés à une colonne choisie arbitrairement.
Le contrôle local `meter_test` allume une adresse à -12 dB pendant deux secondes,
puis l'éteint. Il emprunte la file Ethernet du démon, sans second émetteur.
Il faut observer les colonnes et conserver uniquement une correspondance confirmée.

Exemple depuis la racine du projet, démon actif :

```sh
PYTHONPATH=tools python3 - <<'PY'
from pathlib import Path
from surface_settings import rpc
print(rpc(Path('run').resolve(), 'control.sock',
          {'command': 'meter_test', 'address': 8}))
PY
```

L'adresse 8 est un **candidat**, pas un résultat de calibration.

## Validation et limites

- 69 tests automatisés : sélection, banques multiples et partielles, master,
  désaccord des catalogues, niveaux L/R différents, silence et données périmées,
  rejeu et valeurs invalides, configuration et API HTTP.
- Hook installé et actif : neuf routes reçues (huit pistes et master), deux
  canaux chacune ; correspondance complète avec le catalogue réel d'Ardour.
  La session était arrêtée : les niveaux reçus étaient le silence.
- Navigateur : modification 0,24 → 0,25, sauvegarde, rechargement conservant
  0,25, puis restauration de 0,24 ; message explicite d'application en attente
  lorsque les services sont arrêtés. Rendu inspecté.
- Restent à valider sur le matériel : SELECT corrigé, colonnes droites avec
  signal audio, calibration des six grands vumètres et master L/R physique.
- Les tests synthétiques de routage ne remplacent pas un essai de banques
  longues sur la console. Les limites départs/plugins de control-map.md subsistent.

Sources : [OSC Ardour 8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.cc),
[bindings Lua](https://github.com/Ardour/ardour/blob/8.4/libs/ardour/luabindings.cc),
[calcul des niveaux](https://github.com/Ardour/ardour/blob/8.4/libs/ardour/meter.cc).

### Contrôle visuel de la page

Concept conservé pendant le travail dans `work/procontrol-settings-concept.png` ;
capture du navigateur dans `work/settings-render.png`. Les deux images ont été
inspectées avec view_image. Browser/IAB a servi au contrôle fonctionnel et aux
rendus : dimensions du concept 1586×992, fenêtre courante, puis 390×844.

Comparaison : même ordre des sections et libellés, fond blanc et accents verts,
hiérarchie typographique sans sérif, tableau de six lignes, contrôles source/canal
et vumètres segmentés, bouton de sauvegarde et statut de connexion. Le contenu
est volontairement plus compact pour le laptop de 768 pixels de haut. Les états
« en attente » et les informations de calibration remplacent les niveaux illustratifs
du concept par l'état réel. Sur écran étroit, seul le tableau défile horizontalement.
Aucune erreur ni alerte de console navigateur ; aucun contenu essentiel inaccessible.

État à 19:43 UTC : serveur web actif ; daemon et pointer arrêtés en attente de
l'authentification pkexec locale. Une relance ponctuelle du pointeur attend le
démon pendant 15 minutes. Capture clôturée : 106 trames, zéro perte, dont 42
annonces 0x885f de la console vers le broadcast ; aucune validation active.

### Test lumineux à la demande

La page contient maintenant « Identifier les colonnes de la console » : choisir
une adresse candidate, « Éclairer 2 secondes », puis choisir la colonne réellement
observée et confirmer. Tester ne sauvegarde rien ; confirmer enregistre l'adresse
et applique les réglages. Les adresses de tranches et les doublons sont refusés.
Les colonnes 1/2 recevront alors le master L/R prévu par les affectations existantes.

QA Browser/IAB : page locale non vide, formulaire ouvert, test accepté par le
démon, confirmation sans colonne refusée par l'interface, aucune erreur console.
Aucune correspondance physique n'a été enregistrée sans observation utilisateur.

### Master configuré le 14 septembre

Identification rapportée par l’utilisateur : première colonne adresse décimale 10,
deuxième colonne 42. Configuration enregistrée et appliquée à chaud : master
gauche sur10, master droit sur42. Révision8, autres colonnes désactivées et adresses
non renseignées. La suite supposée des adresses reste une hypothèse.

### Suite des paires confirmée par l’utilisateur

Le 14 septembre : **10/42, 11/43, 12/44, 13/45**, adresses décimales.
Ces quatre paires sont conservées dans confirmed-meter-addresses.json.
Le master reste affecté à10/42 ; aucune source supplémentaire n’est affectée.
La page actuelle expose six sorties individuelles : ne pas confondre ses six
entrées de configuration avec ces quatre paires (huit adresses).
