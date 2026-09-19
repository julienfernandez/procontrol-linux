# Carte fonctionnelle ProControl → Ardour / Linux

## Bibliothèque DSP — 20 septembre 2026

EQ/DYN créent leur effet s’il manque. INSERTS par voie ouvre la chaîne puis une
bibliothèque de huit effets validés : EQ, compresseur, réverb, délai, phaser,
Chaleur, Tube et Tape. Navigation et paramètres sur les huit rotatifs DSP.
Voir [le parcours](curated-plugins.md) et [les nouveaux effets](warm-tape-plugins.md).

## Édition EQ / plugins — 15 septembre 2026

Le [mode EQ et navigateur de greffons](eq-plugin-workflow.md) est installé :
EQ IN/EDIT et DYN IN/EDIT ciblent la piste ; INSERTS/PARAM affiche les plugins.
Les huit rotatifs de tranches règlent les paramètres affichés. Sélection des
filtres et bypass depuis DSP. 139 tests passent ; validation physique demandée.

## État actuel au 14 septembre 2026

Consulter l'[audit des prochains mappings](mapping-roadmap-2026-09-14.md) pour
DSP/EQ, plugins, départs, monitoring et Linux. Les sections datées ci-dessous
conservent l'historique ; leurs anciennes limites ne décrivent pas toutes la
version actuelle.

- Faders : écho physique immédiat, y compris au relâchement ; protection contre
  les anciennes consignes DAW conservée. Utilisateur : fonctionnement parfait.
- SELECT/Channel Matrix : commandes et LEDs corrigées ; affichage conservé
  pendant les mises à jour du catalogue.
- Stéréo : deux canaux par piste via Lua ; master sur les adresses 10/42.
- Départs : lecture de la valeur initiale avant modification, voir send-update.md.
- Plugins : mode et commandes présents, mais noms/valeurs des paramètres et
  section DSP dédiée encore à compléter. PLUGIN/INFO n'ouvrent pas encore la GUI.
- Réglages relevés : souris 0,58, jog 0,85, révision 9 ; conserver la configuration
  courante plutôt que les anciennes valeurs des paragraphes historiques.

Version étendue déployée le 13 septembre 2026 à 18:34 UTC. Les deux processus
restent actifs entre les échanges. Le mapping vient de la table **ProControl**
de ReaControl24, confrontée aux captures locales et aux photos ; les fonctions
Ardour sont adaptées à OSC 8.4. La liste ne signifie pas que chaque bouton a
été essayé physiquement.

**Confirmés par l’utilisateur après déploiement :** afficheurs de tranches,
compteur à huit chiffres et jog. Clavier et clics reçus dans la fenêtre GTK.

## Commandes raccordées

