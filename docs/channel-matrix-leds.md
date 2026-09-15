# LEDs Channel Matrix — 14 septembre 2026

Les 32 touches numérotées disposent désormais de retours lumineux basés sur
le catalogue et les états OSC reçus. L'adresse de LED réutilise la zone0x17 et
les touches0x01–0x20 de la table ProControl vendorizée. La confirmation physique
de ce nouveau rendu reste à obtenir ; les boutons d'entrée étaient déjà utilisés.

- SELECT : LED allumée si Ardour signale la piste sélectionnée.
- MUTE / SOLO / REC : LED allumée lorsque l'état correspondant est actif.
- A–D : pages absolues de32 pistes, indépendantes de la banque des huit faders.
- Aucun état actif affiché pour une position sans piste.
- ALPHA : masque les états de pistes, conserve CAPS ; les états reviennent en sortie.
- Les retours des pistes hors banque de faders actualisent aussi la matrice.
- La déconnexion efface les états de pistes, les changements de catalogue les recalculent.
- Aucun allumage optimiste à l'appui : la LED de sélection suit la réponse Ardour.
- Pas de nouveau /refresh ni de catalogue périodique introduit.

La LED indique l'état, pas simplement l'existence d'une piste : une piste
sélectionnable mais non sélectionnée reste éteinte en SELECT. Aucun niveau
intermédiaire ni clignotement matériel non documenté n'a été inventé.

Validation automatisée :92 tests réussis, dont sélection de la piste17,
bascule mute/solo/rec, page33–64, emplacements vides, suppression de pistes,
ALPHA/CAPS et déconnexion. Démon/pointeur relancés sans authentification.
À la vérification : console Online, Ardour répond, huit pistes identifiées,
catalogue Lua stéréo reçu, aucun output_error. Cela ne constitue pas encore
une validation visuelle des32 LEDs ni une preuve de stabilité prolongée d'Ardour.
