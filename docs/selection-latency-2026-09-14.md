# Sélection, micro-coupures et afficheurs — 14 septembre 2026

## Mesure initiale

L'utilisateur signale pendant la lecture des appuis manqués, clignotements et
coupures de vumètres. Capture locale OSC60s, sans arrêter la passerelle :
`captures/selection-latency-20260914/osc.pcapng`,14091 paquets,0 perte.
SHA256 :845c2913ed67aa3430b446a6b6804c88a649baaf816f17b30feb23582b86d7d5.
Les PCAPNG ont une résolution nanoseconde, lue dans l'option if_tsresol.

17 appuis Matrix SELECT dans la fenêtre, seulement9 messages OSC correspondants.
8 appuis reçus par le démon n'étaient pas transmis : `ready=False` pendant
l'invalidation du catalogue, avec attente pouvant atteindre2s. Les9 commandes
transmises recevaient un retour Ardour en1,10–2,44ms.
[Corrélation initiale](selection-latency-before.json).

Ardour8.4 émet `/strip/list` même lors des sélections, via la notification globale
PresentationInfo puis `_recalcbanks`. Le démon interprétait ce signal comme une
reconstruction de la liste. Le code Ardour consulté est dans
work/research/ardour-8.4/osc.cc (hors livrable), source officielle :
https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.cc

## Première correction et mesure de comparaison

`ArdourSurface.request_catalog` utilise maintenant `/strip` (instantané sans
recréation d'observateurs), suivi de `/set_surface` sans argument : cette lecture
de configuration fournit une réponse marquant la fin de l'instantané.
La configuration initiale avec arguments reste nécessaire et distincte.
Notifications traitées immédiatement ; seul un instantané sans réponse attend
le délai de retry. Vérification de continuité des SSID et du nombre de lignes
contre le catalogue Lua disponible ; les identifiants incomplets ne sont pas
publiés. Un changement réel de nombre de pistes peut attendre le catalogue Lua.

Capture45s après correction : `osc-after.pcapng`,16489 paquets,0 perte.
SHA256 :381c0994742edf7e4aece431009e3995d0f7968b34fcce178acd5045e2ebc618.
31 appuis /31 messages SELECT transmis ; aucun appui manquant dans cette fenêtre.
Traitement appui→émission OSC :0,10–0,43ms (depuis l'événement décodé, pas le contact
physique). Retour sélection Ardour :0,97–4,22ms. Instantané pistes :4,19–6,50ms.
Aucun `/strip/list` ni `/refresh` émis par le client dans cette capture.
[Résultats détaillés](selection-latency-after.json).

Utilisateur : amélioration mais ratés encore perçus, micro-coupures sur les
vumètres de tranches alors que le master reste régulier, affichages de voies
étranges. Ne pas présenter la première correction comme complète.

## Seconde correction des retours visuels

Défauts reproduits par tests :
- `slots()` vide pendant l'instantané faisait envoyer zéro aux mètres de tranches ;
  le master résolvait directement sa source Lua et n'était pas touché ;
- le même afficheur recevait alternativement le fader en pourcentage et le gain
  en dB, notamment lors du rendu de catalogue / changement de banque.

Correction installée : `display_slots()` et les identités déjà validées conservent
la vue pendant l'instantané, tandis que les commandes restent protégées par
`ready`. Le rendu Matrix garde également la sélection connue. Les données audio
continuent d'expirer après1s et une déconnexion efface toujours les tranches.
L'affichage du gain utilise uniquement le retour dB ; le retour fader pilote
uniquement le moteur. Les valeurs négatives signifiant « non pris en charge »
pour mute/solo/rec ne sont pas interprétées comme actives.

106 tests passent. Dernier état relevé : daemon27392, console Online, Ardour
répond,453 sorties /453 ACK, zéro timeout et file vide. Services laissés actifs.
La vidéo annoncée par l'utilisateur n'a pas encore été reçue ; disparition
visuelle des dernières micro-coupures après cette seconde correction non confirmée.

## Vidéo IMG_0356 reçue

Métadonnées vidéo : création2026-09-14T18:49:54Z, durée11,148s,60images/s.
Examen de planche de vues et d'une image à7s : les valeurs en pourcentage sont
visibles au-dessus des encodeurs, deux colonnes master allumées et plusieurs
changements de sélection sur la matrice. Aucun diagnostic de timing ne repose
sur une seule image ou sur un possible effet de balayage de la caméra.

Corrélation du journal sur18:49:54–18:50:06UTC : les afficheurs reçoivent chacun
~20 valeurs dB et~20 valeurs%, confirmant l'alternance logicielle ; les mètres
1/33 reçoivent respectivement19/17 commandes zéro, alors que10/42(master) n'en
reçoivent aucune. Les coupures sont donc aussi présentes dans les trames émises.

Le second correctif est démarré à18:50:22.334680UTC (PID27392), APRÈS la fin
estimée de cette vidéo. Celle-ci documente le défaut antérieur ; elle ne constitue
pas une preuve d'échec ou de réussite du dernier correctif. Visuel après correction
encore à confirmer,106 tests déjà réussis.
