# Atelier ProControl — Mapping

La page locale `http://127.0.0.1:8765/mapping` est accessible depuis le centre de
contrôle. Elle représente la Main Unit en SVG : huit tranches, DSP, matrice,
monitoring, clavier, navigation, transport, jog, trackpad, afficheurs et vumètres.
Un clic **sélectionne** un élément ; il ne joue aucune commande.
La molette zoome, le fond se déplace et le menu des zones cadre chaque section.
Sur téléphone, la fiche se place sous la console.

Le catalogue distingue les éléments physiques et les codes de référence non
placés. Ces derniers se trouvent par la recherche, sans inventer de bouton sur
le dessin. Les commandes analogiques sans encodage établi restent identifiées
comme telles. Les six grandes colonnes ne sont pas automatiquement associées aux
quatre paires d’adresses confirmées. Les sources des observations DSP/navigation
figurent dans chaque fiche ; réception réseau et validation physique sont séparées.

## Préparer et appliquer un preset

« Ardour — configuration actuelle » est protégé. Le dupliquer crée un brouillon.
La fiche propose les dix contextes déjà gérés par la Gateway. Une affectation peut
hériter du comportement actuel, utiliser une fonction guidée, désactiver l’entrée
ou envoyer un chemin OSC avec des arguments typés (`i`, `f`, `s`). Un argument a
soit une `value` constante, soit une `source` : `value`, `delta`, `pressed`,
`channel` (tranche 1–8) ou `selected` (SSID unique sélectionné et connu).

Les fonctions guidées passent par les gestionnaires existants : banques,
modificateurs, EQ/DYN, automation, suivi et fermeture des fenêtres DSP. Le mode
expert utilise la destination Ardour déjà configurée ; les chemins `/strip/*`
experts prennent des SSID réels. La configuration OSC de la surface reste réservée
à la Gateway (`/set_surface`, `/refresh`, `/strip/list` refusés).

Enregistrer un brouillon ne change pas le contrôle actif. « Appliquer le preset »
active d’un bloc ses fonctions et la calibration préparée, avec transport arrêté
et état Ardour frais. La version précédente est conservée pour retour arrière.
Les révisions empêchent une page ancienne d’écraser un changement fait ailleurs.
Les imports/export JSON version 1 ne contiennent que le preset. Le brouillon Logic
peut être préparé mais ne peut pas être activé : aucun adaptateur Logic/Mac n’est
livré ici.

## Capturer sans agir

Démarrer explicitement la capture exige une console en ligne, un transport arrêté,
un état OSC de moins de deux secondes et aucun enregistrement global armé/en cours.
Les faders doivent être relâchés. Durée maximale : dix minutes. La page renouvelle
une présence ; sa disparition termine la capture après sept secondes au plus.
Un changement de transport, une perte de fraîcheur ou une reconnexion la termine.

La Gateway acquitte toujours le protocole, mais intercepte les gestes avant les
modes et les actions Ardour. Le worker X11 confirme son isolation avant le début,
libère ses entrées et refuse aussi les paquets marqués comme capturés. Les actions
différées et le jog sont annulés. Les moteurs sont bloqués pendant l’apprentissage.
Les boutons restés maintenus doivent être relâchés avant leur prochaine action ;
les gestes enregistrés ne sont jamais rejoués.

Les candidats montrent le code brut, les appuis/relâchements et les extrêmes des
faders. Sélectionner le bon dessin puis associer explicitement le candidat. Un
conflit d’encodage est refusé. L’association reste préparée jusqu’à l’application.

## Tester et valider les sorties

Les essais utilisent la file de sortie unique du daemon et son suivi d’ACK. LED,
vumètre, afficheur, couronne et compteur : deux secondes. Pas de balayage d’adresses.
La restauration prend le retour courant, mis à jour pendant l’essai ; une adresse
sans retour connu est éteinte. Un essai moteur exige une position récente, un fader
libre et une confirmation explicite ; course limitée à 4 % maximum, pendant une
seconde. Le toucher annule immédiatement l’essai et sa restauration. La destination
d’un moteur ne peut pas être déplacée vers une autre tranche : ses gardes tactiles
restent attachées au matériel établi.

Les validations emplacement, entrée, retour et fonction ont des niveaux distincts :
à identifier, documenté, observé, confirmé physiquement. L’utilisateur peut ajouter
une note datée. Une validation de fonction appartient au preset, à son contexte
et à sa révision ; elle ne se propage pas à un preset modifié. Aucune réception OSC, compilation ou ACK ne coche automatiquement
une confirmation physique. Une position du dessin peut être corrigée séparément.

## État local et API

`tools/console_layout.py` porte le catalogue versionné. `console-mapping.json`
(non versionné dans Git) conserve calibration, positions, validations, brouillons,
instantané actif et précédent. Écriture atomique, verrou interprocessus et contrôle
de révision. Sauvegarder ce fichier avec les réglages personnels du studio.

- `GET /api/console/model` : implantation, preuves, presets et calibration.
- `GET /api/console/state` : dernier état partagé, sans commander le matériel.
- `GET /api/console/events` : SSE à quatre mises à jour maximum par seconde,
  connexions bornées à une minute, reconnexion automatique.
- `POST /api/console/action` : mutations explicites et opérations du daemon.

Le serveur conserve les protections loopback, Host/Origin et JSON du centre de
contrôle. Les clients partagent un cache RPC pour ne pas multiplier les lectures
du daemon. Historique de 128 événements, valeurs continues regroupées, 64 candidats
maximum et taille de réponse bornée ; les trous de l’historique sont signalés.
Les journaux Ether­net habituels restent la source d’observation complète.

L’atelier ne redémarre ni Ardour, ni la MPC, ni le gadget USB. La supervision
Studio USB reste sur la page principale.
