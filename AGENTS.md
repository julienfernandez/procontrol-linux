# Collaboration ProControl

## État actuel et continuité

- Répondre en français. Donner des retours visibles sur le travail et les résultats.
- L'utilisateur demande d'avancer vite, de réutiliser franchement GitHub et les
  photos, et de raccorder toutes les fonctions possibles à Ardour. L'essai actif,
  les afficheurs, faders, LEDs, vumètres, clavier et souris sont autorisés dans
  ce cadre. Ne pas redemander cette autorisation à chaque commande.
- Les deux processus doivent rester **en arrière-plan entre les échanges** :
  `./procontrol start|status|stop` et `./pointer start|status|stop`. Ne pas les
  arrêter en fin de réponse. Avant d'éditer leurs modules chargés, les arrêter
  proprement puis les relancer. Aucun second émetteur Ethernet concurrent.
- À chaque reprise : `python3 tools/status.py`, puis lire `docs/protocol.md`,
  `docs/control-map.md` et les observations récentes. Vérifier état + verrou ;
  un ancien status.json ne prouve pas qu'un processus tourne.
- Version étendue déployée le 13/09/2026 à 18:34 UTC ; 58 tests passent.
  Références et preuves dans `docs/extended-validation-2026-09-13.json`.
- L'utilisateur confirme Online, PLAY/STOP, trackpad quatre directions, puis
  **afficheurs des tranches, compteur huit chiffres et jog fonctionnels**.
  Clavier ALPHA, majuscules, chiffres et clics gauche/droit réellement reçus
  dans le test GTK : docs/input-live-validation.json. Pas de log clavier global.
- Pointer X11 gain 0,24 après 0,12 jugé lent. Clavier fr/latin9, XTEST ; aucun
  périphérique uinput créé. Pas encore Wayland ni démarrage automatique au boot.
- Reste : six grands vumètres (adressage / stéréo / segments), encodeurs DSP et
  boutons non associés, tests moteurs, banques longues, départs et plugins.
  Consulter les limites concrètes de control-map.md avant d'étendre leur usage.
- ALPHA / pavé / clics : capture contrôlée 20260913T182202Z-alpha-keypad-controls-batch-ndOm88.
  Le fixture de tests conserve corps et actions ; user a confirmé toute la séquence.
- Ancien parcours de table corrigé : 0x15/16/17 sont DSP/monitor/matrix, pas des
  tranches 22/23/24. Les libellés historiques ne sont pas des preuves physiques.
- Sources GPL vendorizées sans modification : phunkyg DEV_OtherDevices
  b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069 ; lazlooose
  b23402542cdfdb09fbb44cc3000ecede1103125b. Le compteur ProControl ET sa LED de
  mode utilisent l'adresse 09. Lire displays.md ; l'ancien essai adresse 19
  était acquitté sans changement visuel, conserver cet historique.
- Maintiens toutes les 10 s indépendamment des ACK : ne pas réintroduire la
  famine de keepalive corrigée. Online/ACK/keepalive seuls suffisent à connecter.
  La reconnexion est testée par modèle ; les cycles câble/alimentation restent à éprouver.

## Captures et privilèges

- Les captures passives ne font pas sortir Offline. Les essais actifs sont
  désormais autorisés ; conserver les expériences et leur provenance distinctes.
- Sur ce laptop AppArmor refuse le signal du label chatgpt vers tcpdump : ne
  pas lancer tcpdump pour capturer depuis l'app et ne pas modifier AppArmor.
  Utiliser dumpcap avec durée native. Le compte moi est membre de wireshark,
  mais l'app conserve ses anciens groupes : lancer avec
  `sg wireshark -c 'PROCONTROL_CAPTURE_BACKEND=dumpcap bash tools/capture.sh ...'`.
- Ne pas modifier le script de capture pendant son exécution. N'analyser que
  les PCAP clôturés. Préserver originaux, SHA-256, trames et statistiques de pertes.
- Une authentification en attente n'est pas une capture active ; attendre son
  ouverture effective avant de demander un geste. Jamais de mot de passe chat,
  utiliser pkexec local. Ne pas supposer sudo partagé avec un autre terminal.
