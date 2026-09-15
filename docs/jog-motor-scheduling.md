# Jog, automation et cadence des moteurs — 15 septembre 2026

## Diagnostic mesuré

La capture `captures/jog-automation-20260915/before.pcapng` contient 5 110
retours OSC de position, 865 trames moteur, 1 703 commandes OSC jog et aucun
mouvement physique ni contact tactile de fader. Un ACK manque pour la séquence
12838 à 18:21:17.431922 UTC : aucun nouvel affichage/moteur ne part pendant
3,001334 s, alors que 677 positions OSC arrivent. La file coalesce déjà les
valeurs ; le défaut est le blocage global 2 s + reprise 1 s après une seule
perte. La cause de la perte Ethernet initiale n'est pas établie.

Le profil CPU avant correction (25 s, `/proc/PID/task/TID/stat`, 100 % = un
cœur logique) montre Ardour vers 29–34 % au repos et jusqu'à 205,4 % dans les
rafales ; passerelle 1–2 % puis pic 36,6 %. Les threads IO et GUI d'Ardour
concentrent la hausse. Ce profil n'est pas une mesure de température ni une
preuve qu'une charge donnée a déclenché le ventilateur.

Le code local Ardour 9.8 confirme le mécanisme : `OSC::jog`, mode 0, appelle
`jump_by_seconds(delta/5)` ; `BasicUI::jump_by_seconds` demande un locate depuis
la position courante. Les threads `IOTaskList` traitent les travaux de disque.
Même à l'arrêt, les déplacements sollicitent les buffers et l'interface.

## Ordonnancement déployé

- Jog normal : première impulsion immédiate, puis somme des déplacements dans
  une fenêtre de 20 ms. Une seule somme en attente, pas une liste de seeks.
  Le dernier reliquat part même sans nouvelle impulsion. La sensibilité 0,2
  reste inchangée. Une autre action flush la somme avant son propre envoi pour
  conserver l'ordre, notamment STOP et changement de mode. Scrub/shuttle
  conservent leurs sémantiques et leur chemin direct.
- Sortie moteurs : seule la dernière cible par voie attend ; jusqu'à huit
  commandes de cinq octets dans une trame, au maximum 50 lots/s. Cela limite
  les paquets/ACK et réduit le décalage entre les voies. Toucher et écho exact
  local gardent leur protection et leur priorité sans attendre cette cadence.
- ACK : une seule trame en vol ; échéance 100 ms, contre 2 s. En cas de perte,
  invalider uniquement les éléments de cette trame, puis reconstruire depuis
  leur état souhaité actuel. Aucun replay complet LCD/LED ou trajectoire
  moteur ancienne. Deux premières reprises immédiates après l'échéance ; à
  partir de trois pertes consécutives, temporisation 0,1/0,2/0,4/0,8/1,6/2 s.
  Un ACK ancien ne valide jamais une séquence plus récente.
- Vumètres : calcul/rendu au plus 50 Hz au lieu de chaque tour de boucle.
  Leur source Lua conserve sa cadence ; ce changement ne prétend pas créer
  de nouvelles mesures audio.
- Les compteurs, LEDs et échos physiques conservent leurs priorités avec équité
  après quatre sorties urgentes. Les keepalive toutes les 10 s restent
  indépendants des ACK. Pas de `/refresh` destructeur ni `/strip/list` périodique.
- Statut : `surface.output_timing` expose l'ACK courant, la latence, les lots
  moteurs et la file ; `jog` expose impulsions reçues, envois, somme en attente
  et déplacements cumulés. Une déconnexion annule le reliquat jog.

La référence `work/ReaControl24-procontrol/ReaControl.py` utilise une attente
ACK de 0,1 s et des paquets pouvant contenir 48 commandes dans un buffer de
314 octets. Notre lot moteur est limité à 8 commandes / 40 octets.
Les sources de référence ne sont pas modifiées.

Un ACK confirme la réception d'une trame, pas l'atteinte mécanique d'une
position. Le regroupement du jog conserve la somme OSC émise, mais ne prouve
pas que chaque seek asynchrone d'Ardour est exécuté : le protocole `/jog` ne
fournit pas de confirmation de cible associée. Cette limite doit rester
explicite si un écart de déplacement persiste.

## Vérification

176 tests passent : charge continue avec perte d'ACK, convergence vers les
huit dernières positions, checksum et compte du paquet groupé, ACK tardif,
limitation 50 Hz, équité compteur, toucher/écho, jog rapide/lent/inverse,
ordre STOP/mode, annulation et émission du dernier reliquat via un vrai socket
UDP local. Les tests d'automation, DSP et sens du pan restent verts.

Sauvegarde et SHA des modules déployés :
`captures/jog-automation-20260915/deployment.json`.
Ardour est resté ouvert ; démon et pointeur ont été relancés sans root.

La capture avant annonce un paquet flushed à la clôture sur chacune des deux
interfaces (Ethernet et loopback), sans perte noyau rapportée. Les PCAP originaux
sont conservés ; les fichiers `*-derived.pcap` sont des conversions de format
pour l'analyse. Les SHA et statistiques sont dans `*-analysis.json`.

Après déploiement : démon 92263, pointeur 92266, Ardour 69132 conservé.
Le statut de connexion confirme un lot de huit moteurs, 185/185 ACK et zéro
timeout. La capture suivante de 90 s (`after.pcapng`, 9 075 paquets) ne contient
aucun jog ni mise à jour moteur : l'utilisateur n'a pas effectué l'essai dans
cette fenêtre. Ce fichier est une mesure de repos, **pas une comparaison sous
charge**. Un paquet loopback flushed à la clôture, aucun sur Ethernet.

CPU pendant ces 90 s au repos : Ardour moyenne 30,09 %, médiane 29,9 % ;
passerelle moyenne 2,51 %, médiane 2 %. Ne pas comparer les pics avant/ce repos
comme preuve d'une baisse de CPU sous manipulation.

L'essai physique sous charge reste à faire. Les services restent actifs ;
aucune capture ne reste ouverte à l'issue de cette validation.

Utilisateur confirme ensuite avoir quitté la console et reporte l’essai physique.
Aucune mesure supplémentaire demandée ni démarrage différé planifié.
