# Historique des versions

## 20 septembre 2026 — revue, documentation et contrôles automatiques

- Intégration des correctifs jog/JACK/Link et de reconnexion du pointeur déjà
  déployés localement, avec leurs tests et preuves de validation.
- Inventaire des boutons corrigé pour inclure les éditeurs DSP et monitoring,
  neuf contextes indépendants et contrôle `--check` contre la dérive des guides.
- Carte fonctionnelle actualisée, index des guides, ordre des cinq patches
  Ardour et distinction entre essais logiciels, Ardour et matériel.
- CI GitHub : tests Python, inventaire, syntaxe, test natif Link, compilation du
  helper Ethernet et du pont Link avec SDK épinglé. [Détail de la revue](docs/review-2026-09-20.md).

## 20 septembre 2026 — édition, bibliothèque DSP et compteur

- Commandes d’édition adaptées aux groupes d’actions Ardour 9.8 : cuts, copie,
  suppression, duplication, calage, UNDO/REDO, SAVE et contexte explicite de l’éditeur.
- Sélection IN/OUT, pas d’une ou quatre mesures, boucles, punch et jog fin ;
  validation sur une copie jetable. [Guide d’édition](docs/console-editing.md).
- INS/SEND par tranche ouvre le navigateur DSP de cette piste ; EQ/DYN ajoutent
  leur effet absent. Huit profils proposés : EQ, compresseur, réverb, délai,
  phaser, Chaleur, Tube et Tape. [Bibliothèque](docs/curated-plugins.md).
- Compteur BBT de largeur fixe et pont unidirectionnel Ardour → Link ;
  [synchro MPC et limites](docs/counter-mpc-sync.md).

## 20 septembre 2026 — reprise de la souris après redémarrage

- Le pont X11 reste en attente lors de l'arrêt de la passerelle et se reconnecte
  automatiquement, en conservant la sensibilité configurée.
- Libération des touches/clics maintenus, abandon de l'ancien flux et tolérance
  à un journal momentanément absent pendant sa rotation.
- Régression reproduite sur l'ancien code ; reprise du même processus vérifiée
  après une relance réelle de la passerelle, Ardour restant ouvert.
  Voir [le rapport](docs/pointer-recovery-2026-09-20.md).

## 20 septembre 2026 — monitoring par tranche

- Page MON/Ø : ASSIGN/MUTE bascule IN/DISK, INPUT/OUTPUT ciblent la piste
  sélectionnée et DEFAULT rend le choix à Ardour. Aucun changement de REC.
- Affichages et voyants confirmés par OSC ; AUTO lent, attente rapide.
- Écritures des deux bits d’écoute sérialisées pour éviter IN+DISK involontaire ;
  cibles absolues protégées lors des changements rapides de sélection/banque.
- 223 tests logiciels passent. Essai physique et auditif de cette extension
  encore à effectuer ; voir [le guide](docs/track-monitoring.md).

## 20 septembre 2026 — jog, début de session et Link

- Correction native de la fuite des événements de transport rejetés et du plan
  JACK périmé qui pouvait redémarrer Ardour à chaque cycle au start.
- Compteur OSC et jog relatif alignés sur la position audible de l'interface.
- Maintien de la lecture Link pendant un locate JACK, compteurs de vrais
  démarrages/arrêts et protection du jog OSC sans observateur de feedback.
- Tests natifs du pool et de Link, scénario de recul au start et outil de
  stress reproductible sur copie de session ; [preuves et limites](docs/jog-link-stability-2026-09-20.md).

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
