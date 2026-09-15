# Utilisation continue en arrière-plan

Le mode continu est demandé explicitement par l'utilisateur. `procontrold.py`
réutilise la session Ethernet et le mapping OSC des essais, sans limite de
durée ni arrêt après 2 000 émissions. Le processus est détaché du terminal de
lancement ; finir un échange dans Codex ne l'arrête pas.

Depuis la racine du projet :

```bash
./procontrol start
./procontrol status
./procontrol stop
```

`start` peut ouvrir la fenêtre d'authentification Linux pour les deux sockets
Ethernet. Le lanceur abandonne ensuite root et transmet uniquement les sockets
ouvertes à un processus exécuté comme **moi**. Les capacités de Python et les
politiques AppArmor restent inchangées. `status` et `stop` ne demandent pas de
mot de passe. Un verrou empêche un second lancement de ce démon dans ce projet.

Les commandes actives vers Ardour sont PLAY, STOP, Go To Start, Go To End,
Rewind et Forward. Les autres événements, dont faders et messages inconnus,
sont décodés/journalisés pour préparer la suite. Le compteur de test n'est pas
rafraîchi par ce mode ; la motorisation et le gain des faders restent à intégrer.

## État et journaux

`run/status.json` est mis à jour toutes les deux secondes : état de la console,
PID, compte utilisateur, compteurs Ethernet, réponse d'Ardour et dernière
commande transférée. Le verrou indique si le processus est effectivement actif ;
un ancien fichier d'état ne suffit pas à conclure qu'il tourne encore.

`run/events.jsonl` contient les trames décodées et les actions OSC. Rotation à
8 Mio, trois archives conservées : environ 32 Mio au maximum pour ce journal.
Les erreurs de lancement apparaissent dans `run/launcher.log`.

Ce journal continu n'est pas une capture PCAP. Pour conserver les preuves d'une
expérience, utiliser en parallèle le script de capture passive dumpcap. Ne pas
lancer un second démon `session_probe.py --send` pendant que procontrold tourne.

## Connexions et arrêt

Le maintien est émis toutes les dix secondes, indépendamment des ACK des
gestes. Le démon attend la console si elle est éteinte et rouvre la session
sur une annonce e0 après déconnexion. Une annonce e1 déjà présente au lancement
est laissée expirer : il ne reprend pas automatiquement une session possiblement
détenue par un autre logiciel. La reconnexion est couverte par les tests de
modèle ; les cycles physiques câble/alimentation restent à éprouver.

Ardour reste sur UDP 3819, réponse Auto. Une indisponibilité OSC ne termine pas
la session de la console ; le démon réessaie la connexion OSC. Les commandes
manquées pendant l'absence du DAW ne sont pas rejouées ensuite.

`stop` utilise une socket de contrôle locale privée et laisse le firmware
revenir naturellement Offline après l'arrêt des maintiens. Aucun paquet de
réinitialisation n'est envoyé. Ce premier mode continu n'installe pas encore de
démarrage automatique au boot : après un redémarrage Linux, relancer `start`.

Validation logicielle historique : **45 tests réussis**, dont un worker réellement détaché
testé sur des sockets locales, maintien du verrou après fermeture des descripteurs
du lanceur, transfert PLAY vers un récepteur OSC, arrêt sans root et reconnexion
de modèle après une heure simulée.

Premier lancement matériel continu : 13/09/2026, 17:31:44 UTC, PID 56762,
UID 1000, PPid 1, capacités effectives nulles. État Online et Ardour répondant
observés après la fin du lanceur. La capture indépendante
`20260913T173255Z-trackpad-horizontal-online-vgcJ0Q` contient 2 880 trames,
aucune perte, 13 annonces e1 et aucun e0, avec 1 423 messages de commandes
unicast acquittés pendant les manipulations trackpad/jog. Les neuf maintiens
observés sont acquittés et espacés d'au plus 10,050097 s. Ceci valide ce
premier essai continu chargé ; les cycles physiques de reconnexion restent
à vérifier. Le PID est une observation historique : utiliser `status` pour
connaître le processus actuel.

## Extension déployée à 18:34 UTC le 13/09/2026

Le worker inclut désormais `surface_map.py`, `surface_osc.py` et
`surface_feedback.py`. Le pont X11 inclut `surface_input.py`. Il faut arrêter
les deux services avant d'éditer leurs modules chargés, puis les relancer.

La [carte](control-map.md) détaille les commandes. `status` expose également
ALPHA, le mode encodeurs/jog, la banque estimée, la file de sorties, les ACK
et une éventuelle suspension du feedback. Le journal ajoute `surface_actions`,
`input_events` et `unmapped_surface` pour poursuivre l'identification.

58 tests réussissent, dont le worker réellement détaché avec acquittement des
sorties d'initialisation avant le transfert PLAY. Les entrées ALPHA / pavé /
clics sont également reçues dans un test GTK réel. La fermeture de sa fenêtre
ne termine pas le pont. L'authentification locale n'a lieu qu'au lancement du
démon Ethernet, pas pour chaque commande de console.
