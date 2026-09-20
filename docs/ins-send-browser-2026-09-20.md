# INS/SEND par tranche → navigateur DSP

Le bouton physique **INS/SEND**, sous REC/RDY et au-dessus d’EQ IN/EDIT,
ouvre le navigateur de plugins de sa piste dans **DSP EDIT/ASSIGN**. Il
utilise le même parcours qu’INSERTS/PARAM global, avec la piste de la tranche
comme cible explicite. Le routage respecte la banque actuelle.

Une piste possédant des effets affiche sa chaîne ; une piste vide affiche la
bibliothèque courte. Un nouvel appui sur la même tranche alterne chaîne et
bibliothèque comme INSERTS/PARAM. Tourner les potards déplace le curseur ;
SELECT d’une ligne DSP ou ENTER ouvre/confirme le choix. Le seul fait d’ouvrir
le navigateur n’insère aucun effet. ESCAPE revient au mixage.

Le voyant INS/SEND de la tranche ciblée suit le navigateur et s’efface à la
sortie, au changement de piste ou lors du passage en EQ/DYN. Le bouton
INSERTS/PARAM global conserve son fonctionnement.

## Origine du décalage

La table tierce appelle le code `01` « Pan_Send » et `0a` « Inserts ».
L’ancien adaptateur envoyait pour `01` une sélection de piste suivie de
`/select/expand`, sans ouvrir notre éditeur DSP. Le navigateur par tranche
était uniquement associé à `0a`.

Le journal local contient un appui `90 01 40` à 07:21:56.833890 UTC le
20 septembre 2026, séquence 299972, puis un relâchement `90 01 00` à
07:21:57.048530 UTC, séquence 299973. Ce geste récent est cohérent avec le
bouton indiqué sur la photo utilisateur ; la photo seule ne démontre pas
son code Ethernet. L’adaptation rattache `01` et l’ancien alias `0a` au même
parcours `browse_track`. Les sources tierces restent inchangées.

## Vérification logicielle

Les tests de navigateur couvrent l’appui/relâchement et le retry exact, la
cible de la seconde banque, le passage d’une piste à l’autre, l’entrée depuis
le monitoring IN/DISK, la bibliothèque d’une piste vide sans insertion et
les voyants de tranche/DSP. Les vérifications physiques et les acquittements
Ethernet sont des preuves distinctes des tests logiciels.
