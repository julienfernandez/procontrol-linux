# Console, départs auxiliaires et interface web — 27 septembre 2026

Cette passe suit la confirmation physique de l’afficheur Channel / Group :
[adressage et essais](channel-group-2026-09-27.md). Le texte reçu par l’utilisateur
est « MPC01-02 ou le nom sélectionné ». L’adresse installée est `0x35`.

## Commandes utilisables

| Commande | Fonction |
|---|---|
| INSERTS / PARAM, PLUGIN | Chaîne des processeurs, puis bibliothèque |
| CREATE, ASSIGN général | Bibliothèque des effets de la piste sélectionnée |
| SELECT, Entrée | Ouvre / ajoute l’effet pointé dans la liste |
| ENABLE, SUSPEND | Dans DSP : active / désactive le processeur ; hors DSP : liaison des groupes Ardour |
| EDIT / BYPASS | Ouvre le choix dans la liste ; bascule le bypass pendant l’édition |
| COMPARE | Dans un effet : mémorise A, puis échange A et les réglages courants à chaque appui |
| INFO | Pendant l’édition : alterne les informations processeur / piste et le contexte de page |
| PARAMETER PAGES | Page suivante ; SHIFT : précédente |
| ESC | Quitte l’éditeur et rétablit les afficheurs de mixage |
| SENDS | Éditeur des départs internes existants de la piste sélectionnée |
| SEND LVL | Ouvre l’éditeur de départs ; dans l’éditeur, sélectionne la ligne courante |
| SEND MUTE (automation) | Ouvre l’éditeur de départs ; dans l’éditeur, bascule le départ pointé |
| FLIP | Dans DSP / départs : échange noms et valeurs des afficheurs. Les faders restent des faders de piste |
| AUTO SUSPEND | Automation de la cible sélectionnée en Manual ; READ la remet en lecture |
| DISPLAY MODE | Compteur temps SMPTE / mesures et temps |

Les huit rangées DSP sont maintenant incluses dans l’inventaire logiciel.
En navigation de chaîne, SELECT ouvre, ENABLE active, BYPASS désactive.
Dans la bibliothèque, SELECT ou ENABLE ouvre / ajoute ; BYPASS retourne à la chaîne.
En paramètres génériques, SELECT choisit le paramètre, ENABLE augmente d’un pas,
BYPASS diminue d’un pas (booléen : ON / OFF). Les incréments utilisent les profils
existants ; SHIFT conserve le réglage fin des rotatifs.
En EQ, les fonctions existantes de sélection et activation des bandes restent en place.

COMPARE ne rappelle que les valeurs de paramètres du processeur en cours. Il exige
un retour récent et vérifie piste, session, révision de catalogue, identité persistante,
nom / index du processeur et schéma des paramètres. La mémoire est effacée en quittant
le processeur. Le premier appui affiche `A GARDE`, l’échange `A/B SWAP`.

## Départs et bus d’effets

SENDS montre huit départs internes de la piste sélectionnée. Les rotatifs DSP et
les rotatifs de tranche règlent les niveaux normalisés ; SELECT choisit une ligne,
ENABLE active, BYPASS coupe. Les destinations et états viennent de `/strip/sends`.
Le numéro utilisé pour écrire est l’index réel renvoyé par Ardour, même s’il n’est pas
consécutif. Une banque différente ne peut pas réinterpréter cet index comme une piste.

Le neuvième afficheur indique `AUX 1/2`, `ATTENTE` ou `0 DEPART`. L’éditeur quitte
une cible devenue invalide ; aucune valeur n’est inventée en l’absence de retour.
Les requêtes ne créent pas de bus ni de connexion. Cette passe ne crée pas de nouveaux
bus de réverbération / délai dans la session ouverte et ne change pas ses entrées USB.
La création de ces bus avec un effet à 100 % wet reste la prochaine étape du routage.

La source locale Ardour 9.8 confirme `/strip/send/fader iif`, `/strip/send/enable iif`
et les groupes de cinq champs de `/strip/sends` (destination, nom, index, niveau,
activation). L’API d’automation ne fournit pas d’automation de mute de départ ;
SEND MUTE est donc une commande directe d’activation, pas une fausse fonction d’automation.

## Couverture et limites physiques

L’inventaire réunit 310 entrées de référence et captures, dont 280 reconnues dans au
moins un contexte. Les 30 autres sont huit sorties Peak sans bouton d’entrée,
16 anciens codes Source Toggle / Roll Off dont aucun bouton physique distinct n’est
établi, et six commandes de sélection analogique / Talkback sans émission Ethernet
locale établie. Il ne s’agit pas de 30 touches numériques connues laissées inutilisées.
Les boutons analogiques conservent leur rôle matériel. Voir [inventaire détaillé](mapping-backlog.md).

