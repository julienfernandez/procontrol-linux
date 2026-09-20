# Expérience

- Date / période UTC / auteur ou outil :
- Identifiant / objectif :
- Question à trancher / critère de réussite / limites de l'expérience :
- Nature : analyse statique / capture passive / essai actif / test logiciel /
  confirmation physique / endurance (préciser et séparer si plusieurs) :
- Commit du code / version des outils / commande exacte reproductible :
- Sources ou images analysées : origine, version, SHA-256, base d'adressage :
- Console : unité principale / extensions ; firmware connu :
- MAC console (source de l'identification) :
- Liaison : directe / switch / port miroir / TAP :
- État initial affiché, mode normal ou diagnostic :
- Hôte compatible présent et logiciel/version, si applicable :
- État réel des services avant : PID, verrou, fraîcheur du statut, erreurs :
- Pour un essai actif : émetteur exclusif, bornes, timeout et procédure de reprise :
- État final affiché :
- Écarts au scénario (autre bouton, fader touché, reconnexion…) :
- Statistiques dumpcap/tcpdump : trames capturées / pertes signalées :
- Pour une capture par socket : périmètre capturé / compteur de pertes noyau :

Noter les gestes au moment de les effectuer. Préciser si les temps sont
approximatifs, relatifs à « File: - » / « listening on », ou issus d'une horloge UTC.
Une confirmation dans le chat n'est pas un horodatage du geste physique.

| Temps | Action | Observation physique |
|---|---|---|
| | Début d'enregistrement | |
| | Mise sous tension OU geste unique | |
| | Relâchement / fin de mouvement | |
| | Fin | |

## Analyse après capture

- Fichier PCAP et SHA-256 :
- Numéros des trames pertinentes et sens source → destination :
- Octets observés et offsets (Ethernet ou payload, préciser) :
- Hypothèse, autres explications possibles :
- Expérience nécessaire pour confirmer :

## Bilan et conservation

- Résultat obtenu et niveau de preuve pour chaque conclusion :
- Nombre de répétitions, comparaison indépendante et différences éventuelles :
- Échecs, interruptions, hypothèses réfutées et correction de méthode :
- Vérifications logicielles effectuées et ce qu'elles ne valident pas :
- Reprise des services et état réel après intervention :
- Points non démontrés / prochaine expérience discriminante :
- Rapport JSON ou manifeste : fichiers, tailles, SHA-256, chemins relatifs :
- Emplacement des preuves brutes exclues de Git / archive et vérification :
- Support indépendant vérifié, ou copie restant sur le même disque :
- Liens depuis l'index documentaire et la mémoire technique :

Publier dans Git le rapport, les outils, tests et preuves minimales appropriées.
Garder les originaux et les archives privées selon les exclusions du projet.
Un SHA identifie un fichier mais ne le sauvegarde pas. Conserver le commit
de publication et sa CI dans l'historique ; ne pas annoncer une validation
matérielle à partir de seuls tests logiciels.
