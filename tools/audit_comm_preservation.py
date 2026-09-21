#!/usr/bin/env python3
"""Audit hors ligne des dix captures comm et interprétation des blocs préservés.

N'importe pas le collecteur. Le rapport inclut des réglages propres à l'unité :
le conserver dans les archives privées, puis publier des conclusions choisies.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import hashlib
import json
from pathlib import Path

from audit_firmware_probe import audit_probe
from inspect_pcap import mac_address

FIELDS = {'comm-boot-vectors': (0, 8), 'comm-application-checksum': (0x30000, 2),
          'comm-network-settings': (0x34000, 10), 'comm-utility-settings': (0x3c000, 88),
          'comm-utility-mirror': (0x40000, 88)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def interpret(fields):
    if set(fields) != set(FIELDS) or any(len(fields[k]) != n for k, (_, n) in FIELDS.items()):
        raise ValueError('Champs ou longueurs incorrects')
    network = fields['comm-network-settings']
    checksum = int.from_bytes(network[8:], 'big')
    computed = sum(network[:8]) & 0xffff
    utility, mirror = (fields[name] for name in ('comm-utility-settings', 'comm-utility-mirror'))
    vectors = fields['comm-boot-vectors']
    return {'boot_vectors': {'initial_stack_pointer': int.from_bytes(vectors[:4], 'big'),
                             'reset_program_counter': int.from_bytes(vectors[4:], 'big')},
            'application_checksum': {'stored_word': int.from_bytes(fields['comm-application-checksum'], 'big'),
                                     'full_application_sum_verified': False},
            'network': {'stored_mac': network[:6].hex(':'),
                        'stored_protocol_type': int.from_bytes(network[6:8], 'big'),
                        'stored_checksum': checksum, 'computed_checksum': computed,
                        'record_valid': checksum != 0 and checksum == computed,
                        'effective_driver_configuration_verified': False},
            'utility': {'stored_marker_hex': utility[:8].hex(' '),
                        'stored_marker_matches_v1_37': utility[:8] == b'v1.37\0\0\0',
                        'mirror_marker_matches_v1_37': mirror[:8] == b'v1.37\0\0\0',
                        'flash_equals_ram': utility == mirror,
                        'different_offsets': [i for i, (a, b) in enumerate(zip(utility, mirror)) if a != b],
                        'snapshot_atomic': False}}


def audit(root, host, peer, fields=FIELDS, schema='comm-preservation-v1', interpreter=interpret):
    manifest_bytes = (root/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    byte_count = sum(size for _, size in fields.values())
    if (manifest.get('schema') != schema or not manifest.get('complete')
            or manifest.get('error') or manifest.get('bytes_per_pass') != byte_count
            or [p.get('number') for p in manifest.get('passes', [])] != [1, 2]):
        raise ValueError('Acquisition incomplète ou plan différent')
    report = {'archive_manifest_sha256': sha(manifest_bytes),
              'method': 'Independent PCAP reconstruction, exact fields and separate interpretation',
              'complete': True, 'passes': [], 'pcap_files': 0, 'frames': 0,
              'socket_drops': 0, 'bytes_per_pass': byte_count,
              'full_device_backup': False, 'ram_snapshot_atomic': False}
    previous_last = None
    seen = set()
    data_passes = []
    for entry in manifest['passes']:
        if not entry.get('complete') or [r.get('name') for r in entry['fields']] != list(fields):
            raise ValueError('Champs absents, réordonnés ou dupliqués')
        data = {}; audits = {}
        for record in entry['fields']:
            name = record['name']; folder = root/f'pass-{entry["number"]}'/name
            saved_bytes = (folder/'result.json').read_bytes()
            cached_bytes = (folder/'audit.json').read_bytes()
            if (sha(saved_bytes) != record['result_sha256'] or sha(cached_bytes) != record['audit_sha256']):
                raise ValueError('Résultat ou audit modifié')
            saved = json.loads(saved_bytes)
            if saved.get('socket_drops') != 0:
                raise ValueError('Pertes socket non nulles ou inconnues')
            current = audit_probe(folder, host, peer)
            if (current != json.loads(cached_bytes) or current.get('state') != name
                    or (current['address'], current['length']) != fields[name]):
                raise ValueError('Audit indépendant différent du résultat enregistré')
            if (current['first_ns'] > current['last_ns'] or current['pcap_sha256'] in seen
                    or (previous_last is not None and current['first_ns'] <= previous_last)):
                raise ValueError('Captures réutilisées, non chronologiques ou chevauchantes')
            previous_last = current['last_ns']; seen.add(current['pcap_sha256'])
            data[name] = bytes.fromhex(current['data_hex']); audits[name] = current
            report['pcap_files'] += 1; report['frames'] += current['counts']['frames']
        data_passes.append(data)
        row = {'number': entry['number'], 'fields': audits}
        if interpreter is not None: row['interpretation'] = interpreter(data)
        report['passes'].append(row)
    report['field_passes_equal'] = {name: data_passes[0][name] == data_passes[1][name] for name in fields}
    report['persistent_fields_equal'] = all(equal for name, equal in report['field_passes_equal'].items()
                                           if name != 'comm-utility-mirror')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--host', type=mac_address, default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer', type=mac_address, default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Nouveau fichier de sortie requis')
    result = audit(args.archive, bytes.fromhex(args.host.replace(':', '')), bytes.fromhex(args.peer.replace(':', '')))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'passes'}, indent=2))
    return int(not result['persistent_fields_equal'])


if __name__ == '__main__':
    raise SystemExit(main())
