# Composants natifs et reconstruction

## Ardour 9.8

Base officielle : `22ed8656c2533e325322ff11831448e5123e0d4b`.
Sur un checkout de travail propre à cette révision, appliquer **dans cet ordre** :

1. [plugin-ui](ardour-9.8-plugin-ui.patch) : ouvrir/fermer les fenêtres depuis OSC.
2. [osc-stability](ardour-9.8-osc-stability.patch) : tableaux de départs et durée de vie des observateurs.
3. [curated-plugins](ardour-9.8-curated-plugins.patch) : identités de pistes et insertion contrôlée des effets.
4. [warm-tape](ardour-9.8-warm-tape.patch) : profils Chaleur, Tube et Tape, validation des contrôles LV2.
5. [jog-pool](ardour-9.8-jog-pool.patch) : pool d’événements, plan JACK et position audible du jog/compteur.
6. [console-state](ardour-9.8-console-state.patch) : retour de lecture seule des états synchro, punch et enregistrement.

Exemple depuis ce checkout Ardour, en remplaçant le chemin de la passerelle :

```sh
bridge_root=/chemin/procontrol-linux
for patch_name in plugin-ui osc-stability curated-plugins warm-tape jog-pool console-state; do
  git apply --check "$bridge_root/native/ardour-9.8-$patch_name.patch" || break
  git apply "$bridge_root/native/ardour-9.8-$patch_name.patch" || break
done
```

Vérifier que les six applications ont réussi avant la compilation. Le build
Ardour doit déjà être configuré avec ses dépendances et son préfixe d’installation.
Les trois cibles modifiées sont :

```sh
python3 waf build --targets=libardour,libardour_cp,libardour_osc -j2
```

Ne pas remplacer une bibliothèque chargée par Ardour. Quitter Ardour proprement,
sauvegarder les anciens binaires, installer les bibliothèques correspondant au
même build, puis relancer. Ne pas appliquer cette série sans adaptation à une
autre version d’Ardour. Les patches ne sont pas une extension chargeable sur un
Ardour standard non recompilé.

Le 20 septembre, les cinq patches ont été appliqués séquentiellement sur la base
propre ; les neuf fichiers obtenus sont identiques aux sources du build local.
[Rapport de revue](../docs/review-2026-09-20.md).

## Tests du pool et de Link

Le test du pool se lie à une bibliothèque Ardour **déjà construite** ; la source
et la bibliothèque doivent correspondre. Il s’exécute dans son propre processus,
sans ouvrir de session ni transmettre de commande à Ardour :

```sh
python3 tools/check_ardour_event_pool.py --source /chemin/source-ardour \
  --library-dir /chemin/installation/lib/ardour9 --output /tmp/test-event-pool
c++ -std=c++17 -Wall -Wextra -Werror native/tests/link-transport.cc -o /tmp/test-link-transport
/tmp/test-link-transport
```

Ces commandes sont à lancer depuis la racine de la passerelle. Le premier test
vérifie 4096 doublons et la récupération complète du pool ; le second vérifie les
transitions de transport, dont 4096 repositionnements JACK en lecture. Les essais
de transport sur copie jetable sont décrits dans le [rapport jog](../docs/jog-link-stability-2026-09-20.md).

## Pont Ardour → Ableton Link

`./link build` compile [ardour_link.cc](ardour_link.cc) avec le SDK officiel épinglé
au commit `902aef95bf94af49746fdda5369b42cdcfa1e6d2`. Il faut Git, C++17 et les
fichiers de développement JACK. Le SDK téléchargé reste dans `work/` et le binaire
dans `build/`. Après une reconstruction, relancer le service pour charger le
nouveau binaire. [Installation et limites de synchronisation](../docs/counter-mpc-sync.md).

La CI compile aussi le pont complet, mais ne démarre ni JACK, ni Link, ni Ardour.
Elle exécute le test de transitions Link ; le test du pool lié à Ardour reste
local, car la bibliothèque patchée n’est pas distribuée dans le dépôt.

## Helper Ethernet

[procontrol-net.c](procontrol-net.c) transmet deux sockets AF_PACKET au daemon.
Il ne lance aucune commande. Son interface est actuellement fixée à `enp0s25`.
La compilation ne nécessite pas de privilège ; l’installation avec CAP_NET_RAW
est décrite dans [le guide dédié](../docs/rootless-launch.md).
