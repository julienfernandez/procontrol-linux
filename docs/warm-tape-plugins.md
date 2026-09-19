# Chaleur, saturation à lampes et bande ondulante

20 septembre 2026. Trois effets rejoignent la bibliothèque de la ProControl,
qui contient maintenant huit choix. Ils sont ajoutés sur demande depuis la
console ; l'installation ne modifie pas les chaînes du projet en cours.

| Affichage | Plugin | Usage |
|---|---|---|
| Chaleur | SWH Valve saturation | Coloration douce, deux réglages |
| Tube | ZamTube | Saturation de triode et filtres de type ampli |
| Tape | CHOW Tape Model 2.11.4 | Saturation de bande, wow et flutter |

## Depuis la console

Appuyer sur **INSERTS de la voie**, puis choisir **+ Effet** si la voie a déjà
des plugins. Tourner un petit rotatif pour déplacer le curseur, puis valider
avec **ENTER** ; **SELECT de la ligne DSP** choisit directement cette ligne.
Les huit choix tiennent sur une page. Un effet déjà présent est ouvert sans
ajouter de doublon.

Les rotatifs DSP et de tranche règlent les paramètres affichés.
**PAGES** avance et **modificateur + PAGES** recule ; **ESCAPE** revient au mixage.

### Chaleur

Deux commandes : **Chaleur** et **Caract.**. Départ à 20 % et 25 %.
Augmenter progressivement Chaleur pour enrichir le son ; le résultat dépend
du niveau qui entre dans le plugin.

### Tube

Première page : **Drive, Niveau, Graves, Mediums, Aigus, Modele, Boost**.
Départ Drive 1,2, niveau −3 dB, Boost désactivé. Ce modèle colore aussi le timbre
avec son tone stack : il peut atténuer sensiblement le signal. Comparer le
niveau avec le bypass et ajuster Niveau. Boost donne une distorsion plus forte.

### Tape : point de départ « bande ondulante »

Ce réglage s'inspire de l'effet recherché par l'utilisateur, sans prétendre
reproduire le matériel ou un preset de Mac DeMarco.

| Potard, page 1 | Affichage | Départ | Rôle |
|---|---|---|---|
| 1 | WowProf | 40 % | Amplitude de l'ondulation lente |
| 2 | WowVit | 20 % | Vitesse du wow |
| 3 | FlutProf | 6 % | Petites variations rapides |
| 4 | FlutVit | 30 % | Vitesse du flutter |
| 5 | Drive | 35 % | Excitation du modèle de bande |
| 6 | Satur. | 40 % | Caractère de la saturation |
| 7 | Melange | 100 % | Proportion de signal traité |
| 8 | Sortie | 0 dB | Compensation de niveau |

Page 2 : **Alea 10 %, Derive 8 %, Bias 60 %, Entree 0 dB, Bande ON, Detune ON**.
Pour accentuer l'effet, monter WowProf puis Alea ; pour le calmer, baisser
WowProf et FlutProf. Melange permet un effet parallèle. Les modules de bande
abîmée et de dégradation sont désactivés au départ ; suréchantillonnage 2×.

Les vitesses sont affichées en pourcentage comme dans cette version du plugin,
pas en hertz. Le wrapper LV2 expose tous les paramètres CHOW sur 0..1 :
la console convertit l'entrée vers −30..+6 dB et la sortie vers −30..+30 dB.
Les interrupteurs Bande/Detune restent binaires même avec le réglage fin.

## Installation et contrat

Valve provient du paquet Ubuntu `swh-lv2`
`1.0.16+git20160519~repack0-4build1`, bundle `~/.lv2/valve-swh.lv2`.
ZamTube était installé dans `/usr/lib/lv2/ZamTube.lv2` (paquet Zam 4.0).
CHOW est le bundle LV2 officiel de la release Linux x64 2.11.4, extrait dans
`~/.lv2/CHOWTapeModel.lv2`. Aucun binaire tiers n'entre dans le dépôt.

Sources : [SWH LV2](https://github.com/swh/lv2),
[ZamAudio](https://www.zamaudio.com/?p=976),
[CHOW Tape 2.11.4](https://github.com/jatinchowdhury18/AnalogTapeModel/releases/tag/v2.11.4),
[manuel CHOW](https://chowdsp.com/manuals/ChowTapeManual.pdf).
Les conversions ont été vérifiées dans `Plugin/Source/PluginProcessor.cpp`
du tag 2.11.4, commit `604372e4ffd9690c3e283362e4598cb43edbb475`.

Appliquer `native/ardour-9.8-warm-tape.patch` **après** les patches plugin-ui,
osc-stability et curated-plugins. Le protocole `/procontrol/plugin/version`
passe à **2** et autorise `warm`, `tube`, `tape`. Le client reste compatible avec
la version 1 pour ses cinq effets d'origine ; les nouveaux choix demandent
la version 2. Les identités persistantes, protections d'insertion et bornes
de paramètres restent celles de la bibliothèque initiale.

## Validation

Voir `warm-tape-validation.json` pour les mesures et empreintes des binaires.
Les nouveaux effets sont créés et réutilisés dans Ardour Dummy en mono et
stéréo ; les 23 commandes mappées sont modifiées et relues dans chaque format,
y compris les deux pages Tape. Les valeurs de départ sont également relues.
Les descripteurs réels rejoignent les fixtures des huit profils.

Un hôte LV2 hors ligne a traité 16 secondes de sinus à 220 Hz, 48 kHz,
amplitude 0,25, blocs de 512. Les trois sorties sont finies et non silencieuses.
Tape produit une variation de hauteur mesurée d'environ 3,7 cents d'écart type
dans cet essai. Cela vérifie l'effet de modulation, pas sa qualité musicale.
Ce test ne joue aucun son sur la Behringer. Les mesures CPU de rendu ne sont
pas une garantie de charge en session, et aucune écoute ni validation physique
des nouveaux écrans n'est revendiquée.

Activation le 20 septembre : sauvegarde puis fermeture normale et réouverture
d’Ardour, module version 2 chargé, passerelle et pointeur relancés. Les 79
connexions audio présentes ont été conservées, dont Master L/R vers Behringer.
Les chaînes de plugins et leurs valeurs sauvegardées sont identiques avant
et après. Passerelle Online, Ardour répondant, huit choix disponibles.