- Séparer l'heure du geste dans les données et celle de la confirmation chat.
  Les gestes après clôture sont dans le journal, pas dans le PCAP précédent.
- Les deux premiers session_probe avaient un magic nanoseconde avec fractions
  microsecondes : originaux préservés, dérivés traffic-us.pcap documentés. Writer corrigé.
- Distinguer observations locales, confirmations utilisateur, hypothèses et
  références Control|24. ACK ne signifie pas succès visuel ; une inscription
  sur une photo ne donne pas un code Ethernet. Photos tierces hors licence GPL.

## Mise à jour SELECT / stéréo / web

- Lire docs/stereo-settings.md : 69 tests, hook Lua installé et validé en réception.
- Trois services désormais : procontrol, pointer et settings (web loopback 8765).
- Déploiement effectué, relance pkexec en attente au 13/09 à 19:40 UTC.
  Ne pas confondre ancien status.json avec un démon actif.
- Calibration des grandes colonnes encore absente ; meter_addresses null.
  Ne pas annoncer le master visible sans validation physique.
- Extension suivante : cibles automation gain/pan/mute/trim, audition/pré-roll,
  punch/sync, zoom avec modificateur et page plugin précédente. 73 tests.
  Lire la dernière section de control-map.md ; validation physique encore attendue.
- tools/mapping_inventory.py génère mapping-coverage.json et mapping-backlog.md.
  284 entrées de table, dont 226 avec une action normale ; ce ne sont pas 284
  boutons physiques. Les codes DSP/navigation non identifiés restent non inventés.

## Reprise à 22:04 Paris

- Démon 68966 et pointeur 68988 confirmés actifs, Online, sans erreur après
  authentification ; utilisateur confirme que le fonctionnement s'améliore.
- Correctif départs/paramètres préparé et testé (78 tests) dans
  work/implementation-stage. Lire docs/send-update.md.
- Bascule ponctuelle work/deploy_send_update.py en attente d'authentification
  pkexec ; elle laisse l'ancien démon actif jusqu'à l'authentification, puis
  arrête les deux services, copie 3 modules + test et relance. Le parent relance
  le pointeur en conservant l'environnement X11. Vérifier PID/date avant de
  conclure au déploiement. Ne pas lancer une seconde bascule concurrente.
- Question utilisateur en attente : candidats grands vumètres 8 (test A) et
  40 (test B), allumages de deux secondes à 21:59:09/13 et 21:59:21/25 Paris.
  Aucun résultat visuel reçu ; meter_addresses reste null.
- docs/unmapped-command-counts.json conserve les commandes inconnues des
  journaux tournants : zone bouton 0x18, encodeur 0x54 notamment. Elles ne sont
  pas encore identifiées physiquement. Aucune capture PCAP en cours.

## État à 22:25 Paris — lanceur sans authentification installé

- Lire docs/rootless-launch.md. /usr/local/libexec/procontrol-net est root:moi
  0750, cap_net_raw=ep, source native/procontrol-net.c. Python sans capability.
  ./procontrol start ouvre les sockets via ce petit binaire ; plus de pkexec
  nécessaire pour les redémarrages ordinaires. Deux démarrages non root validés.
- Correctif départs/paramètres déployé, 81 tests passent avec calibration web et
  lanceur. Dernier démon 71961, pointer relancé ; consulter état réel à la reprise.
- La session Ardour a été renommée /home/moi/Musique/tttt. Le lanceur installé
  est /usr/bin/ardour (pas ardour8). Relancée puis SIGTERM reçu ; question en
  attente pour savoir si arrêt volontaire. Ne pas relancer en boucle.
- Page8765 : panneau Identifier les colonnes de la console, test lumineux par
  RPC sans modifier la config, puis choix manuel de la colonne observée. API
  protégée comme les réglages, adresses interdites/doublons refusés. Aucun
  grand vumètre physiquement identifié, meter_addresses toujours null.
- Plus aucune installation pkexec en attente. Premier script relatif avait
  échoué car pkexec change cwd vers /root ; désormais toujours chemin absolu.

## Correctif retours à 22:35 Paris

- Défaut reproduit : ACK859 absent, ACK858/860 présents ; output_error restait
  définitivement bloquant. Corrigé par reprise temporisée et rafraîchissement
  OSC des états actuels, sans rejouer un ancien moteur. Lire feedback-recovery.md.
