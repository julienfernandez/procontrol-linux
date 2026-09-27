# Studio, voix électroniques et pumping — 27 septembre 2026

Cette passe déploie des corrections de lecture PipeWire et de diagnostic, puis
prépare six effets et leurs commandes ProControl. Le projet utilisateur a été
sauvegardé et rouvert. **La préparation des chaînes est faite ; l'affectation
des deux voix, de la basse et du kick, puis la validation à l'écoute restent à
terminer avec l'utilisateur.** Une insertion réussie ne vaut pas validation
musicale ni confirmation d'un geste sur la console.

## État initial et sauvegardes

Ardour était fermé, avec une sauvegarde du projet à 08 h 04, heure de Paris.
La passerelle, les deux maintiens USB et la MPC fonctionnaient. Le projet
contenait 20 routes ; les pistes nommées au-delà de MPC 15-16 n'avaient pas
d'entrées matérielles correspondantes. La liaison reste à **16 canaux USB**,
44,1 kHz, quantum PipeWire forcé à 512.

Le journal préalable contenait 23 003 lignes de resynchronisation de
l'entrée interne `front:0c`, puis aucune après la fermeture d'Ardour. Un
nettoyage antérieur de son port de mesure avait échoué sur `JSONDecodeError:
Extra data`. Le compteur de supervision PCM valait 157, sans preuve que
l'application MPC ait redémarré 157 fois. L'identité de son processus et son
temps de démarrage doivent accompagner cette mesure.

L'archive locale privée `../studio-vocal-pump-20260927/`, à côté du dépôt,
conserve : session complète et manifeste SHA-256, configuration Ardour,
journaux précédents, copie du code déjà modifié, diff initial, ancien module
OSC, copie du projet MPC et résultats des essais. Il s'agit d'une copie sur
le **même stockage**, sans preuve de sauvegarde sur un support indépendant.
Le projet possède aussi l'instantané `Avant voix et pumping 2026-09-27`.
Les médias, captures d'écran et réglages privés ne sont pas ajoutés à Git.

Le checkout était déjà modifié avant cette intervention, sur la base
`16d50ca2299695ec96968e5ef4d248c7ccc076c3`. Les changements précédents sont
préservés ; aucun commit ni push global de ce checkout n'a été effectué.

## Corrections déployées

- `tools/pipewire_graph.py` centralise les lectures : `pw-dump --no-colors`,
  délai de 4 secondes, séparation de stderr, validation du JSON et des objets,
  trois tentatives au maximum, puis erreur explicite. Un document tronqué ou
  deux documents concaténés ne deviennent pas un graphe vide. Les objets
  Metadata sans `info` restent acceptés ; les liens incomplets sont refusés.
- Le backend attend l'apparition du port Ardour
  `physical_audio_input_monitor_enable`, reprend les lectures et déconnexions
  transitoirement échouées, puis vérifie le graphe. Seuls les liens de
  l'entrée PCI interne vers ce port sont concernés, pas les pistes ou USB.
  Quatre connexions ont été retirées à la dernière relance ; résultat
  `verified: true`, aucun lien interne restant.
- La supervision distingue Ardour fermé/en attente d'un défaut de routage.
  Chaque transition PCM garde direction, état, propriétaire, horodatage de
  déclenchement, période et tampon, ainsi que l'identité MPC avant/après.
  Le compteur de transitions ne déclenche pas à lui seul une réparation.
- `health.jsonl` conserve les événements de santé et une mesure par minute,
  avec rotation bornée indépendante des traces Ethernet/OSC. Le journal de
  supervision est également borné. Les logs de lancement et de nettoyage
  sont accessibles au diagnostic Studio.

## Plugins, presets et protocole

