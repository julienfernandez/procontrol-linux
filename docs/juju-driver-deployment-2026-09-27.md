# Juju Driver — déploiement matériel 32×32

Le 27 septembre 2026, le pilote intégré à la MPC en production exposait encore 16 canaux ; l'affectation musicale « Jette toi2 » vers Out 17,18 était correcte. Les pistes Ardour seules ne prouvaient pas le transport des canaux supérieurs.

Un dépôt indépendant **privé**, `julienfernandez/juju-driver`, contient désormais le module USB `juju_driver`, les sources Linux d'origine et leur provenance, les modifications 32 canaux, l'installateur et la procédure de validation. Le périphérique visible est nommé **Juju Driver** ; les chemins configfs restent des détails techniques.

Le module initial SHA-256 `2bfe4308b76f8737cc134147640900b593acb3717931bbe17c71169387ceb27f` compile pour `6.18.26-az01-2026-04-30-rt4 SMP preempt_rt ARMv7 p2v8` et se charge sur la MPC. LoadPin refuse `/tmp`, mais accepte le fichier installé dans le répertoire normal des modules sur la partition système. La protection n'a pas été désactivée ; la partition a été remise en lecture seule. Une instance configfs isolée a accepté puis relu les compteurs explicites 32/32 avec masques nuls avant suppression.

Côté PC, `mpc_channels.py`, `studio_control.py` et le backend `integrations/mpc_usb/studio.py` acceptent l'identité Juju, détectent les vrais ports AUX0–31, maintiennent le duplex et raccordent les 16 paires stéréo. Le mode historique 16 canaux reste reconnu. La visibilité de Juju ne nécessite pas la modification en mémoire du nom UAC2 de l'application MPC. Les tests ciblés passent : 61 tests au stade de préparation.

Les preuves privées et sauvegardes avant modification se trouvent dans le dossier frère `juju-driver-work/evidence/`. Les projets, captures et configurations privées ne sont pas publiés dans le dépôt du pilote. Ardour est resté ouvert (PID 173019). Le démon ProControl observé est vivant et répond à Ardour ; sa boucle Ethernet n'a pas été arrêtée pour ces changements.

## État après bascule, à 18 h 53 Paris

Juju Driver est actif en production : USB High Speed, PCM signé 16 bits, 44 100 Hz, **32 entrées et 32 sorties**. L'application MPC 3.9.1 ouvre les deux PCM à une période de **128 échantillons, tampon 512**. La carte ALSA interne s'appelle `JujuDriver`, et son nom visible est `Juju Driver 0`. L'ancien UAC2 16 canaux a été retiré de configfs après fermeture de ses clients.

Le banc physique a transmis simultanément 32 fréquences distinctes par sens. Les 32 identités correspondent sans permutation : MPC → PC, 12 secondes acquises et 9 fenêtres centrales validées ; PC → MPC, 10 secondes et 7 fenêtres validées. La fuite maximale mesurée entre signatures est inférieure à 0,0026 %. Aucun xrun n'est signalé dans les journaux ALSA de cet essai court. Les résultats numériques sans contenu musical sont publiés dans le dépôt privé du pilote.

Les 32 entrées AUX0–AUX31 sont connectées aux seize paires Ardour ; les 32 références externes Juju ont été relues dans le XML sauvegardé. Ardour est resté ouvert avec le PID 173019. Le Master conserve ses deux connexions Behringer et aucune autre destination. Le contrôle `/api/studio` indique tous les composants fonctionnels, `pcm_running=true`, 32/32 dans les deux maintiens, 32/32 vers les pistes et `automatic=true`. Les 61 tests ciblés passent après prise en compte de la configuration de production 32 canaux dans les fixtures.

Le service `juju-driver.service` est activé avant `acvs.service`. Le script persistant configure aussi l'identifiant ALSA et la période 128 pour la version précisément identifiée du preload HAKAI. Le module et les scripts sont installés sur la partition système ; LoadPin est toujours actif et la racine a été remise en lecture seule. Le démarrage électrique complet n'a pas été essayé pendant le projet ouvert.

