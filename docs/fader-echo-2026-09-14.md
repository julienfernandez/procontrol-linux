# Cycle tactile et retour moteur — 14 septembre 2026

Vidéo IMG_0357 : création18:52:06UTC, durée4,336667s. Vues extraites examinées
à5images/s ; utilisateur décrit un retour en arrière puis vers la position donnée.
Corrélation du journal sur la voie5 :
- dernière position physique à18:52:09.237285 :889/1023 =0,8690127 ;
- relâchement tactile à18:52:09.240839 ;
- commande moteur à18:52:09.586083 :`b0 04 6f 24 10`, soit889/1023 ;
- délai relâchement→consigne finale :345,244ms.

La valeur moteur finale était correcte : le défaut n'est donc pas ici une
mauvaise conversion numérique. La protection300ms bloquait également l'écho
nécessaire pour synchroniser la consigne interne avec le geste physique. Le
retour transitoire vers une ancienne consigne est cohérent avec la vidéo et ce
délai ; l'état interne du servo n'est pas directement mesuré.

Référence locale consultée : `vendor/reacontrol24/ReaCommon.py`, `_ReaFader`,
méthodes `_update_from_fadermove` et `_update_from_touch` ; ProCfader en hérite.
Ce code renvoie une position physique et renvoie explicitement la position au
relâchement. Sources vendorizées inchangées.

Correction installée :
- une position reçue du fader physique devient la consigne locale prioritaire ;
- seule cette valeur exacte peut être renvoyée au moteur pendant le toucher ;
- une consigne différente d'Ardour reste bloquée pendant le toucher et la garde ;
- au relâchement, écho final explicite sans attendre300ms ;
- une seule trame en attente d'ACK, équité de file maintenue ;
- reconnexion efface l'autorité locale d'écho, les commandes distantes normales
  restent permises hors manipulation.

110 tests passent : quatre nouveaux tests couvrent l'écho physique exact,
le relâchement sans délai300ms, le rejet d'un ancien retour OSC et la reprise
des commandes distantes / remise à zéro à la reconnexion.
Démon28586 démarré18:57:24.595823UTC, console Online, Ardour répond ;
305 sorties /305ACK, zéro timeout à la vérification initiale.
Essai physique demandé à l'utilisateur sur le fader5 ; résultat encore attendu.

Confirmation utilisateur : « le fader, c’est parfait » ; comportement physique validé.