| Effet | Version observée / choix déployé | État préparé |
|---|---|---|
| x42 Autotune | paquet x42 20230915, LV2 | discret et robotique, chromatiques en attendant la tonalité |
| Rubber Band | LV2 3.3.0+dfsg-2build1, moteur classique | quinte +7 et octave −12, mono/stéréo, formants activés |
| Surge XT | 1.3.4, instrument et Effects VST3 | preset Effects vocodeur 20 bandes, synthétiseur porteur séparé |
| LSP Sidechain Compressor | 1.2.14, LV2 mono/stéréo | détecteur externe, ratio 4, attaque 2 ms, release 180 ms |
| B.Shapr | 0.13-0ubuntu1, LV2 sans CV | niveau sur un temps, courbe lissée, mélange 50 % |
| LSP Beat Breather | 1.2.14, LV2 mono/stéréo | direct seul, départ neutre et plugin désactivé |

Rubber Band et B.Shapr proviennent des paquets de la distribution, extraits
dans `~/.lv2` ; ils sont disponibles à Ardour sans installation système APT.
Le paquet Rubber Band annonce aussi R3 dans son manifeste mais le binaire
testé n'exporte pas ces URI : le catalogue emploie les variantes classiques.
Les ports CV de B.Shapr ne sont pas pris en charge dans cet Ardour ; la
variante audio ordinaire est celle retenue.

Les [presets livrés](../presets/studio-vocal-pump/README.md) et la
[fiche ProControl](vocal-pump-controls.md) décrivent les pages de paramètres.
La bibliothèque passe de huit à quatorze choix. La capacité native OSC 3
conserve les messages antérieurs, filtre les nouveaux choix sur les anciennes
extensions et refuse les versions inconnues. DYN conserve son compresseur
habituel. L'insertion est explicite et protégée contre les doublons.

Le vocodeur nécessite un preset nommé effectivement chargé. Ses descripteurs
de paramètres doivent correspondre au mode vocodeur ; les valeurs VST3
normalisées ne sont pas présentées comme des fréquences en Hz. Son insertion
seule ne crée pas le synthétiseur, le MIDI et le câblage d'une chaîne complète.

Le module OSC a été remplacé **Ardour fermé**, puis chargé à la relance de
08 h 53. Le test de signal a ensuite conduit à corriger les broches sidechain
LSP ; cette révision a été installée, Ardour fermé, à 09 h 18 puis relancée.
SHA-256 final installé :
`44b88ceac4569e4184655a6bf45290ccd0a02afe74ab62bd496ea6c13021fd21`.
Les huit patches natifs se réappliquent dans l'ordre sur la base officielle
Ardour et reproduisent les 16 fichiers du build local. La cible
`libardour_osc` a été recompilée ; voir [la reconstruction](../native/README.md).

## Projet préparé et limites musicales

Douze routes supplémentaires portent les voix A/B, quatre retours d'harmonie,
le modulateur, le vocodeur, le synthétiseur MIDI, le kick, son détecteur et le
bus PUMP. Les 21 effets précédemment présents conservent leurs identifiants,
leurs valeurs de ports LV2 et leur état d'activation.

Les sorties du synthétiseur vont exclusivement dans l'entrée principale du
vocodeur ; le modulateur va exclusivement dans son sidechain. Le kick possède
un départ après ses traitements et avant fader vers le détecteur de PUMP.
Ce détecteur ne sort pas dans le Master. Le compresseur et B.Shapr sont
préparés comme deux variantes à écouter séparément.

Les sept départs nouveaux sont explicitement à 0 dB : la valeur de création
Ardour était −inf, ce que le premier test de signal a révélé. Autre correction
mesurée : Ardour 9.8 ne reliait pas automatiquement les broches externes du
compresseur LSP au port sidechain créé. L'insertion native et la préparation
raccordent maintenant le détecteur mono aux deux broches de la version stéréo.
Les versions mono/stéréo ont été vérifiées, ainsi que la sauvegarde et la
réouverture du projet corrigé. Le
[constructeur de chaînes](../ardour/prepare_vocal_pump.lua) conserve ces deux
précautions et désactive initialement les nouveaux effets.

