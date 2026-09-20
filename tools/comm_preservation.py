#!/usr/bin/env python3
"""Deux lectures des cinq champs comm de préservation, sans écriture persistante.

Aperçu par défaut. --send arrête la passerelle, prend son verrou et la relance
dans finally. Chaque champ conserve son PCAP et un audit indépendant immédiat.
Exécuter depuis le dépôt principal après la fin de toute autre acquisition.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from audit_firmware_probe import audit_probe
from firmware_probe import ROOT, STATE_FIELDS, exclusive_console, run_probe
from inspect_pcap import mac_address
from procontrold import ConsoleSession, packet_sockets
from session_probe import mac_bytes

FIELDS = ('comm-boot-vectors', 'comm-application-checksum', 'comm-network-settings',
          'comm-utility-settings', 'comm-utility-mirror')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def acquire(rx, tx, flow, output, host, peer):
    manifest = {'schema': 'comm-preservation-v1', 'complete': False, 'error': None,
                'started_utc': datetime.now(timezone.utc).isoformat(), 'passes': [],
                'source_sha256': sha(Path(__file__).read_bytes()),
                'bytes_per_pass': sum(STATE_FIELDS[name][1] for name in FIELDS)}

    def save():
        manifest['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temporary = output/'manifest.next.json'
        temporary.write_text(json.dumps(manifest, indent=2)+'\n')
        temporary.replace(output/'manifest.json')

    save()
    try:
        for number in (1, 2):
            root = output/f'pass-{number}'
            root.mkdir(mode=0o700)
            current = {'number': number, 'fields': [], 'complete': False}
            manifest['passes'].append(current)
            for name in FIELDS:
                folder = root/name
                folder.mkdir(mode=0o700)
                saved = run_probe(rx, tx, flow, folder, state=name, batch_size=16)
                if saved['error'] is not None:
                    raise RuntimeError(f'{name}: {saved["error"]}')
                if saved.get('socket_drops') != 0:
                    raise RuntimeError(f'{name}: pertes socket non nulles ou inconnues')
                audited = audit_probe(folder, host, peer)
                (folder/'audit.json').write_text(json.dumps(audited, indent=2)+'\n')
                current['fields'].append({'name': name,
                    'result_sha256': sha((folder/'result.json').read_bytes()),
                    'audit_sha256': sha((folder/'audit.json').read_bytes())})
                save()
            current['complete'] = True
            save()
        manifest['complete'] = True
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        manifest['error'] = str(exc) or type(exc).__name__
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return manifest


def preflight():
    path = ROOT/'run/status.json'
    status = json.loads(path.read_text())
    os.kill(status['pid'], 0)
    if (not 0 <= time.time()-path.stat().st_mtime <= 5 or status['console'] != 'online'
            or status['ardour'] != 'waiting' or status['mapping']['learning']
            or status['last_action'] is not None):
        raise ValueError('Passerelle Online fraîche, Ardour fermé et aucun geste récent requis')
    return status


def run_live(interface, host, peer, output, collector=None):
    """Always attempt gateway restart, including failed probes and SIGTERM."""
    try:
        subprocess.run([str(ROOT/'procontrol'), 'stop'], cwd=ROOT, check=True)
        with exclusive_console(ROOT/'run'):
            rx, tx = packet_sockets(interface)
            with rx, tx:
                rx.bind((interface, 0)); tx.bind((interface, 0))
                rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)
                result = (acquire if collector is None else collector)(
                    rx, tx, ConsoleSession(host, peer), output, mac_bytes(host), mac_bytes(peer))
    finally:
        restarted = subprocess.run([str(ROOT/'procontrol'), 'start'], cwd=ROOT,
                                   capture_output=True, text=True)
        (output/'restart.log').write_text(restarted.stdout+restarted.stderr)
        (output/'restart-result.json').write_text(json.dumps({'exit_code': restarted.returncode})+'\n')
        restarted.check_returncode()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--interface', default='enp0s25')
    parser.add_argument('--mac', type=mac_address, default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args(argv)
    if not args.send:
        print(json.dumps({'network_opened': False, 'passes': 2,
                          'bytes_per_pass': sum(STATE_FIELDS[name][1] for name in FIELDS),
                          'fields': {name: STATE_FIELDS[name] for name in FIELDS}}, indent=2))
        return 0
    if os.geteuid() == 0 or args.output is None or args.output.exists():
        parser.error('Compte utilisateur et nouveau dossier --output requis')
    interface = Path('/sys/class/net')/args.interface
    if (not args.interface or '/' in args.interface or not (interface/'type').exists()
            or (interface/'type').read_text().strip() != '1' or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host = (interface/'address').read_text().strip()
    peer = mac_bytes(args.mac)
    if not any(peer) or peer[0]&1 or peer == mac_bytes(host):
        parser.error('MAC console unicast distincte requise')
    status = preflight()
    args.output.mkdir(parents=True, mode=0o700)
    (args.output/'preflight.json').write_text(json.dumps(status, indent=2)+'\n')

    def interrupted(*_):
        raise KeyboardInterrupt('SIGTERM')

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        result = run_live(args.interface, host, args.mac, args.output)
    finally:
        signal.signal(signal.SIGTERM, previous)
    print(json.dumps({k: v for k, v in result.items() if k != 'passes'}, indent=2))
    return int(not result['complete'])


if __name__ == '__main__':
    raise SystemExit(main())
