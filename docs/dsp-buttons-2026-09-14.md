# Boutons DSP — capture confirmée

L'utilisateur a réalisé les deux boutons de gauche de chaque rangée, puis
les huit boutons à droite des molettes. La capture clôturée contient les
24 appuis et 24 relâchements, une paire par bouton : zones 0D..14 du haut
vers le bas ; touches 00/01 à gauche et 02 à droite. Le premier groupe suit
00,01 par rangée, puis le dernier suit 02 du haut vers le bas.

150 trames, zéro perte ; console Online ; direction console vers laptop.
SHA-256 : `5fb439e7712484cc48816aae4a8c8090e65324a1707c9ee2bc3d0fb9781270c8`.
[données et numéros de trames](dsp-buttons-confirmed.json).

Les libellés SELECT/AUTO, ASSIGN/ENABLE et BYPASS/IN-OUT reprennent ceux de
la première rangée dans la référence ProControl. Le geste confirme les
positions et codes, pas encore leur effet dans Ardour ni leurs LEDs.

Un décodeur autonome tools/dsp_controls.py et ses tests sont ajoutés. Il ne
change pas les actions de la passerelle en service, et aucun redémarrage
n'est nécessaire pour ce relevé. Prochaine étape : identifier les afficheurs
DSP et définir les actions suivant le contexte plugin/paramètre. Ne pas
assimiler les huit boutons de droite à huit bypass globaux du même plugin.
