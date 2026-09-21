# Programme comm : couverture complète de 64 Kio

Le **21 septembre 2026**, les 1 768 octets absents des ressources constructeur
ont été lus deux fois sur la console. Chaque complément, associé à la passe
correspondante des segments déjà capturés, forme une image de **65 536 octets**
couvrant exactement `0x20000–0x2ffff`. Les deux images sont identiques.
Leur somme d'octets modulo 65 536 vaut **`0xda49`**, comme le mot de contrôle
relu à `0x30000` pendant chaque nouvelle passe.

Le [manifeste public](comm-application-complete-2026-09-21.json) conserve
la couverture, les dates, les empreintes et l'archive privée. La
[procédure reproductible](comm-application-procedure.md) décrit les outils.

## Acquisition des compléments

| Intervalle, bornes incluses | Octets par passe | Contenu observé deux fois |
|---|---:|---|
| `0x20008–0x20063` | 92 | Tous `ff` |
| `0x20080–0x200ff` | 128 | Tous `ff` |
| `0x20110–0x203ff` | 752 | Tous `ff` |
| `0x2fce4–0x2ffff` | 796 | Tous `ff` |
| Contrôle `0x30000–0x30001`, hors image assemblée | 2 | `da49` |

Les valeurs `ff` ont été reçues, capturées et reconstruites. Elles ne sont
pas un remplissage déduit des adresses ou de la somme attendue.
La nouvelle collecte a duré de **00:04:26,739340 à 00:04:40,445759 UTC**,
avec les contrôles de connexion. Elle produit dix PCAP, sans perte socket
enregistrée, avec des lots de 16 octets et sans répétition automatique.

## Deux images cumulatives vérifiées

Les anciens segments proviennent de la [double acquisition comm du 20 septembre](comm-firmware-readback-2026-09-20.md),
réalisée entre 21:10 et 21:15 UTC. Le vérificateur relit leurs **504 PCAP**,
puis les **dix captures complémentaires**. Le périmètre total contient
**138 715 trames**, toutes avec des statistiques de pertes socket nulles.
Les versions, adresses, ACK, empreintes, doublons et limites des plages
sont contrôlés ; aucune adresse n'est comblée ou écrasée pendant l'assemblage.

Chaque image reconstruite a le SHA-256 :

```text
9a24da8fc2ea58d33fc11a2dc28f6d1fb556dc422a0ec2cd254d605a2d501c48
```

Cette preuve est une **couverture cumulative de deux campagnes**. Leurs
timestamps restent distincts et aucune atomicité n'est affirmée. Les trois
résultats sont séparés : segments connus identiques au constructeur,
deux assemblages identiques octet par octet, puis somme complète égale
au mot stocké. Une somme de 16 bits ne remplace pas les captures ou les octets.

## Conservation

L'archive `procontrol-comm-application-complete.tar.gz` contient les deux
campagnes, les références, les images complètes, l'audit, les sources via
bundle Git, les empreintes de lancement et les contrôles des services.
Ses **1 584 membres** ont été relus et vérifiés ; taille **7 481 368 octets**,
SHA-256 :

```text
6deaa297fd026f20d684880b2868ba6778347468a1aeea415914c2d755565906
```

La copie est vérifiée dans
`~/Documents/OpenProControl-preservation/2026-09-20-comm-1.37/`, sur le même
ordinateur. Cette copie a été extraite dans un dossier neuf et son bundle
Git cloné au commit `d578fbb`. L’audit exécuté depuis ce clone reproduit
exactement le rapport initial et les deux images. Cette restitution hors ligne
ne constitue pas une réinstallation du firmware dans la console.
Les binaires et les captures restent hors du dépôt Git public.
Les sources de la collecte correspondent au commit `d578fbb` ; **445 tests
locaux passent en 102,833 s**, aucun ignoré. La passerelle a redémarré avec
le code zéro ; son processus et celui du pointeur ont été vérifiés Online.

## Périmètre restant

La plage du **programme comm** est maintenant couverte. Le bootstrap comm,
les autres parties de sa flash et l'identité matérielle sont des périmètres
distincts. Il reste aussi 4 838 octets dans la plage du programme fader,
ainsi que son bootstrap. Aucune restauration matérielle n'a été tentée.
