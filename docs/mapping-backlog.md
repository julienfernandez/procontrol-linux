# Inventaire logiciel des boutons

Généré par `python3 tools/mapping_inventory.py` ; vérifier sans modifier avec `--check`.

La table de référence contient des adresses candidates, pas une liste de boutons physiquement validés.
284 entrées ; 233 prises en charge en mode normal ; 245 dans au moins un mode ; 39 sans gestionnaire.

Modes inspectés : normal, Shift, ALPHA, monitoring, EQ, chaîne de plugins,
bibliothèque, paramètres et NUDGE. Les éditeurs de mode du daemon sont installés
dans un contexte neuf pour chaque touche. Aucun message réseau n’est envoyé.

Dans [le JSON](mapping-coverage.json), `null` signifie sans gestionnaire ; `[]`
signifie touche consommée, éventuellement pour changer un état local ou bloquer
une action inadaptée au mode. Une liste non vide décrit les actions demandées.
`mapped` signifie uniquement qu’un gestionnaire reconnaît la touche dans au
moins un mode : cela ne prouve ni un effet dans Ardour ni une validation physique.

## Adresses sans gestionnaire

| Zone | Code | Libellé tiers | Groupe |
|---|---|---|---|
| 00 | 0b | Peak | Channel 1 |
| 00 | 0c | Source Toggle | Channel 1 |
| 00 | 0d | Roll Off | Channel 1 |
| 01 | 0b | Peak | Channel 2 |
| 01 | 0c | Source Toggle | Channel 2 |
| 01 | 0d | Roll Off | Channel 2 |
| 02 | 0b | Peak | Channel 3 |
| 02 | 0c | Source Toggle | Channel 3 |
| 02 | 0d | Roll Off | Channel 3 |
| 03 | 0b | Peak | Channel 4 |
| 03 | 0c | Source Toggle | Channel 4 |
| 03 | 0d | Roll Off | Channel 4 |
| 04 | 0b | Peak | Channel 5 |
| 04 | 0c | Source Toggle | Channel 5 |
| 04 | 0d | Roll Off | Channel 5 |
| 05 | 0b | Peak | Channel 6 |
| 05 | 0c | Source Toggle | Channel 6 |
| 05 | 0d | Roll Off | Channel 6 |
| 06 | 0b | Peak | Channel 7 |
| 06 | 0c | Source Toggle | Channel 7 |
| 06 | 0d | Roll Off | Channel 7 |
| 07 | 0b | Peak | Channel 8 |
| 07 | 0c | Source Toggle | Channel 8 |
| 07 | 0d | Roll Off | Channel 8 |
| 08 | 0c | Assign | utility_misc_meterselect_automationenable |
| 08 | 13 | Flip | utility_misc_meterselect_automationenable |
| 08 | 15 | auto_suspend | utility_misc_meterselect_automationenable |
| 08 | 16 | display_mode | utility_misc_meterselect_automationenable |
| 08 | 1e | send_lvl | utility_misc_meterselect_automationenable |
| 08 | 20 | send_mute | utility_misc_meterselect_automationenable |
| 08 | 22 | Plugin | utility_misc_meterselect_automationenable |
| 15 | 04 | Create | DSPEdit+Groups |
| 15 | 07 | Select | DSPEdit+Groups |
| 16 | 00 | MixToAux | ControlRoom |
| 16 | 01 | StereoMix | ControlRoom |
| 16 | 02 | SRC1_3-4 | ControlRoom |
| 16 | 03 | SRC2_5-6 | ControlRoom |
| 16 | 04 | SRC3 | ControlRoom |
| 1c | 0c | Talkback | Transport |

Les contrôles analogiques peuvent ne pas émettre en Ethernet. Les encodeurs,
faders et commandes absentes de la table nécessitent un inventaire séparé.
La table tierce ne décrit notamment que la première rangée DSP ; les huit
rangées et les rotatifs ont leurs [captures dédiées](dsp-buttons-2026-09-14.md).
Les cinq touches de navigation autour de ZOOM/SEL restent à identifier
par capture contrôlée ; ne pas leur attribuer des codes d’après leur position.
Le [guide fonctionnel](control-map.md) décrit les usages actuels.
