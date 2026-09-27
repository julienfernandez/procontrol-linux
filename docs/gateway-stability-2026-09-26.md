# Supervision et page web — 26 septembre 2026

Cette intervention corrige la réaction de la passerelle à un service arrêté,
une MPC déconnectée et plusieurs pages web en attente. Elle complète le
[correctif natif des callbacks OSC](osc-callback-lifetime-2026-09-26.md), traité
séparément. Les erreurs USB et le SIGSEGV natif ne sont pas assimilés à une
cause unique.

## Défauts reproduits et corrections

- Un fichier de statut âgé de moins de cinq secondes autorisait le routage
  même après la disparition du worker. La lecture commune vérifie maintenant
  le verrou de service, la fraîcheur du même fichier ouvert et son indicateur
  de fonctionnement. `running` décrit le verrou ; `live` exige aussi un état
  récent et actif. Les anciens états de connexion, sources et niveaux sont
  retirés quand l'observation n'est plus valable. Un arrêt propre conserve
  son libellé `stopped`.
- Une reprise automatique en attente restait exécutable après décochage de
  l'option. Elle est maintenant annulée et journalisée. Une opération déjà
  démarrée termine normalement ; les demandes manuelles restent distinctes.
- Une reprise automatique partait sur le diagnostic du cycle précédent.
  Elle revérifie maintenant l'appareil avant de démarrer. Une disparition
  réseau ou une réparation intervenue entretemps annule le travail en attente.
- Si le gadget existe sur la MPC mais n'est pas connecté et n'apparaît pas
  côté PC, la supervision attend le câble au lieu de relancer la préparation
  à cause d'autres états incomplets. Le panneau donne cette raison. Un gadget
  absent après redémarrage peut toujours être recréé automatiquement.
- Le lanceur réutilise jusqu'à son terme le travail déjà engagé, y compris
  une annulation ou un échec. Une attente câble/réseau confirmée n'entraîne
  plus une nouvelle préparation manuelle ou une attente inutile de 65 secondes.
- Au démarrage du serveur, le lanceur attend le premier diagnostic frais.
  L'absence initiale de diagnostic ne doit pas déclencher une préparation.
  Ce cas a été découvert pendant la remise en service décrite ci-dessous.
- Le cache partagé des lectures console démarre son délai **après** la
  réponse ou le timeout. Les pages qui attendaient la même réponse lente
  partagent désormais son résultat.
- Les deux sondages du panneau attendent leur réponse précédente, suspendent
  leur activité dans un onglet masqué et reprennent dès son affichage. Les
  lectures expirent après cinq secondes, corps JSON compris. Cette expiration
  ne s'applique pas aux écritures, dont il faut connaître le résultat.

Le traitement Ethernet/OSC, l'unique émetteur, les ACK, le regroupement des
moteurs et le jog sont conservés. Aucun sondage global `/refresh` ni
reconstruction périodique `/set_surface` n'est ajouté. Ces correctifs ne changent
pas les valeurs de priorité audio, de tampon ou de nombre de canaux. La remise
en service utilise ensuite la préparation USB existante, décrite ci-dessous.

## Vérifications reproductibles

Les cinq nouveaux cas ciblant les anciennes sources ont tous échoué avant
correction : statut sans worker, câble absent, désactivation de la reprise,
revalidation avant reprise et partage d'une réponse lente. Les tests corrigés
couvrent aussi la conservation des demandes manuelles et des réponses valides.

Mesure synthétique avec huit clients simultanés et une réponse RPC expirant
après 310 ms ; il ne s'agit pas de latence physique de la console :

| Version | Appels RPC | Attente médiane | Attente maximale |
|---|---:|---:|---:|
| Avant | 8 | 1 409,2 ms | 2 497,0 ms |
| Après | 1 | 312,2 ms | 313,6 ms |

Commandes de contrôle :

```sh
python3 -m unittest discover -s tests
node tests/test_web_polling.js
git diff --check
```

Le passage complet réussit : **460 tests en 138,010 s**. Après le dernier
correctif du démarrage sans diagnostic, les **11 tests du lanceur** passent,
dont le nouveau cas ; la suite complète n'est pas répétée pendant la mesure
audio réelle. Le test JavaScript passe également.

