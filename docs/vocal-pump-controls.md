# Voix, harmonies et pumping — commandes ProControl

Le catalogue reste limité à quatorze effets choisis. Utiliser **INSERTS/PARAM → + Effet**, sélectionner le choix puis confirmer pour insérer. Une seconde action sur le même choix reprend le processeur existant. **DYN** conserve le compresseur LSP habituel. Les effets ajoutés ici nécessitent la capacité native OSC **3** ; un ancien module garde les choix de sa version.

Les rotatifs de paramètres et les changements de page fonctionnent comme dans la bibliothèque existante ; le modificateur de précision affine les pas. Les bornes proviennent des descripteurs renvoyés par Ardour.

| Choix | Première page, rotatifs 1 à 8 | Suite / remarque |
|---|---|---|
| Autotune | Quantité, suivi, biais, décalage, accord A, mode, Fast Correction, étendue pitch bend | Notes de la gamme et MIDI dans l’interface. Fast Correction est un compromis de latence, pas le réglage de lissage. |
| Harmonie | Demi-tons, cents, octaves, part directe, formants, texture | 0 % de part directe = tout traité. Le niveau du retour se règle au fader. |
| Sidechain | Seuil, ratio, attaque, relâchement, coude, compensation, gain traité, sortie | Gains linéaires du plugin présentés et incrémentés en dB. Entrée externe dans le routage Ardour. |
| Pump LFO | Mélange, durée, unité, lissage, profondeur de forme 1, sortie | Dessin de la courbe dans B.Shapr. Durée 1 + unité Beats = un temps. |
| Attaques | Attaque bande 1, relâchement bande 1, expansion, gain maximum, seuil, sortie bande 1, direct, traité | Autres bandes et filtres dans LSP. Insertion initialement désactivée. |
| Vocodeur | Entrée, gate, suivi d’enveloppe, Q, bandes, fréquence basse, fréquence haute, mélange | Page 2 : entrée modulateur, étendue, centre. Les valeurs Surge sont normalisées en %, selon son interface VST3. |

Le profil Surge exige les noms de paramètres propres au vocodeur. Si l’effet est changé dans sa fenêtre, le profil devient incomplet et la passerelle bloque les écritures après le nouveau relevé. Elle ne présente pas les paramètres d’un délai ou d’une réverbération comme des réglages vocaux. Le type d’effet lui-même n’est pas sur ces pages.

## Chaînes préparées

- `VOIX A`, `VOIX B` : x42 avant les départs vers les harmonies et le modulateur. Entrées en attente de repérage.
- `HARM A/B Quinte +7`, `HARM A/B Octave -12` : retours à −18 dB, muets et pitch shifter désactivé au départ.
- `VOC ACCORDS` : Surge XT reçoit les notes MIDI et sort exclusivement dans `VOCODEUR`. `VOC MOD` reçoit les départs des deux voix et sort exclusivement vers le sidechain de Surge XT Effects.
- `KICK` → départ après traitements et avant fader → `KICK SC` → détecteur externe de `PUMP`. `KICK SC` n’est pas audible dans le Master. Le kick ne passe pas dans le bus PUMP.
- `PUMP` : compresseur sidechain puis B.Shapr, à comparer séparément. L’entrée basse reste à affecter.

Tous les nouveaux traitements sont désactivés tant que les sources ne sont pas affectées. Les presets sont chargés et restent modifiables. Activer seulement le traitement désiré, puis comparer à niveau égal. Le monitoring du clavier `VOC ACCORDS` et son port MIDI devront être affectés avec la source retenue.

B.Shapr transmet sa courbe à l'interface pendant son traitement DSP. Si la fenêtre affiche seulement les limites alors que le plugin est désactivé, l'activer sur un bus silencieux permet de vérifier la courbe chargée, puis le désactiver à nouveau. La courbe du preset « Pump 1 temps » a été vérifiée ainsi après rechargement.

## Latence et écoute

x42 a déclaré 1056 échantillons à 44,1 kHz, environ 24 ms, dans le test isolé. Rubber Band classique et Beat Breather peuvent introduire des délais importants ; leurs retours sont préparés désactivés. Le délai audio total inclut aussi les tampons et le matériel : l’acceptabilité musicale n’est pas établie par le chargement d’un plugin.

L’écoute reste nécessaire pour la tonalité, la quantité de correction, les accords MIDI, la réduction réelle du sidechain et le retour de la basse entre deux kicks.
