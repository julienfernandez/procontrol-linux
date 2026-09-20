# Essais console à son rythme

## Règle de fonctionnement

Pour chaque lot, ouvrir une capture passive de **600 secondes**, vérifier son
ouverture effective, puis annoncer clairement que l’écoute est prête, l’heure
de fin et **une seule séquence de gestes**. Les services ProControl et pointeur
restent actifs. Ne pas modifier leurs modules pendant le lot.

L’utilisateur peut se déplacer jusqu’à la console, effectuer les gestes et
répondre « fait » à son rythme. Sa confirmation permet de clôturer plus tôt.
« Attends » demande une nouvelle fenêtre de dix minutes après la clôture
propre de la précédente. Sans réponse, conserver la capture jusqu’à son terme,
puis distinguer les gestes reçus d’une simple période de repos. Ne pas déclarer
un contrôle validé seulement parce qu’un délai s’est écoulé.

Si l’utilisateur précise un ordre différent dans sa réponse, cet ordre réel
remplace la consigne. Conserver les deux ; ne pas associer automatiquement les
paquets au premier scénario. L’heure du message n’est pas l’heure du geste.
Les journaux permanents permettent aussi de retrouver un geste tardif, mais
il n’appartient pas au PCAP déjà fermé.

## Ordre des lots

1. **Identifier les adresses** des boutons inconnus, par petits groupes.
   Trois appuis par bouton, avec relâchement, puis confirmation de l’ordre réel.
2. **Raccorder et tester le mapping logiciel**, vérifier ses modes et les retries.
3. **Valider les voyants et la navigation**, sans commande d’édition destructive.
4. **Édition sur une copie jetable** : IN/OUT, boucle, séparation, copie,
   suppression, UNDO/REDO, SAVE. Comparer aussi le contenu de la copie.
5. **Monitoring et plugins**, puis **audio/synchronisation et endurance** dans
   des lots distincts. Une LED reçue ne valide pas un résultat audio.

## Premier lot — identifié le 20 septembre

L’utilisateur a pressé **PREVIOUS ×3, ZOOM/SEL ×3, NEXT ×3, UP ×3, DOWN ×3**.
La capture a été ouverte pour dix minutes et clôturée après sa confirmation.
Les quinze couples appui/relâchement sont présents, sans perte dumpcap.
[Preuves et numéros des trames](navigation-buttons-confirmed.json).

| Touche | Zone / code | ZOOM/SEL éteint : navigation | ZOOM/SEL allumé : zoom |
|---|---|---|---|
| UP | 18 / 00 | Voie précédente | Augmenter la hauteur des pistes sélectionnées |
| PREVIOUS | 18 / 01 | Limite de région précédente sur les pistes sélectionnées | Dézoomer horizontalement |
| ZOOM/SEL | 18 / 02 | Passer au zoom | Revenir à la navigation |
| NEXT | 18 / 03 | Limite de région suivante sur les pistes sélectionnées | Zoomer horizontalement |
| DOWN | 18 / 04 | Voie suivante | Réduire la hauteur des pistes sélectionnées |

SHIFT + ZOOM/SEL cadre la sélection ; ALT + ZOOM/SEL cadre la session, sans
changer de mode. Une reconnexion revient à la navigation, voyant éteint.
PREVIOUS/NEXT déplacent le curseur, sans sélectionner automatiquement une région.
Pour éditer les formes d’onde, utiliser IN/OUT puis GRAB comme dans le
[guide d’édition](console-editing.md). Si une piste ne contient aucune région,
ses limites ne fournissent pas de cible de déplacement.

## Retour lumineux des commandes ponctuelles

Les commandes transmises à Ardour déclenchent une impulsion de **350 ms**,
à compter de l’envoi de l’allumage : UNDO/REDO, SAVE, édition, IN/OUT, PRE/POST,
fenêtres, marqueurs, banques et quatre flèches de navigation. Les touches
concernées sont listées dans `SurfaceFeedback.PULSE_BUTTONS`.

La passerelle utilise sa file habituelle et son ACK unique. Les appuis répétés
prolongent une seule impulsion ; les retries Ethernet et un maintien ne créent
pas de commande supplémentaire dans l’éditeur. Un allumage qui n’a pas pu
partir en une seconde est abandonné ; il n’est pas rejoué tardivement. Après
l’impulsion, le dernier état réel du voyant est restauré. La reconnexion annule
les impulsions. Aucun thread ni attente bloquante n’est ajouté.

PLAY, REC, boucle, mute, solo, sélection, monitoring, DSP et NUDGE conservent
leurs indications d’état. Le centre ZOOM/SEL indique son mode par un allumage
fixe. UNDO = annuler ; SHIFT + UNDO = rétablir ; SAVE = sauvegarder.

Le flash signifie **commande reconnue et transmise**, pas confirmation que
l’opération a modifié la session : annuler sans historique, par exemple, peut
ne rien changer. L’ACK Ethernet prouve la réception du message, pas la présence
d’une lampe derrière chaque touche ni son rendu visuel ; ceux-ci demandent le
retour de l’utilisateur.

## État de validation

250 tests Python passent sur l’arbre préparé (53,663 s). Les modules installés
ont été comparés octet par octet à cet arbre. Les nouveaux tests couvrent les
quinze gestes capturés, les modes sélection/zoom, les raccourcis, le maintien,
la déduplication, les délais de flash, la perte d’ACK, les changements d’état
pendant une impulsion et son annulation à la reconnexion.

Après déploiement : passerelle Online, Ardour répondant et pointeur actif.
L’identification physique des cinq touches est confirmée ; la seconde fenêtre
d’essai visuel a été ouverte pour dix minutes. L’envoi des commandes et les ACK
ne suffisent pas à déclarer le flash visible ni le zoom physiquement validé.
