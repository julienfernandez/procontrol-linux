# Essai afficheurs DSP — en attente de confirmation visuelle

Commande texte de référence f0 13 00 40 adresse 00 ASCII8 f7.
Adresses candidates 0D..14 et 2D..34, motivées par les zones DSP observées
et le décalage 20 des afficheurs de tranches, non encore confirmées.
Textes DSP1-A..DSP8-A et DSP1-B..DSP8-B envoyés par la file ACK du démon.
Effacement automatique au bout de120s ; aucune émission Ethernet concurrente.
RPC local dsp_display_test, paramètres fixes et recouvrement refusé.
119 tests passent. Capture150s ouverte dans captures/dsp-displays-20260914 ;
ne pas analyser avant clôture. Heure précise dans test-request.json.
Ardour waiting, console Online au lancement ; test indépendant d'Ardour.

## Validation par photo utilisateur

La photo reçue montre DSP1-B..DSP8-B du haut vers le bas. Les adresses
2D..34 (45..52 décimal) sont confirmées pour ces huit écrans. La série A
n'est pas localisée : ne pas conclure que les deux adresses sont deux lignes
ou qu'A n'a aucun effet. Les données sont dans dsp-displays-confirmed.json.
La fonction pure dsp_controls.dsp_text encode désormais ces sorties confirmées,
sans encore modifier le feedback du démon. Le test ne valide pas de plugin EQ.