- Reprise e1 autorisée uniquement si announced_host_candidate == MAC laptop,
  sous verrou local exclusif. Ne pas réintroduire l'attente de sa propre session.
- 85 tests passent. Démon75543 Online, Ardour75777 relancé sur session tttt ;
  191/191 retours acquittés à la validation, huit pistes et stéréo actives.
- Gains utilisateur désormais souris0.58 et jog4.65 (révision3), à conserver.
- Capture feedback-recovery clôturée, audit et SHA conservés. Aucun PCAP actif.

## Lanceur graphique installé le 14 septembre

- Icône ProControl sur ~/Bureau et menu ~/.local/share/applications.
  tools/desktop_launcher.py démarre procontrol, pointer, settings puis ouvre8765.
  Verrou global du lanceur et starts idempotents ; aucune authentification.
  Lire docs/desktop-launcher.md. Journal run/desktop-launch.log.
- Validation après reboot : console Online, pointeur actif, HTTP joignable,
  trois PID inchangés au second lancement ; sensitivités0.58/4.65 conservées.
  Ardour était fermé et attendu, pas lancé automatiquement par le raccourci.

- Lanceur amélioré : --restart, icône ProControl — Redémarrer sur le bureau et Desktop Action Restart. Attend arrêt réel des trois services avant relance ; normal vérifie leur état et conserve les PID. Vérification live réussie.

- Master grands vumètres : utilisateur identifie les adresses décimales10 et42.
  Config appliquée à chaud révision8 : master L→10, R→42, quatre autres désactivés.
  Ne pas remettre ces deux adresses à null ; suite des colonnes non confirmée.

- Suite des adresses confirmée utilisateur : paires10/42,11/43,12/44,13/45.
  Voir docs/confirmed-meter-addresses.json. Master10/42 conservé ; aucune autre
  source demandée. Le modèle UI actuel à six sorties individuelles ne représente
  pas quatre paires : clarifier la topologie physique avant extension du modèle.

## Crashs Ardour — 14 septembre

- Lire docs/ardour-crashes-2026-09-14.md. Cinq coredumps OSC, dont trois dans
  routes_list/destruction OSCRouteObserver, un set_surface, un refresh_surface.
  Ne plus interpréter l'ancien SIGTERM comme preuve de fermeture volontaire.
- Catalogue /strip/list toutes les 2 s supprimé après réponse : cette commande
  reconstruit les observateurs Ardour 8.4. Requête initiale/changement/retry seulement.
- /refresh intercepté au client : lecture transport seulement. Reconnexion de
  console et F1 rejouent les sorties locales actuelles, protections moteurs conservées.
  Paramètres inconnus attendent le feedback normal, sans full refresh.
- 88 tests passent ; daemon/pointer relancés sans root, console Online 72/72 ACK.
  Ardour laissé fermé ; contournement validé en tests, stabilité réelle à confirmer.

## Channel Matrix — retours lumineux

- Lire docs/channel-matrix-leds.md. SurfaceRouting rend les32 LEDs depuis les
  états OSC absolus, modes SELECT/MUTE/SOLO/REC et pages A–D. ALPHA masque les
  pistes, garde CAPS ; déconnexion efface. Initialisation utilise les mêmes
  clés LED que les mises à jour, pour éviter de rejouer un ancien mode.
- 92 tests passent. Démon24947/pointeur relancés ; Ardour répond avec8 pistes
  et stéréo. Validation visuelle demandée à l'utilisateur, encore attendue.
- Aucun nouveau /refresh ni sondage périodique catalogue. Le contournement
  crash précédent est préservé ; ne pas annoncer Ardour stable à long terme.

## Réactivité — 14 septembre

- Utilisateur confirme LEDs Matrix fonctionnelles, demande optimisation lenteur/timecode.
- Lire docs/latency-2026-09-14.md. Attente fixe50ms remplacée par attente au prochain
  envoi + réveil sur OSC/Lua ; espacement2ms, un seul ACK en attente, priorité
  compteur/LED limitée à4 avant la plus ancienne sortie. Moteurs touchés sans busy loop.
