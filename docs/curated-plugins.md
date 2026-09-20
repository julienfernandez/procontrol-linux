# EQ/DYN automatiques et bibliothèque de console

Mise à jour le 20 septembre 2026. La passerelle utilise une bibliothèque explicite de huit
effets. Elle ne parcourt pas le catalogue VST/LV2 installé pour proposer des ajouts.

## Gestes

- **EQ IN/EDIT** d'une voie : ouvre son LSP EQ x8 ; s'il manque, crée la variante
  mono/stéréo et attend ses descripteurs avant de donner le contrôle aux rotatifs.
- **DYN IN/EDIT** : même principe pour LSP Compressor. L'EQ neuf est plat et
  le compresseur neuf a un ratio de 1:1. Le second appui quitte l'édition.
- **INS/SEND** d'une voie (key `0x01`, zones `0..7`) : ouvre ses effets dans
  **DSP EDIT/ASSIGN** et sélectionne directement cette piste. L'ancien code
  INSERTS `0x0a` reste un alias. Le voyant INS/SEND suit la piste du navigateur.
  Si la
  voie est vide, affiche directement la bibliothèque. Sinon, SELECT sur
  **+ Effet**, ou un nouvel appui INS/SEND, ouvre cette bibliothèque.
- **INSERTS/PARAM** global et **WINDOWS PLUG-IN** : même navigateur pour la voie
  sélectionnée. Depuis une édition, retourne à la liste ; depuis la liste,
  passe à la bibliothèque ; depuis la bibliothèque, revient à la liste.
- Tourner un rotatif DSP ou de tranche déplace le curseur `>` dans la liste.
  **ENTER du pavé numérique** confirme ce choix. **SELECT d'une ligne DSP**
  ouvre directement la ligne correspondante. Le tour seul n'insère rien.
- **OUVRIR** signifie que cet effet est déjà présent ; **AJOUTER** qu'il manque.
  Les boutons ENABLE/BYPASS des lignes agissent seulement sur les effets déjà
  insérés. MASTER BYPASS garde son rôle dans l'édition.
- En édition d'un compresseur ou effet, les huit petits rotatifs DSP et les
  huit rotatifs de tranche règlent la page affichée. Modificateur = pas fin.
  PAGES parcourt les paramètres ; modificateur + PAGES revient en arrière.
- L'EQ conserve son parcours : SELECT choisit une des huit bandes, les rotatifs
  de tranche règlent fréquence/gain/Q/etc., et les rotatifs DSP choisissent le
  type de chaque bande. ESCAPE revient au mixage.

SELECT, Matrix et BANK suivent la famille EQ/compresseur mais **n'ajoutent aucun
effet sur la nouvelle voie**. Appuyer explicitement sur EQ/DYN ou confirmer dans
la bibliothèque pour insérer. Les effets existants hors bibliothèque restent
consultables dans la chaîne de la voie ; ils ne deviennent pas des choix d'ajout.

## Les huit choix

| Choix | Plugin | Première page |
|---|---|---|
| EQ | LSP Parametric Equalizer x8 Mono/Stereo | Profil des huit bandes existant |
| Compresseur | LSP Compressor Mono/Stereo | Seuil, ratio, attaque, release, knee, makeup, wet, sortie |
| Réverb | Dragonfly Room Reverb | Durée, prédélai, taille, niveau réverb, réflexions, direct, coupe-haut, largeur |
| Délai | ZamDelay | Temps, feedback, mélange, filtre, synchro BPM, division, sortie, inversion |
| Phaser | SWH LFO Phaser | Vitesse, profondeur, feedback, étendue |
| Chaleur | SWH Valve saturation | Chaleur, caractère |
| Tube | ZamTube | Drive, niveau, graves, médiums, aigus, modèle, boost |
| Tape | CHOW Tape Model | Wow profondeur/vitesse, flutter profondeur/vitesse, drive, saturation, mélange, sortie |

Voir [Chaleur et Tape](warm-tape-plugins.md) pour les réglages de départ,
les deux pages Tape et la validation des trois ajouts du 20 septembre.

Les profils associent les libellés aux identifiants **réellement renvoyés par
Ardour**, avec bornes et flags. Un profil incomplet interdit les écritures.
Les unités des effets sont explicites : secondes, ms, Hz, %, dB et octaves.
Le délai démarre à 250 ms, feedback 25 %, mélange 20 % ; le phaser à 0,4 Hz,
profondeur 50 %, feedback 20 %. La réverb garde ses valeurs de départ.

