#!/usr/bin/env python3
"""Essai ProControl borné : session, transport OSC et test optionnel du compteur."""
# SPDX-License-Identifier: GPL-3.0-or-later
# Référence : phunkyg/ReaControl24 b6268cbb, ReaControl.py DeviceSession.
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import select
import socket
import struct
import tempfile
import time

from audit_diginet import candidate_header
from inspect_pcap import CaptureError, mac_address
from pcap_writer import write_header, write_packet
from ardour_transport import ArdourTransport
from procontrol_mapping import decode_body, mapping_tree, SOURCE_COMMIT
from procontrol_display import clock_command, CLOCK_TEST_STEPS, CLOCK_SOURCE_COMMIT


def mac_bytes(value):
    return bytes.fromhex(value.replace(':', ''))


class Session:
    """Session minimale ; le compteur n'est commandé qu'avec clock_test=True."""
    def __init__(self, host, peer, duration=60, clock_test=False):
        if clock_test and (duration is None or duration < 70):
            raise ValueError('Le test du compteur nécessite au moins 70 secondes')
        self.host, self.peer = mac_bytes(host), mac_bytes(peer)
        self.duration = duration
        self.started = None
        self.last_heartbeat = None
        self.sequence = 1
        self.online_acked = False
        self.clock_steps = list(CLOCK_TEST_STEPS) if clock_test else []
        self.clock_pending = None

    def frame(self, command, count=0, sequence=0, ack=0, body=b''):
        header = struct.pack('>HHIIHBB', 16 + len(body), sum(body), sequence, ack, 0, command, count)
        return (self.peer + self.host + b'\x88\x5f' + header + body).ljust(60, b'\0')

    def active(self, now):
        return self.started is not None and (self.duration is None or now < self.started + self.duration)

    def receive(self, frame, now):
        if len(frame) < 30 or frame[6:12] != self.peer or frame[12:14] != b'\x88\x5f':
            return []
        if frame[:6] not in (self.host, b'\xff' * 6):
            return []
        h = candidate_header(frame[14:])
        if self.started is None:
            if frame[:6] != b'\xff' * 6 or h['command_field'] not in (0xe0, 0xe1):
                return []
            # Même disposition d'identification pour les annonces e0/e1 du journal tiers.
            body = bytes.fromhex(h['body_hex'])
            if len(body) < 33 or body[24:33].rstrip(b'\0') != b'MAINUNIT':
                return []
            if h['command_field'] == 0xe1:
                raise RuntimeError('Annonce e1 avant notre connexion : session existante possible ; arrêt.')
            self.started = self.last_heartbeat = now
            return [self.frame(0xe2, sequence=1)]
        if not self.active(now) or frame[:6] != self.host:
            return []
        if h['command_field'] == 0xa0:
            if h['ack_candidate'] == 1:
                self.online_acked = True
            if self.clock_pending and h['ack_candidate'] == self.clock_pending[0]:
                self.clock_pending = None
            return []
        if h['command_field'] != 0xa0 and h['command_count_candidate'] > 0:
            return [self.frame(0xa0, ack=h['sequence_candidate'])]
        return []

    def tick(self, now):
        if self.active(now):
            if self.clock_pending and now - self.clock_pending[1] >= 2:
                raise RuntimeError('Test compteur interrompu : commande non acquittée en 2 secondes')
            if self.clock_steps and now - self.started >= self.clock_steps[0][0]:
                if not self.online_acked and now - self.started >= 5:
                    raise RuntimeError('Test compteur interrompu : ouverture non acquittée')
                if self.online_acked and self.clock_pending is None:
                    _, text = self.clock_steps.pop(0)
                    self.sequence += 1
                    self.last_heartbeat = now
                    self.clock_pending = (self.sequence, now)
                    return [self.frame(0, count=1, sequence=self.sequence, body=clock_command(text))]
        # Les ACK d'une rafale de gestes ne doivent pas affamer le maintien.
        # Cadence indépendante à valider sur le firmware, voir le rapport Online.
        if self.active(now) and now - self.last_heartbeat >= 10:
            self.sequence += 1
            self.last_heartbeat = now
            return [self.frame(0, count=1, sequence=self.sequence, body=b'\0')]
        return []