- 98 tests passent. Mesure live compteur médiane212→99,5ms, max269→101,6ms sur20s,
  aucun timeoutACK. Visuel de l'optimisation encore à confirmer ; services actifs.
- Ne pas promettre plus de10Hz sans modifier la source temporelle Ardour.
- Confirmation utilisateur reçue ensuite : compteur et LEDs « nettement plus réactifs ».

## Sélections et micro-coupures — 14 septembre

- Lire docs/selection-latency-2026-09-14.md. Capture montre8/17 appuis non transmis
  pendant invalidation catalogue2s. Client utilise désormais /strip + /set_surface
  sans arguments (lecture/bord de snapshot), jamais catalogue legacy /strip/list.
  Notifications immédiates ; captures suivantes31/31 sélections transmises.
- Utilisateur signale encore micro-coupures des mètres de tranches et valeurs
  étranges après cette première correction. Seconde correction installée : vue
  d'affichage conservée pendant snapshot, commandes toujours guarded ready ; gain
  uniquement en dB, fader uniquement moteur. Master utilisait déjà l'identité directe.
- 106 tests passent ; daemon27392 Online/Ardour répond,453/453ACK. Vidéo annoncée
  encore attendue. Ne pas prétendre la dernière correction validée visuellement.

## Fader tactile — vidéo IMG_0357

- Lire docs/fader-echo-2026-09-14.md : moteur reçoit la bonne position finale,
  mais345ms après release. Ancienne protection empêchait aussi l'écho physique
  prévu dans ReaCommon/_ReaFader au relâchement.
- Correction : feedback.local recueille la position physique ; seule sa valeur
  exacte peut être renvoyée pendant le toucher, prioritaire. Release renvoie
  explicitement la dernière position sans délai300ms. Consignes DAW différentes
  restent bloquées pendant toucher/garde, resync efface l'autorité locale.
- 110 tests passent ; daemon28586 Online/Ardour répond,305/305ACK. Test physique
  fader5 demandé, résultat encore attendu ; ne pas annoncer résolu sans lui.

- Fader : utilisateur confirme le correctif parfait, validation physique acquise.

## DSP — 14 septembre 21:20 Paris

- Lire docs/dsp-encoders-2026-09-14.md. Capture take2 confirme huit encodeurs
  4D..54 haut→bas ; mapping page plugin installé, 114 tests. Valeur initiale
  obligatoire, pas de modification du mode des encodeurs de tranches.
- Relance suivie crash Ardour PID30783 dans set_surface ; rapport conservé.
  Ardour relancé une fois. Ne pas considérer le problème des redémarrages résolu.
- Réglages utilisateur révision10 : souris0.58, jog0.2, master10/42 conservés.

- DSP afficheurs : photo utilisateur confirme série B, adresses2D..34 haut→bas.
  Lire docs/dsp-displays-confirmed.json. Série A encore indéterminée.
  Fonction dsp_controls.dsp_text testée ; pas encore reliée au feedback plugin.

## Sources Ardour et contrat OSC —14 septembre

- Lire docs/ardour-osc-contract.md et ardour-source-audit-2026-09-14.md.
- Source8.4 : pool audio512 demandés, poolOSC128. Trace Pool::alloc audio
  distincte de détection corruption heap pendant set_surface ; lien non prouvé.
- Correctifs upstream4eccfcc3b423 (LocateDone redondant), ed7f7e26af93
  (chargement session),142fa9f55db4 (feedback observateur),a9a578739932 (pages).
  Patches conservés docs/ardour-upstream-patches, trois passent apply--check ;
  ed7 nécessite rétroportage. Aucun binaire compilé/installé, aucun crash résolu annoncé.
- /select/plugin est relatif, float delta ; /select/plug_page float signé.
  /select/expand int0/1 n'ouvre pas la fenêtreGUI. Ne pas confondre indicesLV2,
  identifiants plugin et positions1..8 de page. Signature source prime sur hypothèse.

## Migration Ardour9.8 en cours

- Utilisateur demande finalement la dernière version stable, installation
  directe et debug ensuite. Compilation8.4 arrêtée, aucun binaire8.4 modifié.
- Sources officielles9.8 : work/ardour-build-9.8, commit22ed8656c2533e325322ff11831448e5123e0d4b,
  aucun patch local. Les quatre corrections auditées sont déjà présentes.