LSP, Dragonfly et Zam étaient déjà installés. Le bundle `phasers-swh.lv2` a été
installé dans `~/.lv2` depuis le paquet Ubuntu `swh-lv2`
`1.0.16+git20160519~repack0-4build1`. Seul LFO Phaser entre dans notre bibliothèque.
Ardour adapte les plugins mono sur une voie stéréo par réplication. Les insertions
mono/stéréo ont été vérifiées dans le moteur Dummy ; cela ne valide pas l'écoute.

Sources des effets : [Dragonfly](https://github.com/michaelwillis/dragonfly-reverb),
[SWH LV2](https://github.com/swh/lv2), métadonnées TTL installées et fixtures OSC.

## Extension native

`native/ardour-9.8-curated-plugins.patch` s'applique après les deux patches
`ardour-9.8-plugin-ui.patch` et `ardour-9.8-osc-stability.patch` sur Ardour 9.8.
Ajouter ensuite `native/ardour-9.8-warm-tape.patch` pour les huit effets.
Compilation : `python3 waf build --targets=libardour_osc -j2`.

| Message | Arguments |
|---|---|
| `/procontrol/plugin/version` | Aucun ; réponse entière `2` (`1` pour les cinq effets initiaux) |
| `/procontrol/plugin/ensure` | `ssss` : chemin session, ID route persistant, clé, jeton de requête |
| `/procontrol/plugin/result` | `ssssiis` : mêmes quatre chaînes, résultat, index 1-based, nom |

Clés autorisées : `eq`, `comp`, `reverb`, `delay`, `phaser`, `warm`, `tube`, `tape`.
Les trois dernières demandent la version native 2.
Résultats : `1` réutilisé, `2` créé, `-1` identité refusée, `-2` format/clé non
supporté, `-3` plusieurs instances, `-4` absent du catalogue Ardour, `-5` valeurs
initiales incompatibles, `-6` échec insertion. Master/monitor et voies autres que
mono/stéréo sont refusés. Aucune commande de sauvegarde ou changement du moteur.

La recherche native utilise l'URI LV2, tient compte des deux variantes LSP et
refuse les choix ambigus. Plusieurs instances existantes se choisissent par la
liste de la chaîne. Les ajouts sont pré-fader ; un EQ nouveau se place avant un
compresseur LSP existant. Le jeton est vérifié côté passerelle ; aucune répétition
automatique de mutation après timeout (5 s). Une réponse pendant une mise à jour
du catalogue attend la revalidation de l'identité. Une déconnexion annule l'attente.

L'extension corrige aussi deux déréférencements nuls dans la négociation des
tailles de pages quand le feedback sélectionné est désactivé. Le défaut a été
reproduit dans la session de test avant correction, puis le même handshake sans
feedback a réussi. Aucun changement des files ACK, keepalives ou moteurs.

## Déploiement et validation

Le remplacement d'un module **en place sur son inode chargé** est interdit.
Pour préparer un prochain lancement sans interrompre Ardour, copier le module
vers un fichier temporaire voisin puis effectuer un renommage atomique : le
processus actuel conserve son ancien inode. Le nouveau code s'active au prochain
redémarrage d'Ardour. La passerelle indique `dsp.creation_supported` après
négociation. Si le module actif ne fournit pas encore l'ajout, la console affiche
`RELANCER / ARDOUR / PUIS EQ / OU DYN`. Les états d'attente et d'erreur s'affichent
sur le DSP et les afficheurs de tranche, y compris en mode compresseur.

Validation initiale du 19 septembre : **195 tests Python**, compilation native, dix créations réelles
(cinq effets × deux formats), dix réutilisations, **72 réglages relus par OSC**,
rejets session/route/master/format/clé, fermeture normale de la session de test.
Les snapshots réels servent de fixtures mono et stéréo.
La session de test utilise le moteur Dummy, un port OSC réservé et des réglages
isolés ; le démarrage et les routes de l'utilisateur restent indépendants.
Voir `curated-plugins-validation.json` pour les résultats et SHA.

Activation réelle le 19 septembre : session `studio-mpc-usb` sauvegardée,
Ardour fermé normalement puis relancé avec le même exécutable et environnement
audio. Le nouveau module est chargé et `creation_supported` est vrai.
Le parcours logiciel des boutons EQ/DYN a créé un EQ plat et un compresseur
à ratio 1:1 sur `MPC 01-02`, puis chargé leurs descripteurs. Réouverture et
réutilisation confirmées sans doublon. Aucun geste physique n'a été injecté
sur Ethernet. Voir `plugin-activation-2026-09-19.json`.

Restent à confirmer sur la console physique : affichage du nouveau navigateur,
sens/confort du curseur et audition des effets. Les tests réseau
et les relectures de paramètres ne sont pas une validation visuelle ou sonore.
