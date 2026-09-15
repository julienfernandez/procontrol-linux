# Premières observations locales — 13 septembre 2026

Source : `captures/20260913T152134Z-startup-1wddjZ/traffic.pcap`, capture terminée
entre 17:21:34 et 17:23:04 heure de Paris selon les métadonnées.
SHA-256 : `3bf426a0f801fd9197c0a7550cc66a3e3711fb25ada43d2384bbef9db8a73de2`.
Le nom « startup » ne prouve pas les gestes effectués : les notes d'expérience
n'ont pas été remplies. Les numéros ci-dessous sont ceux du PCAP complet.

## Mesures

- 51 trames enregistrées ; 0 perte noyau dans le journal tcpdump, 0 troncature.
- 13 trames `0x885f` depuis `00:a0:7e:a0:ad:9c`, toutes en broadcast.
- 38 autres trames provenant du laptop ; aucune trame `0x885f` émise par le laptop.
- 7 annonces de 64 octets : trames 12, 17, 20, 22, 26, 36, 46. Elles contiennent
  `MAINUNIT` et `1.37`, conformément au schéma d'annonce candidat de ReaControl.
  Cela étaye l'identification de l'unité principale et de sa version annoncée.
- Aux offsets Ethernet 18–21, la lecture big-endian donne 1 à 13 sur les treize
  trames, y compris les messages hors annonces. Sens de compteur séquentiel
  fortement étayé ; règles d'ACK non établies.
- Offset 28 : `e0` sur les annonces ; `00` sur les six autres messages. L'octet
  suivant vaut `01`. Aucune séquence de connexion hôte n'est observée.
- Champ de longueur aux offsets 14–15 : 50 sur les annonces, 23 ou 27 sur les
  messages courts, cohérent avec l'en-tête candidat de 16 octets et la charge
  utile, en excluant le remplissage Ethernet final.

## Messages supplémentaires, fonction à établir

| Trames | Corps après l'en-tête candidat | Observation |
|---|---|---|
| 25, 40 | `f0 13 00 70 00 55 f7` | Octet ASCII U |
| 45, 47 | `f0 13 00 70 00 50/52 32 33 33 34 f7` | P2334 puis R2334, écart 170 ms environ |
| 48, 49 | `f0 13 00 70 00 50/52 31 35 30 31 f7` | P1501 puis R1501, écart 170 ms environ |

L'interprétation P/R comme pression/relâchement est une **hypothèse**, pas une
correspondance PLAY/STOP vérifiée. Il faut connaître les gestes et le mode de la
console ; un mode diagnostic est notamment une possibilité à distinguer du mode
normal. Les annonces seules ne permettent pas d'inférer l'état physique `Offline`.

## Seconde capture et incident d'arrêt

`20260913T152442Z-startup-i3v6DV` a été demandé à 17:24:42, mais tcpdump n'a
démarré qu'à 17:32:23 après authentification. Son arrêt demandé après 90 secondes
n'a pas fonctionné. Le processus parent porte le label AppArmor `chatgpt`, tandis
que tcpdump porte `tcpdump (enforce)` ; l'abstraction locale n'autorise la réception
de signaux que depuis `unconfined` ou le même profil, hors signaux de vérification.
Un essai de SIGINT privilégié depuis l'app a reçu « Permission denied ».

L'utilisateur a arrêté cette seconde capture depuis son terminal. Bilan final :
241 trames, zéro perte noyau signalée, zéro troncature, 146 trames de la console.
Les paquets s'étendent de 15:32:23.958956 à 15:44:44.212054 UTC, soit 740,253098 s.
Ne pas la considérer comme un essai de 90 s. SHA-256 :
`0ce957e9a1572080829743d7bfa764b402390ff6100643b9bb3817f287fba933`.

Le bilan du script a ensuite échoué car son fichier avait été modifié pendant
que bash attendait tcpdump. Le PCAP était intact ; sa relecture, son bilan et
son hash ont été récupérés séparément. Le code d'orchestration 2 et la récupération
figurent dans metadata.txt ; le code de sortie original de tcpdump n'est pas
reconstitué. Le script charge désormais son corps dans une fonction avant la capture.

Les 146 compteurs sont continus de 107 à 252. Il y a 104 annonces e0 et
42 messages courts : U (8), X (1), puis plusieurs P/R. Les gestes et leur mode
ne sont pas connus. Les trames individuelles figurent dans diginet-audit.json.

## Essais avec dumpcap : Offline hors diagnostics

État initial communiqué par l'utilisateur : **Offline, hors diagnostics**.
Toutes les captures de ce tableau sont clôturées, avec arrêt natif dumpcap,
zéro perte signalée et zéro troncature. La durée demandée est la fenêtre
d'enregistrement ; l'étendue des paquets peut être plus courte.

| Dossier dans captures/ | Durée demandée | Total / console | Résultat console |
|---|---:|---:|---|
| 20260913T155212Z-idle-normal-5aADp2 | 30 s | 4 / 4 | Quatre annonces e0, compteurs 324–327 |
| 20260913T155318Z-play-offline-ef6VCD | 60 s | 27 / 10 | Neuf annonces e0 ; U à la trame 4 ; compteurs 333–342 |
| 20260913T155757Z-stop-offline-CuTd6P | 120 s | 18 / 18 | Dix-sept annonces e0 ; U à la trame 11 ; compteurs 373–390 |

SHA-256, respectivement :

- idle : `e56f8b086b67d0c2128604f9d01c845ed91da8e98f143a55e1fb013cd7ffa158`
- play : `5f81a4941fb78b2c038d084972d314dfacd3f63f859ed46d8e8095fc837e1172`
- stop : `66d90c488412ea2b9b566343f64537d2003256c4cdd6c693119fba82101c769b`

PLAY a été confirmé pressé puis relâché ; la confirmation est arrivée après
clôture, sans heure physique du geste. Pour STOP, l'utilisateur a explicitement
confirmé le geste pendant l'enregistrement, avant son heure de fin. Les temps
exacts de pression et relâchement restent non mesurés.

Dans PLAY, U apparaît à 15:53:36.798088 UTC ; dans STOP, à 15:59:04.907943 UTC.
Les deux corps sont `f0 13 00 70 00 55 f7`. Ils ne permettent pas de distinguer
PLAY et STOP. Les captures ne démontrent donc aucun mapping de bouton. U existe
aussi dans les premières captures ; sa périodicité n'y est pas constante.
L'absence de couple P/R dans ces essais ne prouve pas une panne.

## Champ de somme candidat

Sur les **191 trames console 0x885f des cinq captures passives**, le champ
big-endian à l'offset Ethernet 16 (payload +2) égale la somme des octets du
corps logique, après l'en-tête de 16 octets : **191 correspondances sur 191**.
Les JSON d'audit conservent pour chaque numéro de trame le champ et la somme.
Exemple : PLAY, trame 4, champ `02 bf`, corps `f0 13 00 70 00 55 f7`, somme 703.

L'hypothèse d'un checksum additif est fortement étayée, mais aucune somme
observée n'atteint 65536 : la règle de débordement n'est pas testée par ces
captures. Le remplissage observé est nul, donc son inclusion éventuelle ne peut
pas être départagée par la seule égalité arithmétique. L'acceptation ou le rejet
par le matériel d'une somme modifiée n'a pas été testé.

## Passage à l'essai actif

L'utilisateur a demandé un démon établissant Online, après discussion du succès
ProControl confirmé dans les commentaires GitHub. Voir [session-reference.md](session-reference.md).
Les mesures ci-dessus précèdent toute émission de ce démon et restent notre
référence passive. Les résultats actifs sont consignés séparément.
