# Audit du code Ardour — transport, mémoire et OSC

Date : 14 septembre 2026. Installation : paquet Ubuntu 1:8.4.0+ds1-2ubuntu8.
Comparaison du tag officiel 8.4 avec master et les commits officiels ci-dessous.
Les sources lues sont conservées dans work/research/ardour-8.4/libs et
work/research/ardour-master/libs. Le paquet de distribution peut porter des
patches : cet audit de source n'est pas une reconstruction de son binaire.

## Réserve d'événements et message de mémoire

Le journal utilisateur `.xsession-errors`, lignes 1010–1022 lors du relevé,
contient Pool::alloc → SessionEvent::operator new → Session::start_transport →
TransportFSM::process_event/process_events → Session::process → backend ALSA.
825 erreurs « bad transition » étaient présentes dans ce journal, notamment
LocateDone reçu dans Stopped ou Rolling/WaitingForButler. Les traces ne sont
pas toutes horodatées ; ne pas les attribuer à un geste précis sans capture.

Dans libs/pbd/pool.cc, Pool::alloc émet le message fatal « POOL OUT OF MEMORY -
RECOMPILE WITH LARGER SIZE!! » quand sa liste d'éléments libres est vide.
La trace correspond à ce chemin. Le texte du message est retrouvé dans la
bibliothèque installée et dans la source, pas comme ligne du journal capturé.

Dans libs/ardour/audioengine.cc, AudioEngine::thread_init demande un pool de
512 événements par thread. Le thread OSC demande son propre pool de128.
Le pool de la trace est celui du moteur audio : augmenter seulement le pool
OSC ne traiterait donc pas nécessairement cet épuisement.

Chemin du jog mode0 :

- osc.cc, OSC::jog : appelle jump_by_seconds(delta / 5).
- basic_ui.cc, BasicUI::jump_by_seconds : lit la position courante, ajoute le
  déplacement et appelle Session::request_locate.
- session_transport.cc : demande Locate/LocateRoll puis machine de transport.
- Session::start_transport alloue jusqu'à deux événements TransportStateChange
  dans le chemin normal, programmés à la position de départ et après pré-roll.

Cela relie effectivement le jog au mécanisme vu dans la trace. Cela ne démontre
pas encore quel événement est perdu/accumulé dans notre session. Les demandes
rapprochées calculées sur une position non encore mise à jour sont une piste de
reproduction, pas une causalité établie.

## Corrections officielles du transport pertinentes

- [4eccfcc3b423](https://github.com/Ardour/ardour/commit/4eccfcc3b423db09d2682fc944d76aa25793267b), 22 février2026 : mémorise `_last_locate = l` dans
  start_locate_while_stopped. Le message du commit cite explicitement une
  transition invalide causée par LocateDone. Absent du tag8.4 examiné.
- [ed7f7e26af93](https://github.com/Ardour/ardour/commit/ed7f7e26af93fb0e0b397b45f565c83880827d6f), 21 février2026 : supprime une demande de déplacement redondante
  pendant le chargement de session. Le commit décrit deux LocateDone dont le
  second arrive alors que le transport est déjà arrêté. Absent du tag8.4.

Ces corrections sont pertinentes pour nos erreurs de transition ; elles ne
prouvent pas la résolution du pool épuisé ni des corruptions mémoire OSC.
Aucune mise à jour du binaire n'a été effectuée par cet audit.

## OSC et défauts qui affectent notre interface

La passerelle ouvre actuellement un port source UDP éphémère, envoie la
configuration /set_surface à l'ouverture, puis feedback0 à la fermeture.
Ardour identifie la surface par son adresse de retour. set_surface reconfigure
les observateurs, strip_feedback, la banque, la sélection et le feedback global.
Cela correspond au chemin du dernier coredump (PID30783,21:20:30 Paris), où
l'allocateur détecte une corruption mémoire pendant l'initialisation OSC.
La pile de détection ne localise pas l'écriture qui a corrompu la mémoire.

Deux corrections officielles postérieures à8.4 concernent directement les plugins :

- [a9a578739932](https://github.com/Ardour/ardour/commit/a9a5787399327921ff364d6e2d455ea0f94278c7), 30 juin2024 : les tailles de pages demandées par set_surface
  pouvaient être inscrites dans la structure sans être transmises à l'observateur.
  Une réponse set_surface annonçant8 n'est donc pas une preuve de huit retours.
- [142fa9f55db4](https://github.com/Ardour/ardour/commit/142fa9f55db4c3488edf417feeb94bdc8e7d5809), 30 juin2024 : transmet les changements de configuration
  du feedback à OSCSelectObserver, au lieu de conserver ses valeurs initiales.

Un ancien correctif de double libération (810b2fb78d89,2020) est déjà présent
au tag8.4 : il ne faut pas le présenter comme notre correctif manquant.

## Suites techniques et validation

1. Tester les correctifs officiels dans une construction séparée d'Ardour,
   ou une version qui les contient explicitement ; préserver la session originale.
2. Rendre l'identité de la surface persistante et éviter les reconstructions
   inutiles. Vérifier réutilisation, reprise des états et changement de session.
3. Mesurer les rafales du jog et la fin effective des déplacements. Un éventuel
   regroupement doit préserver la somme des déplacements et les inversions,
   sans ajouter de délai aux boutons PLAY/STOP ni aux faders.
4. Valider arrêt/lecture, déplacements répétés, chargement, reconnexion,
   boucle/pré-roll puis pages plugin. Vérifier absence d'erreurs de transition,
   de nouvelle trace Pool::alloc et de coredump ; ne pas confondre tests de
   mapping Python et stabilité du moteur audio.

Les quatre patches officiels sont conservés dans ardour-upstream-patches,
avec SHA et résultat du contrôle d'application. Ils ne sont ni compilés ni
installés. Voir aussi [contrat OSC](ardour-osc-contract.md) et
[relevé mémoire/ALSA](alsa-memory-investigation-2026-09-14.json).

Contrôle des patches contre les sources officielles8.4 : 4eccfcc3b423,
142fa9f55db4 et a9a578739932 passent git apply --check. ed7f7e26af93 ne
s'applique pas directement (contexte session_state.cc différent : set_clean
intercalé) et nécessite un rétroportage revu. Aucun de ces contrôles ne constitue
une compilation ou un test de stabilité. Les patches sont conservés inchangés.
