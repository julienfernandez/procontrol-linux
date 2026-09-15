# Adresses de boutons restant sans action

Inventaire de la table de référence, pas un comptage de boutons physiques validés.
284 entrées ; 228 ont une action en mode normal ; 56 restent sans action.

| Zone | Code | Libellé tiers | Groupe |
|---|---|---|---|
| 00 | 04 | pre_post_assign_mute | Channel 1 |
| 00 | 0b | Peak | Channel 1 |
| 00 | 0c | Source Toggle | Channel 1 |
| 00 | 0d | Roll Off | Channel 1 |
| 01 | 04 | pre_post_assign_mute | Channel 2 |
| 01 | 0b | Peak | Channel 2 |
| 01 | 0c | Source Toggle | Channel 2 |
| 01 | 0d | Roll Off | Channel 2 |
| 02 | 04 | pre_post_assign_mute | Channel 3 |
| 02 | 0b | Peak | Channel 3 |
| 02 | 0c | Source Toggle | Channel 3 |
| 02 | 0d | Roll Off | Channel 3 |
| 03 | 04 | pre_post_assign_mute | Channel 4 |
| 03 | 0b | Peak | Channel 4 |
| 03 | 0c | Source Toggle | Channel 4 |
| 03 | 0d | Roll Off | Channel 4 |
| 04 | 04 | pre_post_assign_mute | Channel 5 |
| 04 | 0b | Peak | Channel 5 |
| 04 | 0c | Source Toggle | Channel 5 |
| 04 | 0d | Roll Off | Channel 5 |
| 05 | 04 | pre_post_assign_mute | Channel 6 |
| 05 | 0b | Peak | Channel 6 |
| 05 | 0c | Source Toggle | Channel 6 |
| 05 | 0d | Roll Off | Channel 6 |
| 06 | 04 | pre_post_assign_mute | Channel 7 |
| 06 | 0b | Peak | Channel 7 |
| 06 | 0c | Source Toggle | Channel 7 |
| 06 | 0d | Roll Off | Channel 7 |
| 07 | 04 | pre_post_assign_mute | Channel 8 |
| 07 | 0b | Peak | Channel 8 |
| 07 | 0c | Source Toggle | Channel 8 |
| 07 | 0d | Roll Off | Channel 8 |
| 08 | 07 | default | utility_misc_meterselect_automationenable |
| 08 | 0a | Input | utility_misc_meterselect_automationenable |
| 08 | 0b | Output | utility_misc_meterselect_automationenable |
| 08 | 0c | Assign | utility_misc_meterselect_automationenable |
| 08 | 13 | Flip | utility_misc_meterselect_automationenable |
| 08 | 15 | auto_suspend | utility_misc_meterselect_automationenable |
| 08 | 16 | display_mode | utility_misc_meterselect_automationenable |
| 08 | 1e | send_lvl | utility_misc_meterselect_automationenable |
| 08 | 20 | send_mute | utility_misc_meterselect_automationenable |
| 08 | 22 | Plugin | utility_misc_meterselect_automationenable |
| 0d | 00 | select_auto | DSPEdit1 |
| 0d | 01 | assign_enable | DSPEdit1 |
| 0d | 02 | bypass_in_out | DSPEdit1 |
| 15 | 04 | Create | DSPEdit+Groups |
| 15 | 07 | Select | DSPEdit+Groups |
| 16 | 00 | MixToAux | ControlRoom |
| 16 | 01 | StereoMix | ControlRoom |
| 16 | 02 | SRC1_3-4 | ControlRoom |
| 16 | 03 | SRC2_5-6 | ControlRoom |
| 16 | 04 | SRC3 | ControlRoom |
| 19 | 03 | Trans | Window+ZoomPresets+Navigation |
| 1c | 04 | Post Roll | Transport |
| 1c | 0a | Loop Record | Transport |
| 1c | 0c | Talkback | Transport |

Les contrôles analogiques peuvent ne pas émettre en Ethernet. Les encodeurs,
faders et commandes absentes de la table nécessitent un inventaire séparé.
Une adaptation expérimentale existante compte comme action, pas comme validation.
Ne pas attribuer arbitrairement des codes aux huit encodeurs DSP ou aux flèches.