## Crash et espace temporaire : deux problèmes distincts

Le crash utilisateur de 18 h 35 se produit dans le thread `Audio Processin`, juste après passage de l'ancien USB 16 canaux (période 128) vers Internal (192). Aucun OOM n'apparaît dans le journal noyau. Une ouverture Juju 32×32 à 192 reproduit le SIGSEGV même sans projet chargé, alors que les utilitaires ALSA seuls fonctionnent à cette période. La pile de l'application propriétaire n'est pas symbolisée : le contournement du déclencheur est vérifié, pas une correction de son code source.

Le preload HAKAI accepte 64, 96, 128 et 192 ; une demande de 256 est ramenée à 128. Le réglage a donc été fixé explicitement à 128. L'application PID 29579, démarrée à 18 h 42 min 56, a chargé Wonderland et reste active sans redémarrage au contrôle de 18 h 53. Une lecture musicale courte a été capturée sur la paire 7–8 ; l'écoute humaine de « Jette toi 2 » sur 17–18 reste à confirmer séparément du test matériel des 32 canaux.

L'alerte visible est **Disk Space Low / Low on temporary space**. Le volume interne `/storage` dispose de 744 Mio, tandis que la SD exFAT dispose de 29,4 Gio. La RAM disponible après chargement de Wonderland est d'environ 560 Mio. Le projet Wonderland est déjà sur la SD. La préférence `temporaryFileLocation` a été préparée vers un dossier SD mais les descripteurs ouverts montrent encore l'ancien dossier interne : le choix dans l'interface reste à terminer, et ne doit pas être présenté comme appliqué.

Une archive locale complète du Wonderland sauvegardé avant bascule a été conservée, ainsi que les préférences, journaux et mesures dans `../juju-driver-work/incident-20260927-1838/`. Les fichiers de mesure temporaires créés par nos outils sur la MPC ont été rapatriés et retirés ; aucun média utilisateur n'a été supprimé.

## Livraison et limites

Dépôt privé : <https://github.com/julienfernandez/juju-driver>. Commit de validation `b702698249cf23834d8128a4c375bd257a88a2f6`, CI réussie : <https://github.com/julienfernandez/juju-driver/actions/runs/36334676576>. Le SHA distant et le caractère privé du dépôt ont été relus.

Restent distincts des résultats établis : sélection effective du stockage temporaire dans l'interface, écoute de 17–18, endurance de plusieurs heures et démarrage électrique complet. Aucun transport audio Ethernet 32 canaux n'a été installé ; le service réseau existant gère le MIDI.

## Suite finalisée à 21 h 55 Paris : SD et démarrage automatique

Cette section remplace les réserves précédentes sur le stockage temporaire et le redémarrage logiciel. La préférence SD, même choisie dans l'interface puis suivie d'un rechargement et d'un redémarrage de l'application, laissait les fichiers temporaires sur `/storage`. Le service optionnel `juju-temp-storage` monte maintenant le dossier SD sur le chemin réellement utilisé par MPC. Dix-huit descripteurs temporaires ont été observés sur le périphérique SD. Après le dernier redémarrage, les deux chemins ont les mêmes périphérique/inode ; `df` indique **29,4 Gio disponibles** et l'alerte n'est plus affichée. Aucun sample ou projet utilisateur n'a été supprimé.

La SD est identifiée par son UUID configuré. Le script refuse une autre carte, un montage incompatible ou un dossier temporaire interne contenant encore des fichiers de récupération. Sur ce système, BusyBox `blkid` ne reconnaît pas exFAT : le contrôle utilise les propriétés `udevadm`. Si nécessaire, la carte vérifiée est montée avant le lancement de MPC ; attendre le montage habituel par l'application créait une dépendance circulaire.

