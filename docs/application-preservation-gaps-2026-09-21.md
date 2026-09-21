# Octets encore manquants dans les plages des programmes

Ce relevé initial est complété par la [lecture réelle des 1 768 octets comm](comm-application-complete-2026-09-21.md). Les quatre intervalles fader restent à acquérir.

Calcul du **21 septembre 2026** à partir des quatre segments adressés par
chaque ressource constructeur et des plages additionnées au démarrage.
Ce document décrit une couverture à compléter ; les intervalles ci-dessous
n'ont pas encore été lus sur la console lors de ce relevé.

La [carte statique](preservation-layout-2026-09-21.md) identifie les plages
`comm 0x20000–0x2ffff` et `fader 0x8000–0xbfff`. La ressource constructeur
ne fournit pas tous leurs octets : il manque **1 768 octets comm** et
**4 838 octets fader**. Les vecteurs de démarrage et le reste du bootstrap
constituent encore un périmètre distinct.

| Processeur | Intervalle absent de la ressource, bornes incluses | Octets |
|---|---|---:|
| comm | `0x20008–0x20063` | 92 |
| comm | `0x20080–0x200ff` | 128 |
| comm | `0x20110–0x203ff` | 752 |
| comm | `0x2fce4–0x2ffff` | 796 |
| fader | `0x8008–0x8063` | 92 |
| fader | `0x8080–0x80ff` | 128 |
| fader | `0x8110–0x83ff` | 752 |
| fader | `0xb0e6–0xbfff` | 3 866 |

Vérification arithmétique : `63 768 + 1 768 = 65 536` côté comm ;
`11 546 + 4 838 = 16 384` côté faders. Ces nombres découlent des adresses,
pas d'une hypothèse de remplissage avec `00` ou `ff`.
Le [relevé structuré](application-preservation-gaps-2026-09-21.json) donne
les mêmes intervalles avec borne haute exclusive.

## Prochaine preuve utile

Préparer des plans limités à ces intervalles, puis effectuer deux lectures
distinctes et les reconstruire depuis les captures. Pour les faders, conserver
les contrôles de mode, de file RX et les relâchements vérifiés après chaque
bloc. Une adresse absente de la ressource reste une donnée inconnue, même
si les octets voisins ont tous été vérifiés.

Une fois chaque plage entièrement acquise, recalculer sa somme d'octets
non signés modulo 65 536 et la comparer au mot de contrôle conservé à
`0x30000` pour comm et `0xfffe` pour les faders. Les lecteurs de ces mots
sont décrits dans la [carte statique](preservation-layout-2026-09-21.md).
L'égalité d'une somme de 16 bits ne remplace ni les octets manquants ni
la comparaison exacte des deux acquisitions.

Le contenu des réglages persistants, la RAM de calibration et les vecteurs
du bootstrap auront leurs propres rapports. Une sauvegarde de programme
complète ne suffira pas à déclarer une restauration matérielle éprouvée.
