# Presets voix et pumping

Créés le 27 septembre 2026 avec les versions installées : x42/fat1 (paquet x42-plugins 20230915), Rubber Band LV2 3.3.0, B.Shapr 0.13, LSP 1.2.14 et Surge XT 1.3.4. Ces fichiers sont des réglages, pas les plugins.

- **Voix discrète chromatique** : correction 65 %, filtre 0,1.
- **Voix robot chromatique** : correction 100 %, filtre 0,02. Les douze notes restent permises tant que la tonalité n’est pas confirmée.
- **Quinte +7 / Octave -12** : transposition fixe, préservation des formants, sortie entièrement traitée. Le réglage Rubber Band « Wet-Dry Mix » vaut 0 pour tout traité et 1 pour tout direct.
- **Pump kick externe** : sidechain externe, ratio 4:1, attaque 2 ms, relâchement 180 ms, seuil initial −12 dBFS, compensation 0 dB. Ajuster le seuil sur le kick réel pour viser 3–6 dB de réduction ; ce preset seul ne garantit pas cette réduction.
- **Pump 1 temps** : B.Shapr, base en temps, durée 1, mélange 50 %, lissage 20 ms. La courbe passe par 5 % au départ, reste basse jusqu’à 12 % du temps, remonte vers 85 % à 55 %, puis 100 % ; retour lissé au creux en fin de cycle.
- **Transitoires neutres** : direct 1, traité 0. La préparation garde aussi le processeur désactivé pour éviter sa latence tant qu’il n’est pas utilisé.
- **Vocodeur 20 bandes** : Surge XT Effects VST3, type Vocoder, modulation mono, mélange traité 100 %. La voix arrive dans le sidechain ; un synthétiseur piloté en MIDI fournit le porteur sur l’entrée principale.

## Installation

Copier chaque sous-dossier de `lv2/` dans `~/.lv2/`, et le contenu de `vst3/` dans `~/.vst3/presets/`. Conserver toute version personnelle existante avant remplacement. Relancer le scan des plugins ou Ardour si nécessaire. Le preset Surge porte exactement le nom **ProControl - Vocodeur 20 bandes** : l’insertion native le demande et refuse son absence. Les variantes Rubber Band sélectionnées sont les versions classiques mono/stéréo. Le paquet Ubuntu local annonce aussi R3 dans son manifeste, mais le binaire testé ne les exporte pas.

Voir le [rapport de préparation](../../docs/studio-vocal-pump-2026-09-27.md) et la [fiche console](../../docs/vocal-pump-controls.md).