La reconnaissance logicielle n’est pas une validation physique de chaque geste.
Les codes des huit rangées DSP ont leurs captures historiques ; les nouvelles
fonctions sont testées par modèles puis demandent l’essai musical de l’utilisateur.

## Interface et vumètres

Les deux vues web partagent un thème sombre : fond `#080b0f`, panneaux `#10161c`,
bords fins, angles de 2 px, textes clairs et accent `#79cef4`. La géométrie de la
ProControl est conservée, ainsi que les presets, captures, validations et contrôles.
Les descriptions des nouvelles fonctions sont lisibles avant les commandes techniques.

Les vumètres utilisent désormais `/api/meters/events`, un flux indépendant à 25
trames par seconde visées. Une trame contient les dB bruts des huit paires de tranches
et des six grandes colonnes, sans catalogue, gestes ni historique. Un cache partagé
borne les RPC, même avec plusieurs onglets et lorsque le démon est absent. Le délai
RPC est de 120 ms, le délai d’écriture réseau de 2 s ; les connexions sont renouvelées
et se ferment lorsque la page est masquée.

Le dessin utilise requestAnimationFrame, attaque de 18 ms et retour de 180 ms,
avec crête de 650 ms dans la vue Studio. Ce lissage n’ajoute aucune mesure audio.
Le hook Lua existant fournit les nouvelles mesures à environ 10 Hz ; il n’a pas été
remplacé. Les données périmées disparaissent, les deux canaux restent indépendants,
et la préférence de réduction des animations supprime le lissage.

## Validation et archives

Préparation isolée : `work/console-complete-20260927/stage` ; manifeste de départ
`baseline.json`, liste des fichiers déployés `deploy-files.json`. Les modifications
préexistantes ont été comparées par empreinte avant installation.

- Suite générale : **508 tests Python réussis**. Après la relecture finale, 21 tests
  ciblés passent (DSP, afficheur de contexte, départs), dont trois cas supplémentaires :
  bypass du choix dans la chaîne, INFO / COMPARE hors édition, priorité des opérations
  sur l’affichage INFO. Les tests JavaScript de balistique et de polling passent aussi.
- Trois flux simultanés pendant huit secondes : **24,86 à 24,88 trames/s**,
  intervalle médian **40,08 à 40,10 ms**, maximum **50,06 ms**, médiane **422 octets**.
  Nouvelles mesures Lua : médiane **100,7 ms**. Âge maximal observé du dernier
  échantillon au moment de la lecture : **97,71 ms**. Ce test mesure le transport des
  données en silence ; il ne prouve pas encore la perception visuelle sur de la musique.
- Navigateur : vues desktop et mobile 390 px, recherche / sélection de contrôle,
  fiche SENDS, contexte départs et encodage, aucune erreur JavaScript ; aucun
  débordement horizontal observé. Captures `console-desktop.png`, `console-mobile.png`
  dans l’archive de travail. Le prototype visuel sert au style, pas à inventer des
  contrôles absents de la ProControl réelle.
- Démon final **249952**, pointeur **249955**, web **250371**. Console Online,
  Ardour répond, **220/220 ACK**, zéro timeout, erreurs OSC / sortie absentes.
  Nouvelle mémoire résidente du démon à ce relevé : 25 864 Kio.
- Ardour **173019**, démarré à 09:18:51 local, conservé. Même identité de processus
  et même SHA-256 du fichier de session avant / après. Les trois services restent actifs.
  La prévisualisation temporaire 8766 a été arrêtée.
- Fichiers installés relus et comparés au manifeste SHA-256 ; `mapping_inventory.py
  --check` et `git diff --check` sans écart attendu. Aucune publication GitHub dans
  cette passe.

La confirmation physique du nouvel afficheur est acquise ; la validation musicale
et gestuelle des nouvelles fonctions reste distincte. L’utilisateur a été invité
à observer les vumètres après actualisation ; aucune réponse n’a encore été reçue
au moment du relevé.

Le contrôle visuel a révélé une coupure de présentation au renouvellement SSE :
le navigateur attendait son délai de reconnexion par défaut. Correction installée :
reconnexion annoncée à 100 ms, maintien uniquement tant que la trame audio est fraîche
(800 ms maximum), indication de panne console après une seconde sans retour.
Les tests JavaScript couvrent fermeture transitoire, péremption, page masquée et reprise.

Vérification réelle du renouvellement : 1 500 trames sur 60,631 s, puis réouverture
du flux en 3,423 ms côté client de mesure, source toujours active. Ce temps de
réouverture HTTP ne mesure pas le délai de reconnexion du navigateur.
