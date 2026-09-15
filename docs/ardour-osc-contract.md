# Contrat Ardour OSC de la passerelle ProControl

Référence de travail : Ardour8.4 installé, code officiel du tag8.4 vérifié le
14 septembre2026. Le manuel en ligne évolue ; ses exemples ne suffisent pas
à garantir le comportement de cette version. Distinguer commande envoyée,
feedback reçu et validation physique de la console.

## Sources officielles

- [Configuration OSC](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/)
- [Commandes](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/osc-control/)
- [Requêtes, plugins et descripteurs](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/querying-ardour-with-osc/)
- [Retours d'état](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/feedback-in-osc/)
- [Implémentation OSC8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc.cc)
- [Feedback sélection/plugins8.4](https://github.com/Ardour/ardour/blob/8.4/libs/surfaces/osc/osc_select_observer.cc)
- [Déplacements BasicUI8.4](https://github.com/Ardour/ardour/blob/8.4/libs/ctrl-interface/control_protocol/basic_ui.cc)

## Transport et identification

UDP vers127.0.0.1:3819, réponses vers le port source avec le mode Auto choisi
par l'utilisateur. OSC utilise des arguments typés, distincts d'une chaîne
contenant une commande. La passerelle encode int32/float32/string.

Configuration actuelle : `/set_surface 0 63 8307 2 8 8 0`.
Banque Ardour0 (catalogue complet), types63, feedback8307, gainmode2,
8 départs et8 paramètres demandés, linkset0. La banque physique de8 pistes est
locale. Les défauts8.4 de pages et feedback sont détaillés dans l'audit source.

## Commandes utilisées et conventions

| Adresse | Arguments de la passerelle | Sens et précautions |
|---|---|---|
| /transport_play, /transport_stop | float1.0 (sans argument également accepté) | Contrôles de transport ; ne pas les mettre derrière une file longue de jog |
| /transport_speed | Aucun pour lecture | Requête légère d'état, utilisée pour présence et reprise |
| /jog | float delta | Mode0 : déplacement en secondes = delta/5 ; notre sensibilité intervient avant l'envoi |
| /jog/mode | float mode | 0 déplacement,2 scrub,3 shuttle ; ne pas regrouper sans tenir compte du mode |
| /strip/select | int SSID, int0 | Convention locale vérifiée sur8.4 et physiquement ; LED pilotée par le retour |
| /strip/fader | int SSID, float0..1 | Position normalisée ; distincte de la valeur gain en dB |
| /strip/gain/touch | int SSID, int0/1 | Relâchement/contact ; conserve la gestion tactile validée |
| /strip/pan_stereo_position | int SSID, float0..1 | Pan normalisé |
| /strip/sends | int SSID | Lire les départs avant modification ; pas de valeur initiale supposée |
| /strip/send/fader | int SSID, int départ, float0..1 | Niveau normalisé du départ identifié |
| /strip/plugin/list | int SSID | Liste des plugins ; leurs identifiants ne sont pas des numéros de paramètres |
| /strip/plugin/descriptor | int SSID, int pluginID | Descripteurs : noms, bornes, types ; vérifier le format de réponse |
| /select/plugin | float delta, converti en entier | **Navigation relative** dans8.4, pas sélection absolue du plugin numéro delta |
| /select/plug_page | float delta signé | Signe positif/négatif : page suivante/précédente ; pas numéro absolu de page |
| /select/plugin/parameter | int position dans page, float0..1 | Indice1..8 dans notre page ; valeur normalisée via interface_to_internal |
| /select/plugin/activate | float0/1 | Activation du plugin sélectionné ; ne pas confondre bypass d'une bande EQ |
| /select/expand | int0/1 | Sélection développée de la surface ; **n'ouvre pas une fenêtre de plugin** |
| /access_action | string Groupe/action | Action GUI enregistrée par Ardour ; vérifier nom et contexte |

L'adresse /select/plugin relative corrige une ambiguïté de la feuille de route
initiale. Pour sélectionner explicitement un insert, définir un mécanisme dédié
à partir du catalogue/feedback ; ne pas utiliser cet endpoint comme ID absolu.
Les indices des ports LV2 ne sont pas directement les indices OSC de page.

## Catalogue et retours

`/strip` sans argument fournit notre catalogue ; `/set_surface` sans argument
renvoie neuf valeurs de configuration et sert de borne de réponse. Cette
lecture ne doit pas être confondue avec /set_surface muni d'arguments.

Les commandes sont bloquées tant que le nouveau catalogue n'est pas complet.
L'affichage conserve sa dernière vue cohérente pendant cette courte transition.
Les notifications entraînent une requête immédiate, pas une attente de2s.

Feedback plugin : `/select/plugin/name`, `/select/plugin/parameter/name` avec
indice+nom, `/select/plugin/parameter` avec indice+valeur. Invalider les valeurs
lors du changement de piste/plugin/page. Ne jamais appliquer une ancienne
valeur au plugin suivant. Les pages réellement reçues doivent être vérifiées,
à cause du défaut /set_surface de8.4.

## Afficheurs et EQ

Les huit écrans DSP sont confirmés aux adresses Ethernet2D..34 ; molettes4D..54 ;
boutons00/01/02 dans les zones0D..14. Voir les trois relevés DSP et leurs captures.
Ce sont des adresses ProControl, sans relation directe avec les identifiants OSC.

Un écran a un seul propriétaire à un instant donné : nom ou valeur du paramètre.
Prévoir unité réelle, état vide, changement de page et restauration du nom après
réglage. Le premier profil ACE EQ couvre24 paramètres ; il reste proposé,
non relié au feedback. Largeur en octaves, pas Q. Pas d'EQ universel natif8.4
à présumer derrière /select/eq_* : choisir un plugin réel et ses descripteurs.

## Garde-fous issus de nos incidents

- Ne pas réintroduire /refresh ni le catalogue legacy /strip/list périodique.
- Ne pas supposer ACK Ethernet = résultat physique correct.
- Un seul émetteur console ; regroupement des sorties absolues, équité entre
  afficheurs, LEDs et vumètres ; écho tactile immédiat inchangé.
- Commande reconnue, effet Ardour et feedback physique sont trois validations.
- Ne pas recopier un exemple d'une version récente sans contrôler sa signature
  et ses conversions dans la version réellement utilisée.

[Analyse des crashs et patches officiels](ardour-source-audit-2026-09-14.md).
