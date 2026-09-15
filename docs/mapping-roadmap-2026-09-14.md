# Audit des fonctions restantes — 14 septembre 2026

Le prochain lot recommandé est **DSP / plugins / EQ**, avec sélection du plugin,
huit paramètres nommés, valeurs lisibles, pages et bypass. Il apporte davantage
que l'ajout de raccourcis isolés, et exploite la section dédiée de la console.

Cet audit distingue le code existant, les essais physiques et les propositions.
Il ne déploie pas de nouveau mapping dans le démon. Le correctif moteur est
maintenant confirmé par l'utilisateur : fader « parfait ». Le démon reste actif.

## Inventaire et limites

L'inventaire généré contient **284 entrées de référence : 228 associées à une
action en mode normal, 56 sans action**. Cela ne mesure ni le nombre de boutons
physiques ni le nombre de fonctions validées : une action existante peut manquer
de feedback, de contexte ou d'essai physique. Voir [inventaire](mapping-coverage.json)
et [codes restants](mapping-backlog.md).

Fonctions déjà éprouvées : transport PLAY/STOP, sélection corrigée, noms de
tranches, compteur, jog, trackpad, clavier/clics et retour moteur. La stéréo
utilise le hook Lua ; les adresses master sont 10/42. Les banques longues,
plugins, départs et plusieurs fonctions d'édition restent moins éprouvés.

## Priorités fonctionnelles

| Priorité / zone | Fonction à obtenir | Existant | Travail restant |
|---|---|---|---|
| 1 — DSP EDIT/ASSIGN | Huit paramètres du plugin sélectionné avec noms et valeurs | Commandes OSC de paramètres sur encodeurs de tranches en mode plugin | Identifier les huit encodeurs DSP, boutons de rangée et afficheurs ; connecter leur feedback |
| 1 — INSERTS/PARAM | Choisir un insert puis parcourir ses paramètres | Mode plugin et pages déjà présents | Liste réelle des inserts, index bornés, nom du plugin et numéro de page |
| 1 — PLUGIN/INFO | Ouvrir la fenêtre du plugin ciblé | Appelle actuellement /select/expand | Implémenter une ouverture GUI ciblée ; expand ne signifie pas ouvrir la fenêtre |
| 1 — BYPASS/IN-OUT | Activer/désactiver le plugin ou la bande avec LED fidèle | Activation du plugin sélectionné partiellement raccordée | Séparer bypass global, bypass de bande et bouton de rangée ; suivre l'état réel |
| 1 — EQ | Accès direct fréquence, gain, largeur, activation | ACE EQ installé, profil préparé | Résoudre les paramètres du plugin présent dans la piste, afficher les unités, tester |
| 2 — Dynamics | Seuil, ratio, attaque, relâchement, knee, makeup, bypass | ACE Compressor installé | Profil à partir des descripteurs du plugin mono/stéréo réellement choisi |
| 2 — SENDS | Choisir un départ, régler niveau et activation, afficher nom/destination | Niveau de départ avec lecture de valeur initiale | Feedback complet, navigation et tests sur une piste possédant des départs |
| 2 — FLIP | Échanger faders et encodeurs pour départs ou paramètres | Bouton de référence non associé | Gestion du changement de cible, moteurs, contact et retour au volume |
| 2 — Automation | Lire/Touch/Latch/Write/Off sur la cible affichée | Cibles gain/pan/mute/trim | Automation de paramètre et LED de mode ; distinguer contact et mouvement |
| 3 — Édition | Marqueurs, plages, boucle, punch, pré/post-roll, zoom, outils | Nombreuses actions raccordées | Essais fonctionnels et retours d'état ; adaptations Pro Tools ≠ Ardour |
| 3 — Monitoring | DIM/MONO/MUTE et éventuellement niveau d'écoute | Actions monitor Ardour | Vérifier section monitor présente ; identifier contrôles numériques accessibles |
| 3 — Linux | Navigation applications, raccourcis utiles, profils de touches | X11/XTEST, ALPHA, pavé et souris fonctionnent | Profils explicites, indication du mode, affectations configurables |
| 4 — Matériel externe | Pilotage via OSC/MIDI selon le matériel | Aucune liaison MIDI externe démontrée | Inventaire ports/appareils et preuve du transport avant routage |

## Architecture de contrôle des plugins

1. Partir de la piste sélectionnée et demander ses inserts via
   `/strip/plugin/list SSID` ; ne pas supposer « plugin 1 = EQ ».
2. Obtenir les descripteurs via `/strip/plugin/descriptor SSID pluginID` : noms,
   bornes et types. Distinguer indice de port LV2, identifiant OSC et position
   dans la page des paramètres contrôlables.
3. Choisir le plugin sélectionné avec `/select/plugin`, et une page de huit
   paramètres. Utiliser les retours `/select/plugin/name`,
   `/select/plugin/parameter/name` et `/select/plugin/parameter`.
4. Définir un propriétaire par afficheur : en mode mixage, nom/gain de piste ;
   en mode paramètres, nom/valeur du paramètre. Deux producteurs ne doivent pas
   alternativement réécrire le même bandeau.