Les entrées des nouvelles chaînes restent libres et tous leurs nouveaux
traitements sont désactivés. Les retours d'harmonie sont en plus muets à
−18 dB. Cela évite d'imposer un traitement ou sa compensation de latence
avant le choix des sources. x42 a déclaré 1056 échantillons de délai dans
l'essai à 44,1 kHz, environ 24 ms ; Rubber Band classique et Beat Breather
peuvent ajouter des délais bien plus grands. La latence aller-retour réelle
et son acceptabilité en direct restent à mesurer et écouter.

Le kick de la séquence courante est identifié au pad A01 par le sample et
les événements note 36. Les huit paires USB étant occupées, isoler ce pad
exige de choisir une paire à libérer ou de regrouper d'autres instruments.
Le projet MPC a été sauvegardé, mais son routage n'a pas encore été modifié :
la proposition de regroupement et l'identité des deux voix/basse attendent
la réponse utilisateur. Les noms et détails musicaux restent dans la fiche
locale privée, pas dans ce dépôt public.

Le service Link a retrouvé sa préférence de lancement. La MPC affiche Link
désactivé, sans pair détecté ; son tempo courant (120) diffère du tempo
Ardour (90). Le service démarré ne prouve donc pas une synchronisation
effective du morceau. Aucun tempo n'a été imposé à la MPC.

## Validation et incidents observés

- `python3 -m unittest discover -s tests` : **474 tests réussis** en 140,582 s.
  Ils couvrent notamment les lectures invalides/interrompues, l'apparition et
  la disparition de ports, le nettoyage ciblé, les transitions PCM, le
  lancement idempotent, les capacités et les limites de paramètres.
- Un Ardour isolé a inséré les quatorze choix sur des routes mono et stéréo,
  relu leurs vrais descripteurs, écrit puis relu des paramètres, repris un
  effet existant sans doublon et refusé les cibles/URI non autorisées.
- La session de test avec les chaînes a été sauvegardée puis rouverte. Une
  auto-connexion Ardour différée ajoutait initialement une sortie Master aux
  bus porteur/modulateur ; le montage attend maintenant la stabilisation
  des ports avant d'appliquer et vérifier leurs sorties exclusives.
- Un signal sinusoïdal dans le moteur Dummy, sans sortie matérielle, traverse
  les départs modulateur et détecteur après correction. Sur ce signal d'essai,
  seuil du compresseur −20 dBFS et départ détecteur à +6 dB : réduction mesurée
  **3,78 dB**. Le preset musical reste à son seuil initial −12 dBFS, à régler
  sur le kick réel. Le synthétiseur reçoit une note MIDI ; couper le modulateur
  fait chuter la sortie du vocodeur de **38,81 dB**. Ces tests valident le
  passage et la dépendance des signaux, pas le timbre ni les accords du morceau.
- Les fenêtres x42 A/B, Surge Effects, sidechain LSP, Beat Breather, Rubber
  Band et B.Shapr ont été ouvertes successivement depuis l'extension native,
  avec vérification des fenêtres réellement présentes. Un premier délai de
  deux secondes était trop court pour Beat Breather ; trois secondes ont
  permis l'affichage. La courbe B.Shapr apparaît après activation DSP :
  sa fenêtre seule, plugin désactivé, ne recevait pas encore les points.
- Une capture privée de huit secondes a reçu un signal non nul sur les
  16 canaux MPC. Cela prouve un flux reçu, pas l'identité auditive de chaque
  source ni l'absence de défaut audible. Des crêtes du mix existant ont
  dépassé 0 dBFS lors de la lecture ; l'équilibrage reste à faire à l'écoute.

Trois processus **luasession de test isolés** ont produit un SIGSEGV à 08 h 33,
08 h 46 et 08 h 47. Les piles conservées passent par
`Route::sidechain_change_handler` lors de la destruction de références Lua
aux processeurs à sidechain après fermeture de leur session. Le scénario de test
libère désormais ces références et force la collecte avant fermeture ;
les sauvegardes/réouvertures suivantes ont réussi. Ce correctif de méthode
ne prétend pas corriger cette durée de vie dans le cœur Ardour. Le processus
Ardour graphique ouvert à ce moment-là et la MPC sont restés actifs.

