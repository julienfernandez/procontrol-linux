# Afficheurs ProControl — validation obtenue

Mise à jour du 20 septembre : [correction du compteur mesures/temps/ticks](counter-mpc-sync.md).
Le dépassement des ticks Ardour à quatre chiffres est corrigé en logiciel ;
la confirmation visuelle de cette correction reste distincte des anciens tests SMPTE.

Le **13 septembre 2026**, après déploiement du feedback continu, l'utilisateur
confirme explicitement : **« Afficheurs et jog fonctionnent tous »**, en réponse
à la question portant sur les noms des tranches, la position du compteur à
huit chiffres et le déplacement du curseur Ardour par le jog.

## Version qui fonctionne

`surface_feedback.py` reçoit les noms, valeurs et positions OSC d'Ardour.
Les noms apparaissent sur la rangée inférieure et les valeurs sur la supérieure.
Le compteur affiche SMPTE ; COUNTER MODE choisit mesures / temps, mode encore
à éprouver séparément. Les sorties sont regroupées et acquittées une à une.

```
Afficheur : f0 13 00 40 ADRESSE 00 [8 caractères ASCII] f7
Compteur  : f0 13 00 30 09 POINTS D8 D7 D6 D5 D4 D3 D2 D1 f7
Mode      : f0 13 00 20 09 20 f7             (SMPTE)
```

Adresses tranches : 00..07 en haut, 20..27 en bas. Les caractères sont ramenés
à l'ASCII et tronqués / complétés à huit positions. Les chiffres sont des
masques sept segments, dans l'ordre inverse de lecture. Points SMPTE = 0x2a.
La commande de mode / LED à l'adresse 09 a été ajoutée à cette version ; elle
était absente des anciens essais. Les essais ne permettent pas d'attribuer
à elle seule la réussite, plusieurs sorties ayant été ajoutées ensemble.

Capture `20260913T183358Z-extended-surface-online-p2Vy6E`, SHA-256
`c3bcb08b7959feb276906b6ede87f66ea6eabe9ab63983ce7701d9f6281bd76c` :
509 trames sans perte ; 80 sorties de feedback et 21 maintiens, tous acquittés.
Afficheur : 26/27 ; valeur : 28/29 ; mode compteur : 58/59 ; chiffres : 60/61.
Les manipulations du jog après la fin du PCAP figurent dans l'instantané du
journal. Voir [le rapport de validation](extended-validation-2026-09-13.json).
Le retour visuel utilisateur complète ces preuves réseau.

## Références et anciens essais

La [capture Pro Tools de l'issue 12](https://github.com/phunkyg/ReaControl24/files/4520019/Ptewlscapture.txt)
donne la famille 40 et les deux rangées de huit caractères.
Le [fork lazlooose](https://github.com/lazlooose/ReaControl24/blob/b23402542cdfdb09fbb44cc3000ecede1103125b/procontrolosc.py#L408)
corrige l'adresse du compteur **et** du mode en 09. Les sources et leur commit
sont conservés dans `vendor/reacontrol24-lazlooose`.

Premier essai, adresse 19 héritée du code commun :
`20260913T170423Z-online-probe-k353ijr6`, trois motifs acquittés, aucun changement
visible confirmé par l'utilisateur. Second essai, adresse 09 mais sans commande
de mode : `20260913T171154Z-online-probe-cej_2q_o`, 37 trames, zéro perte,
10/10 ACK ; l'utilisateur indiquait encore des afficheurs non fonctionnels
avant le déploiement étendu. Conserver ces résultats historiques distincts
de la nouvelle validation.

## Vumètres et autres retours

Le pilote émet aussi LEDs, anneaux de pan, moteur des pistes présentes et
vumètres de référence. **La confirmation des afficheurs ne valide pas les six
grands vumètres.** Leur affectation, segments, crêtes et canaux stéréo restent
à éprouver. Ardour fournit actuellement un niveau scalaire par piste ; l'adresse
8 pour le premier grand vumètre est une hypothèse provisoire.

Le retour moteur est bloqué pendant le contact tactile et 300 ms après le
mouvement. Des ACK sont observés, mais le comportement moteur bidirectionnel
n'a pas encore fait l'objet d'une confirmation utilisateur séparée.
