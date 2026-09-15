# Départs et paramètres — correctif du 13 septembre

## Comportement préparé

Les encodeurs en mode SEND A–E demandent `/strip/sends SSID` avant toute écriture.
Ardour 8.4 répond avec des groupes : destination, nom, index du départ, gain
normalisé, activation. Le mouvement relatif est ajouté à ce gain réel et borné
à 0–1. Plusieurs mouvements en attente sont regroupés. Une réponse absente,
malformée ou âgée de plus d'une seconde ne provoque aucune écriture. Un changement
de banque ou de catalogue annule les mouvements en attente.

Cette requête native décrit les **départs internes** ; les départs externes ne
sont pas pris en charge par ce chemin. Un départ absent ne sera pas créé.

SEND MUTE bascule l'activation du départ A–E choisi **sur la piste sélectionnée**,
à partir du retour `/select/send_enable`. Les encodeurs restent associés aux
huit pistes de la banque. Le bouton exige un retour connu avant de basculer.

Les paramètres plugin exigent une valeur reçue avant de produire une variation.
Les caches sélectionnés sont invalidés aux changements de sélection et de plugin,
et le cache plugin lors d'un changement de page. Cela évite le départ arbitraire
à zéro et la réutilisation d'une valeur d'un autre contexte.

MON/PHASE bascule la polarité de la piste sélectionnée, tous canaux ensemble
(comportement de l'OSC Ardour 8.4). Il attend un état connu ; cette adaptation
logicielle ne commande pas la section audio analogique de la ProControl.

## Vérifications

78 tests passent, dont gain initial 0,75 + deux mouvements 0,01 → 0,77,
réponse retardée, départ absent, NaN, réponse incomplète, changement de banque,
cache de sélection et SEND MUTE. La requête a aussi été vérifiée contre Ardour
actif : piste 2 → `/strip/sends [2]`, aucun départ interne dans cette piste.
Voir send-query-live.json. Aucun gain n'a été modifié par cet essai de lecture.

Sources vérifiées dans le code Ardour 8.4 :
[route_get_sends, route_set_send_fader et select_plugin_parameter](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.cc)
et [retours de sélection](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc_select_observer.cc).

## Déploiement

Version testée préparée sous work/implementation-stage. La bascule ponctuelle
work/deploy_send_update.py demande l'authentification **avant** d'arrêter les
services, remplace les fichiers avec le propriétaire du projet, puis relance le
démon. Le pointeur est relancé ensuite dans l'environnement X11 de l'utilisateur.
L'ancienne version reste active tant que l'authentification n'est pas terminée.

Les tests lumineux des candidats 8 et 40 ont été demandés au démon et acceptés
à 21:59:09/13 et 21:59:21/25, heure de Paris. La correspondance physique attend
la réponse de l'utilisateur : aucune adresse de grand vumètre n'a été enregistrée.

Déploiement effectué à 20:20:51 UTC après correction du chemin absolu du script
pkexec. Le lanceur sans authentification a ensuite été installé et éprouvé ;
voir rootless-launch.md. Les modules de départs/paramètres sont désormais déployés.
