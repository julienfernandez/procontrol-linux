# ReaControl24 — table ProControl conservée sans modification

Source : https://github.com/phunkyg/ReaControl24
Branche consultée : DEV_OtherDevices.
Commit : `b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069`.

`procontrolmap.py`, `ReaCommon.py`, `procontrolosc.py` et `COPYING.md` sont des
copies identiques aux fichiers de ce commit. Copyright (C) 2018 PhaseWalker,
GPL version 3 ou ultérieure selon
l'en-tête du fichier source. Les mentions d'origine sont conservées.

SHA-256 :

```
5e54cb39368f0e2a09692c2293a11981be08418e6f85de088a447c26bd8ff253  procontrolmap.py
1b3782ccad7b8614100cda30d3faf42fc39f2e97932908c543005053b654ca68  COPYING.md
080137487bdd0ae7f15098fc5ef56bc90017690378298935172b79741e240a5d  ReaCommon.py
caa472cd0af57d098b7d1ad85eedeb5dc591f480d0ac4da5926db07323cb98af  procontrolosc.py
```

`tools/procontrol_mapping.py` adapte en Python 3 le parcours de table et le
découpage de `_ReaOscsession.parsecmd` / `itsplit` dans `ReaCommon.py`, ainsi
que le calcul de position issu de `ReaBase.tenbits`. Il ajoute des contrôles de
longueur et conserve les messages inconnus. Le chargement de la table lit sa
valeur littérale ; il ne lance pas le daemon ni ses dépendances Python 2.

`tools/procontrol_display.py` lit de la même manière les constantes `sevenseg`
et `clockbytes` de `ReaClock`. Il reprend l'ordre inversé de `_xform_txt`, applique
l'octet de famille 00 de `ProCclock`, et borne le premier essai à huit chiffres,
espaces ou tirets, sans points ni commande des LEDs de mode.

Les adresses de cette table sont celles du modèle ReaControl/Reaper. Leur
traduction vers Ardour appartient à notre adaptateur OSC. Elles constituent des
identifications de référence ; elles ne prouvent pas à elles seules le mapping
physique de chaque commande de la console présente.
