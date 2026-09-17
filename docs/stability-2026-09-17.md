# Stabilité Ardour et passerelle — 17 septembre 2026

## Diagnostic confirmé

Les deux coredumps du 17 septembre à 18:27:29 et 18:27:53 (Paris) concernent
Ardour 9.8.0, SIGABRT, `malloc(): unaligned tcache chunk detected`.
La pile de détection traverse `LV2Plugin::get_parameter_descriptor`,
`OSCSelectObserver::plugin_init`, `sel_plug_pagesize`, puis `OSC::set_surface`.
Ce n'est pas la preuve que le greffon LSP corrompt la mémoire : l'allocateur
détecte à cet endroit une corruption antérieure.

La reproduction sur une copie de la session, avec le module OSC **compilé avec
AddressSanitizer**, localise le premier accès invalide :

```text
heap-buffer-overflow
OSCSelectObserver::send_gain                 osc_select_observer.cc:1030
OSCSelectObserver::send_init                 osc_select_observer.cc:405
OSC::sel_send_pagesize -> OSC::set_surface
```

La commande habituelle `/set_surface 0 63 8307 2 8 8 0` demande huit départs.
Sur une piste qui n'en possède aucun, `_last_send` ne contient que l'index zéro,
mais `send_gain(1..8)` accède aux huit autres cases. La boucle des compteurs
temporisés utilise aussi `<= size()` et dépasse le tableau. La trace minimale
est conservée dans [la preuve ASan](ardour-osc-asan-reproduction-2026-09-17.txt).

Le précédent journal du 16 septembre contient un autre défaut : après SIGTERM,
`OSC::stop()` libère les surfaces alors que le thread OSC exécute encore
`get_surface()`. ASan y signale un `heap-use-after-free`. Le précédent simple
préchargement de l'allocateur avait détecté ce cas, sans instrumenter le module.

## Corrections natives

[ardour-9.8-osc-stability.patch](../native/ardour-9.8-osc-stability.patch) :

- Allocation de tous les emplacements de départ avant leur premier retour,
  y compris les cases sans départ ; borne correcte du timer et états initiaux.
- Attente de la fin du thread OSC avant destruction des surfaces et observateurs.
- Un abonnement `DropReferences` par surface sélectionnée, remplacé au changement
  de sélection. Le code précédent ajoutait un abonnement à la liste globale
  à chaque sélection/reconstruction sans enlever le précédent.
- Stockage des surfaces dans une liste stable : ajouter/enlever un client ne
  déplace plus les autres surfaces et ne détruit pas leurs connexions copiées.
  Les observateurs appartiennent à la surface stockée, jamais à une copie locale.
- Libération du nom Lilv renvoyé par `lilv_port_get_name`, anciennement marqué
  `XXX leaks`, et de plusieurs adresses/URL OSC allouées pendant les sélections.

Les fuites sont établies par lecture des allocations et de leur propriété ;
elles ne suffisent pas à attribuer rétrospectivement le blocage de tout le PC.

## Corrections de la passerelle

- Port source OSC fixe `127.0.0.1:3821`, configurable par `--osc-reply-port`.
  Ardour identifie une surface par son adresse de retour : le port ne change
  plus à chaque reconnexion ou redémarrage. Aucun partage du port entre processus.
- Après vingt secondes sans réponse OSC valide, invalidation des commandes en
  attente et reconnexion après cinq secondes, même si UDP ne signale pas d'erreur.
- Une déconnexion en erreur ferme la socket sans envoyer une nouvelle commande
  de configuration à un Ardour qui redémarre.
- L'erreur répétée « Ardour absent » est journalisée au plus une fois par minute
  tant qu'elle ne change pas ; la reprise est explicitement journalisée.
- `status.json` expose RSS, pic RSS, temps CPU et nombre de threads/descripteurs.
  Un événement `health` par minute ajoute les tailles des files et caches aux
  journaux déjà tournants (quatre fichiers de 8 Mio au maximum). Aucun historique
  de mesures ne s'accumule en mémoire.

