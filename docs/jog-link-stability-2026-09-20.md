# Jog en lecture, début de session et synchronisation JACK / Link

## Problème observé

Photo utilisateur : `CRITICAL: AudioEngine 1 POOL OUT OF MEMORY - RECOMPILE WITH LARGER SIZE!!`.
Ardour 9.8 local, session studio-mpc-usb, PipeWire/JACK à 44,1 kHz / 512 samples,
synchronisation externe JACK et timebase master activés pour le pont vers Link.
L'utilisateur identifie ensuite le retour au start comme déclencheur et précise
que le chiffre 1 de la console était bien en mode temporel, pas en mesures.

## Causes vérifiées

1. **Fuite du pool.** `SessionEventManager::merge_event()` rejetait un doublon
   `(type, action_sample)` sans le détruire. Le test natif, lié à la bibliothèque
   installée avant correction, perd une case dès le premier doublon. Sous GDB,
   l'ancien binaire atteint la réserve vide dans `Session::start_transport()` :
   pool AudioEngine 1 de 512 entrées, index lecture = index écriture. Au second
   relevé, seulement 14 événements TransportStateChange restent dans la liste,
   et aucun événement immédiat : une réserve vide ne signifie donc pas une
   file de 512 déplacements légitimes. Les objets rejetés ont été perdus.
2. **Plan JACK périmé.** Dans `plan_master_strategy_engine()`, la branche
   « JACK arrêté, Ardour encore en lecture » exécutait STOP immédiatement mais
   conservait l'ancien plan, éventuellement START. `implement_master_strategy()`
   pouvait ensuite redémarrer la session à chaque cycle. Après le premier
   correctif mémoire seul, le test de recul au start échoue encore : position
   interne 2560 répétée et vitesse 0/1, malgré JACK arrêté. La correction du
   plan est nécessaire en plus de celle du pool.
3. **Position affichée et relative.** L'horloge GUI utilise `audible_sample()`
   (position JACK en synchronisation externe), alors que le retour OSC et
   `BasicUI::jump_by_seconds()` utilisaient `transport_sample()` (lecteurs audio,
   avec avance de compensation). À 44,1 kHz et 30 images/s, une avance de 2560
   samples explique une dernière unité SMPTE à 1 alors que JACK reste à zéro.
   Ce n'est pas une conversion secondes/mesures. L'écart pouvait aussi faire
   avancer un petit pas négatif de jog, inférieur à l'avance des lecteurs.
4. **Pont Link.** `JackTransportStarting` pendant un locate en lecture était
   interprété comme STOP. Le pont conserve maintenant l'intention de lecture
   pendant cette attente, puis recale la phase quand JACK roule à nouveau.
   Un vrai JackTransportStopped ou une source invalide reste un arrêt.

La réserve a aussi été épuisée avec le service Link arrêté et JACK conservé :
le pont Link n'a pas besoin d'être actif pour déclencher le défaut natif.

## Correctif

`native/ardour-9.8-jog-pool.patch` s'ajoute aux patches locaux OSC existants sur
la source Ardour 9.8 `22ed8656c2533e325322ff11831448e5123e0d4b`.

- Rend au pool tout événement rejeté ; coalesce silencieusement les notifications
  de transport identiques, en conservant l'erreur pour les autres types.
- Remplace le plan JACK par STOP dans la phase de planification, pour exécution
  dans le cycle de traitement prévu, sans rejouer un ancien START.
- Avant une nouvelle paire de notifications de démarrage, met en file leur
  nettoyage précédent. Pas de suppression directe pendant une itération de
  timeline. La notification future de monitoring d'un preroll record trim est
  préservée lorsque cette fonction est active.
- Utilise la position audible pour les affichages OSC et le jog relatif en
  secondes, comme la GUI. `/transport_frame` conserve sa sémantique interne.
- Protège aussi `/jog/mode` lorsqu'aucun observateur global OSC n'existe. Ce
  SIGSEGV distinct a été rencontré avec un client de test sans feedback.

Aucune augmentation de réserve, modification de cadence ProControl ou
modification de sensibilité utilisateur. Le pont reste unidirectionnel
Ardour → Link ; il expose `transport_starts` et `transport_stops` pour contrôler
les commandes émises pendant les seeks.

