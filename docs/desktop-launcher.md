# Lanceur graphique ProControl

Installé sur le bureau sous le nom **ProControl**, ainsi que dans le menu des
applications (catégorie Audio). Un clic selon les préférences du bureau lance
la passerelle Ethernet, le pont souris/clavier et le serveur de réglages, puis
ouvre http://127.0.0.1:8765 dans le navigateur habituel.

Le lanceur utilise le helper CAP_NET_RAW déjà installé : aucun mot de passe
n'est nécessaire. Les services déjà actifs sont conservés ; un verrou empêche
les démarrages simultanés depuis plusieurs clics. Les réglages persistants sont
conservés. Ardour se lance séparément ; la passerelle l'attend s'il est fermé.

Fichiers installés : ~/Bureau/ProControl.desktop et
~/.local/share/applications/procontrol.desktop. Copie dans le projet :
ProControl.desktop. Icône : assets/procontrol.svg. Entrée :
tools/desktop_launcher.py. En cas d'échec, une notification signale le service
concerné ; détails dans run/desktop-launch.log.

Vérification après reboot : trois services démarrés sans élévation, console
Online, serveur HTTP joignable ; second lancement conservant les trois PID.
Raccourci exécutable, marqué trusted et syntaxe desktop-file-validate valide.
Le démarrage reste manuel par le raccourci, sans ajout à l'autostart.

## Redémarrage

Une seconde icône **ProControl — Redémarrer** est disponible sur le bureau.
L’entrée ProControl expose aussi l’action « Redémarrer la passerelle » dans les
menus qui prennent en charge les actions desktop.

Le redémarrage arrête pointer, procontrol et settings, attend leur arrêt réel,
puis les relance dans l’ordre procontrol, pointer, settings et ouvre les réglages.
Le verrou du lanceur couvre toute l’opération. Les réglages sont conservés.

Vérifié : lancement normal conservant les trois PID, redémarrage remplaçant les
trois PID, puis nouveau lancement normal conservant ces nouveaux PID.
