# Un seul lanceur Ardour — Studio

Le raccourci **Ardour — Studio** sur le Bureau et dans les favoris du menu Mint
ouvre le même parcours. L’identifiant de menu `ardour.desktop` est conservé :
il masque l’entrée de l’ancien Ardour système et garde le favori existant.

1. Démarrer les services Gateway existants, de façon idempotente.
2. Démarrer le pont Link lorsque `launch_link: true` est enregistré dans la
   configuration locale `studio.json`.
3. Si Ardour 9.8 est déjà ouvert, le remettre au premier plan et conserver son
   projet. Aucun deuxième Ardour ni nouveau routage n’est lancé dans ce cas.
4. Sinon, demander la préparation USB à la Gateway, en réutilisant une opération
   déjà en cours. Ouvrir ensuite le projet studio configuré dans Ardour 9.8,
   avec le lanceur installé qui fournit PipeWire/JACK et la latence existante.
5. Vérifier le routage de cette session studio après ouverture. Pour un autre
   fichier de projet passé au lanceur, conserver ses connexions propres.

Si la MPC est éteinte ou indisponible, Ardour peut ouvrir la session ; la Gateway
reste le point de diagnostic et de remise en service. Après un reboot MPC, la
sélection UAC2_Gadget sur son écran reste nécessaire.

Le clic droit sur le raccourci propose **Centre de contrôle Gateway** pour
ouvrir la page de supervision. Les réglages et projets Ardour restent dans
leurs emplacements habituels. Le lanceur ne ferme ni ne sauvegarde de force
une session déjà ouverte.

## Installation et configuration

L’implémentation est `tools/studio_launcher.py`. Elle utilise `studio.json`
(session et dossier de données déjà configurés pour la Gateway). L’option
locale `ardour_launcher` peut préciser le chemin du lanceur Ardour ; par défaut,
`~/.local/opt/ardour-9.8/bin/ardour9`. Le pont Link doit être installé avant
l’activation de `launch_link`.

Les fichiers `.desktop` installés sont propres à la machine. L’entrée du menu
et la copie Bureau doivent contenir la même commande, avec le chemin absolu :

```ini
Exec=/usr/bin/python3 "/chemin/vers/procontrol-linux/tools/studio_launcher.py" %f
StartupWMClass=Ardour
MimeType=application/x-ardour;
```

L’action de contrôle utilise le même script avec `--control`. Un verrou évite
les ouvertures concurrentes pendant un double clic ; le journal est
`run/ardour-studio-launch.log`. La préparation audio n’est pas répétée par le
hook du lanceur Ardour, puisque la Gateway en est responsable.

## Nettoyage local du 20 septembre 2026

Trois anciennes entrées du Bureau ont été archivées : `Ardour 9.8.desktop`,
`ardour.desktop` et `Studio MPC USB.desktop`. L’entrée de menu indépendante
`studio-mpc-usb.desktop` a également été archivée. Le Bureau contient maintenant
un seul raccourci Ardour, et le menu résout un seul `ardour.desktop` visible.
Les autres favoris et les outils ProControl indépendants sont conservés.

Les anciens fichiers et la configuration des favoris sont sauvegardés sous
`~/.local/state/procontrol/launcher-backups/`. Ce dossier, la configuration
personnelle et les fichiers `.desktop` ne sont pas publiés dans le dépôt.

Les cas de nouveau lancement, projet personnalisé, MPC indisponible, opération
Gateway déjà active et Ardour déjà ouvert sont vérifiés par tests logiciels.
Le parcours de l’entrée installée est testé sur le vrai Ardour déjà ouvert ;
un démarrage à froid n’est pas imposé à la session contenant des modifications
non enregistrées.
