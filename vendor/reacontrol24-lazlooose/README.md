# Correction ProControl du fork lazlooose

Fichier `procontrolosc.py` copié sans modification depuis :
https://github.com/lazlooose/ReaControl24/blob/b23402542cdfdb09fbb44cc3000ecede1103125b/procontrolosc.py

Commit du 24 avril 2020 : `b23402542cdfdb09fbb44cc3000ecede1103125b`.
SHA-256 : `7f4bac5d7919cc0cb515127e204e087405ffd2b1ce636470b3c6dbf8c5ef37f5`.
Les mentions d'origine PhaseWalker et GPLv3 ou ultérieure sont conservées.
Le texte de licence figure aussi dans [COPYING.md](../reacontrol24/COPYING.md).

Ce fork est lié par l'utilisateur ayant rapporté le fonctionnement de sa
ProControl dans les issues du projet. Dans `C24clock`, les lignes 408–410
changent explicitement l'adresse de compteur **0x19 en 0x09**, en plus de la
famille **00**. La branche phunkyg DEV_OtherDevices consultée ne conserve que
le changement de famille ; notre premier essai à l'adresse 19 n'a pas affiché
les chiffres, malgré des ACK Ethernet.

`tools/procontrol_display.py` lit uniquement les constantes littérales de
`C24clock`, sans importer ni exécuter ce client Python 2/Reaper. L'adaptateur
conserve les caractères et l'ordre des octets du code d'origine.