Les resynchronisations de l'entrée interne ont cessé dans la fenêtre
observée après nettoyage. Des resynchronisations **de la sortie Behringer**
ont toutefois été journalisées entre 08 h 53 et 08 h 57, puis à la relance de
09 h 19. Ses réglages étaient réellement appliqués : période ALSA
64 (demi-période USB batch de la demande 128), marge effective 576 pour une
demande 512. Aucun changement global de fréquence ou quantum n'est ajouté
pour masquer cette observation. Le code de
[PipeWire 1.0.5](https://github.com/PipeWire/pipewire/blob/1.0.5/spa/plugins/alsa/alsa-pcm.c)
déclenche ici la reprise sur un écart au tampon cible ; la seule ligne de
journal ne permet pas d'attribuer la cause à la MPC ou à un plugin précis.

Les transitions PCM relevées après 08 h 53 gardent le même PID MPC et la même
identité de démarrage. De nombreux intervalles valent environ 21,339 s, ou
un multiple de cette durée. La séquence affichée est bien à 120 BPM, huit
mesures (boucle de 16 s) : on ne peut donc pas assimiler ces transitions
aux tours de boucle. Aucun redémarrage automatique n’est déclenché à partir
de ce seul compteur. Le journal de l’application ne fournit pas de cause
explicite pour ces reprises.

Les deux premiers collecteurs ponctuels ont été interrompus par SIGTERM ;
leurs segments sont conservés, sans les présenter comme 30 minutes
continues. Le journal de santé du daemon est indépendant de ces collecteurs.
L'essai musical demandé de 30 minutes **avec les deux voix affectées, la
basse, le kick séparé et les effets actifs n'est pas validé**. Il dépend du
routage restant à choisir, puis des confirmations d'écoute et de gestes
ProControl.

## Reprise

Le relevé de clôture à **09 h 24 min 39 s** est conservé dans le
[bilan JSON](studio-vocal-pump-2026-09-27.json). La passerelle a fonctionné
31 min 15 s depuis sa relance : 56 648 retours envoyés, deux timeouts et deux
récupérations, aucune erreur OSC active ; ACK maximal observé 191,44 ms,
dernier ACK 2,94 ms. Ces mesures sous installation et tests ne suffisent pas
à conclure à une amélioration statistique par rapport à la veille.

Le graphe final compte 16 connexions d'entrée MPC, deux sorties Master
Behringer, aucune autre destination Master et aucun lien du vumètre interne.
Les deux maintiens USB sont raccordés sur leurs 16 canaux, PCM dans les deux
sens actif. Le compteur de supervision a relevé 35 transitions PCM depuis
son démarrage, sans nouvelle identité d'application MPC. Les sept lignes de
resynchronisation Behringer après 08 h 53 annoncent aussi 67 messages masqués
par le limiteur du journal ; aucune ne concerne l'entrée interne.

Les compteurs `pw-top` sont conservés comme tels : certains sont antérieurs
à cette passe et le nœud Ardour a été recréé lors des relances. Ils ne doivent
pas être additionnés comme des xruns nouveaux sur cette seule période.
La fenêtre supplémentaire d'échantillonnage a été clôturée explicitement ;
sa durée exacte figure dans le JSON. La période de santé de plus de 30 minutes
inclut une fermeture volontaire d'Ardour pour le dernier module et ne remplace
pas l'endurance musicale encore à faire.

Choisir la paire USB à libérer, router A01 séparément dans le mixer de pads
MPC et vérifier que le bus de batterie ne reçoit plus ce kick en doublon.
Affecter ensuite les deux voix et la basse dans Ardour, confirmer la tonalité
et le tempo, choisir le port MIDI du porteur et son monitoring, puis régler
les 3 à 6 dB de réduction du sidechain sur le signal réel. Comparer les
traitements à niveau égal et conserver séparément mesures et avis d'écoute.
Une nouvelle observation continue devra inclure ces traitements actifs,
les resynchronisations Behringer, les xruns et les temps ACK.
