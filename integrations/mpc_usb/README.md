# Backend USB MPC de la Gateway

Sources de la préparation USB et du routage, auparavant dans le lanceur local
`mpc-one-usb-audio`. La Gateway est maintenant propriétaire de cette
implémentation ; les fichiers privés et dépendances compilées restent dans le
dossier de données existant. Voir [le guide du centre de contrôle](../../docs/studio-control.md).

`studio.py` reçoit `MPC_STUDIO_ROOT`, `MPC_HOST`, `MPC_STUDIO_SESSION` par
l’environnement. `MPC_ARDOUR_BIN` peut remplacer le lanceur installé. Le panneau
web appelle seulement `prepare` et `route`, jamais `start` ou `stop`.

L’expérience HAKAI est réversible et spécifique au matériel/build vérifiés.
Aucun firmware, projet ou mécanisme de démarrage MPC n’est modifié. Les
empreintes de compatibilité sont des gardes, pas une détection universelle.