- Dépendances de compilation installées via apt avec authentification utilisateur.
- Préfixe prévu ~/.local/opt/ardour-9.8 ; build-manifest et sauvegarde session
  dans outputs/ardour-corrected. Ne pas dire installé avant validation du manifest.
- La session originale et config8 sont sauvegardées. Ardour8 PID32024 tué
  explicitement à la demande utilisateur. Passerelle et pointeur restent actifs.

## Ardour9.8 installé — 14 septembre 23:29 Paris

- Compilation et installation réussies, version9.8.0 vérifiée, ldd sans manque.
  Préfixe ~/.local/opt/ardour-9.8 ; icône Bureau/Ardour 9.8.desktop et menu Ardour.
- Lire ../ardour-corrected/README.md et build-manifest.json pour état exact.
- Migration OSC : ControlProtocols/Protocol doit avoir config="" ; anciennes
  entrées8 ignorées sans attribut. OSC réactivé3819.
- Migration Lua : bitset LuaSignal50→52 bits. Hook stéréo hérité déclenchait un
  événement de région. Réenregistré dans Script Manager sur LuaTimerDS, sauvegardé.
  Utilisateur confirme contrôle console, puis vumètres pistes ET master.
- SIGSEGV9.8 PID59282 dans OSC::strip_state/allocation mémoire : cause précise
  non établie, backtrace+core conservés dans ../ardour-corrected.
- Session actuellement PID59708 avec LD_PRELOAD libasan.so temporaire (allocateur,
  PAS binaire instrumenté ASan). Contrôle/retours validés ainsi ; aucun nouveau
  coredump pendant validation. Le lanceur normal n'ajoute pas ce préchargement.
  Ne pas prétendre crash résolu. Éviter redémarrage inutile pendant utilisation.
- Gateway PID46985/pointer46990 observés actifs ; vérifier état réel à la reprise.
  Réglages souris0.58/jog0.2/master10/42 inchangés. Aucune capture active.

## Greffons installés — 14 septembre 2026, 23:43 Paris

LSP/x42/Zam/Dragonfly/Surge installés. Lire docs/free-plugins-selection.md et
docs/installed-dsp-chains.json. Session tttt : 8 pistes stéréo, chacune EQ x8 puis
compresseur LSP neutres ; 16 ajouts, relecture XML et second passage sans doublon.
Script réutilisable ardour/procontrol_add_eq_compressor.lua. Ardour PID64154
relancé avec le même préchargement allocateur ASan (pas instrumentation complète).
Profils DSP LSP et affichage dynamique des paramètres restent à implémenter ;
installation ne prouve pas le mapping de huit bandes aux huit encodeurs.

## Mode EQ, compresseur et navigateur — 15 septembre 2026

Lire docs/eq-plugin-workflow.md et eq-plugin-validation.json. tools/eq_editor.py
intégré au démon : EQ/DYN IN EDIT ciblés, INSERTS/PARAM navigateur, boutons DSP
pour filtres/plugins, paramètres sur rotatifs de tranches, LEDs clignotantes.
Liste+descripteurs OSC ciblés toutes les500ms en édition seulement ; valeurs
internes/IDs1-based nth-control. Aucun refresh/catalogue legacy. 138 tests passent.
Démon 66901 et pointer relancés sans root ; vérifier état réel.
Compresseur LSP Stereo confirmé sur les8 pistes actuelles. Création automatique
des chaînes pour les pistes futures pas encore implémentée.
Question utilisateur en attente : EQ IN/EDIT puis SELECT ligneDSP2, rotatifs
tranches1/2 ; confirmer écrans, LED et changementsGUI. Ne pas annoncer validé
physiquement avant réponse. Backup before-eq-browser-* conserve versions.

### Correction observée pendant essai utilisateur, 00:06 Paris