Le test JavaScript utilise une horloge et des requêtes contrôlées pour vérifier
l'absence d'empilement, l'onglet masqué, la reprise, l'expiration et la requête
suivante. Les tests du pointer utilisent son vrai worker dans un environnement
temporaire, sans injection sur le bureau. Sa fixture publie désormais le champ
`running`, comme le vrai démon. Le premier passage complet avait également
détecté la perte du libellé d'arrêt propre ; cette régression a été corrigée.

## Contrôle dans le navigateur

Parcours : panneau Studio → état des services arrêtés → modification d'une
sensibilité → sauvegarde → ouverture des journaux. Serveur isolé, configuration
temporaire, aucun superviseur matériel démarré. Chromium via Playwright déjà
installé ; le skill Browser n'était pas disponible.

| Contrôle | Résultat |
|---|---|
| URL, titre et contenu principal | Corrects |
| Erreurs JavaScript et écran d'erreur | Aucune |
| Réglage sauvegardé et relu par API | Correct, dans la configuration temporaire |
| Journal ouvert et rendu | Correct |
| Lectures retardées de 1,8 s | Une seule en vol |
| Bureau 1280 × 900 et mobile 390 × 844 | Captures relues, page sans débordement horizontal |

Les preuves brutes, captures et mesures restent dans les dossiers privés
`work/gateway-stability-20260926` et le dossier de dépannage du poste. Elles
ne contiennent aucune nouvelle validation auditive ou gestuelle. Le retour
USB 16 canaux nécessite que la MPC soit de nouveau présente ; 32 canaux ne
sont pas activés par cette intervention.

## Remise en service réelle

Après fermeture de la copie native, une préparation USB 16 × S16 est effectuée.
La MPC conserve son processus applicatif et son démarrage système. L'USB et le
pont MIDI réapparaissent ; la sélection du périphérique audio reste manuelle.

Le premier lancement du pointeur échoue parce que cette application a hérité
`XDG_SESSION_TYPE=tty` lors d'un démarrage depuis SSH. Les variables graphiques
sont reprises du vrai processus de session X11, puis le lanceur habituel est
réutilisé. Aucun contournement du garde-fou Wayland n'est ajouté au code.

Le lancement a également provoqué **un second appel de préparation non voulu** :
le serveur web n'avait pas encore publié son premier diagnostic. La procédure
existante a conservé le gadget configuré et le processus MPC. Le lanceur attend
désormais un diagnostic frais avant de décider ; son nouveau test reproduit
ce démarrage. Aucune troisième préparation n'est lancée pour le vérifier.

La session musicale originale est ouverte, transport arrêté et enregistrement
désarmé, avec Link laissé inactif. Le SHA-256 du fichier `.ardour` est identique
avant et après ouverture. La préférence persistante Link n'a pas été changée ;
seul ce lancement ne l'active pas. La reprise automatique USB reste activée,
avec `repair_needed=false`.

À 15 h 26–27, une observation de **30,03 secondes** relève :

| Élément | Observation |
|---|---|
| Démon / pointeur / Ardour | PID 19924 / 20227 / 20304 ; états frais, console Online, OSC répond |
| Catalogues | Session attendue, stéréo active, bus MPC SUB 1 retrouvé |
| USB et MIDI | Deux sens 16/16, aucun lien erroné, pont MIDI présent |
| Routage | 16 entrées MPC, Master 2/2 vers Behringer, aucune autre destination |
| Sorties console | 240/240 feedbacks acquittés depuis démarrage, zéro timeout/reprise, file vide |
| ACK | Maximum observé depuis démarrage : 3,05 ms ; ce n'est pas une latence de fader physique |
| Ressources passerelle | RSS 25 412 Kio, 11 descripteurs, 1 thread constants ; CPU environ 5,64 % d'un cœur |
| Application MPC | Même PID 319, aucun reboot ni arrêt de l'application |
| Audio dans la MPC | PCM fermé : choisir Preferences → Audio Device → UAC2_Gadget 0 |

La page réelle `http://127.0.0.1:8765/` est relue dans Chromium : console Online,
Ardour connecté, stéréo active, bus présent dans la liste et journaux accessibles,
sans erreur JavaScript. Aucun réglage utilisateur n'est écrit pendant ce test web.
Les services sont laissés actifs. La demande de sélection MPC est transmise à
l'utilisateur ; tant qu'elle n'est pas confirmée et relue, aucune écoute ni
validation du flux applicatif MPC ne peut être annoncée. Cette observation au
repos reste distincte d'un essai gestuel chargé ou d'une endurance nocturne.