| Zone de la console | Action actuelle |
|---|---|
| PLAY / STOP | Lecture / arrêt Ardour, déjà confirmés physiquement |
| RTZ / END, REW / FF | Début / fin et déplacement arrière / avant |
| Jog | Déplacement du curseur via `/jog` ; SCRUB / SHUTTLE choisissent les modes correspondants |
| REC, LOOP, IN / OUT | Armement global, boucle, punch in / out |
| Huit faders + contact | Volume normalisé ; déclaration de contact tactile ; retour moteur suspendu pendant le contact et 300 ms après un mouvement |
| SELECT, MUTE, SOLO, REC ARM de tranche | Sélection, mute, solo et armement de la piste de la banque |
| Encodeurs des huit tranches | Pan par défaut ; commandes SEND A–E choisissent un départ ; mode plugin pour les paramètres sélectionnés |
| BANK gauche / droite | Banque de huit pistes ; NUDGE transforme ces boutons en sélection précédente / suivante |
| CHANNEL MATRIX hors ALPHA | Sélection / mute / solo / armement selon le mode ; banques A–D ; adressage à éprouver dans une session comportant plusieurs banques |
| MASTER FADERS | Bascule la vue locale vers le master, puis revient aux pistes |
| ALPHA + CHANNEL MATRIX | Clavier A–Z, SHIFT, CAPS, #, &, retour arrière et espace |
| Modificateurs et pavé numérique | Shift, Alt, Ctrl ; chiffres, opérateurs et Entrée vers la fenêtre Linux active |
| Trackpad et boutons souris | Déplacement, clic gauche et droit ; gain réglable, actuellement 0,24 |
| WRITE / TOUCH / LATCH / READ / OFF | Mode d'automation du gain de la piste sélectionnée |
| UNDO / SAVE | Annuler / sauvegarder ; modificateur + UNDO → rétablir |
| CUT / COPY / PASTE / DELETE / SEPARATE | Actions d'édition Ardour correspondantes |
| TRIM / SELECT / GRAB / PENCIL | Outils time-stretch, plage, objet, dessin d'Ardour |
| SHUFFLE / SLIP / SPOT / GRID | Modes ripple, slide, verrouillage et cycle de grille ; adaptations, pas des équivalents Pro Tools exacts |
| MIX / EDIT / STATUS / MEM LOC | Mixeur, éditeur, meterbridge et fenêtre des positions |
| F1 / F2 / F3 / F4 | Rafraîchir / ajouter un marqueur / précédent / suivant |
| MONO / DIM / MUTE monitoring | Fonctions de la section monitor d'Ardour, si présente dans la session |
| GROUP ENABLE / SUSPEND | Utilisation des groupes |
| INSERTS / PARAM, BYPASS, PAGES | Mode paramètres du plugin sélectionné, activation, page suivante |
| SNAPSHOT / CLEAR ALL / ESCAPE | Instantané de session, annuler les solos, Escape |
| COUNTER MODE | Compteur SMPTE ↔ mesures / temps |

Le pavé émet des caractères vers l'application active ; les raccourcis
spécifiques au pavé Pro Tools ne sont pas tous reproduits. ALPHA est un mode
logiciel du pont, signalé par sa LED. Les touches et clics sont libérés à
l'arrêt, à la perte de connexion et à la sortie du mode ALPHA.

## Retours envoyés à la console

Noms et valeurs des huit tranches, compteur à huit chiffres, LEDs de transport
et de tranche, anneaux de pan, faders motorisés et niveaux de vumètres sont
raccordés au feedback OSC. Un seul message de sortie attend son ACK à la fois ;
les valeurs intermédiaires sont regroupées. Une absence d'ACK de deux secondes
déclenche une reprise automatique temporisée, sans interrompre les maintiens
de session. Voir [feedback-recovery.md](feedback-recovery.md).

Le hook Lua fournit désormais deux niveaux indépendants par piste stéréo.
Voir [stereo-settings.md](stereo-settings.md) pour le déploiement et les validations. L'adresse 8 pour le premier grand vumètre est une
hypothèse issue des références ; les **six grands vumètres**, leurs segments,
les crêtes et leur routage complet restent à identifier visuellement.
Voir [les essais des afficheurs](displays.md).

## Limites à traiter ensuite

- Les huit encodeurs DSP et certains boutons DSP/automation ne sont pas encore
  associés à une fonction confirmée. Les commandes inconnues sont conservées
  dans le journal, sans action par défaut.
- Départs et plugins : adaptation expérimentale, à valider sur une session
  qui en possède. Le cache des départs par tranche n'est pas encore synchronisé
  avec leur valeur initiale ; éviter ce mode pour préserver un mix existant.
- Banques longues : routage unifié et borné au catalogue, testé sur plusieurs
  banques synthétiques ; validation physique encore à effectuer.
- Certains contrôles analogiques de monitoring appartiennent au circuit audio
  de la console ; les photos ne prouvent pas qu'ils émettent un message Ethernet.
- Wayland et démarrage automatique au boot ne sont pas encore pris en charge.

## Sources et inventaire

