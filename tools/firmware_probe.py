#!/usr/bin/env python3
"""Interrogation diagnostic ProControl bornée, sous le verrou de la passerelle.

Par défaut : aperçu hors ligne. Requête de version comm V, puis lecture
optionnelle de 1..256 octets dans les segments de code connus du firmware 1.37.
La cible fader autorise uniquement la version V, sans lecture mémoire.
Champs comm nommés (RAM, démarrage, réglages) et fenêtres RX identifiés séparément.
Aucun interpréteur libre, accès MMIO, écriture des octets ciblés ou effacement.
La passerelle doit être arrêtée avant --send et relancée après l'expérience.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import struct
import time

from inspect_pcap import CaptureError, mac_address
from pcap_writer import write_header, write_packet
from procontrold import ConsoleSession, packet_sockets
from session_probe import mac_bytes

ROOT = Path(__file__).resolve().parents[1]
VERSION_REQUEST = bytes.fromhex('f0 13 00 70 00 56 f7')
PREFIX = bytes.fromhex('f0 13 00 70 00')
EXPECTED_VERSION = b'COMv1.37\n\r'
FADER_PREFIX = bytes.fromhex('f0 13 00 70 01')
FADER_VERSION = b'FDRv1.37\n\r'
PROFILES = {'comm': (PREFIX, EXPECTED_VERSION),
            'fader': (FADER_PREFIX, FADER_VERSION)}
CODE_SEGMENTS = ((0x20000, 0x20008), (0x20064, 0x20080),
                 (0x20100, 0x20110), (0x20400, 0x2fce4))
# Exact fields identified in comm 1.37; no arbitrary memory address mode.
# Preservation ranges: docs/preservation-layout-2026-09-21.md (static analysis).
STATE_FIELDS = {'fader-version': (0x5094a, 10),
                'fader-errors': (0x509ba, 4),
                'fader-version-valid': (0x509c2, 4),
                'fader-tx-ring': (0x6c10e, 24),
                'fader-rx-ring': (0x6bf0e, 24),
                'fader-touch-state': (0x508ea, 16),
                'fader-mode': (0x5095c, 1),
                'comm-boot-vectors': (0x00000, 8),
                'comm-application-checksum': (0x30000, 2),
                'comm-network-settings': (0x34000, 10),
                'comm-utility-settings': (0x3c000, 88),
                'comm-utility-mirror': (0x40000, 88),
                'comm-diagnostic-overflows': (0x6b51e, 4),
                'comm-app-gap-20008': (0x20008, 92),
                'comm-app-gap-20080': (0x20080, 128),
                'comm-app-gap-20110': (0x20110, 752),
                'comm-app-gap-2fce4': (0x2fce4, 796)}
RX_BUFFER_START = 0x6bf26
RX_BUFFER_SIZE = 488


def read_selection(address, length, batch_size, target, state, ring_offset=None):
    if ring_offset is not None:
        if (target != 'comm' or state is not None or address is not None
                or not 1 <= length <= 256 or not 0 <= ring_offset < RX_BUFFER_SIZE
                or ring_offset+length > RX_BUFFER_SIZE):
            raise ValueError('Fenêtre RX limitée au tampon RAM comm connu, sans adresse libre')
        return RX_BUFFER_START+ring_offset, length
    if state is None:
        return address, length
    if (state not in STATE_FIELDS or target != 'comm' or address is not None
            or length != 1):
        raise ValueError('Champ nommé : cible comm seule, sans adresse ni longueur personnalisées')
    return STATE_FIELDS[state]


def requests_for(address=None, length=1, batch_size=1, target='comm', state=None, ring_offset=None,
                 experimental_batch32=False):
    """Absolute address per byte: an absent/duplicate reply cannot shift reads."""
    if target not in PROFILES:
        raise ValueError('Cible diagnostic inconnue')
    if experimental_batch32 and (target!='comm' or state is not None or ring_offset is not None
            or address!=0x2a3d0 or length!=256 or batch_size!=32):
        raise ValueError('Pilote batch32 limité au bloc comm 0x2a3d0 de 256 octets')
    if target == 'fader' and (address is not None or length != 1 or batch_size != 1):
        raise ValueError('Cible fader limitée à la version ; lecture mémoire non validée')
    address, length = read_selection(address, length, batch_size, target, state, ring_offset)
    prefix, _ = PROFILES[target]
    result = [(None, prefix + b'V\xf7')]
    if not 1 <= batch_size <= (32 if experimental_batch32 else 16):
        raise ValueError('Lot limité à 1..16 octets ; 32 réservé au pilote explicite')
    if address is not None:
        if state is None and ring_offset is None and (not 1 <= length <= 256 or not any(
                lo <= address and address+length <= hi for lo, hi in CODE_SEGMENTS)):
            raise ValueError('Lecture limitée à 1..256 octets dans un segment comm 1.37 connu')
        for read_target in range(address, address+length, batch_size):
            size = min(batch_size, address+length-read_target)
            reads = b'm' if batch_size == 1 else b'M'*size
            result.append((read_target, PREFIX + f'A{read_target:08X}'.encode('ascii') + reads + b'\xf7'))
    return result


def memory_reply(payload, address):
    # The firmware prints the byte twice: hex and literal, including control
    # characters. Do not split on lines or assume MIDI's seven-bit data rule.
    match = re.fullmatch(rb'([0-9a-fA-F]{8}): ([0-9a-fA-F]{2}) \'(.)\'\n\r', payload, re.DOTALL)
    if match and int(match[1], 16) == address:
        value = int(match[2], 16)
        if value != match[3][0]:
            raise ValueError('Les deux représentations de l’octet lu divergent')
        return value
    return None


@contextmanager
def exclusive_console(runtime):
    """Same inode and flock as procontrold, held before opening any socket."""
    with (runtime / 'daemon.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Passerelle active : essai refusé, aucune socket ouverte') from None
        yield


def diagnostic_payload(body, target='comm'):
    # Deliberately require one whole envelope; preserve unexpected bodies in
    # the PCAP instead of interpreting the existing MIDI-like splitter as a
    # complete grammar (memory replies may contain bytes with their high bit).
    prefix, _ = PROFILES[target]
    if body.startswith(prefix) and body.endswith(b'\xf7'):
        return body[len(prefix):-1]
    return None


def diagnostic_payloads(body, target='comm'):
    """Recognized response sizes, never a split on f7 inside a literal byte.

    A batch can place multiple complete envelopes in one DigiNet body. Reject
    ambiguous concatenations instead of guessing where a raw memory byte ends.
    Unknown standalone envelopes remain available to the version gate/log.
    """
    result = []
    prefix, expected_version = PROFILES[target]
    while body.startswith(prefix):
        for size in (8, 16, 24):
            if len(body) < size or body[size-1] != 0xf7:
                continue
            payload = body[5:size-1]
            if (payload == b'\n\r' or
                    (len(payload) == 10 and payload.startswith(expected_version[:3]) and payload.endswith(b'\n\r')) or
                    re.fullmatch(rb"[0-9a-fA-F]{8}: [0-9a-fA-F]{2} '.'\n\r", payload, re.DOTALL)):
                result.append(payload)
                body = body[size:]
                break
        else:
            if not result:
                payload = diagnostic_payload(body, target)
                return [payload] if payload is not None else []
            raise ValueError('Enveloppes diagnostic concaténées non reconnues')
    if body and result:
        raise ValueError('Octets résiduels après une réponse diagnostic')
    return result


def run_probe(rx, tx, flow, output, connect_timeout=15., reply_timeout=2.,
              address=None, length=1, batch_size=1, target='comm', state=None, ring_offset=None,
              experimental_batch32=False):
    """One outstanding request, no retries, at most 50 Hz, version before reads."""
    requests = requests_for(address, length, batch_size, target, state, ring_offset, experimental_batch32)
    address, length = read_selection(address, length, batch_size, target, state, ring_offset)
    _, expected_version = PROFILES[target]
    report = {'started_utc': datetime.now(timezone.utc).isoformat(),
              'probe_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'probe': ('comm_rx_buffer_read' if ring_offset is not None else
                        ('comm_state_read' if state else 'comm_code_read')) if address is not None else f'{target}_version',
              'read_state': state,
              'read_ring_offset': ring_offset,
              'target': target, 'expected_version_hex': expected_version.hex(' '),
              'request_hex': requests[0][1].hex(' '),
              'request_sequence': None, 'ack_received': False,
              'responses': [], 'announcements': [], 'error': None,
              'capture_clock': 'host userspace time_ns, microsecond PCAP',
              'frames_tx': 0, 'frames_rx': 0, 'transactions': [],
              'read_address': address, 'read_length': length if address is not None else 0,
              'batch_size': batch_size}
    if experimental_batch32:report['experimental_batch32']=True
    deadline = time.monotonic() + connect_timeout
    request_time = None
    next_send = 0.
    cursor = 0
    transaction = None
    finished = False
    values = bytearray()
    batch_values = {}
    received_sequences = set()
    path = output / 'traffic.pcap'
    with path.open('xb') as capture:
        write_header(capture)

        def send(frames):
            for frame in frames:
                if frame[28] == 0xa0:
                    time.sleep(.0008)
                if tx.send(frame) != len(frame):
                    raise OSError('Émission Ethernet incomplète')
                write_packet(capture, time.time_ns(), frame)
                report['frames_tx'] += 1

        try:
            while time.monotonic() < deadline:
                now = time.monotonic()
                send(flow.tick(now))
                if transaction is not None and flow.phase != 'online':
                    raise RuntimeError('Session perdue après la requête ; aucun nouvel essai')
                if not finished and request_time is None and flow.phase == 'online' and now >= next_send:
                    flow.session.sequence += 1
                    read_target, body = requests[cursor]
                    batch_values = {}
                    transaction = {'index': cursor, 'address': read_target, 'request_hex': body.hex(' '),
                                   'length': min(batch_size, address+length-read_target) if read_target is not None else 0,
                                   'sequence': flow.session.sequence, 'ack': False, 'matched': False}
                    report['transactions'].append(transaction)
                    if cursor == 0:
                        report['request_sequence'] = flow.session.sequence
                    send([flow.session.frame(0, count=1, sequence=flow.session.sequence,
                                             body=body)])
                    request_time = now
                    deadline = now + reply_timeout
                if not select.select([rx], [], [], min(.02, max(0., deadline-now)))[0]:
                    continue
                frame = rx.recv(65535)
                if len(frame) < 30 or frame[6:12] != flow.session.peer:
                    continue
                write_packet(capture, time.time_ns(), frame)
                report['frames_rx'] += 1
                frames, header = flow.receive(frame, time.monotonic())
                send(frames)
                if header is None:
                    continue
                if transaction is not None and (flow.phase != 'online' or header['command_field'] == 0xe0):
                    raise RuntimeError('Session perdue après la requête ; aucun nouvel essai')
                if header['command_field'] in (0xe0, 0xe1):
                    identity = {key: header.get(key) for key in
                                ('device_candidate', 'version_candidate', 'announced_host_candidate')}
                    if identity not in report['announcements']:
                        report['announcements'].append(identity)
                if transaction is None or frame[:6] != flow.session.host:
                    continue
                if header['command_field'] == 0xa0:
                    if header['ack_candidate'] == transaction['sequence']:
                        transaction['ack'] = True
                        if cursor == 0:
                            report['ack_received'] = True
                elif header['command_field'] == 0:
                    payloads = diagnostic_payloads(bytes.fromhex(header['body_hex']), target)
                    if payloads:
                        sequence = header['sequence_candidate']
                        duplicate = sequence in received_sequences
                        received_sequences.add(sequence)
                    for payload in payloads:
                        report['responses'].append({'sequence': sequence, 'duplicate': duplicate,
                            'request_index': transaction['index'],
                            'delay_ms': round((time.monotonic()-(request_time or now))*1000, 3),
                            'payload_hex': payload.hex(' '),
                            'payload_ascii': payload.decode('ascii', errors='backslashreplace')})
                        if not duplicate and not transaction['matched']:
                            read_target = transaction['address']
                            if read_target is None:
                                if payload.startswith(expected_version[:3]) and payload != expected_version:
                                    raise RuntimeError(f'Version {target} différente de 1.37 ; arrêt')
                                transaction['matched'] = payload == expected_version
                            else:
                                for item in range(read_target, read_target+transaction['length']):
                                    value = memory_reply(payload, item)
                                    if value is not None:
                                        if item in batch_values and batch_values[item] != value:
                                            raise ValueError('Deux réponses différentes pour la même adresse')
                                        batch_values[item] = value
                                        break
                                transaction['matched'] = len(batch_values) == transaction['length']
                if not finished and request_time is not None and transaction['ack'] and transaction['matched']:
                    if transaction['address'] is not None:
                        values.extend(batch_values[item] for item in sorted(batch_values))
                    cursor += 1
                    next_send = (request_time or now) + .02
                    request_time = None
                    if cursor == len(requests):
                        finished = True
                        deadline = time.monotonic() + .05
                    else:
                        # We already have an online session; this merely allows
                        # the cadence delay before the next bounded transaction.
                        deadline = next_send + reply_timeout
            if not report['transactions']:
                report['error'] = 'Console non connectée dans le délai'
            elif not finished:
                report['error'] = 'Transaction diagnostic incomplète dans le délai (ACK insuffisant)'
        except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
            report['error'] = str(exc) or type(exc).__name__
        finally:
            if rx.family == socket.AF_PACKET:
                # SOL_PACKET/PACKET_STATISTICS, since socket creation. Includes
                # traffic ignored above; counters are kernel loss evidence.
                try:
                    report['socket_packets'], report['socket_drops'] = struct.unpack(
                        'II', rx.getsockopt(263, 6, 8))
                except OSError as exc:
                    report['socket_statistics_error'] = str(exc)
    report['pcap_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    report['read_bytes_hex'] = values.hex(' ')
    if finished and report['error'] is None and address is not None:
        (output/'memory.bin').write_bytes(values)
        report['memory_sha256'] = hashlib.sha256(values).hexdigest()
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'result.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    return report


def run_fader_version(rx, tx, flow, output, connect_timeout=15., reply_timeout=2.):
    """Confirm comm in the same session before the one fader version request."""
    prerequisite = output/'comm-version'
    prerequisite.mkdir(mode=0o700)
    comm = run_probe(rx, tx, flow, prerequisite, connect_timeout, reply_timeout)
    if comm['error']:
        result = {'probe': 'fader_version', 'target': 'fader',
                  'error': 'Version comm non validée ; aucune requête fader envoyée',
                  'transactions': [], 'responses': [], 'fader_request_sent': False}
    else:
        result = run_probe(rx, tx, flow, output, connect_timeout, reply_timeout, target='fader')
        result['fader_request_sent'] = bool(result['transactions'])
    result['comm_prerequisite'] = {'result': 'comm-version/result.json',
        'result_sha256': hashlib.sha256((prerequisite/'result.json').read_bytes()).hexdigest(),
        'error': comm['error']}
    (output/'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='enp0s25')
    parser.add_argument('--mac', type=mac_address, default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--target', choices=tuple(PROFILES), default='comm',
                        help='comm : version/lecture de code ; fader : version seulement')
    parser.add_argument('--read-code', type=lambda value: int(value, 0), metavar='ADDRESS')
    parser.add_argument('--read-state', choices=tuple(STATE_FIELDS),
                        help='Champ comm 1.37 précisément identifié ; RAM ou plage persistante bornée')
    parser.add_argument('--read-ring-offset', type=lambda value: int(value, 0),
                        help='Offset 0..487 dans le tampon RX série comm ; au plus 256 octets sans bouclage')
    parser.add_argument('--length', type=int, default=1)
    parser.add_argument('--batch-size', type=int, default=1, help='1..16 octets par requête')
    parser.add_argument('--experimental-batch32',action='store_true',
                        help='Pilote seulement : --read-code 0x2a3d0 --length 256 --batch-size 32')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args(argv)
    try:
        requests = requests_for(args.read_code, args.length, args.batch_size, args.target,
                                args.read_state, args.read_ring_offset, args.experimental_batch32)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.send:
        if args.target == 'fader':
            requests = [(None, VERSION_REQUEST)] + requests
        print(json.dumps({'requests_hex': [body.hex(' ') for _, body in requests],
                          'network_opened': False, 'exclusive_lock': str(ROOT/'run/daemon.lock')}))
        return 0
    if os.geteuid() == 0:
        parser.error('Lancer avec le compte utilisateur, via le helper Ethernet installé')
    if args.output is None or args.output.exists():
        parser.error('--output doit désigner un nouveau dossier')
    if not args.interface or '/' in args.interface:
        parser.error('Interface invalide')
    interface = Path('/sys/class/net') / args.interface
    if (not (interface/'type').exists() or (interface/'type').read_text().strip() != '1'
            or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host = (interface/'address').read_text().strip()
    peer = mac_bytes(args.mac)
    if not any(peer) or peer[0] & 1 or peer == mac_bytes(host):
        parser.error('MAC console unicast distincte requise')
    with exclusive_console(ROOT/'run'):
        rx, tx = packet_sockets(args.interface)
        with rx, tx:
            rx.bind((args.interface, 0)); tx.bind((args.interface, 0))
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)
            args.output.mkdir(mode=0o700, parents=True)
            flow = ConsoleSession(host, args.mac)
            if args.target == 'fader':
                result = run_fader_version(rx, tx, flow, args.output)
            else:
                result = run_probe(rx, tx, flow, args.output,
                                   address=args.read_code, length=args.length, batch_size=args.batch_size,
                                   target=args.target, state=args.read_state, ring_offset=args.read_ring_offset,
                                   experimental_batch32=args.experimental_batch32)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return int(result['error'] is not None)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        raise SystemExit(str(exc))
