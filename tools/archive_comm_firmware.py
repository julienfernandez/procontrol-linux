#!/usr/bin/env python3
"""Deux acquisitions des quatre segments connus de comm 1.37 ; aucun flashage.

Le démon doit être arrêté. Le verrou Ethernet reste détenu pendant les deux
passes ; chaque bloc conserve capture, réponses et empreintes. Aucun trou
d'adressage, ROM inconnue, RAM ou EEPROM n'est lu par cet outil.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import time

from firmware_probe import ROOT, CODE_SEGMENTS, exclusive_console, run_probe
from inspect_pcap import mac_address
from procontrold import ConsoleSession, packet_sockets
from session_probe import mac_bytes

REFERENCE_SHA256 = (
    '230e4cc0835ad1fbd6cac5b383d422b9f270ca2000d5072a428b9b035f235b03',
    '64e9a8906127c7ba897b21e6e2d87336c8957576d3d6ed13070a0043f8209074',
    'ab98bf58a7b2442d97c4c9c61d414a231ee743687c840983d9aa7ea0d2e07bf2',
    'e2945b200be72745afb10a3bc68300b4dc3b5adba90b3a8157cec37f051e1af8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def chunk_plan():
    return [(start, min(256, hi-start)) for lo, hi in CODE_SEGMENTS
            for start in range(lo, hi, 256)]


def references(directory):
    result = {}
    for (lo, hi), expected in zip(CODE_SEGMENTS, REFERENCE_SHA256):
        data = (directory/f'CODE-26-{lo:08x}.bin').read_bytes()
        if len(data) != hi-lo or digest(data) != expected:
            raise ValueError(f'Image constructeur comm 1.37 différente à {lo:#x}')
        result[lo] = data
    return result


def acquire(rx, tx, flow, output, reference, reader=run_probe, progress=print):
    total = sum(hi-lo for lo, hi in CODE_SEGMENTS)
    manifest = {'started_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'Four known comm 1.37 code segments; not a complete device backup',
                'source_sha256': digest(Path(__file__).read_bytes()),
                'required_passes': 2, 'bytes_per_pass': total, 'passes': [],
                'complete': False, 'matches_reference': False, 'passes_equal': False,
                'error': None}
    started = time.monotonic()

    def save():
        manifest['elapsed_seconds'] = round(time.monotonic()-started, 3)
        temp = output/'progress.tmp'
        temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
        temp.replace(output/'progress.json')

    save()
    try:
        for number in (1, 2):
            folder = output/f'pass-{number}'
            folder.mkdir()
            current = {'number': number, 'segments': [], 'chunks': [], 'bytes_read': 0}
            manifest['passes'].append(current)
            for lo, hi in CODE_SEGMENTS:
                data = bytearray()
                for address in range(lo, hi, 256):
                    length = min(256, hi-address)
                    block = folder/f'{address:08x}'
                    block.mkdir()
                    report = reader(rx, tx, flow, block, address=address, length=length, batch_size=16)
                    if report['error'] is not None:
                        raise RuntimeError(f'Passe {number}, {address:#x} : {report["error"]}')
                    acquired = (block/'memory.bin').read_bytes()
                    if len(acquired) != length:
                        raise ValueError('Bloc incomplet malgré résultat annoncé complet')
                    expected = reference[lo][address-lo:address-lo+length]
                    row = {'address': address, 'length': length,
                           'directory': str(block.relative_to(output)),
                           'sha256': digest(acquired), 'matches_reference': acquired == expected,
                           'pcap_sha256': report['pcap_sha256'],
                           'result_sha256': digest((block/'result.json').read_bytes()),
                           'socket_drops': report.get('socket_drops')}
                    current['chunks'].append(row)
                    data.extend(acquired)
                    current['bytes_read'] += length
                    save()
                    if len(current['chunks']) % 16 == 0 or address+length == hi:
                        progress(json.dumps({'pass': number, 'bytes': current['bytes_read'],
                                             'total': total, 'elapsed_seconds': round(time.monotonic()-started,1)}))
                name = f'comm-{lo:08x}.bin'
                (folder/name).write_bytes(data)
                current['segments'].append({'address': lo, 'end_exclusive': hi,
                    'length': len(data), 'file': f'pass-{number}/{name}', 'sha256': digest(data),
                    'matches_reference': bytes(data) == reference[lo]})
                save()
        first, second = manifest['passes']
        manifest['passes_equal'] = all(a['sha256'] == b['sha256'] for a, b in zip(first['segments'], second['segments']))
        manifest['matches_reference'] = all(s['matches_reference'] for p in manifest['passes'] for s in p['segments'])
        manifest['complete'] = all(p['bytes_read'] == total and len(p['segments']) == len(CODE_SEGMENTS)
                                   for p in manifest['passes'])
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        manifest['error'] = str(exc) or type(exc).__name__
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='enp0s25')
    parser.add_argument('--mac', type=mac_address, default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--reference', type=Path, help='Dossier extrait par inspect_firmware.py')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args(argv)
    if not args.send:
        print(json.dumps({'network_opened': False, 'passes': 2, 'chunks_per_pass': len(chunk_plan()),
                          'bytes_per_pass': sum(hi-lo for lo, hi in CODE_SEGMENTS),
                          'batch_size': 16, 'segments': CODE_SEGMENTS}, indent=2))
        return 0
    if os.geteuid() == 0 or args.output is None or args.output.exists() or args.reference is None:
        parser.error('Compte non root, --reference valide et --output nouveau requis')
    reference = references(args.reference)  # Validate all inputs before opening a socket.
    if not args.interface or '/' in args.interface:
        parser.error('Interface invalide')
    interface = Path('/sys/class/net')/args.interface
    if (not (interface/'type').exists() or (interface/'type').read_text().strip() != '1'
            or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host = (interface/'address').read_text().strip()
    peer = mac_bytes(args.mac)
    if not any(peer) or peer[0]&1 or peer == mac_bytes(host):
        parser.error('MAC console unicast distincte requise')
    with exclusive_console(ROOT/'run'):
        rx, tx = packet_sockets(args.interface)
        with rx, tx:
            rx.bind((args.interface,0));tx.bind((args.interface,0))
            rx.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
            args.output.mkdir(mode=0o700,parents=True)
            manifest = acquire(rx,tx,ConsoleSession(host,args.mac),args.output,reference,
                               progress=lambda line: print(line,flush=True))
    print(json.dumps({k:manifest[k] for k in ('complete','matches_reference','passes_equal','error','elapsed_seconds')}))
    return int(not (manifest['complete'] and manifest['matches_reference'] and manifest['passes_equal']) or manifest['error'] is not None)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc: raise SystemExit(str(exc))
