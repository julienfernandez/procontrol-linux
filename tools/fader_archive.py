#!/usr/bin/env python3
"""Acquisition des quatre segments fader 1.37, deux passages audités par défaut.

Aperçu par défaut. --send suspend la passerelle et la relance dans finally.
Chaque bloc est suivi des huit lectures de relâchement, puis contrôlé par PCAP.
Les copies ne couvrent ni bootstrap, ni EEPROM/calibration, ni trous mémoire.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from audit_fader_serial import audit_plan
from fader_serial_probe import acquire_plan,code_plan,RELEASE_PLAN,SEGMENTS,digest
from firmware_probe import ROOT,exclusive_console
from inspect_pcap import mac_address
from procontrold import ConsoleSession,packet_sockets
from session_probe import mac_bytes

REFERENCE_SHA256=('0b94948d9565a02762f1a6b7f83c5cf28908ea1bf882cdc5800eb57e0fdd8b2d',
                  'e35d2da6b9a2cab4ad24a40299cbbf8d6028950f3c33d8914dc057e174d8f4ec',
                  '42bfe0154783f4cf48373891ce4bad48f4dac5ff0d54020c61b656473f06222b',
                  '2479230a850da18b33b1dcf7292dbb12af6421aceabc047b2ae07d5582f23e05')


def references(folder):
    result={}
    for (lo,hi),expected in zip(SEGMENTS,REFERENCE_SHA256):
        data=(folder/f'CODE-27-{lo:08x}.bin').read_bytes()
        if len(data)!=hi-lo or digest(data)!=expected:raise ValueError('Référence constructeur différente')
        result[lo]=data
    return result


def blocks():
    return [(address,min(12,hi-address)) for lo,hi in SEGMENTS for address in range(lo,hi,12)]


def acquire_archive(rx,tx,flow,output,reference,host,peer,passes=2,progress=None):
    if passes not in (1,2):raise ValueError('Un ou deux passages seulement')
    report={'started_utc':datetime.now(timezone.utc).isoformat(),'complete':False,'error':None,
            'planned_passes':passes,'expected_bytes_per_pass':sum(hi-lo for lo,hi in SEGMENTS),
            'source_sha256':digest(Path(__file__).read_bytes()),'passes':[]}
    def save():
        report['updated_utc']=datetime.now(timezone.utc).isoformat()
        temporary=output/'manifest.next.json'
        temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(output/'manifest.json')
    def read(folder,plan,verified,expected=None):
        folder.mkdir(mode=0o700)
        result=acquire_plan(rx,tx,flow,folder,plan,expected,verified)
        if not result['complete']:raise RuntimeError(f'{folder.name}: {result["error"]}')
        audited=audit_plan(folder,host,peer)
        (folder/'audit.json').write_text(json.dumps(audited,indent=2)+'\n')
        return bytes.fromhex(audited['data_hex'])
    try:
        save()
        release=read(output/'release-proof',RELEASE_PLAN,False,bytes(range(0xd0,0xd8)))
        if release!=bytes(range(0xd0,0xd8)):raise RuntimeError('Relâchements non vérifiés')
        report['release_proof_manifest_sha256']=digest((output/'release-proof/manifest.json').read_bytes())
        completed=0
        for number in range(1,passes+1):
            entry={'number':number,'complete':False,'chunks':[],'segments':[]};report['passes'].append(entry)
            pass_root=output/f'pass-{number}';pass_root.mkdir(mode=0o700)
            for lo,hi in SEGMENTS:
                data=bytearray()
                for address in range(lo,hi,12):
                    length=min(12,hi-address);folder=pass_root/f'{address:08x}'
                    decoded=read(folder,code_plan(address,length),True)
                    values=decoded[:-8]
                    (folder/'code.bin').write_bytes(values)
                    expected=reference[lo][address-lo:address-lo+length]
                    record={'address':address,'length':length,'sha256':digest(values),
                            'manifest_sha256':digest((folder/'manifest.json').read_bytes()),
                            'audit_sha256':digest((folder/'audit.json').read_bytes()),
                            'matches_reference':values==expected}
                    entry['chunks'].append(record);data.extend(values);completed+=1
                    save()
                    if values!=expected:raise RuntimeError(f'Octets différents de la référence à {address:#x}')
                    if progress is not None:progress(completed,passes*len(blocks()),number,address)
                name=f'fader-{lo:08x}.bin';(pass_root/name).write_bytes(data)
                entry['segments'].append({'address':lo,'length':hi-lo,'sha256':digest(data),
                                           'matches_reference':data==reference[lo]})
            entry['complete']=True;save()
        report['passes_equal']=(None if passes==1 else
            [s['sha256'] for s in report['passes'][0]['segments']]==[s['sha256'] for s in report['passes'][1]['segments']])
        report['complete']=all(p['complete'] for p in report['passes'])
    except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as exc:
        report['error']=str(exc) or type(exc).__name__
    report['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--interface',default='enp0s25')
    parser.add_argument('--mac',type=mac_address,default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--passes',type=int,choices=(1,2),default=2)
    parser.add_argument('--send',action='store_true')
    args=parser.parse_args()
    if not args.send:
        print(json.dumps({'network_opened':False,'passes':args.passes,'blocks_per_pass':len(blocks()),
                          'bytes_per_pass':sum(hi-lo for lo,hi in SEGMENTS),'max_serial_bytes_per_block':465,
                          'method':'Code reads followed by eight verified release-byte reads; PCAP audit per block'}));return 0
    if os.geteuid()==0:parser.error('Utiliser le compte utilisateur et le helper installé')
    if args.reference is None or args.output is None or args.output.exists():parser.error('Référence et nouveau dossier requis')
    try:reference=references(args.reference)
    except (OSError,ValueError) as exc:parser.error(str(exc))
    interface=Path('/sys/class/net')/args.interface
    if (not args.interface or '/' in args.interface or not (interface/'type').exists()
            or (interface/'type').read_text().strip()!='1' or (interface/'wireless').exists()):parser.error('Ethernet filaire requis')
    host=(interface/'address').read_text().strip();peer=mac_bytes(args.mac)
    if not any(peer) or peer[0]&1 or peer==mac_bytes(host):parser.error('MAC unicast distincte requise')
    status_path=ROOT/'run/status.json';status=json.loads(status_path.read_text());os.kill(status['pid'],0)
    if (time.time()-status_path.stat().st_mtime>5 or status['console']!='online'
            or status['ardour']!='waiting' or status['mapping']['learning'] or status['last_action'] is not None):
        parser.error('Passerelle Online fraîche, Ardour fermé, aucun apprentissage/geste récent requis')
    args.output.mkdir(parents=True,mode=0o700)
    (args.output/'preflight.json').write_text(json.dumps(status,indent=2)+'\n')
    def interrupted(*_):raise KeyboardInterrupt('SIGTERM')
    signal.signal(signal.SIGTERM,interrupted)
    def progress(done,total,number,address):
        if done%10==0 or done==total:
            print(json.dumps({'completed_blocks':done,'total_blocks':total,'pass':number,
                              'last_address':hex(address),'utc':datetime.now(timezone.utc).isoformat()}),flush=True)
    result=None
    try:
        subprocess.run([str(ROOT/'procontrol'),'stop'],cwd=ROOT,check=True)
        with exclusive_console(ROOT/'run'):
            rx,tx=packet_sockets(args.interface)
            with rx,tx:
                rx.bind((args.interface,0));tx.bind((args.interface,0))
                rx.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
                result=acquire_archive(rx,tx,ConsoleSession(host,args.mac),args.output,reference,
                                       mac_bytes(host),peer,args.passes,progress)
    finally:
        restarted=subprocess.run([str(ROOT/'procontrol'),'start'],cwd=ROOT,capture_output=True,text=True)
        (args.output/'restart.log').write_text(restarted.stdout+restarted.stderr)
        (args.output/'restart-result.json').write_text(json.dumps({'exit_code':restarted.returncode})+'\n')
        restarted.check_returncode()
    print(json.dumps({k:v for k,v in result.items() if k!='passes'},indent=2))
    return int(not result['complete'])


if __name__=='__main__':raise SystemExit(main())