Avant intervention : passerelle active depuis plus de deux heures, environ
24 Mio RSS, un thread, zéro sortie en attente, aucun événement `fatal` dans
les journaux encore disponibles. Les arrêts conservés portent `error: null`.
Les journaux noyau des deux derniers démarrages ne montrent ni OOM ni processus
tué par manque de mémoire dans la période examinée. Cela ne mesure pas la charge
de la nuit signalée : la cause complète du blocage du PC reste non établie.

## Reconstruction

Base : tag officiel Ardour `9.8`, commit
`22ed8656c2533e325322ff11831448e5123e0d4b`.
Les deux patches appliqués dans cet ordre reproduisent exactement les quatre
fichiers source modifiés sur cette machine :

```bash
git apply /chemin/procontrol-linux/native/ardour-9.8-plugin-ui.patch
git apply /chemin/procontrol-linux/native/ardour-9.8-osc-stability.patch
python3 waf build --targets=libardour_osc -j2
```

Le build doit déjà être configuré avec les dépendances et le préfixe d'installation
adaptés à la machine. La reconstruction met aussi à jour `libardour` pour la
libération du nom Lilv. Installer ces bibliothèques Ardour fermé, en sauvegardant
les précédentes ; ne pas remplacer une bibliothèque en écrasant un fichier mappé
par un Ardour en cours d'exécution. Le patch de stabilité est distinct du suivi
des fenêtres de greffons et ne remplace pas ce dernier.

Pour reproduire le diagnostic, ajouter temporairement `-fsanitize=address` et
`-fno-omit-frame-pointer` à la compilation du module OSC, ainsi que
`-fsanitize=address` à son édition de liens. Le processus hôte doit alors charger
le runtime ASan en premier. **Un simple `LD_PRELOAD` sans cette compilation n'est
pas une instrumentation des accès mémoire du module.** Le reste d'Ardour n'est
pas intégralement instrumenté dans cet essai.

## Validation reproductible

```bash
python3 -m unittest discover -s tests -v
```

179 tests de la passerelle passent, dont cent réouvertures conservant le même
port, refus d'un second propriétaire du port, déconnexion silencieuse et reprise
du véritable processus démon après vingt secondes sans réponse valide.

Sur une **copie jetable** d'une session de huit pistes avec EQ et compresseur,
Ardour déjà chargé et passerelle arrêtée :

```bash
python3 tools/check_ardour_osc.py --cycles 200 --pid PID_ARDOUR --output resultat.json
```

Cet essai change les tailles des pages (0, 1, 8, 16), la sélection et lit les
descripteurs des greffons. Il attend une réponse de configuration à chaque cycle.
Il ne modifie pas les paramètres audio et ne sauvegarde pas la session.
Les résultats de la validation locale sont consignés dans
[stability-validation-2026-09-17.json](stability-validation-2026-09-17.json).

Les essais courts, même instrumentés, ne constituent pas une validation d'une
nuit entière. La télémétrie ajoutée permet désormais de documenter cette durée
sans confondre crash Ardour, arrêt de passerelle et saturation de la machine.

## Reprise de validation et publication — 17 septembre, 21 h 24 Paris

Les modifications avaient été laissées non commitées sur la branche
`fix/ardour-osc-stability`. La reprise vérifie179tests et l'application des deux
patches depuis le tag9.8 : les quatre sources obtenues sont identiques aux
fichiers du build local. Les SHA des deux bibliothèques installées correspondent
au manifest du build corrigé.

Le script de validation de l'autre session a réalisé un démarrage et des
commandes PLAY/STOP, puis envoyé SIGTERM. Il exigeait ensuite le code0, alors
que le processus est sorti avec-15. Cet échec d'assertion ne démontre pas un
nouveau crash ; les trois cycles annoncés n'ont donc pas été achevés.

Ardour relancé une fois normalement, sans préchargement ASan. La passerelle
existante a récupéré automatiquement la session : huit pistes, retours stéréo
et extension de fenêtres présents, sans redémarrage du démon. Ce contrôle
laisse Ardour et les trois services actifs ; aucune lecture ou écriture de
paramètre audio n'a été déclenchée par cette reprise. La validation matérielle
intensive et la stabilité sur une nuit ne sont pas déduites de ce contrôle.