Les essais de démarrage ont aussi révélé que les liens `systemctl enable` dans l'overlay tardif `/etc` n'entraient pas dans le graphe initial de démarrage. `set-boot-mpc-one` installe les dépendances dans la partition système précoce et remet la racine en lecture seule. Au dernier **redémarrage complet par logiciel**, avec la supervision PC active, Juju Driver et le stockage SD démarrent automatiquement avant `acvs`. Boot `470893df-f929-4465-bf15-2c26bafacbb5` : application PID 366, `NRestarts=0`, les deux PCM ouverts en **32 canaux, 44,1 kHz, S16_LE, période 128, tampon 512**. Il ne s'agit pas d'un essai par coupure électrique ni d'une validation sans PC connecté.

Wonderland est chargé. Une capture musicale après ce dernier démarrage reçoit les canaux 1–26, notamment **17 = 0,20413 et 18 = 0,18820 en crête linéaire**. Les 27–32 sont silencieux dans cette lecture du projet ; leur transport a été vérifié séparément par les 32 signatures du banc duplex. La lecture de test a été arrêtée par MMC. L'application précédente avait tenu environ 2 h 48 sans redémarrage, ce qui ne constitue pas une endurance audio continue. Le relevé final conserve aussi trois changements d'ouverture PCM observés par la supervision : aucune affirmation de continuité parfaite n'en est déduite.

## Incident Ardour découvert pendant les essais et récupération

Le retrait USB du premier redémarrage a fait terminer Ardour PID 173019 à 21 h 35 min 44. Le core montre une conversion d'un nom JACK nul en `std::string` dans `JACKAudioBackend::connect_callback`, ligne 347 de la source de base. Le [patch JACK](../native/ardour-9.8-jack-port-removal.patch) protège les deux recherches de ports et les deux noms. Le test compile le corps réel du callback avec des objets JACK simulés : l'ancien code reproduit l'exception, le nouveau passe. Il ne remplace pas un essai matériel d'endurance ni une instrumentation ASan.

Seul `jack_audiobackend` a été reconstruit. L'ancien binaire a été sauvegardé et remplacé pendant qu'Ardour était fermé. Le backend actif a pour SHA-256 `526d4973113bb9c86c99d64f19a975d336edf9eacbb8ce2c22d9b42234c1b937`. Ardour PID 272570 a récupéré le fichier `.pending` de 21 h 35 du projet `studio-mpc-usb-jette-toi`, puis la session a été sauvegardée. Les 32 identités de routes et les 273 identités de processeurs correspondent à la récupération ; ces processeurs incluent les composants internes, pas seulement les plugins.

Le graphe final indique 32/32 entrées raccordées, maintien duplex 32/32 et Master vers les deux sorties Behringer. ProControl reste actif. Deux connexions de vumètre interne inutilisées sont signalées ; la protection de routage du projet utilisateur, distinct du projet par défaut, est conservée. Les choix de mixage récupérés sont également conservés : MPC 17–18 en écoute disque et MPC 19–20 en solo. La présence du signal USB ne prouve donc pas à elle seule son écoute dans ce mixage.

## Sauvegardes et publication finale

Les preuves restent privées dans `../juju-driver-work/storage-20260927-2125/`, notamment `production-final.txt`, `studio-final.json`, les mesures musicales et les copies de session avant récupération. L'archive `Wonderland-before-temp-reload.tar` contient 98 670 080 octets, SHA-256 `e52219bcf70d44e874c65f9be27645329d4b0ca933790621b5ae9da474a00a2d`.

Le dépôt [Juju Driver](https://github.com/julienfernandez/juju-driver) reste **privé**. Commit distant vérifié `88831d364d7bdbbaa6dcf922bd4d213023885b9c`, [CI réussie](https://github.com/julienfernandez/juju-driver/actions/runs/36345720892). Il contient les scripts de démarrage et de stockage, le patch hôte et leurs procédures, sans projet ni capture musicale utilisateur.
