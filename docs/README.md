# Guides et preuves de validation

Les guides ci-dessous décrivent les fonctions actuelles. Les rapports datés
conservent les observations de leur essai : leurs anciens compteurs de tests,
PID, réglages et sommes SHA ne décrivent pas nécessairement le runtime actuel.

## Utiliser la console

- [Atelier visuel ProControl — Mapping, apprentissage et presets](console-mapping.md).

- [Essais asynchrones, navigation et voyants](console-test-workflow.md).
- [Carte fonctionnelle](control-map.md) et [édition, cuts, sélection et boucles](console-editing.md).
- [Écoute IN / DISK / AUTO](track-monitoring.md) et [automation du gain](automation-modes.md).
- [Bibliothèque de huit effets](curated-plugins.md), [EQ / compresseur](eq-plugin-workflow.md),
  [Chaleur / Tube / Tape](warm-tape-plugins.md) et [INS/SEND par tranche](ins-send-browser-2026-09-20.md).
- [Compteur et synchronisation MPC / Link](counter-mpc-sync.md).
- [Clavier et souris](keyboard-mouse.md), [lanceur](desktop-launcher.md),
  [réglages stéréo](stereo-settings.md) et [lancement sans root](rootless-launch.md).

## Développer et reconstruire

- [Tests et structure du dépôt](../README.md#développement-et-tests).
- [Ordre des six patches Ardour et compilation native](../native/README.md).
- [Contrat OSC](ardour-osc-contract.md), [ordonnancement jog/moteurs](jog-motor-scheduling.md).
- [Inventaire généré des boutons](mapping-backlog.md) et [actions par mode](mapping-coverage.json).
- [Protocole observé](protocol.md), [capture contrôlée](capture-linux.md),
  [provenance des références](research.md).

## Vérifications récentes

- [Exploration du firmware et du diagnostic réseau](firmware-research-2026-09-20.md),
  [preuves, empreintes et adresses](firmware-research-2026-09-20.json).

- [Édition, sélection et voyants de transport](edit-interaction-2026-09-20.md).

- [Revue et publication du 20 septembre](review-2026-09-20.md).
- [Édition Ardour sur copie jetable](console-editing-validation-2026-09-20.json).
- [Jog, pool d’événements et Link](jog-link-stability-2026-09-20.md),
  [mesures](jog-link-validation-2026-09-20.json).
- [Reconnexion du pont souris](pointer-recovery-2026-09-20.md).
- [Bibliothèque DSP](curated-plugins-validation.json), [effets Tape/Tube](warm-tape-validation.json),
  [compteur et Link](counter-link-validation-2026-09-20.json).
- [Stabilité OSC du 17 septembre](stability-2026-09-17.md).

Les autres fichiers datés documentent l’enquête et ses résultats intermédiaires,
y compris des crashs ou hypothèses remplacées ensuite. Les captures brutes, sessions
audio, sauvegardes, binaires et journaux restent locaux et ignorés par Git.
