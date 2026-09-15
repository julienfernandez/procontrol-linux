#!/usr/bin/env python3
"""Trackpad ProControl : décodage hors ligne, aucune injection d'entrée."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_diginet import audit
from inspect_pcap import mac_address


def decode_pointer(body):
    """Format observé f0 13 00 60 01 H X Y f7, coordonnées signées sur 8 bits.

    L'empaquetage correspond aux coordonnées du protocole souris Microsoft
    décrit par Linux drivers/input/mouse/sermouse.c, sans son bit de synchronisation.
    C'est une correspondance d'encodage, pas la preuve d'un transport série.
    Les bits 4/5 sont exposés bruts tant que les clics ne sont pas validés.
    """
    if len(body) != 9 or body[:5] != bytes.fromhex('f0 13 00 60 01') or body[-1] != 0xf7:
        return None
    h, x, y = body[5:8]
    if h > 0x3f or x > 0x3f or y > 0x3f:
        return None
    def signed(value):
        return value - 256 if value >= 128 else value
    return {'dx': signed(((h & 3) << 6) | x),
            'dy': signed(((h & 12) << 4) | y),
            'button_bits': h & 0x30}


def report(path, peer):
    source = audit(path, peer)
    events, seen = [], set()
    for row in source['frames']:
        if (row.get('src') != peer or row.get('dst') == 'ff:ff:ff:ff:ff:ff'
                or row.get('command_field') != 0 or not row.get('body_sum16_match')):
            continue
        decoded = decode_pointer(bytes.fromhex(row['body_hex']))
        if decoded is None:
            continue
        key = (row['sequence_candidate'], row['body_hex'])
        duplicate = key in seen
        seen.add(key)
        events.append({k: row[k] for k in ('frame', 'utc', 'timestamp_ns', 'body_hex')}
                      | decoded | {'duplicate': duplicate})
    groups = []
    for event in (e for e in events if not e['duplicate']):
        if not groups or event['timestamp_ns'] - groups[-1][-1]['timestamp_ns'] > 1_000_000_000:
            groups.append([])
        groups[-1].append(event)
    bursts = []
    for group in groups:
        bursts.append({'first_frame': group[0]['frame'], 'last_frame': group[-1]['frame'],
                       'start_utc': group[0]['utc'], 'end_utc': group[-1]['utc'], 'count': len(group),
                       'sum_dx': sum(e['dx'] for e in group), 'sum_dy': sum(e['dy'] for e in group),
                       'abs_dx': sum(abs(e['dx']) for e in group), 'abs_dy': sum(abs(e['dy']) for e in group)})
    return {'pcap': str(path), 'sha256': source['sha256'], 'audit_errors': source['errors'],
            'events_count': len(events), 'duplicate_count': sum(e['duplicate'] for e in events),
            'button_bits_counts': dict(Counter(e['button_bits'] for e in events)),
            'interpretation': 'Relative X/Y from observed encoding; button bits unvalidated; no input injection.',
            'bursts': bursts, 'events': events}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pcap', type=Path)
    p.add_argument('--mac', required=True, type=mac_address)
    p.add_argument('--json', type=Path)
    args = p.parse_args()
    result = report(args.pcap, args.mac)
    if args.json:
        with args.json.open('x') as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
            out.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'events'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
