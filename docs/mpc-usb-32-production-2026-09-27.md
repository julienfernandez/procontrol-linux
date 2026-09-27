# MPC USB : diagnostic des canaux 17–32 et déploiement PC

Le 27 septembre 2026, l'utilisateur signale que la dernière paire reçue est
15–16 et demande l'activation immédiate des 32 entrées/sorties. **La liaison
physique reste à 16×16.** Les corrections du côté Linux Mint décrites ici sont
déployées ; elles ne constituent pas un pilote MPC 32×32 installé ou validé.

## Cause vérifiée

- `/proc/asound/card2/stream0` sur le PC annonce 16 canaux S16_LE dans chaque
  sens, à 44 100 Hz. Les ports PipeWire vont de AUX0 à AUX15.
- Sur la MPC, les deux PCM UAC2Gadget ouverts par l'application utilisent
  également 16 canaux, période 128 et tampon 768.
- Le projet ouvert dans Ardour possède bien les 32 entrées nommées, mais
  seulement 16 sont raccordées à de vrais canaux USB. Le Master reste relié
  aux deux sorties Behringer.
- Le noyau MPC est `6.18.26-az01-2026-04-30-rt4`, avec `CONFIG_USB_F_UAC2=y`
  et `CONFIG_USB_U_AUDIO=y`. Le pilote est intégré au noyau ; il n'existe
  pas de module UAC2 32 canaux compilé oublié dans ce déploiement.
- Configfs expose `p_chmask/c_chmask`, ainsi que l'extension locale
  `named_channels`, mais pas `p_channels/c_channels`. L'extension
  `named_channels=0` ne supprime pas le refus du masque supérieur à
  `0x07ffffff`.

Le [rapport du 26 septembre](mpc-submix-master-2026-09-26.md) conserve le refus
effectivement observé lors du précédent essai à 32 canaux et la restauration
à 16. Cette passe ne répète pas cette reconfiguration interrompant l'audio.
Une copie en lecture seule du noyau installé, décompressée et désassemblée
avec les adresses de `/proc/kallsyms`, confirme les deux refus dans
`afunc_bind`, aux adresses `0xc0678364` et `0xc0678370`. Le contrôle se trouve
avant l'utilisation des descripteurs de canaux. Cela concorde avec la
[validation du pilote Linux 6.18](https://github.com/torvalds/linux/blob/v6.18/drivers/usb/gadget/function/f_uac2.c#L905).
Le pilote installé comporte des extensions constructeur : la source amont
ne doit pas être présentée comme sa source exacte.

## Corrections déployées sur Linux Mint

Le backend lit désormais `usb_channels` dans `studio.json` (16 par défaut),
avec une surcharge de diagnostic `MPC_USB_CHANNELS`. Les valeurs permises
sont 16 et 32. Les noms des périphériques, les flux de maintien, les cartes
de canaux et le raccordement des seize paires ne sont plus limités à huit
paires dans le code PC. La migration des maintiens utilise des noms distincts
en 32 canaux et conserve le nombre de canaux dans leur état.

La supervision compte séparément les ports USB réellement disponibles,
les entrées attendues par les pistes et les connexions existantes. Elle
affiche maintenant « 16 entrées / 16 sorties USB réelles », « 16/32 canaux
raccordés » et l'absence des canaux 17–32. Cet écart ne déclenche pas une
boucle de reconfiguration automatique. Le lanceur accepte également une
interface réelle à 32 canaux au lieu d'exiger toujours exactement 16 liens.

Avant toute préparation à 32 canaux, le backend exige les attributs de
compte explicite côté MPC. En leur absence, il s'arrête avant les écritures
distantes, les transferts de scripts ou les changements du graphe. Après une
préparation, il vérifie les ports dans les deux sens avant de lancer les
maintiens. Le routage vérifie toutes les entrées MPC nécessaires avant la
première connexion. Les comptages refusent les périphériques ambigus et les
cartes de ports incomplètes.

La configuration de production reste volontairement à sa valeur effective
16 ; positionner uniquement `usb_channels` à 32 n'active pas un pilote MPC.
Le contrôle `MPC_USB_CHANNELS=32 ./studio check`, via le wrapper local, a
effectivement refusé la MPC actuelle en conservant sa liaison.

## Validation et préservation

65 tests ciblés réussissent : backend, supervision, lanceur, graphe PipeWire
et nouveaux cas 32 canaux. Ils couvrent notamment les canaux 17 et 32,
un dernier lien absent, 32 entrées nommées sur une interface 16 canaux, les
ports matériels incomplets, un doublon de périphérique et le refus avant
écriture. Les tests 32 canaux utilisent des graphes et clients simulés,
**pas un transfert audio matériel à 32 canaux**.

Seul le service web/supervision a redémarré pour charger la correction
(PID 164938 → 237904). Ardour 173019, la passerelle console 164931 et les
deux maintiens 19799/19807 conservent leur identité de démarrage. Les liens
PipeWire sont identiques avant/après, et les PCM MPC restent observés actifs.
Le nouveau backend a relu et validé le périphérique et les deux maintiens
16 canaux existants. Aucun projet ou réglage de greffon n'a été modifié.
Ce contrôle ne constitue pas une nouvelle écoute ni un essai d'endurance.

Les preuves privées sont conservées dans `../mpc-32-production-20260927/` :
état avant/après, code initial et copie de préparation, manifeste déployé,
copie de la session sauvegardée, graphe, configuration du pilote, noyau et
désassemblage. Copie locale sur le même disque, pas une archive indépendante.
SHA-256 de l'image noyau copiée :
`80811457af7422acd27872597ba974dca5f1f5429d067f7b2c60caca3d38da19`.
Le code constructeur brut, les réglages et la session restent hors Git.

## Blocage restant

L'activation matérielle nécessite un pilote du noyau MPC qui sépare le
nombre de canaux discrets de leur masque de positions. Aucun tel pilote
compatible avec ce noyau constructeur n'est disponible dans le workspace ;
les sources exactes et un binaire compatible n'ont pas été obtenus dans
cette passe. Aucun noyau ou firmware n'a été modifié.

Il reste à obtenir/reconstruire ce pilote, valider sa compatibilité avec le
noyau MPC, puis effectuer la bascule USB avec sauvegarde du projet MPC et
possibilité de retour. Il faudra ensuite vérifier les 32 canaux dans chaque
sens, raccorder les seize paires, mesurer un signal sur 17–18 puis 31–32,
et contrôler l'écoute et l'endurance. Le budget de tampon devra aussi être
vérifié : 32 canaux S16 doublent les octets par trame par rapport à l'état
16 canaux, avec une limite de période à une page dans le pilote audio amont.

## Mise à jour après bascule, le 27 septembre à 18 h 53

Le blocage matériel décrit ci-dessus est levé : [Juju Driver est déployé](juju-driver-deployment-2026-09-27.md), les 32 identités de canaux ont été mesurées dans les deux sens et les 32 entrées sont raccordées dans Ardour avec sauvegarde des références Juju. La production fonctionne en 32×32 à 44,1 kHz, période 128 / tampon 512. Le service est activé au démarrage et la supervision PC est réactivée. L'écoute humaine, l'endurance longue et le démarrage électrique complet restent à consigner séparément.
