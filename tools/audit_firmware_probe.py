#!/usr/bin/env python3
"""Audit hors ligne d'une capture clôturée de version ou d'un champ nommé comm.

Un audit fidèle peut confirmer un essai incomplet : observed_complete reste
alors false. Aucune socket, aucun accès à la console et aucune écriture mémoire.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_comm_archive import audit_chunk
from audit_diginet import candidate_header
from inspect_pcap import packets, mac_address

VERSIONS = {'comm': (bytes.fromhex('f0 13 00 70 00'), b'COMv1.37\n\r'),
            'fader': (bytes.fromhex('f0 13 00 70 01'), b'FDRv1.37\n\r')}
STATES = {'fader-version': (0x5094a,10), 'fader-version-valid': (0x509c2,4),
          'fader-errors': (0x509ba,4), 'fader-tx-ring': (0x6c10e,24),
          'fader-rx-ring': (0x6bf0e,24), 'fader-touch-state': (0x508ea,16),
          'fader-mode': (0x5095c,1),
          'comm-boot-vectors': (0x00000,8),
          'comm-application-checksum': (0x30000,2),
          'comm-network-settings': (0x34000,10),
          'comm-utility-settings': (0x3c000,88),
          'comm-utility-mirror': (0x40000,88),
          'comm-diagnostic-overflows': (0x6b51e,4),
          'comm-app-gap-20008': (0x20008,92), 'comm-app-gap-20080': (0x20080,128),
          'comm-app-gap-20110': (0x20110,752), 'comm-app-gap-2fce4': (0x2fce4,796)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit_version(path, target, host, peer):
    prefix, expected = VERSIONS[target]
    request = None
    ack = None
    responses = []
    seen = {}
    counts = Counter()
    for number,(stamp,frame,wirelen) in enumerate(packets(path),1):
        if len(frame) != wirelen or len(frame) < 30 or frame[12:14] != b'\x88\x5f':
            raise ValueError('Trame tronquée ou hors DigiNet')
        header = candidate_header(frame[14:])
        if not header['body_sum16_match']:
            raise ValueError('Somme du corps incorrecte')
        counts['frames'] += 1
        body = bytes.fromhex(header['body_hex'])
        command = header['command_field']
        if frame[6:12] == host and frame[:6] == peer:
            if command != 0 or body == b'\0':
                continue
            if body != prefix+b'V\xf7' or request is not None or header['command_count_candidate'] != 1:
                raise ValueError('Requête hors du plan de version unique')
            request = {'frame': number, 'timestamp_ns': stamp,
                       'sequence': header['sequence_candidate'], 'body_hex': body.hex(' ')}
        elif frame[6:12] == peer and frame[:6] == host:
            if command == 0xa0 and request and header['ack_candidate'] == request['sequence']:
                ack = {'frame': number, 'timestamp_ns': stamp}
            elif command == 0:
                if not body.startswith(prefix):
                    counts['other_input_frames'] += 1
                    continue
                if (request is None or len(body) != 16 or body[-1] != 0xf7
                        or header['command_count_candidate'] != 1):
                    raise ValueError('Réponse de version inattendue')
                sequence = header['sequence_candidate']
                if sequence in seen:
                    if seen[sequence] != body:
                        raise ValueError('Même séquence avec des données différentes')
                    counts['duplicates'] += 1
                    continue
                seen[sequence] = body
                responses.append({'frame': number, 'timestamp_ns': stamp,
                    'sequence': sequence, 'payload_hex': body[5:-1].hex(' '),
                    'payload_ascii': body[5:-1].decode('ascii',errors='backslashreplace'),
                    'request_to_response_ms': (stamp-request['timestamp_ns'])/1e6})
        elif frame[6:12] != peer or frame[:6] != b'\xff'*6:
            raise ValueError('Émetteur ou destinataire inattendu')
    complete = bool(request and ack and len(responses) == 1
                    and bytes.fromhex(responses[0]['payload_hex']) == expected)
    return {'method': 'Independent fixed-length version envelope audit',
            'target': target, 'counts': dict(counts), 'request': request,
            'ack': ack, 'responses': responses, 'observed_complete': complete,
            'pcap_sha256': sha(path.read_bytes())}


def audit_probe(folder, host, peer, expected_batch_size=None):
    saved = json.loads((folder/'result.json').read_text())
    path = folder/'traffic.pcap'
    if saved.get('read_state') or saved.get('read_ring_offset') is not None:
        if saved['target'] != 'comm':
            raise ValueError('Lecture de champ hors cible comm')
        if saved.get('read_state'):
            start,length = STATES[saved['read_state']]
        else:
            offset,length = saved['read_ring_offset'],saved['read_length']
            if not 1 <= length <= 256 or not 0 <= offset or offset+length > 488:
                raise ValueError('Fenêtre RX hors limites')
            start = 0x6bf26+offset
        if (saved['read_address'],saved['read_length']) != (start,length):
            raise ValueError('Bornes du champ incohérentes')
        data,result = audit_chunk(path,start,length,host,peer,expected_batch_size=expected_batch_size)
        if data != (folder/'memory.bin').read_bytes() or data != bytes.fromhex(saved['read_bytes_hex']):
            raise ValueError('Mémoire reconstruite différente des fichiers enregistrés')
        if saved['memory_sha256'] != sha(data):
            raise ValueError('Empreinte mémoire incohérente')
        result.update({'method': 'Independent addressed-byte PCAP reconstruction',
                       'state': saved.get('read_state'), 'ring_offset': saved.get('read_ring_offset'),
                       'address': start, 'length': length,
                       'data_hex': data.hex(' '), 'observed_complete': True})
    else:
        result = audit_version(path,saved['target'],host,peer)
    if result['pcap_sha256'] != saved['pcap_sha256']:
        raise ValueError('Capture différente du rapport')
    if result['observed_complete'] != (saved['error'] is None):
        raise ValueError('Conclusion indépendante différente du rapport')
    result['result_sha256'] = sha((folder/'result.json').read_bytes())
    result['matches_report'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--host',type=mac_address,default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',type=mac_address,default='00:a0:7e:a0:ad:9c')
    args = parser.parse_args()
    report = audit_probe(args.folder,bytes.fromhex(args.host.replace(':','')),
                         bytes.fromhex(args.peer.replace(':','')))
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__ == '__main__':
    main()
