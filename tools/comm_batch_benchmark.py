#!/usr/bin/env python3
"""Pilote fixe : comparer les lectures comm de 16 et 32 octets sur 256 octets connus.

Aperçu par défaut ; compteur de débordement avant/après chaque essai,
audit indépendant des captures, arrêt sans répétition dès une anomalie.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics

from audit_comm_archive import audit_chunk
from audit_firmware_probe import audit_probe
from comm_preservation import preflight, run_live
from firmware_probe import run_probe
from inspect_pcap import mac_address
from session_probe import mac_bytes

START, LENGTH = 0x2a3d0, 256
ORDER = (16, 32, 32, 16)*2
REFERENCE_SHA = 'e2945b200be72745afb10a3bc68300b4dc3b5adba90b3a8157cec37f051e1af8'
COUNTER = 'comm-diagnostic-overflows'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reference_bytes(path):
    full = path.read_bytes()
    if len(full) != 63716 or sha(full) != REFERENCE_SHA:
        raise ValueError('Référence CODE-26-00020400.bin différente du segment vérifié')
    return full[START-0x20400:START-0x20400+LENGTH]


def acquire(rx, tx, flow, output, host, peer, reference):
    if len(reference) != LENGTH:
        raise ValueError('Référence du pilote de 256 octets requise')
    sources = ('comm_batch_benchmark.py', 'firmware_probe.py', 'audit_firmware_probe.py',
               'audit_comm_archive.py', 'comm_preservation.py')
    manifest = {'schema': 'comm-batch-benchmark-v1', 'complete': False, 'error': None,
                'started_utc': datetime.now(timezone.utc).isoformat(), 'runs': [],
                'address': START, 'length': LENGTH, 'order': ORDER,
                'reference_sha256': sha(reference), 'physical_latency_validated': False,
                'source_sha256': {n: sha(Path(__file__).with_name(n).read_bytes()) for n in sources}}

    def save():
        manifest['updated_utc'] = datetime.now(timezone.utc).isoformat()
        path = output/'manifest.next.json'
        path.write_text(json.dumps(manifest, indent=2)+'\n'); path.replace(output/'manifest.json')

    def read(folder, **kwargs):
        folder.mkdir(mode=0o700)
        saved = run_probe(rx, tx, flow, folder, **kwargs)
        if saved['error'] is not None:
            raise RuntimeError(f'{folder.name}: {saved["error"]}')
        if saved.get('socket_drops') != 0:
            raise RuntimeError(f'{folder.name}: pertes socket non nulles ou inconnues')
        return saved

    def counter(folder):
        read(folder, state=COUNTER, batch_size=16)
        checked = audit_probe(folder, host, peer)
        (folder/'audit.json').write_text(json.dumps(checked, indent=2)+'\n')
        return int.from_bytes(bytes.fromhex(checked['data_hex']), 'big')

    save()
    try:
        for number, batch in enumerate(ORDER, 1):
            folder = output/f'run-{number:02d}-batch-{batch}'; folder.mkdir(mode=0o700)
            entry = {'number': number, 'batch_size': batch, 'complete': False}
            manifest['runs'].append(entry); save()
            entry['overflows_before'] = counter(folder/'before'); save()
            saved = read(folder/'code', address=START, length=LENGTH, batch_size=batch,
                         experimental_batch32=batch == 32)
            data, checked = audit_chunk(folder/'code/traffic.pcap', START, LENGTH, host, peer,
                                        expected_batch_size=batch)
            (folder/'code/audit.json').write_text(json.dumps(checked, indent=2)+'\n')
            if (data != reference or data != (folder/'code/memory.bin').read_bytes()
                    or saved['pcap_sha256'] != checked['pcap_sha256']
                    or saved['memory_sha256'] != sha(data)
                    or bytes.fromhex(saved['read_bytes_hex']) != data):
                raise ValueError('Code reconstruit, référence ou résultat enregistré différents')
            elapsed = (datetime.fromisoformat(saved['finished_utc'])-
                       datetime.fromisoformat(saved['started_utc'])).total_seconds()
            if elapsed <= 0:
                raise ValueError('Durée de lecture non positive')
            entry.update(elapsed_seconds=elapsed, pcap_sha256=checked['pcap_sha256'],
                         counts=checked['counts'], reference_matches=True)
            entry['overflows_after'] = counter(folder/'after'); save()
            if entry['overflows_before'] != entry['overflows_after']:
                raise ValueError('Compteur de débordement modifié pendant le pilote')
            entry['complete'] = True; save()
        medians = {str(b): statistics.median(r['elapsed_seconds'] for r in manifest['runs']
                                            if r['batch_size'] == b) for b in (16, 32)}
        manifest.update(complete=True, median_seconds=medians,
                        median_ratio_16_over_32=medians['16']/medians['32'])
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        manifest['error'] = str(exc) or type(exc).__name__
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat(); save()
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--interface', default='enp0s25')
    parser.add_argument('--mac', type=mac_address, default='00:a0:7e:a0:ad:9c')
    args = parser.parse_args(argv)
    if not args.send:
        print(json.dumps({'network_opened': False, 'address': START, 'length': LENGTH,
                          'order': ORDER, 'counter_before_after': COUNTER}, indent=2)); return 0
    if os.geteuid() == 0 or args.output is None or args.output.exists() or args.reference is None:
        parser.error('Compte utilisateur, référence et nouveau dossier --output requis')
    reference = reference_bytes(args.reference)
    interface = Path('/sys/class/net')/args.interface
    if (not args.interface or '/' in args.interface or not (interface/'type').exists()
            or (interface/'type').read_text().strip() != '1' or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host = (interface/'address').read_text().strip(); peer = mac_bytes(args.mac)
    if not any(peer) or peer[0]&1 or peer == mac_bytes(host):
        parser.error('MAC console unicast distincte requise')
    status = preflight(); args.output.mkdir(mode=0o700, parents=True)
    (args.output/'preflight.json').write_text(json.dumps(status, indent=2)+'\n')
    def interrupted(*_): raise KeyboardInterrupt('SIGTERM')
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        result = run_live(args.interface, host, args.mac, args.output,
                          collector=partial(acquire, reference=reference))
    finally:
        signal.signal(signal.SIGTERM, previous)
    print(json.dumps({k:v for k,v in result.items() if k != 'runs'}, indent=2))
    return int(not result['complete'])


if __name__ == '__main__':
    raise SystemExit(main())
