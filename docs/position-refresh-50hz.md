# Afficheur de position : cible 50 Hz

Demande utilisateur du14 septembre2026 : augmenter le rafraîchissement du compteur, cible50Hz.
Statut : faisabilité examinée, changement non déployé.

## Vérifications

- Ardour9.8 libs/surfaces/osc/osc.cc:258 crée le timer OSC à100ms (10Hz).
- OSCGlobalObserver::tick lit transport_sample puis émet /position/smpte et /position/bbt.
- Le même timer appelle les observateurs de pistes, vumètres, heartbeat et compteurs de timeout.
  Remplacer100 par20 modifierait aussi ces comportements ; éviter ce changement global.
- Passerelle : SEND_INTERVAL=2ms, un ACK en vol, coalescence et priorité compteur déjà présentes.
  Ces réglages permettent d'envisager50Hz mais ne prouvent pas la cadence physique sous charge.
- Session tttt : timecode-format=timecode_30. SMPTE ne peut donner que30 valeurs de frame
  distinctes par seconde en lecture normale, même si l'échantillonnage est à50Hz.

## Mise en œuvre visée

Extraire l'envoi de position dans une mise à jour dédiée toutes les20ms côté OSC Ardour,
sur son même event loop. Garder le cycle existant pour les autres observateurs/timeouts.
Conserver la déduplication : pas d'envoi des chiffres identiques, pas de file de vieilles positions.
Pas d'extrapolation de position côté passerelle, pour respecter les sauts, boucles et le jog.
Mesurer en lecture + sélections + faders : cadence OSC, délais/ACK Ethernet, timeouts,
longues pauses et absence de retard des autres sorties. Confirmation visuelle nécessaire.
La stabilité OSC9.8 reste un diagnostic ouvert ; ne pas déclarer50Hz validé sans ces mesures.
