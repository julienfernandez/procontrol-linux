# Fermetures Ardour — diagnostic du 14 septembre 2026

## Preuves locales

Ardour installé : 8.4.0~ds1-2ubuntu8. Cinq rapports systemd-coredump
retrouvés dans le journal, tous avec le module OSC dans la pile du thread fautif.
Les heures ci-dessous sont celles de publication des rapports, Europe/Paris ;
la faute peut précéder de quelques secondes la fin du rapport.

| Rapport | PID | Signal | Chemin de la pile fautive |
|---|---:|---|---|
| 13/09 21:48:43 | 45752 | SIGSEGV (11) | routes_list → strip_feedback → destruction OSCRouteObserver |
| 13/09 22:22:25 | 71226 | SIGSEGV (11) | routes_list → strip_feedback → destruction OSCRouteObserver |
| 13/09 22:33:58 | 73070 | SIGABRT (6) | set_surface → OSCSelectObserver → allocation liblo |
| 13/09 23:36:34 | 75777 | SIGSEGV (11) | routes_list → strip_feedback → destruction OSCRouteObserver |
| 14/09 20:22:37 | 19321 | SIGSEGV (11) | refresh_surface → set_surface → _strip_select2 → allocation |

Le noyau date la dernière faute à **20:22:35**. Le journal passerelle indique
`feedback_recovery` à **20:22:35.384968** (18:22:35 UTC), après un ACK manquant
(3749 sorties / 3748 ACK). Ce chemin envoyait immédiatement `/refresh`.
À 20:22:37.450871, le port Ardour refuse les datagrammes.

Les extractions conservées :
- [Piles des cinq rapports](ardour-crash-evidence.json)
- [Événements de la passerelle autour du dernier crash](ardour-crash-gateway-events.json)

Aucun événement OOM trouvé avec la recherche `oom-kill|Out of memory|Killed process.*ardour`
dans les journaux accessibles depuis le 13 septembre. Les cinq signaux ci-dessus
prouvent des crashs, pas des commandes normales de fermeture. Les anciennes
mentions « Got SIGTERM, quitting » ne suffisaient pas à expliquer ces incidents.

## Analyse et contournement

Le [code officiel Ardour 8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.cc)
montre que `routes_list` appelle `strip_feedback(sur, true)` et que
`refresh_surface` détruit puis recrée les observateurs. Notre catalogue toutes
les deux secondes répétait donc une opération avec effets internes, pas une
simple lecture. La corrélation du dernier crash et la pile établissent fortement
l'implication de la passerelle comme déclencheur. L'origine exacte de la corruption
mémoire C++ reste à établir ; ce diagnostic ne prétend pas la corriger dans Ardour.

Contournement installé :
- suppression du catalogue périodique une fois reçu ; nouvelle demande au démarrage,
  après notification de changement ou réponse manquante, avec délai de reprise ;
- aucun `/refresh` complet transmis, y compris F1 et les demandes de paramètres
  encore inconnus ; simple lecture de la vitesse de transport à sa place ;
- resynchronisation console depuis les dernières sorties connues, en conservant
  les protections des moteurs et les nouvelles valeurs reçues ;
- configuration initiale OSC et catalogue initial conservés : le risque interne
  Ardour n'est donc pas supprimé de manière absolue.

Limite volontaire : F1 réaffiche le cache local. Un paramètre de plugin ou de départ
encore inconnu attend son retour OSC normal ; il ne provoque plus une reconstruction
complète de la surface. Une restauration exhaustive de retours OSC perdus nécessite
un mécanisme de requêtes ciblées supplémentaire.

Validation : 88 tests réussis, dont UDP local vérifiant l'absence de `/refresh`,
conservation de PLAY, catalogue uniquement à la demande et protection fader touché.
Services relancés sans root : démon 24092, pointeur 24095 ; web 19617 conservé.
Console Online, 72 sorties / 72 ACK, aucun output_error à la vérification.
Révision réglages 8 conservée, master 10/42 et sensibilités utilisateur inchangés.
Ardour n'a pas été lancé durant cette investigation. La stabilité prolongée et les
retours visuels après sa prochaine ouverture restent à valider en situation réelle.

## Nouveau lancement utilisateur pendant le diagnostic

Sixième rapport : **14/09 20:36:12.640650 +02:00**, PID23567, SIGABRT(6),
`set_surface → _set_bank → _strip_select2 → allocation → malloc_printerr → abort`.
Il précède la bascule du correctif : ancien démon arrêté à20:36:29.344858,
nouveau démarré à20:36:29.765599. Ce crash ne constitue donc pas un essai du
contournement déployé. Il confirme toutefois le risque à l'initialisation OSC,
qui reste présente après correction. Aucun lancement Ardour par l'agent.

Limites configurées /etc/security/limits.conf lignes66–68 :
`@audio - rtprio 95`, `@audio - memlock unlimited`, `@audio - nice -19`.
Ce sont des permissions/plafonds : elles ne forcent pas tous les processus du
groupe à tourner avec cette priorité ou à verrouiller toute la RAM. Aucun indice
local ne les relie au crash. Les limites effectives du PID23567 n'ont pas pu être
lues dans /proc puisqu'il était déjà terminé. Ne pas les modifier sans preuve.
