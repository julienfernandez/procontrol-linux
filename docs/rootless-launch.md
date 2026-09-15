# Démarrer et relancer sans authentification

Installé le 13 septembre 2026. Le démon fonctionne avec le compte `moi` (UID
1000) ; Python n'a aucune capability. Seul le binaire court
`/usr/local/libexec/procontrol-net` possède `cap_net_raw=ep`.
Il appartient à `root:moi`, mode 0750 : exécution réservée à root et au groupe moi.

Le lanceur C ouvre deux sockets AF_PACKET liées à `enp0s25` et au protocole
0x885f, les transmet par SCM_RIGHTS au processus appelant, puis quitte. Il ne
lit aucun fichier de configuration, ne lance aucune commande et ne devient
pas root. Le démon conserve les sockets et fonctionne ensuite sans capability.
Le droit accordé permet l'accès Ethernet brut via ces sockets ; ce n'est pas
une élévation générale de Python. Il est réservé à cette interface du laptop.

## Utilisation

```sh
./procontrol start
./procontrol stop
./pointer start
./pointer stop
./settings start
```

Pour une bascule complète : arrêter pointer et procontrol, puis démarrer
procontrol et pointer. Les commandes ordinaires ne demandent plus `pkexec`.
L'installation initiale ou la modification du binaire privilégié nécessitent
encore l'administrateur. Aucun sudo sans mot de passe ni règle polkit générale
n'a été ajouté. En l'absence du lanceur, l'ancien démarrage par pkexec reste disponible.

## Source et reconstruction

Source : `native/procontrol-net.c`. Compilation effectuée avec cc, C11,
`-O2 -Wall -Wextra -Werror -D_FORTIFY_SOURCE=2 -fstack-protector-strong`
et liens `-Wl,-z,relro,-z,now`.
Installer le résultat sous le chemin fixe indiqué, propriétaire root, groupe
local autorisé, mode 0750, puis appliquer `setcap cap_net_raw=ep` au binaire.
Ne pas appliquer de capability à l'interpréteur Python.

## Validation locale

- Démarrage après installation et second cycle arrêt/démarrage exécutés sous
  UID 1000, sans pkexec ; console Online après reconnexion.
- `/proc/<pid>/status` : Uid 1000/1000/1000/1000, CapPrm/CapEff/CapAmb à zéro.
- `getcap` confirme uniquement CAP_NET_RAW sur le lanceur ; aucune sur Python.
- Deux sockets ouvertes sans root, interface enp0s25, EtherType 34911 = 0x885f.
- Tests des refus : autre interface, FD invalide, arguments supplémentaires.
- 81 tests du projet passent, dont les tests de calibration web.

Le serveur web et le pointeur restent des processus utilisateur séparés.