139 tests. Une sélection Ardour émet /strip/list même sans changement de piste ;
le premier déploiement quittait le mode DSP et effaçait les écrans. Corrigé :
attendre le catalogue en gardant les écrans, bloquer les commandes puis vérifier
identité/révision avant reprise. Démon67205/pointer67208 (vérifier).
DYN Neverender à22:06:13UTC : mode params actif/ready, plugin2,21snapshots à22:06:24,
542/542ACK, aucun timeout. Ce constat réseau ne vaut pas confirmation visuelle.
Question en attente : affichage stable du compresseur, ratio depuis rotatif2.
Utilisateur a décrit la disparition initiale après publication du correctif ;
les logs séparent les essais22:04:xx qui s effaçaient et22:06:13 qui persistent.

### Vérification réelle après correction

Les paramètres ont été modifiés depuis les commandes console : lecture OSC
indépendante confirme compresseur Neverender ratio1.6, attaque21ms, release103ms.
Capture osc-active.pcapng :4770paquets,0perte,23écritures plugin, requêtes
descripteurs médiane552ms. Premier osc.pcapng précédait les gestes (0écriture).
Preuves dans captures/eq-browser-20260915/analysis.json et
docs/compressor-live-edits.json. EQ et compresseur restent ouverts après
sélection dans les observations suivantes. Confirmation visuelle utilisateur
encore attendue ; ne pas attribuer son constat initial négatif au correctif final
sans examiner l heure et les nouvelles actions. 139tests sont le dernier total.

## Fenêtres greffons natives — 15 septembre, 00:19 Paris

Lire docs/plugin-window-follow.md et plugin-window-validation.json. Extension
locale OSC d’Ardour9.8 compilée/installée : native/ardour-9.8-plugin-ui.patch.
La source officielle est désormais modifiée dans osc.cc/osc.h ; l’ancienne
mention « aucun patch » est historique. ShowUI/HideUI natifs via thread GUI.
Version1 négociée ; ciblage session + ID route persistant + nth_plugin1-based +
nom exact. Une seule fenêtre gérée ; clear réservé à son émetteur OSC. Les
retours périodiques des paramètres ne rouvrent pas la fenêtre. Absence du patch
sur une autre version désactive uniquement le suivi, pas les commandes DSP.

Passerelle : tools/plugin_window.py, surface_osc.py et procontrold.py.
EQEditor conserve EQ/compresseur lors des SELECT/Matrix/Bank. Browser garde
la liste ; greffon générique revient à la liste lors du changement de voie.
150tests réussis. Essais natifs : comp Audio1→Neverender, EQ Neverender,
rejets mauvaise session/ID débordant/nom, clear d’un autre client inopérant.
Utilisateur confirme « Oui, les fenêtres suivent correctement ». Capture GUI
et logs montrent EQ Audio2 suivi et valeurs éditées depuis console.
Ardour69132/gateway69124/pointer69128 constatés ; vérifier à la reprise.
Ardour relancé avec le même allocateur libasan préchargé : toujours PAS de
binaire ASan-instrumenté, cause des anciens crashs toujours non établie.
Aucune Mackie virtuelle activée : possibilité analysée/documentée ; fonctions
fenêtre reprises directement des API utilisées par Mackie/FaderPort.

## AUTO de chaque voie — 15 septembre 19:50 Paris

Lire docs/automation-modes.md et automation-validation.json. AUTO0x90/key05
sur zones0..7 cycle gain Manual0→Play1→Write2→Touch3→Latch4 ; Shift inverse.
Un maintien/un retry n’avance pas deux fois. Cible voie réelle selon banque,
indépendante de la sélection. Sans feedback d’automation connu : aucune écriture.
Ardour gainmode2 renvoie /strip/fader/automation : alias normalisé vers gain.
Aucune requête de catalogue périodique ajoutée. Pending borné1s pour appuis
rapides ; LEDs seulement depuis confirmation DAW, banques/reconnexion gérées.
Lampes F0 13 00 20 channel0-based bits F7 : RD04 WR40 TC20 LT10 ; Manual00,
TM08 inutilisé car pas d’équivalent Trim parmi les modes du fader Ardour.
165tests passent. Utilisateur confirme les cinq états. Capture mixte90s
clôturée dans captures/automation-modes-20260915 :20appuis=20commandes,
21retours et21lampes acquittées, appui→envoi lampe médiane3.8835ms/max5.112ms.
1paquet flushed par interface à clôture dumpcap, consigné ; originaux+SHA.
Démon89191 et pointer relancés sans root, Ardour69132 resté actif. Vérifier PIDs.
Souris gain0.58 inchangé ; utilisateur satisfait. Ne pas attribuer les gestes
capturés à la voie1 : cette voie était dans la consigne, PCAP observe voies2/3.

