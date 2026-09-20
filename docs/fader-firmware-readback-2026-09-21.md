# Programme fader installé : deux acquisitions complètes

Le **21 septembre 2026**, les quatre segments connus du programme fader 1.37
ont été lus deux fois sur la console. Les **11 546 octets de chaque passe**
sont identiques entre les deux acquisitions et aux ressources constructeur.
L'audit indépendant reconstruit ce résultat depuis les **30 584 captures
Ethernet**, soit **1 345 137 trames** et **1 928 blocs de code**.
Tous les compteurs de pertes socket enregistrés valent zéro.

Le [manifeste de preuves](fader-firmware-readback-2026-09-21.json) conserve
les empreintes, les segments, les sources et l'archive privée correspondante.
Ce rapport complète la [première passe](fader-first-pass-2026-09-21.md),
les [audits partiels](fader-archive-verification.md) et les
[premiers essais de récupération](fader-raw-readback-2026-09-20.md).

## Périmètre et chronologie

| Plage fader, bornes incluses | Octets par passe | Résultat des deux passes |
|---|---:|---|
| `0x8000–0x8007` | 8 | Identiques au constructeur |
| `0x8064–0x807f` | 28 | Identiques au constructeur |
| `0x8100–0x810f` | 16 | Identiques au constructeur |
| `0x8400–0xb0e5` | 11 494 | Identiques au constructeur |

La première requête de bloc date du 20 septembre à 22:21:57,680931 UTC.
La première passe finit à 23:04:24,436404 UTC ; la seconde commence
à 23:04:24,530781 UTC et finit à 23:47:02,858020 UTC. Ces bornes viennent
des captures, et représentent environ 85 minutes pour les deux passes.
La date locale à Paris est alors le 21 septembre.

Le manifeste terminal porte `complete: true`, `passes_equal: true` et
`error: null`. Le collecteur lancé depuis les sources du commit `5c4959d`
a conservé leurs sept empreintes jusqu'à la fin. Les lecteurs préparés
en parallèle n'ont pas changé ces sources pendant l'expérience.

## Vérification indépendante

Le vérificateur relit chaque PCAP clôturé, les ACK, les adresses et les
réponses série reconstituées depuis la RAM RX de comm. Il vérifie les
représentations hexadécimale et brute, les comptes d'enveloppes DigiNet,
la chronologie des blocs, leurs manifests et audits enregistrés, les fichiers
`code.bin`, les huit segments assemblés et les quatre références constructeur.

Chaque bloc conserve la preuve de mode normal, de toucher neutre, de
stabilité du tampon RX et les huit octets de relâchement vérifiés. Les
erreurs du filtre série sont conservées séparément des pertes réseau,
selon la [méthode de neutralisation](fader-touch-recovery-2026-09-21.md).

L'audit final est complet : `complete_archive: true`,
`completed_prefix_only: false`, `passes_equal: true`,
`all_match_reference: true`, `all_socket_drop_counts_zero: true`.
Le SHA-256 de son manifeste figé est
`11278a0c12ff5b3fa140a06452942fb5df2fa7eb7c44f7ea48c9d4584be0c8ca`.
Celui du rapport d'audit complet est
`e02f7d8b65963c7e56a2967e37d73be30a0e948df345a672afd93031f606009b`.

## Conservation et reprise

L'archive privée `procontrol-fader-complete-evidence.tar.gz` regroupe les
captures des deux passes, les résultats et audits, les huit fichiers
reconstruits, les références constructeur, les sources liées à l'acquisition,
un bundle Git et l'observation des services après clôture. Son inventaire
et ses empreintes figurent dans le manifeste public. Les captures et les
binaires constructeur restent hors du dépôt GitHub public.

Les **93 723 membres** de l'archive ont été relus et vérifiés. Sa taille est
65 727 389 octets ; son SHA-256 est
`c02ee710e438e4eb817ef13b9fc5f48fa72d0fe8f327b9129960e3ef80364e28`.
La copie est vérifiée dans
`~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/` ; elle reste
sur le même ordinateur.

Cette copie a été extraite dans un dossier neuf, puis son bundle Git cloné
au commit `613a1e9`. L'auditeur issu de ce clone a reconstruit les huit images
à partir des captures restaurées. Le 20 septembre à **23:51:25 UTC**, son
rapport est identique à l'original, hormis le nom du manifeste figé. La
restitution hors ligne des preuves est ainsi vérifiée ; aucun firmware
n'a été réécrit dans la console.

À **23:47:12 UTC**, le lecteur PID 641580 a disparu ; la passerelle
PID 664715 est réellement Online et le pointeur PID 622060 est vivant,
avec un état Online frais. Le redémarrage de passerelle s'est terminé
avec le code zéro. Cet état décrit cet instant, avant les expériences suivantes.

## Ce qui reste à établir

Cette double acquisition couvre les octets adressés par l'image fader.
Il manque encore **4 838 octets** à l'intérieur de la plage complète du
programme, ainsi que le bootstrap et les autres zones nécessaires à une
préservation de toute l'unité. Voir les
[intervalles manquants exacts](application-preservation-gaps-2026-09-21.md).

La lecture des seuils et de la calibration RAM constitue une campagne
distincte. Cette preuve réseau ne valide ni sensation ou course des moteurs,
ni endurance prolongée, ni restauration matérielle. Les paramètres moteurs
et la calibration n'ont pas été modifiés pendant cette acquisition.
