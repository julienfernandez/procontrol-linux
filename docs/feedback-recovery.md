# Retours console rétablis — 13 septembre 2026

## Cause observée

À 20:26:47 UTC, le retour numéro 859 n'a pas reçu son ACK dans les journaux
conservés. Les ACK 858 puis 860 sont présents. Le statut montrait 836 sorties
et 835 acquittements ; le programme avait enregistré une erreur bloquant
indéfiniment toute sortie. Les commandes vers Ardour et les maintiens Ethernet
continuaient, ce qui expliquait le fonctionnement dans un seul sens.
Voir feedback-failure-evidence.json. La cause de la perte initiale de l'ACK
n'est pas établie ; le blocage permanent était un défaut logiciel certain.

> Historique : les délais décrits ci-dessous sont remplacés le 15 septembre
> par [la reprise à 100 ms et les lots moteurs](jog-motor-scheduling.md).

## Correction

Après deux secondes sans ACK, la file est reconstruite à partir des dernières
valeurs souhaitées et un rafraîchissement OSC est demandé. Une temporisation
progressive de 1, 2, 4, 8 puis 10 secondes limite les tentatives si le problème
persiste. Les nouvelles sorties utilisent de nouveaux compteurs : les vieux ACK
ne valident pas une nouvelle commande. Le premier ACK correspondant rétablit
l'état normal et incrémente le compteur de reprises.

Les valeurs absolues remplacent les anciennes valeurs : aucun ancien mouvement
moteur en attente n'est rejoué aveuglément. Les protections de contact tactile,
de mouvement récent et de tranche inactive restent appliquées. Les maintiens
de session continuent indépendamment des sorties.

Au redémarrage, une annonce e1 désignant explicitement la MAC de ce laptop
permet de rouvrir sa propre session, sous le verrou local exclusif du démon.
Une annonce désignant un autre hôte reste en attente et n'est pas reprise.

La page locale distingue maintenant « Retours actifs », « Reprise des retours »
et « Retours en attente », en plus de l'état d'Ardour et de la connexion console.

## Vérification

85 tests passent. Les nouveaux tests simulent un ACK perdu, un ACK tardif, des
pertes répétées avec temporisation bornée, une valeur actualisée pendant l'attente,
un fader touché et une reprise de session appartenant ou non à ce laptop.

Capture clôturée : 20260913T203252Z-feedback-recovery-3YKbu8, 356 trames,
zéro perte signalée par dumpcap, 356/356 checksums candidats concordants.
Elle couvre la bascule ; la validation finale d'Ardour est postérieure à sa clôture.
SHA-256 : dafc2ccb86966c4be7319a99257831a1b44df8c38a8ac625f83d5bfc3426324e.

État final enregistré dans feedback-recovery-live.json : console Online,
Ardour répond, huit pistes reconnues, stéréo active, 191 sorties et 191 ACK,
aucune erreur et file vide. La reprise après perte est testée automatiquement ;
aucune perte réseau artificielle n'a été injectée sur la console physique.
L'effet visuel précis reste à confirmer par l'utilisateur.

Browser/IAB : la page affiche Console Online, Ardour connecté, Stéréo active
et Retours actifs ; pas d'erreur console. Les gains utilisateur 0,58 (souris)
et 4,65 (jog) ont été conservés. Démon, pointeur et serveur de réglages restent
actifs, sans processus Python root ni nouvelle demande d'authentification.

Confirmation utilisateur après reprise : un crash report Ardour était affiché ;
il confirme ensuite « c'est good ». Cela complète la validation logicielle et
réseau par un retour utilisateur positif, sans attribuer une cause au crash Ardour.