5. Invalider les anciennes valeurs lors du changement de piste/plugin/page.
   Ne pas envoyer un réglage basé sur le cache du plugin précédent.
6. Prévoir réglage fin avec modificateur, paramètres à choix et interrupteurs,
   bornes, unités et indication de page. Les profils spécialisés complètent le
   mode générique ; un plugin inconnu reste contrôlable par pages.
7. Pour ouvrir une fenêtre, rechercher une action GUI ciblée ou ajouter une
   action Lua Ardour. L'OSC `/select/expand` actuel choisit le strip développé
   pour la surface : il ne prouve aucune ouverture de fenêtre.

Les commandes et feedback de plugins sont exposés par Ardour :
[requêtes OSC](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/querying-ardour-with-osc/),
[commandes OSC](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-control/),
[feedback OSC](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/feedback-in-osc/).
Les implémentations 8.4 sont consultées localement dans work/research/ardour-8.4.

## EQ : profil ACE EQ proposé

Les endpoints génériques `/select/eq_*` ne doivent pas être considérés comme
un accès universel à tout EQ LV2. Ardour 8.4 repose ici sur des contrôles
spécifiquement associés ; `Route::eq_band_cnt()` retourne zéro avec le commentaire
qu'Ardour n'a pas d'objet EQ connu. Nous utiliserons les paramètres du plugin
réel plutôt que d'envoyer aveuglément ces commandes.
Source : [Route Ardour 8.4](https://github.com/Ardour/ardour/blob/8.4/libs/ardour/route.cc).

Le plugin installé `urn:ardour:a-eq` possède 24 paramètres de contrôle. Le
[profil proposé](ace-eq-proposed-profile.json) reprend les ports du fichier
`/usr/lib/lv2/a-eq.lv2/a-eq.ttl`. **Il n'est pas connecté au moteur de mapping.**
Les indices LV2 ne sont pas utilisés comme identifiants OSC présumés.

| Page | Encodeurs 1 à 8 |
|---|---|
| Graves et bandes 1–2 | Fréquence grave, gain grave, fréquence 1, gain 1, largeur 1, fréquence 2, gain 2, largeur 2 |
| Bandes 3–4 et aigus | Fréquence 3, gain 3, largeur 3, fréquence 4, gain 4, largeur 4, fréquence aiguë, gain aigu |
| Activations | Gain global, grave actif, bande 1, bande 2, bande 3, bande 4, aigu actif, EQ actif |

Fréquences : 20 Hz–20 kHz ; gains : −20 à +20 dB ; largeurs : 0,1 à 4 octaves.
La largeur ACE EQ est exprimée en **octaves**, pas en Q. L'affichage devra
refléter l'unité et la conversion propres au paramètre. Les boutons de rangée
pourraient servir au bypass de bande, après identification physique.

Le fichier de session enregistré `tttt.ardour` consulté ne contient pas
encore d'insert ; cela ne préjuge pas des modifications non sauvegardées de
la session ouverte. Aucun plugin n'a été ajouté par cet audit.

## Hardware et Linux

Les commandes analogiques de la section monitoring ne sont pas toutes
nécessairement exposées sur Ethernet. Tester MixToAux/SRC et les potentiomètres
sans déduire une adresse de leur emplacement. Le contrôle du monitor Ardour,
le volume système Linux et le monitoring analogique de la console sont trois
cibles distinctes à présenter clairement dans les réglages.

La page locale de réglages peut accueillir un profil par zone : Mixage,
Plugins/EQ et Linux, avec action, cible et état de validation. Conserver les
valeurs utilisateur actuelles : au relevé du 14 septembre à 21:13 Paris,
révision 9, gain souris 0,58 et jog 0,85. Les anciennes valeurs documentées ne
doivent pas les écraser.

## Capture DSP de cet audit

Capture clôturée : `captures/dsp-encoders-20260914/ethernet.pcapng`.
2 529 trames reçues/capturées, zéro perte selon dumpcap.
SHA-256 : `f239b0e039ad84d4d6c04b9be906f361b4b05dd4734aab2cf79e487e04a0ca11`.
Le dérivé `ethernet.pcap` conserve la résolution nanoseconde ; audit et
commandes avec numéros de trames dans le même dossier.

**Aucune commande de mouvement b0 dans cette fenêtre.** Les 16 commandes
entrantes décodées comprennent boutons et messages système. La séquence
physique demandée n'est pas confirmée à la rédaction. Cette capture ne permet
pas d'assigner les huit encodeurs DSP. Il faudra une nouvelle fenêtre active si
les gestes n'ont pas eu lieu pendant celle-ci.

## Critères du prochain lot

- Huit encodeurs réellement identifiés ; sens et pas vérifiés, sans invention.
- Noms/valeurs stables, sans alternance avec les gains de piste.
- EQ présent explicitement choisi ; chaque paramètre agit sur la bonne cible.
- Changements de piste/page/bypass sans valeur ancienne envoyée au nouveau plugin.
- Protection et écho tactile des faders conservés ; FLIP traité séparément.
- Aucun retour aux requêtes /refresh ou au catalogue legacy /strip/list qui
  reconstruisaient les observateurs ; sorties regroupées et ACK préservés.
- Vérification de la latence et des vumètres pendant la manipulation des paramètres.
