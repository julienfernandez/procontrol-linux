#!/usr/bin/env python3
"""Appliquer hors ligne la table ProControl de ReaControl24 à un PCAP."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_diginet import audit
from inspect_pcap import mac_address
from procontrol_mapping import decode_body, SOURCE_COMMIT, TABLE_PATH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcap', type=Path)
    parser.add_argument('--mac', required=True, type=mac_address, help='MAC source de la console')
    parser.add_argument('--json', type=Path, help='Créer un nouveau rapport JSON')
    args = parser.parse_args()
    source = audit(args.pcap, args.mac)
    decoded = []
    # Toutes les réceptions cmd=0 restent présentes, broadcast compris.
    for row in source['frames']:
        if row.get('src') != args.mac or row.get('command_field') != 0:
            continue
        if 'error' in row or not row.get('body_sum16_match'):
            continue
        for index, event in enumerate(decode_body(bytes.fromhex(row['body_hex'])), 1):
            decoded.append({'frame': row['frame'], 'utc': row['utc'], 'destination': row['dst'],
                            'command_index': index, **event})
    summary = Counter(r.get('address', r.get('partial_address', '')) if r['status'] == 'mapped_reference'
                      else f"{r['status']} : {r['hex']}" for r in decoded)
    result = {'pcap': str(args.pcap), 'pcap_sha256': hashlib.sha256(args.pcap.read_bytes()).hexdigest(),
              'reference_commit': SOURCE_COMMIT,
              'mapping_sha256': hashlib.sha256(TABLE_PATH.read_bytes()).hexdigest(),
              'interpretation': 'Reference mappings, not new controlled physical validations. No network emission.',
              'status_counts': dict(Counter(r['status'] for r in decoded)),
              'audit_errors': source['errors'],
              'events': decoded}
    if args.json:
        with args.json.open('x') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(json.dumps(result['status_counts'], ensure_ascii=False))
    for name, count in summary.most_common(40):
        print(f'{count:5d}  {name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