La [table originale ProControl](https://github.com/phunkyg/ReaControl24/blob/b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069/procontrolmap.py)
est conservée dans `vendor/reacontrol24`, avec sa licence GPL. Son parcours
historique masquait les zones DSP, monitor et matrix : 0x15, 0x16 et 0x17
étaient prises pour des tranches. Notre adaptateur corrige le routage, sans
modifier le fichier tiers. Les anciens libellés « track/23 » ne sont donc pas
des preuves de numéros de pistes physiques.

[control-map.json](control-map.json) expose les octets, libellés de référence
et actions calculées. Ses entrées incluent des emplacements et libellés
hérités : leur nombre ne correspond pas à un nombre de boutons réels validés.
Les tests rejouent aussi la capture locale ALPHA / pavé / clics.

Les deux [photos consultées](reference-photos/README.md) ont permis de lire
les inscriptions de la surface, notamment toute la dernière rangée ALPHA.

Fonctions OSC vérifiées dans les sources officielles
[osc.cc Ardour 8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.cc),
[feedback de tranche](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc_route_observer.cc)
et [actions de l'éditeur](https://github.com/Ardour/ardour/blob/8.4/gtk2_ardour/editor_actions.cc).
Configuration utilisée : catalogue sans banque (0), strip types 63, feedback 8307, gainmode 2,
8 départs et 8 paramètres par page. Le gainmode 2 fournit fader normalisé et dB,
sans remplacer temporairement les noms de pistes par leur gain.

## Extension du 13 septembre, 19:48 UTC

- VOL / PAN / MUTE / TRIM choisissent la cible des touches WRITE, TOUCH, LATCH,
  READ et OFF : gain, panoramique, mute ou trim de la piste sélectionnée.
  TRIM est ici une cible Ardour, pas le mode d'automation relative de Pro Tools.
- IN/EDIT ouvre l'éditeur ; PLUGIN et INFO développent les paramètres de la
  piste sélectionnée et choisissent le mode plugin des encodeurs.
- COMPARE appelle l'alternance A/B des plugins sélectionnés dans le mixeur.
- CAPTURE définit la boucle depuis la plage d'édition (adaptation Ardour).
- AUDITION lit les régions sélectionnées ; PRE ROLL lance la lecture avec pré-roll.
- ONLINE et EXT TRANS basculent la synchronisation externe d'Ardour. Ils ne
  commandent pas la connexion Ethernet de la ProControl.
- QUICK PUNCH bascule ensemble punch in/out ; aucun enregistrement n'est lancé
  par cette touche seule.
- Modificateur + F1 : zoom session ; + F2 : zoom sélection ; + F3/F4 : zoom arrière/avant.
  Les fonctions F1–F4 sans modificateur sont conservées.
- Modificateur + PLUG-IN/PAGES revient à la page précédente ; sans modificateur,
  page suivante.

Sources vérifiées : ardour_ui_ed.cc, editor_actions.cc et osc.cc d'Ardour 8.4,
plus les raccourcis installés dans /etc/ardour8/ardour.keys. Ces adaptations
n'ont pas encore été testées physiquement ; les tests couvrent notamment les
relâchements, retries, changement de cible d'automation et modificateurs.
73 tests passent après extension. La relance du daemon reste en attente de
l'authentification Linux locale au moment du déploiement.

[Inventaire complet calculé](mapping-coverage.json) et [adresses restantes](mapping-backlog.md).
Régénération : `python3 tools/mapping_inventory.py`. Les entrées de référence
comprennent des emplacements hérités et ne constituent pas un décompte matériel.

## AUTO par voie — 15 septembre

AUTO parcourt Manual → Play → Write → Touch → Latch ; Shift inverse.
Voyants RD/WR/TC/LT selon état reçu, tous éteints en Manual.
Voir [modes d’automation](automation-modes.md) pour périmètre, sources et preuves.

## Sens des balances — 15 septembre

Inversion du delta appliquée uniquement au mode pan des huit rotatifs de
tranches, suite au signalement utilisateur. OSC conserve0=gauche/1=droite ;
les anneaux suivent toujours les valeurs Ardour selon la table ProControl
de référence. Les modes départs/plugins/EQ et le jog gardent leur direction.
165tests réussis ; détails dans pan-direction-validation.json.
