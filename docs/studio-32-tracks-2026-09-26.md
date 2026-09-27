# Projet de test : 32 canaux nommés en 16 pistes stéréo MPC

## Objectif et état final

Le 26 septembre 2026, demande d'étendre le projet de test par défaut, puis
précision : pistes stéréo nommées par paires comme le début de la liste.
La session `studio-mpc-usb`, cible du lanceur Studio et ouverte dans Ardour
9.8.0, contient désormais **16 pistes stéréo MPC**, de `MPC 01-02` à
`MPC 31-32`, regroupées dans cet ordre, puis `Behringer stereo` et
`Roland RS-9 MIDI`. Le Master est conservé.

Les effets existants gardent leurs paramètres et leur activation. Les huit
nouvelles paires n'ont pas de greffons et sortent vers le Master stéréo.
Leurs entrées restent libres : PipeWire expose **16 canaux USB MPC dans
chaque sens**, et cette intervention ne reconfigure pas la liaison USB.
Le nom des 32 canaux préparés dans Ardour ne prouve pas leur transport USB.

## Méthode

Transport arrêté et enregistrement désactivé, vérifiés par OSC. Sauvegarde de
l'état ouvert via `Common/Save`, puis copie complète du projet sur le même
disque. Modification par l'API native depuis la console Lua d'Ardour.

Une première interprétation avait ajouté `Audio 17` à `Audio 32`, déjà en
stéréo. Après précision de l'utilisateur, les pistes vides `Audio 10` à
`Audio 17` ont été réutilisées pour les huit nouvelles paires MPC et les
quinze pistes ajoutées en trop retirées. Présence de deux canaux, absence de
régions et de greffons contrôlées avant chaque retrait ou renommage.
Les identifiants des pistes préexistantes et leurs enregistrements sont conservés.

La console Lua n'expose pas `dofile` : l'essai a échoué avant toute mutation,
puis le script a été collé directement. Le tri des pistes est renormalisé
par le mixeur pendant les changements d'ordre ; Behringer et MIDI ont été
placées après toutes les paires MPC, puis l'ordre final relu par OSC et XML.

## Vérifications et limites

- 16 pistes MPC avec deux entrées et deux sorties audio chacune, vérifiées
  dans le fichier sauvegardé et avec `/strip/list` ; numéros OSC 1 à 16.
- Behringer puis MIDI après les pistes MPC, numéros OSC 17 et 18.
- Greffons originaux inchangés ; traitement et routage des huit premières
  paires MPC, de Behringer et de MIDI conservés. Seul l'ordre de présentation
  des TriggerBox de Behringer et MIDI change avec leur position dans la liste.
- Sources et régions XML inchangées. Après la première extension, 87 fichiers
  audio/MIDI et états de greffons, soit 148 038 928 octets, étaient identiques
  par SHA-256 à la copie originale ; la réorganisation ne traite que des pistes vides.
- Ardour est resté ouvert (PID 847067), passerelle PID 671903 en ligne et
  répondant, pointeur PID 622060 en ligne sans erreur ; aucun redémarrage.

Ces observations sont des vérifications logicielles, pas une écoute, un essai
physique des banques ProControl ou une validation d'endurance. Pour recevoir
32 canaux MPC distincts, il reste à reconfigurer et valider la liaison USB.

## Conservation

Preuves privées dans `outputs/studio-32-tracks-20260926/` : copie complète
`session-backup/`, `saved-live-before.ardour`, scripts Lua, manifeste des
fichiers conservés et résultats intermédiaires. Résultat final dans
`final-stereo-verification.json` et `final-stereo-osc.json`.
La sauvegarde reste sur le même disque, sans support indépendant.

- Session originale sauvegardée : SHA-256
  `d14aa3163118d9b1bb7f692f6ac2338420d829b9934ec26cedf12b773e86ef56`.
- Session finale : SHA-256
  `9e39218b56bac7c8b5c3f604776bf33c78b7c86193f129ef365ecc57b386bc7a`.
