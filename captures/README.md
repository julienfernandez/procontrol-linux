# Captures locales

Chaque expérience crée son propre dossier horodaté : `traffic.pcap`,
`metadata.txt`, `tcpdump.log` ou `dumpcap.log`, `summary.txt`, `SHA256SUMS` et `notes.md`.
Ne pas renommer un essai raté en essai réussi : le conserver et recommencer.

Les captures sont exclues de Git par défaut. Les fichiers peuvent contenir du
trafic d'autres appareils sur un réseau partagé ; privilégier le lien dédié.
Les tests du lecteur utilisent des trames synthétiques dans un dossier temporaire,
jamais présentées comme des observations de la console.
