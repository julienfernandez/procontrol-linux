# Fenêtre de greffon suivant la ProControl

Extension locale d’Ardour 9.8 + passerelle, 15 septembre 2026.

## Utilisation

- EQ IN/EDIT ouvre l’EQ LSP de la voie ; DYN IN/EDIT ouvre son compresseur.
- SELECT sur une autre voie, Channel Matrix ou changement de banque conserve
  la famille EQ/compresseur et passe à l’instance de cette voie.
- INSERTS/PARAM montre la liste des greffons sur les huit écrans DSP ; SELECT
  d’une ligne entre dans le greffon et ouvre son interface Ardour.
- Le navigateur reste un navigateur quand on change de voie. Pour un greffon
  générique hors des profils LSP EQ/compresseur, le changement de voie revient
  à la liste pour choisir une cible explicite.
- ESCAPE, sortie d’édition ou retour à la liste ferme la fenêtre gérée.
- Si on ferme la fenêtre avec sa croix, elle reste fermée jusqu’à un nouveau
  choix de cible ou une nouvelle entrée en édition.

Le suivi attend des descripteurs et une identité de piste valides. Une courte
notification de catalogue conserve la fenêtre ; les retours de paramètres ne
provoquent pas de nouvelle ouverture. Une réponse absente est réessayée une fois.
Les faders et paramètres audio ne sont pas modifiés par le suivi de fenêtre.

## Extension OSC locale

Ces messages ne sont PAS des commandes officielles d’Ardour 9.8. Ils sont ajoutés
par `native/ardour-9.8-plugin-ui.patch`, sur le commit officiel
`22ed8656c2533e325322ff11831448e5123e0d4b`.

| Message | Types | Effet |
| --- | --- | --- |
| `/procontrol/plugin_ui/version` | aucun | Répond avec la version entière 1 |
| `/procontrol/plugin_ui/show` | ssis | Chemin session, ID persistant route, index greffon 1-based, nom exact |
| `/procontrol/plugin_ui/result` | ssisi | Réponse : mêmes arguments puis 1 succès / -1 cible refusée |
| `/procontrol/plugin_ui/clear` | aucun | Ferme la fenêtre gérée par cet émetteur OSC |
| `/procontrol/plugin_ui/cleared` | i | Confirme le traitement de clear |

Le serveur vérifie la session, l’ID persistant, l’index nth_plugin et le nom.
Il garde une référence faible au processeur. ShowUI/HideUI sont les signaux
natifs de Processor, raccordés au thread graphique par ProcessorWindowProxy.
Mackie et FaderPort utilisent ces mêmes signaux. Un clear provenant d’une
ancienne adresse OSC ne ferme pas la fenêtre prise en charge par un nouveau client.
La gestion concerne la fenêtre choisie par la passerelle, pas toutes les fenêtres
ouvertes à la main. Une absence de l’extension désactive uniquement ce suivi.

## Compilation et installation

Source : `work/ardour-build-9.8` à la racine de l’espace de travail.
Compilation incrémentale : `python3 waf build --targets=libardour_osc -j3`.
Bibliothèque : `build/libs/surfaces/osc/libardour_osc.so`.
Destination : `~/.local/opt/ardour-9.8/lib/ardour9/surfaces/libardour_osc.so`.
Arrêter Ardour normalement avant de remplacer le module ; conserver sauvegarde
et SHA dans `plugin-window-validation.json`. Une mise à jour d’Ardour peut
remplacer ce module ; le patch doit alors être adapté/recompilé.

## Plusieurs protocoles à la fois

Ardour accepte plusieurs surfaces simultanément. Le gestionnaire
ControlProtocolManager maintient aussi plusieurs instances de protocoles.
Une passerelle peut donc exposer OSC, MIDI générique et une Mackie virtuelle.
Cela ne fusionne pas automatiquement leurs fonctions : banques, sélection et
propriété des sorties doivent être coordonnées. Une seule logique doit piloter
chaque moteur/LED pour éviter les commandes doubles et retours contradictoires.

Pour les fenêtres, cette extension reprend directement les fonctions natives
utilisées par Mackie ; aucune Mackie virtuelle supplémentaire n’a été activée.
Pour les commandes Linux, le pont X11 existant reste distinct des commandes DAW.
Le passage MIDI de la console reste à étudier, pas implémenté par ce travail.

Références primaires :
- https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-control/
- https://github.com/Ardour/ardour/blob/9.8/libs/ardour/control_protocol_manager.cc
- https://github.com/Ardour/ardour/blob/9.8/libs/ardour/ardour/processor.h
- https://github.com/Ardour/ardour/blob/9.8/libs/surfaces/mackie/subview.cc
- https://github.com/Ardour/ardour/blob/9.8/gtk2_ardour/processor_box.cc

Validation automatisée : 150 tests passent, dont suivi de cible, maintien pendant
catalogue, changements voie/greffon, réponse ancienne, retry borné, sortie,
reconnexion et absence d’extension. Validation en application consignée dans
`plugin-window-validation.json`.

Validation réelle : EQ et compresseur ouverts sur plusieurs voies, refus des
cibles incohérentes, fermeture limitée au client propriétaire. L’utilisateur
confirme le suivi EQ → compresseur → autre voie depuis la console.
