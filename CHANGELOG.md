# Historique des versions

## 17 septembre 2026 — stabilité OSC

- Port de retour OSC stable, reconnexion après silence et fermeture silencieuse
  lors des erreurs ; limitation des journaux répétitifs et télémétrie mémoire/CPU.
- Patch Ardour9.8 : bornes des tableaux de départs, durée de vie des surfaces
  et observateurs OSC, ordre d’arrêt du thread et libérations de ressources.
- Outil de vérification OSC sur une session de test, preuve ASan et rapport
  de validation ;179tests passent.
- Reconnexion réelle vers huit pistes vérifiée ; endurance nocturne non validée.

## v0.1.0 — 15 septembre 2026

Première version du projet suivie dans Git. Elle regroupe le travail initial
sur la ProControl originale et son interfaçage Ethernet / OSC avec Ardour.

- Passerelle persistante, lancement sans root via helper dédié et réglages web.
- Transport, sélection, banques, gain, pan, automation et retours lumineux.
- Faders motorisés, afficheurs, compteur, vumètres stéréo et master calibré.
- Trackpad, clics et clavier ALPHA sous X11.
- Navigation DSP, profils LSP EQ/compresseur et suivi des fenêtres Ardour.
- Regroupement du jog à 50 Hz, lots de huit cibles moteurs et reprise ACK à
  100 ms ; validation physique intensive de cette dernière évolution en attente.
- 176 tests, documentation du protocole, mesures et provenance des références.

Version expérimentale, configurée initialement pour la machine et la console
de développement. Les crashs historiques d'Ardour ne sont pas déclarés résolus.
