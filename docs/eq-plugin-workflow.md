# EQ, compresseur et navigateur de greffons

Le parcours est complété le 19 septembre par [la création automatique et la bibliothèque restreinte](curated-plugins.md). Les sections ci-dessous décrivent la base du 15 septembre.

## Parcours depuis la console

- **EQ IN/EDIT d'une tranche** : ouvre l'édition de l'unique LSP EQ x8 de cette
  piste. La LED EQ de cette tranche et SELECT du filtre choisi clignotent à 2 Hz.
  Un second appui sur EQ de la même piste revient au mixage.
- **DYN IN/EDIT** : accès direct au LSP Compressor de la piste, mono ou stéréo.
  Un second appui revient au mixage ; la LED DYN désigne la piste éditée.
- **INSERTS/PARAM** au-dessus de SENDS, ou la touche PLUG-IN de WINDOWS : liste
  des greffons de la piste sélectionnée. Un greffon par écran DSP, huit par page.
  Les noms longs sont abrégés sur les écrans de huit caractères.
- **SELECT à gauche d'une ligne DSP** : ouvre le greffon de cette ligne.
  LSP EQ x8 utilise son profil dédié ; les autres greffons exposent leurs
  paramètres d'entrée par groupes de huit. LSP Compressor commence par sa page utile.
- **INSERTS/PARAM** pendant l'édition : retourne à la liste des greffons.
- **SELECT d'une tranche** ou **Channel Matrix en mode SELECT** : liste des
  greffons de la nouvelle piste. BANK change de banque et ouvre la première
  piste ; avec NUDGE, passe à la piste précédente/suivante.
- **PAGES** : page suivante ; modificateur + PAGES : précédente. En EQ, ces
  touches choisissent le filtre suivant/précédent parmi les huit.
- **ESCAPE** : revient au mixage et restitue les valeurs de gain actuelles.

Les faders, SELECT/mute/solo/rec de mixage et le transport gardent leurs fonctions.
Les noms des pistes sur les afficheurs du bas restent visibles. Les écrans du
haut sont réservés aux paramètres tant que ce mode est ouvert. ALPHA et les
autres modes d'encodeurs quittent l'édition.

## Les huit filtres de l'EQ

Les huit lignes DSP représentent les huit filtres, dans l'ordre. SELECT choisit
le filtre sans modifier le son. ASSIGN/ENABLE et BYPASS activent ou désactivent
ce filtre. Une désactivation utilise Filter mute, afin de garder son type et
ses valeurs ; un filtre initialement Off devient Bell au premier allumage.
La LED ENABLE indique un filtre actif, BYPASS un filtre coupé.
Le petit rotatif DSP de chaque ligne choisit le type du filtre de cette ligne.

| Rotatif de tranche | Paramètre du filtre sélectionné | Affichage type |
|---|---|---|
| 1 | Fréquence | F2 1.00k |
| 2 | Gain | G2 +0.0 |
| 3 | Q | Q2 0.50 |
| 4 | Type : Off, Bell, passe-haut, shelves, etc. | T2 Bell |
| 5 | Multiplicateur de pente, x1 à x4 | S2 x1 |
| 6 | Famille de filtre : RLC, BWC, LRX, APO | M2 RLC-B |
| 7 | Largeur de bande, en octaves | W2 4.00o |
| 8 | Gain de sortie de l'EQ | Out+0.0 |

La disponibilité sonore de Q, largeur et pente dépend du type/mode du filtre.
La pente est affichée en multiplicateur : sa valeur en dB/octave dépend aussi
de la famille de filtre, elle n'est pas inventée par la passerelle.
MASTER BYPASS coupe/remet l'EQ entier. Dans le navigateur, BYPASS de chaque
ligne agit sur le greffon correspondant ; dans les paramètres, MASTER BYPASS
agit sur le greffon ouvert.

Fréquence : progression multiplicative ; gain : pas de 0,25 dB.
Un modificateur maintenu réduit les pas (gain 0,05 dB, fréquence dix fois plus fin).
Type et famille restent des choix discrets, bornés aux descripteurs Ardour.

## Compresseur de référence

Les huit pistes audio de la session tttt possèdent chacune LSP Compressor Stereo,
après LSP EQ x8 Stereo. État vérifié dans la session sauvegardée le 15 septembre.
Le script `ardour/procontrol_add_eq_compressor.lua` choisit la variante mono pour
les pistes mono et stéréo pour les pistes stéréo, sans doublonner les instances.
Il s'agit des pistes audio actuelles, pas d'un hook automatique de création.

Première page : **seuil d'attaque, ratio, attaque, relâchement, knee, makeup,
gain wet, gain de sortie**. Les écrans DSP portent les noms ; les écrans des
tranches portent les valeurs (dB, ms, ratio). Les autres paramètres suivent
avec PAGES. Le ratio initial 1:1 n'applique pas de compression ; le modifier
et adapter le seuil permet d'en éprouver l'action.

## Contrat technique et vérifications

Sources : code local officiel Ardour 9.8, `libs/surfaces/osc/osc.cc`, fonctions
route_plugin_list, route_plugin_descriptor, route_plugin_parameter ;
[manuel LSP EQ x8](https://lsp-plug.in/?page=manuals&section=para_equalizer_x8_stereo).
Les réglages précis ont été confrontés aux TTL installés et aux descripteurs
réellement renvoyés par la session.

- `/strip/plugin/list i` retourne des triplets index, nom, état.
- `/strip/plugin/descriptor ii` retourne les IDs de contrôle **1-based**, labels,
  bornes, flags, choix et valeur courante, puis descriptor_end.
- `/strip/plugin/parameter iiif` écrit une valeur **interne**, pas normalisée.
  Ces identifiants ne sont ni des numéros de ports LV2 bruts, ni des positions
  de la page `/select/plugin/parameter`.
- La découverte et les lectures concernent seulement la piste éditée : une
  liste puis un snapshot toutes les 500 ms. Aucun /refresh ni /strip/list global,
  aucune reconstruction périodique des observateurs.
- Les tours de rotatif envoient la valeur immédiatement ; l'affichage local est
  mis à jour et coalescé dans la file ACK existante. Les modifications depuis
  la GUI reviennent au prochain snapshot, soit environ 500 ms en régime normal.
- Les valeurs inconnues/périmées sont bloquées ; un snapshot déjà en vol ne
  rembobine pas un tour plus récent. Un snapshot demandé après le tour rend
  ensuite la priorité à l'état Ardour, notamment à l'automation.
- Changement effectif de piste/identité ou perte de connexion : sortie du mode ; aucune ancienne commande
  n'est rejouée. Une notification de catalogue seule suspend les écritures, conserve
  les écrans et reprend après validation des mêmes identités. La liste est revérifiée avant chaque snapshot ; OSC utilise
  néanmoins des indices de greffons, pas des identités immuables.
- Plusieurs EQ identiques : l'accès direct refuse de choisir arbitrairement ;
  sélectionner l'instance dans le navigateur.

139 tests passent au déploiement, dont 19 nouveaux scénarios avec un fixture
capturé sur les deux LSP réels. Les tests historiques de faders, retours, souris,
clavier, stéréo et catalogue restent verts. Cela ne remplace pas le test visuel.

## Fenêtres Ardour et navigation entre voies

Voir [le suivi de fenêtre](plugin-window-follow.md). SELECT/Matrix/Bank conservent
désormais la famille EQ/compresseur en édition ; le navigateur conserve sa liste.