## Vérification reproductible

Le test natif utilise une réserve de 16 éléments et appelle réellement les
méthodes de libardour, sans réimplémenter le gestionnaire :

```sh
python3 tools/check_ardour_event_pool.py --source /chemin/ardour-9.8 \
  --library-dir /chemin/installation/lib/ardour9 --output /tmp/test-event-pool
c++ -std=c++17 native/tests/link-transport.cc -o /tmp/test-link-transport
/tmp/test-link-transport
```

Après ouverture d'une **copie jetable** sans enregistrement armé, reproduire
le maintien vers le début puis les déplacements alternés :

```sh
python3 tools/check_ardour_jog.py --disposable-session --pattern start-boundary \
  --duration 60 --output /tmp/jog-start.json
python3 tools/check_ardour_jog.py --disposable-session --duration 120 \
  --output /tmp/jog-alternating.json
```

Ces essais lancent la lecture et peuvent démarrer les pairs Link connectés.
Ils vérifient les réponses OSC, la reprise de lecture après relâchement et STOP.
Le rapport JSON adjacent conserve les résultats finaux et les limites.

### Résultats de la version finale

- Recul continu au start : 60,005 s, 2 976 commandes, aucune action physique
  concurrente trouvée dans le journal. Reprise de lecture après relâchement,
  STOP confirmé, un START et un STOP émis par le pont Link.
- Aller-retour : 120,006 s, 5 925 commandes automatiques, auxquelles se sont
  ajoutés 396 jogs physiques et trois retours au start en fin d'essai. Reprise
  et STOP confirmés ; un START et un STOP émis par Link dans cette fenêtre.
- Contrôle isolé, passerelle arrêtée brièvement puis relancée : SMPTE
  `00:00:00:00` au start ; petit recul restant à zéro ; jog +0,2 donnant
  1 764 samples (40 ms), puis -0,2 ramenant à zéro. `/jog/mode` répond encore
  après suppression du feedback global.
- Fermeture normale de la copie, réouverture de la session originale avec le
  lanceur Ardour habituel, PLAY puis STOP validés, retour au start. Routage
  MPC 16 canaux, Behringer stéréo et Roland MIDI USB 2 remis en place.
- Passerelle Online, huit tranches prêtes, session originale reconnue ; Link
  actif avec un pair. 223 tests Python passent, ainsi que les tests natifs.

L’utilisateur confirme ensuite sur la session originale : **« Oui, lecture et
compteur corrects »**, en réponse au test physique lecture + jog jusqu’au start
et compteur à zéro. Cette validation physique est acquise pour ce scénario.

Voir [les mesures structurées](jog-link-validation-2026-09-20.json). Les
bibliothèques `libardour`, `libardourcp` et `libardour_osc` ont été compilées
et installées ; les anciennes versions restent dans le dossier de preuves.
Compilation : `python3 waf build --targets=libardour,libardour_cp,libardour_osc -j2`.

## Preuves locales et limites

Dossier ignoré par Git : `run/jog-link-20260920/`. Il conserve les sessions
sauvegardées et copiées, anciennes bibliothèques, traces GDB, builds, scénarios
et le manifeste SHA-256 des bibliothèques installées. Aucune piste originale
n'a été enregistrée ou éditée pour les essais.

Les reproductions initiales ont épuisé le pool après environ 31 s avec Link,
puis 19 s sans pont Link. L'utilisateur a également effectué des gestes réels
pendant une partie du diagnostic ; ces fenêtres mixtes ne sont pas une mesure
isolée du seul générateur. Le premier stress corrigé de 103 s a été interrompu
par une erreur du script GDB après une interruption diagnostique volontaire :
il ne compte pas comme un test de 180 s réussi ni comme un crash spontané.
Le premier test ciblé au start, avec le seul correctif mémoire installé, a
révélé le défaut du plan JACK encore présent et n'est pas un succès final.

Les tests du pool et de transport Link portent sur 4096 répétitions chacun.
Ils ne prouvent pas l'endurance audio, l'alignement audible MPC ou tous les
modes de boucle, tempo, enregistrement et synchronisation.
