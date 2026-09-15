# Encodeurs DSP identifiés et raccordés

Capture take2, console Online, Ethernet console → laptop, utilisateur confirme
la séquence du haut vers le bas. 4 542 trames, zéro perte. Le PCAP contient
également un mouvement du fader 2 avant les encodeurs ; les gestes ne sont pas
une séquence strictement isolée. Plusieurs passages successifs 4D..54 rendent
l'ordre identifiable. Sens signé repris du modèle relatif, valeurs 3F/41
observées sur chaque encodeur (−1/+1) ; validation du sens à l'écran reste à faire.

| Molette haut→bas | Code hex | Événements | Première–dernière trame |
|---|---|---|---|
| 1 | 4D | 42 | 1268–2106 |
| 2 | 4E | 41 | 1375–2176 |
| 3 | 4F | 25 | 1610–2256 |
| 4 | 50 | 27 | 1676–2345 |
| 5 | 51 | 27 | 1732–2435 |
| 6 | 52 | 23 | 1784–2517 |
| 7 | 53 | 24 | 1835–2619 |
| 8 | 54 | 56 | 1893–2717 |

SHA-256 original : `c44fae0b17a6ca9cdc65af8bebe63861fab62213b0c0b1d3474d1be29e9db616`.
Preuves : captures/dsp-encoders-take2-20260914/{audit,commands,encoder-summary}.json.

Mapping installé : chaque molette contrôle le paramètre correspondant de la
page du plugin sélectionné, indépendamment du mode pan/send des encodeurs de
tranches. Valeur initiale obligatoire ; pas normal 0,01 et fin avec modificateur
0,002, bornés à 0..1. Les données d'un ancien plugin/piste sont invalidées.
114 tests passent. L'affichage DSP et les boutons de rangée restent à identifier.
Le profil ACE EQ n'est pas encore appliqué : ceci est le contrôle générique.

La relance du démon a été suivie d'un crash Ardour à 21:20:30 Paris (PID30783),
SIGABRT dans allocation mémoire liblo pendant set_surface / OSCSelectObserver.
Voir ardour-crash-dsp-restart-20260914.txt. Cette pile ne prouve pas l'origine
initiale de la corruption mémoire. Ardour a été relancé une fois sur tttt ;
aucune validation réelle de paramètre n'est annoncée à ce stade.
