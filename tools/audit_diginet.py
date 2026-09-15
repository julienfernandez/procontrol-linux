#!/usr/bin/env python3
"""Audit hors ligne du schéma Digidesign candidat ; aucune émission réseau."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

from inspect_pcap import CaptureError, ethernet, mac_address, packets, timestamp


def candidate_header(payload):
    if len(payload) < 16:
        raise CaptureError('Moins de 16 octets pour l’en-tête candidat')
    length, field, sequence, ack, retry, command, count = struct.unpack('>HHIIHBB', payload[:16])
    if not 16 <= length <= len(payload):
        raise CaptureError(f'Longueur logique candidate {length} incompatible avec {len(payload)} octets capturés')
    body = payload[16:length]
    result = {
        'logical_length': length, 'field_at_payload_2': field,
        'sequence_candidate': sequence, 'ack_candidate': ack,
        'retry_candidate': retry, 'command_field': command, 'command_count_candidate': count,
        'body_hex': body.hex(' '), 'body_sum': sum(body),
        'body_sum16_match': field == (sum(body) & 0xffff),
        'trailing_bytes': len(payload) - length,
    }
    if command in (0xe0, 0xe1) and len(body) >= 33:
        result['announced_host_candidate'] = ':'.join(f'{byte:02x}' for byte in body[:6])
        result['version_candidate'] = body[15:24].split(b'\0', 1)[0].decode('ascii', errors='replace')
        result['device_candidate'] = body[24:33].split(b'\0', 1)[0].decode('ascii', errors='replace')
    prefix = bytes.fromhex('f0 13 00 70 00')
    if body.startswith(prefix) and body.endswith(b'\xf7'):
        result['text_after_70_candidate'] = body[len(prefix):-1].decode('ascii', errors='replace')
    return result


def audit(path, mac=None):
    rows, errors, total = [], [], 0
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    for number, (ts, data, wirelen) in enumerate(packets(path), 1):
        total += 1
        try:
            src, dst, kind, tags, payload = ethernet(data)
        except CaptureError as exc:
            errors.append({'frame': number, 'error': str(exc)})
            continue
        if kind != '0x885f' or (mac and mac not in (src, dst)):
            continue
        row = {'frame': number, 'utc': timestamp(ts), 'timestamp_ns': ts,
               'src': src, 'dst': dst, 'vlan_ids': tags,
               'captured_length': len(data), 'wire_length': wirelen}
        try:
            row.update(candidate_header(payload))
        except CaptureError as exc:
            row['error'] = str(exc)
            errors.append({'frame': number, 'error': str(exc)})
        rows.append(row)
    valid = [r for r in rows if 'error' not in r]
    return {
        'source': str(path), 'sha256': digest.hexdigest(), 'total_frames': total,
        'selected_frames': len(rows), 'valid_candidate_headers': len(valid),
        'body_sum16_matches': sum(r['body_sum16_match'] for r in valid),
        'sums_reaching_65536': sum(r['body_sum'] >= 65536 for r in valid),
        'errors': errors, 'frames': rows,
        'interpretation': 'Schéma candidat comparé aux octets ; aucune sémantique de commande ni vérification par le matériel démontrée.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcap', type=Path)
    parser.add_argument('--mac', type=mac_address)
    parser.add_argument('--json', type=Path, help='Nouveau fichier JSON de preuve ; refuse de remplacer un fichier existant')
    args = parser.parse_args()
    try:
        report = audit(args.pcap, args.mac)
        if args.json:
            with args.json.open('x') as output:
                json.dump(report, output, indent=2, ensure_ascii=False)
                output.write('\n')
        valid = [r for r in report['frames'] if 'error' not in r]
        print(f"Fichier : {args.pcap}\nSHA-256 : {report['sha256']}")
        print(f"Trames totales : {report['total_frames']} ; 0x885f sélectionnées : {report['selected_frames']}")
        print(f"Champ +2 = somme du corps sur 16 bits : {report['body_sum16_matches']}/{len(valid)}")
        print(f"Sommes atteignant 65536 : {report['sums_reaching_65536']} (zéro signifie que le débordement n’est pas testé par ces données)")
        print('Identifications candidates :', dict(Counter((r.get('device_candidate'), r.get('version_candidate')) for r in valid if 'device_candidate' in r)))
        print('Champs commande :', {f'0x{k:02x}': v for k, v in Counter(r['command_field'] for r in valid).items()})
        print('Textes après f0 13 00 70 00 :', dict(Counter(r['text_after_70_candidate'] for r in valid if 'text_after_70_candidate' in r)))
        for error in report['errors']:
            print('Erreur :', error, file=sys.stderr)
        print(report['interpretation'])
        return int(bool(report['errors']))
    except (OSError, CaptureError) as exc:
        print(f'Erreur : {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
