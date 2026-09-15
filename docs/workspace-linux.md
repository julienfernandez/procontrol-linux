# Un espace de travail plus fluide

Diagnostic du 13 septembre 2026 : XFCE sur X11 ; Codex CLI embarqué
`0.154.0-alpha.6.2`. Terminal et fichiers accessibles. Contrôle natif des apps
Linux désactivé dans les outils de cette session. Les outils de navigateur sont
distincts du contrôle du bureau.

## Améliorations déjà locales

- `python3 tools/status.py` : interfaces, outils, dernières captures, bilans et
  processus. Aucune authentification ni capture déclenchée.
- `AGENTS.md` : reprendre les fichiers réellement présents, donner un retour
  visible au démarrage effectif et distinguer un blocage d'une capture active.
- `capture.sh` : verrou contre les lancements simultanés du kit sur une même
  interface, sélection de dumpcap quand installé, durée gérée nativement par
  dumpcap. Refus de lancer tcpdump depuis le profil chatgpt affecté par le problème
  d'AppArmor constaté. AppArmor n'a pas été modifié.

## Capture réseau configurée et testée

**dumpcap 4.2.2** est installé avec `cap_net_admin,cap_net_raw=eip` et un accès
par le groupe wireshark. L'ajout de moi à ce groupe a été effectué via
l'authentification système ; `sg wireshark -c 'dumpcap -D'` fonctionne.
Le script utilise dumpcap sans sudo ; son option `-a duration:90` assure la durée
depuis le processus de capture, sans dépendre d'un signal externe de timeout.
Cela n'accorde pas un shell root à Codex. Les droits de capture ainsi configurés
ne sont toutefois pas limités au seul port ProControl.

Cette configuration suit le modèle Debian/Ubuntu référencé dans la
[documentation Wireshark sur les privilèges](https://wiki.wireshark.org/CaptureSetup/CapturePrivileges).
L'app déjà ouverte conserve ses anciens groupes. `sg wireshark` permet d'utiliser
la nouvelle appartenance dès maintenant, sans mot de passe ni redémarrage.
Une prochaine ouverture de session utilisateur la chargera directement.
Les essais matériels de 30 et 60 secondes se sont arrêtés automatiquement,
avec respectivement 4 et 27 paquets, zéro perte signalée et un PCAP valide.

Le kit l'utilise ensuite automatiquement, ou explicitement :

```bash
sg wireshark -c 'PROCONTROL_CAPTURE_BACKEND=dumpcap bash tools/capture.sh enp0s25 idle 30'
```

Référence : [dumpcap et son arrêt par durée](https://www.wireshark.org/docs/man-pages/dumpcap.html).

## Codex ou Hermes ?

Pour ProControl, conserver Codex est une option cohérente : les opérations
principales sont des commandes, des fichiers, du code et des analyses. Le
[terminal intégré](https://learn.chatgpt.com/docs/integrated-terminal) rend les
commandes visibles ; ce n'est pas la même interface que le terminal interne d'un
appel d'outil. Les permissions Linux restent applicables dans les deux cas.

La [documentation Computer Use OpenAI](https://learn.chatgpt.com/docs/computer-use)
énumère macOS et Windows pour le contrôle natif. Elle ne promet pas ici une
parité Linux. Les outils disponibles dans notre session confirment cette limite.

Si « Hermes » désigne **Hermes Agent de Nous Research**, sa
[documentation Computer Use](https://hermes-agent.nousresearch.com/docs/user-guide/features/computer-use/)
décrit un pilote `cua-driver` sous Linux, avec AT-SPI et X11/Wayland. C'est une
piste pour le contrôle graphique ; sa fluidité sur ce ThinkPad n'a pas été
testée. L'installation d'Hermes n'efface pas les permissions réseau du système.
Codex accepte aussi des [serveurs MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) :
une intégration de bureau Linux pourrait être évaluée séparément, sans promettre
qu'elle fonctionne déjà dans cette session. Aucun pilote supplémentaire installé.

La proactivité entre deux interventions peut utiliser des
[tâches planifiées](https://learn.chatgpt.com/docs/automations?surface=app), avec
l'app et le laptop actifs pour les fichiers locaux. Rien n'a été planifié ici :
définir d'abord le déclenchement et les notifications souhaitées, par exemple
analyser les nouveaux PCAP sans lancer de nouvelle capture ni envoyer de trame.