def drop_privileges():
    if os.geteuid() == 0:
        uid = int(os.environ.get('PKEXEC_UID') or os.environ.get('SUDO_UID') or '0')
        if uid == 0:
            raise RuntimeError('Lancer depuis un compte utilisateur via pkexec ou sudo.')
        account = pwd.getpwuid(uid)
        os.initgroups(account.pw_name, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(uid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', required=True)
    parser.add_argument('--mac', required=True, type=mac_address)
    parser.add_argument('--duration', type=int, default=60, help='Session active 10..900 secondes')
    parser.add_argument('--observe-after', type=int, default=20, help='Écoute sans émission après la session, 0..60 secondes')
    parser.add_argument('--send', action='store_true', help='Ouvrir les sockets et effectuer l’essai ; sinon aperçu sans réseau')
    parser.add_argument('--osc-port', type=int, help='Activer transport et navigation vers Ardour sur 127.0.0.1:PORT')
    parser.add_argument('--quiet', action='store_true', help='Journal complet sur disque, console réduite aux événements utiles')
    parser.add_argument('--clock-test', action='store_true', help='Tester le compteur : 12345678 à +3 s, 87654321 à +33 s, effacement à +63 s')
    args = parser.parse_args()
    if not 10 <= args.duration <= 900 or not 0 <= args.observe_after <= 60:
        parser.error('Durées hors limites')
    if args.osc_port is not None and not 1024 < args.osc_port < 65536:
        parser.error('Port OSC attendu : 1025..65535')
    if args.clock_test and args.duration < 70:
        parser.error('--clock-test nécessite --duration au moins 70')
    if '/' in args.interface or not args.interface:
        parser.error('Interface invalide')
    interface = Path('/sys/class/net') / args.interface
    if not (interface / 'type').exists() or (interface / 'type').read_text().strip() != '1' or (interface / 'wireless').exists():
        parser.error('Interface Ethernet filaire requise')
    host = (interface / 'address').read_text().strip()
    peer = mac_bytes(args.mac)
    if peer[0] & 1 or peer == mac_bytes(host) or not any(peer):
        parser.error('MAC distante unicast distincte requise')
    session = Session(host, args.mac, args.duration, clock_test=args.clock_test)
    mapping_tree()  # Charger la table avant la boucle de capture.
    clock_patterns = {clock_command(text): text for _, text in CLOCK_TEST_STEPS} if args.clock_test else {}
    if not args.send:
        print(json.dumps({'mode': 'aperçu, aucune socket ouverte', 'interface': args.interface,
                          'host': host, 'peer': args.mac, 'online_hex': session.frame(0xe2, sequence=1).hex(' '),
                          'active_seconds': args.duration, 'passive_tail_seconds': args.observe_after,
                          'osc_target': f'127.0.0.1:{args.osc_port}' if args.osc_port else None,
                          'clock_test': [{'after_seconds': sec, 'text': text, 'body_hex': clock_command(text).hex(' ')}
                                         for sec, text in CLOCK_TEST_STEPS] if args.clock_test else None,
                          'commands': ['online e2', 'ACK a0 reprenant le compteur reçu', 'keepalive corps 00 toutes les 10 s indépendamment des ACK']}, indent=2, ensure_ascii=False))
        return 0
    # Deux sockets : rx voit aussi les envois de tx via PACKET_OUTGOING.
    # Aucune modification de capacités, d'interface ou de politique système.
    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as rx, socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x885f)) as tx:
        rx.bind((args.interface, 0))
        tx.bind((args.interface, 0))
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        drop_privileges()  # Les fichiers et toute la boucle réseau s'exécutent comme moi.
        os.umask(0o077)
        captures = Path(__file__).resolve().parents[1] / 'captures'
        captures.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        out = Path(tempfile.mkdtemp(prefix=f'{stamp}-online-probe-', dir=captures))
        print(f'Écoute effective : {args.interface} ; dossier : {out}', flush=True)
        counts = Counter()
        error = None
        began = time.monotonic()
        stopped_notice = False
        stats = None
        osc = None
        with (out / 'traffic.pcap').open('xb') as pcap, (out / 'events.jsonl').open('x') as log:
            write_header(pcap)

            def event(kind, **details):
                row = {'utc': datetime.now(timezone.utc).isoformat(), 'event': kind, **details}
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
                log.flush()
                useful = (kind not in ('frame', 'tx_sent', 'osc_feedback')
                          or (kind == 'tx_sent' and details.get('command') == 0xe2)
                          or (kind == 'osc_feedback' and details.get('address') in ('/transport_play', '/transport_stop', '/set_surface')))
                if not args.quiet or useful:
                    print(json.dumps(row, ensure_ascii=False), flush=True)

            def send(frames):
                for frame in frames:
                    if counts['tx_sent'] >= 2000:
                        raise RuntimeError('Limite de 2000 émissions atteinte')
                    if frame[28] == 0xa0:
                        time.sleep(0.0008)  # Délai du code de référence, pas une exigence mesurée.
                    size = tx.send(frame)
                    if size != len(frame):
                        raise RuntimeError('Émission incomplète')
                    counts['tx_sent'] += 1
                    event('tx_sent', hex=frame.hex(' '), command=frame[28])
                    body = frame[30:14 + int.from_bytes(frame[14:16], 'big')]
                    if body in clock_patterns:
                        event('clock_pattern', text=clock_patterns[body], body_hex=body.hex(' '),
                              sequence=int.from_bytes(frame[18:22], 'big'))

            event('start', host=host, peer=args.mac, active_seconds=args.duration,
                  passive_tail_seconds=args.observe_after, uid=os.geteuid(),
                  keepalive_policy='periodic_independent_of_ack', keepalive_interval_seconds=10,
                  procontrol_mapping_commit=SOURCE_COMMIT, clock_test=args.clock_test,
                  clock_source_commit=CLOCK_SOURCE_COMMIT if args.clock_test else None)
            try:
                if args.osc_port:
                    osc = ArdourTransport(args.osc_port)
                    event('osc_connected', target=f'127.0.0.1:{args.osc_port}', feedback_port=osc.socket.getsockname()[1])
                while True:
                    now = time.monotonic()
                    if session.started is None and now - began >= 20:
                        raise RuntimeError('Aucune annonce MAINUNIT e0 ciblée reçue en 20 secondes')
                    if session.started is not None:
                        if now >= session.started + args.duration + args.observe_after:
                            break
                        if not session.active(now) and not stopped_notice:
                            event('emission_stopped', reason='durée active écoulée ; observation du retour Offline')
                            stopped_notice = True
                    send(session.tick(now))
                    if osc:
                        for address, values in osc.poll():
                            event('osc_feedback', address=address, values=values)
                    if not select.select([rx], [], [], 0.05)[0]:
                        continue
                    frame, address = rx.recvfrom(65535)
                    if len(frame) < 14 or frame[12:14] != b'\x88\x5f' or peer not in (frame[:6], frame[6:12]):
                        continue
                    ns = time.time_ns()
                    write_packet(pcap, ns, frame)
                    counts['captured'] += 1
                    outgoing = address[2] == socket.PACKET_OUTGOING
                    counts['tx_observed' if outgoing else 'rx_observed'] += 1
                    try:
                        h = candidate_header(frame[14:])
                        if not outgoing and h['command_field'] == 0:
                            h['reference_decoding'] = decode_body(bytes.fromhex(h['body_hex']))
                        event('frame', frame=counts['captured'], direction='out' if outgoing else 'in', **h)
                        if not outgoing:
                            send(session.receive(frame, time.monotonic()))
                            if osc and session.active(time.monotonic()) and frame[:6] == session.host and frame[6:12] == session.peer and h['command_field'] == 0:
                                address = osc.forward(h['sequence_candidate'], bytes.fromhex(h['body_hex']))
                                if address:
                                    event('osc_sent', address=address, value=1, source_frame=counts['captured'])
                    except CaptureError as exc:
                        counts['malformed'] += 1
                        event('malformed', detail=str(exc))
            except (RuntimeError, OSError, KeyboardInterrupt) as exc:
                error = str(exc) or type(exc).__name__
                event('error', detail=error)
            finally:
                if osc:
                    osc.close()
                # Linux SOL_PACKET / PACKET_STATISTICS : paquets reçus et pertes socket.
                try:
                    received, dropped = struct.unpack('II', rx.getsockopt(263, 6, 8))
                    stats = {'socket_received_all_protocols': received, 'socket_dropped_all_protocols': dropped}
                except OSError:
                    pass
                event('end', counts=dict(counts), socket_stats=stats, error=error)
        digest = hashlib.sha256((out / 'traffic.pcap').read_bytes()).hexdigest()
        (out / 'SHA256SUMS').write_text(f'{digest}  traffic.pcap\n')
        (out / 'metadata.json').write_text(json.dumps({
            'interface': args.interface, 'host': host, 'peer': args.mac,
            'counts': dict(counts), 'socket_stats': stats, 'error': error,
            'capture_exit_code': int(error is not None), 'sha256': digest,
            'timestamp_source': 'userspace receive time, microseconds in PCAP',
            'capture_source': 'AF_PACKET receive socket; includes kernel-observed outgoing frames from separate send socket',
            'active_seconds_requested': args.duration, 'passive_tail_seconds': args.observe_after,
            'clock_initialization_sent': False,
            'clock_display_test': args.clock_test,
            'clock_source_commit': CLOCK_SOURCE_COMMIT if args.clock_test else None,
            'clock_test_steps': list(CLOCK_TEST_STEPS) if args.clock_test else [],
            'keepalive_policy': 'periodic_independent_of_ack',
            'keepalive_interval_seconds': 10,
            'procontrol_mapping_commit': SOURCE_COMMIT,
            'osc_target': f'127.0.0.1:{args.osc_port}' if args.osc_port else None,
        }, indent=2, ensure_ascii=False) + '\n')
        print(f'Essai terminé : {out}', flush=True)
        return int(error is not None)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f'Erreur : {exc}')