## Sens pan — 15 septembre 19:57 Paris

Suite au signalement « sens des balances inversés », delta inversé uniquement
pour mode pan des rotatifs0x40..0x47 : old-step au lieu de old+step. Aucun
changement EQ/plugins/départs/jog. Table LED G/C/D de _ReaVpot conservée.
165tests passent, contrôles huit voies deux sens/précision/limites/anneaux.
Démon90294 relancé sans root, Ardour69132 conservé ;192/192ACK à vérification.
Question physique en attente : Ardour ET anneau suivent-ils le bon sens ?
Ne pas considérer les deux sens physiques validés avant réponse utilisateur.
Backup before-pan-direction-* ; docs/pan-direction-validation.json.

## Jog / automation / CPU — 15 septembre 20:28 Paris

Lire docs/jog-motor-scheduling.md. ACK12838 manquant dans la capture avant :
3,001s sans sortie, 677 positions OSC reçues pendant ce gel, aucun toucher.
Profil rafales : Ardour jusqu'à205,4 % (IO/GUI), passerelle36,6 % (100 %=1cœur).
Version déployée : ACK100ms avec reprise seulement des éléments non confirmés ;
lots de8moteurs max50Hz, dernière cible ; jog normal somme20ms/50Hz, premier
geste immédiat, barrières d'ordre avant autres commandes ; rendu mètres50Hz.
Scrub/shuttle directs, toucher/écho inchangés. Nouveau tools/jog_scheduler.py.
176tests passent, notamment perte sous charge et convergence, cadence, UDP jog.
Statut surface.output_timing + jog. Démon92263/pointeur92266 actifs, Ardour69132
conservé (préchargement ASan allocateur seulement). Vérifier PID à la reprise.
Un lot de8 confirmé par ACK,185/185 init. Capture after90s SANS geste : validation
sous charge/physique encore attendue ; ne pas annoncer baisse CPU prouvée.
Captures clôturées, SHA/statistiques dans captures/jog-automation-20260915.

Utilisateur absent de la console, essai reporté à son retour. Ne pas demander
un geste immédiat ni interpréter la capture de repos comme un test du correctif.

## Versionnement Git

Dépôt du projet : julienfernandez/procontrol-linux sur GitHub, visibilité privée.
Branche principale main ; premier instantané expérimental v0.1.0.
.gitignore exclut run, captures brutes, backups, settings.json, raccourcis
desktop locaux et images de référence tierces. Garder ces exclusions lors
des prochains commits. Les rapports/fixtures minimales et sources GPL restent
versionnés. La copie exportée depuis l'index Git passe176tests.
Les opérations Git et de documentation ne nécessitent pas l'arrêt des services.

## Stabilité OSC reprise — 17 septembre 2026

Lire docs/stability-2026-09-17.md et stability-validation-2026-09-17.json.
Modifications de l'autre session retrouvées noncommitées sur
fix/ardour-osc-stability : portOSCsource3821 stable, timeout20s/retry5s, fermeture
silencieuse après erreur, métriques ressources et logs bornés.179tests passent.
Native : ardour-9.8-osc-stability.patch s'applique APRÈS ardour-9.8-plugin-ui.patch
sur22ed8656c2533e325322ff11831448e5123e0d4b ; les quatre sources reproduites
correspondent au build installé. Runtime normal sans LD_PRELOAD ASan désormais.
Précédent script live :1démarrage/PLAYSTOP réussis, assertion exit0 échouée après
son SIGTERM (code-15), pas3cycles achevés. Ne pas déclarer tous les crashs réglés.
Reprise ici : démon80167 déjà à jour et gardé actif ; Ardour82472 relancé,8pistes,
stéréo et extension pluginUI récupérés automatiquement ; pointer80170 et
settings61383 actifs. Vérifier les PID/états courants à la prochaine reprise.
Pas de nouveau geste physique ni test nocturne. Changements à conserver dans
main et sur la branche de correction, sans réécrire l'historique v0.1.0.
