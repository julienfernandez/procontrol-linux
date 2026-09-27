# Ardour : callbacks OSC périmés — 26 septembre 2026

## Incident et diagnostic

Le coredump Ardour de 12:09:13 montre un SIGSEGV dans
`OSCRouteObserver::send_trim_message()`, appelé depuis un callback PBD mis en
file. L'observateur contient des champs incohérents : `ssid=470519520`,
`_init=32`, et une cible de fonction située dans le tas. Ces éléments sont
compatibles avec l'utilisation d'un observateur déjà détruit.

Les quatre familles d'observateurs OSC raccordaient 103 signaux avec
`MISSING_INVALIDATOR`. Déconnecter leurs signaux empêche de nouvelles
notifications mais n'annule pas celles déjà en attente. Les changements de
piste, de banque ou de plugin peuvent donc laisser en file des appels vers
un objet détruit, ou vers la génération précédente d'un observateur réutilisé.

Le défaut de durée de vie est reproduit de manière déterministe dans le test
natif. Le scénario musical exact précédant le coredump n'est pas reconstitué.
Les erreurs USB/PipeWire voisines dans le journal constituent un autre problème ;
leur causalité avec ce SIGSEGV n'est pas établie.

## Correction

`native/ardour-9.8-osc-callback-lifetime.patch` s'applique après les six patches
existants à Ardour 9.8, base `22ed8656c2533e325322ff11831448e5123e0d4b`.

- Chaque groupe de connexions possède un objet suivi par les invalidateurs PBD.
- `drop_connections()` déconnecte les signaux puis invalide les callbacks en
  attente de ce groupe ; une nouvelle génération peut ensuite être raccordée.
- La destruction des observateurs route, sélection, global et cue utilise
  le même mécanisme. PBD conserve les invalidateurs tant qu'ils sont référencés,
  puis les récupère lors du drainage de sa boucle d'événements.
- `_tick_busy` de l'observateur de piste est initialisé explicitement.

Le traitement utilise le mécanisme existant de PBD. Aucun délai d'attente ni
verrou supplémentaire n'est ajouté au callback audio. Les anciennes corrections
de jog, pool, tableaux de sends et plugins sont conservées.

## Tests natifs et reconstruction

`tools/check_ardour_observer_lifetime.py` compile et exécute le test avec la vraie
`AbstractUI` PBD, ses signaux et ses files. Il ne pilote aucune session musicale.

| File | Témoin ancien : callback périmé exécuté | Notifications valides | Callbacks périmés protégés exécutés | Invalidateurs après drainage |
|---|---:|---:|---:|---:|
| Générique (heap) | 1 | 4096 | 0 | 0 |
| Circulaire temps réel | 1 | 4096 | 0 | 0 |

Chaque cycle vérifie une notification valide, un reset avec callback en attente,
puis une destruction avec callback en attente. Le nettoyage est vérifié après
la fin du lot de dispatch, au passage suivant de la boucle PBD.

Les sept patches sont réappliqués séquentiellement à des fichiers extraits de
la base officielle : les **16 fichiers** obtenus correspondent exactement aux
sources du build. Compilation `libardour_osc` réussie. Le wrapper du test est
également passé avec la bibliothèque PBD installée.

Installation effectuée Ardour arrêté, après sauvegarde du module précédent.
SHA-256 du module installé et du module compilé :
`2f7010b29dd30f26803cce1f5101fc922e508e89ddec9d7313ad70e691b8f2af`.
Ancien module sauvegardé :
`1bc7e98f65bbdaae2bebdebac0e5cbeade56ba145c8fcfd4ed3961cab48bbcce`.

## Essais dans Ardour

Session et configuration utilisateur copiées dans un répertoire de diagnostic
privé ; sorties audio déconnectées dans cette copie. Exécution directe du binaire
pour éviter la préparation MPC du lanceur. Gateway, pointeur, supervision et
Link arrêtés. Le module chargé est vérifié dans les mappings du processus.

Un premier essai combiné a volontairement produit un trafic trop important :
trois clients, reconstruction répétée des surfaces et actions du mixer GUI.
155 488 messages de feedback sont reçus en 16,25 s sur le client GUI ; seuls
120 des 400 accusés de configuration sont reçus dans les délais. Les tests
concurrents de pages et de jog expirent. **Cet essai n'est pas une validation
de fluidité.** Ardour ne plante pas et répond de nouveau normalement après
arrêt des rafales. Cette limite justifie les demandes bornées côté passerelle.

Les essais séquentiels passent :

- Pages OSC : **200 cycles**, 437 933 datagrammes reçus en 78,862 s, réponses
  vérifiées à chaque cycle. 46 threads constants. RSS de 817 048 à 835 708 Kio
  dans les échantillons ; cette courte mesure ne prouve pas une absence de fuite
  sur longue durée.
- Jog vers le début : **2923 commandes en 60,005 s**, lecture initiale et reprise
  vérifiées, puis vitesse finale nulle. Pont Link arrêté.
- Actions de gain depuis le mixer GUI pendant la reconstruction des banques :
  **80 cycles / 160 actions**, **80 réponses sur 80**, 36 786 datagrammes en
  9,715 s ; les gains 0 et -0,1 dB sont observés. Le test utilise le pas de gain
  réel du mixer (0,1 dB). Aucun crash ni blocage.

Les essais sont terminés en arrêt de lecture. La copie est fermée sans
réenregistrer les modifications de test. La session musicale originale et
sa configuration utilisateur restent séparées de ces essais.

## Limites et retour arrière

La MPC n'est pas présente dans ALSA/USB pendant ces essais. La sortie PipeWire
disponible fonctionne à 48 kHz / 512 échantillons ; la session copiée, créée à
44,1 kHz, est chargée avec l'avertissement de conversion. Ces essais ne valident
ni le flux USB 16 canaux, ni la latence aller-retour physique, ni une nuit entière
de fonctionnement. Aucun réglage de priorité, de gouverneur CPU ou de taille de
tampon n'est modifié : les threads audio bénéficient déjà de priorités temps réel.

Les sources d'avant intervention, le module précédent, les journaux et les
copies de session sont gardés dans le dossier privé de dépannage sur le poste.
Pour revenir au module précédent, fermer Ardour puis restaurer uniquement ce
module sauvegardé. Ne pas remplacer une bibliothèque encore chargée.
