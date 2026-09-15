# Greffons libres — sélection du14 septembre2026

Recherche pour Ardour9.8 / ThinkPadX230 / ProControl. Installation réalisée le 14 septembre 2026.

## Priorité

1. LSP Plugins LV2 : EQ paramétrique x8 mono/stéréo, compresseur, gate, de-esser,
   limiteur. Base proposée pour les profils DSP de console. Évaluer charge réelle.
   https://lsp-plug.in/ ; https://lsp-plug.in/?page=manuals
2. Dragonfly Reverb : Room/Hall/Plate/Early, GPL3, Linux/LV2.
   https://github.com/michaelwillis/dragonfly-reverb
3. x42 : EQ et outils de mesure/utilitaires, GPL2+. Certains binaires du site sont
   commerciaux avec interface en démo ; préférer les paquets de distribution ou
   une compilation libre, et vérifier quels greffons le paquet fournit.
   https://x42-plugins.com/x42/faq ; https://www.x42-plugins.com/x42/x42-eq
4. ZamAudio : collection GPL2 LV2, effets et dynamique comme alternative.
   https://github.com/zamaudio/zam-plugins
5. Surge XT : synthétiseur GPL3, LinuxVST3/CLAP, candidat instruments ultérieur.
   https://surge-synthesizer.github.io/faq/

## État local vérifié

Paquets installés et vérifiés avec dpkg :

- lsp-plugins-lv2 1.2.14-1
- x42-plugins 20230915+ds-1build2
- zam-plugins 4.2+ds-1build1
- dragonfly-reverb-lv2 3.2.10-3build1
- surge-xt 1.3.4, paquet officiel GitHub releases-xt.

Ardour a été relancé après la découverte : avant le redémarrage, les nouvelles
entrées figuraient au catalogue mais leur chargement Lua retournait nil.
Après redémarrage, les 16 instances LSP ont été chargées et sauvegardées.
Les autres collections sont installées, sans validation audio instance par instance.

## Chaîne de départ dans tttt

Les huit pistes audio sont stéréo : chacune reçoit LSP Parametric Equalizer x8
Stereo puis LSP Compressor Stereo. Master inchangé.
EQ : huit Bell, 60/120/250/500/1000/2000/4000/8000 Hz, gains 0 dB.
Compresseur : ratio 1:1. Paramètres contrôlés dans le XML sauvegardé.
Charge DSP affichée au repos environ 11–13 %, sans mesure de charge en lecture.

Script réutilisable : `ardour/procontrol_add_eq_compressor.lua`, également installé
comme EditorAction dans `~/.config/ardour9/scripts/`. Il complète les pistes audio
mono/stéréo sans doubler les URI déjà présentes ; deuxième exécution : 0 ajout.
Cela ne crée pas encore un hook automatique pour toute nouvelle piste.
Sauvegarde préalable : `backups/before-default-dsp-20260914T233610`.
Preuve : `installed-dsp-chains.json`.

## Intégration ProControl

Choisir un EQ et un compresseur de référence avant extension. Préférence LV2 :
ports/identifiants/unités et plages inspectables dans les métadonnées.
Le contrôle passe toujours par Ardour OSC ; un LV2 n'est pas nativement piloté par OSC.
Ne pas promettre toutes les fonctions GUI exposées. Valider ports scalaires, conversions
normalisées/logarithmiques, valeurs initiales, pagination et bypass.
Les huit encodeurs DSP commandent huit paramètres par page, pas automatiquement huit bandes.
Mono pour voie mono ; stéréo pour voie stéréo ; variantesLR/MS seulement pour usage voulu.
