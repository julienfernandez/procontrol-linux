# Compléter la plage du programme comm

Le lecteur `tools/comm_application_gaps.py` acquiert deux fois les
[quatre intervalles manquants](application-preservation-gaps-2026-09-21.md)
de `0x20000–0x2ffff`, puis le mot de contrôle à `0x30000`. Cela représente
1 768 octets complémentaires et deux octets de contrôle par passe.
Les lots restent limités à 16 octets ; chaque champ possède son PCAP,
son résultat brut et un audit indépendant. Il n'existe pas d'adresse libre.

Les fonctions communes de collecte et de vérification reçoivent un plan
explicite. Le lecteur initial des cinq champs de réglages conserve son plan
et son format de rapport par défaut. Les audits anciens restent lisibles.

## Acquisition

Depuis la racine du dépôt principal, aperçu sans réseau :

```sh
python3 tools/comm_application_gaps.py
```

Pendant une période de test autorisée, avec un dossier neuf :

```sh
python3 tools/comm_application_gaps.py --send \
  --output work/firmware-research-20260920/comm-application-gaps-1
```

Les mêmes contrôles que pour les [réglages comm](comm-preservation-procedure.md)
s'appliquent : passerelle Online fraîche, Ardour fermé, verrou exclusif,
arrêt au premier échec, absence de répétition automatique et relance garantie
de la passerelle. Le programme conserve aussi les valeurs qui ne correspondent
pas à une hypothèse de remplissage ou à la passe précédente.

## Assemblage et somme complète

```sh
python3 tools/audit_comm_application.py \
  work/firmware-research-20260920/comm-application-gaps-1 \
  --code-archive work/firmware-research-20260920/comm-full-double-1 \
  --reference work/firmware-research-20260920/extracted \
  --output work/firmware-research-20260920/comm-application-audit.json \
  --reconstruct work/firmware-research-20260920/comm-application-rebuilt
```

Le vérificateur reconstruit d'abord les anciens segments depuis leurs captures,
puis les nouveaux champs. Il exige des captures distinctes, une chronologie
cohérente et des comptes de pertes nuls, y compris dans l'ancienne campagne.
Chaque image de 65 536 octets provient d'une passe de code antérieure et de
la passe correspondante des compléments. Les bornes doivent se joindre
exactement : aucun remplissage, trou ou recouvrement n'est accepté.

La somme des octets non signés modulo 65 536 est comparée au mot de contrôle
lu pendant la campagne complémentaire. Les images et le rapport sont conservés
même si les sommes ou les deux images diffèrent ; le CLI signale alors un échec.

Il s'agit d'une **couverture cumulative de deux campagnes datées séparément**,
pas d'un snapshot atomique. La comparaison des anciens segments au constructeur,
l'égalité des deux assemblages et la somme de 16 bits sont trois contrôles
distincts. Cette étape ne couvre ni le bootstrap entier, ni toute la flash,
ni une restauration matérielle de la console.
