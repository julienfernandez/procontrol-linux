#!/usr/bin/env python3
"""Pilote fixe de lecture RX par lots de 16/32 sur douze octets fader connus.

Huit essais alternés, preuve initiale des relâchements, contrôles de débordement
comm et série, audits PCAP. Le lecteur fader courant conserve ses lots de 16.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime,timezone
from functools import partial
import json
import os
from pathlib import Path
import signal
import statistics

from audit_fader_preservation import inspect_block,sha
from audit_firmware_probe import audit_probe
from comm_preservation import preflight,run_live
from fader_serial_probe import acquire_plan,code_plan,RELEASE_PLAN
from firmware_probe import run_probe
from inspect_pcap import mac_address
from session_probe import mac_bytes

ORDER=(16,32,32,16)*2
REFERENCE_SHA='2479230a850da18b33b1dcf7292dbb12af6421aceabc047b2ae07d5582f23e05'


def reference_bytes(path):
    data=path.read_bytes()
    if len(data)!=11494 or sha(data)!=REFERENCE_SHA:
        raise ValueError('Référence CODE-27-00008400.bin incorrecte')
    return data[:12]


def seconds(result):
    return (datetime.fromisoformat(result['finished_utc'])-
            datetime.fromisoformat(result['started_utc'])).total_seconds()


def acquire(rx,tx,flow,output,host,peer,reference):
    if len(reference)!=12:raise ValueError('Douze octets de référence requis')
    manifest={'schema':'fader-rx-benchmark-v1','complete':False,'error':None,'runs':[],
              'started_utc':datetime.now(timezone.utc).isoformat(),'order':ORDER,
              'address':0x8400,'length':12,'reference_sha256':sha(reference),
              'source_sha256':{name:sha(Path(__file__).with_name(name).read_bytes())for name in
                  ('fader_rx_benchmark.py','fader_serial_probe.py','firmware_probe.py',
                   'audit_fader_serial.py','audit_firmware_probe.py','audit_comm_archive.py')},
              'physical_latency_validated':False,'endurance_validated':False}
    previous=None
    def save():
        manifest['updated_utc']=datetime.now(timezone.utc).isoformat()
        path=output/'manifest.next.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
        path.replace(output/'manifest.json')
    def counter(folder):
        nonlocal previous
        folder.mkdir(mode=0o700)
        result=run_probe(rx,tx,flow,folder,state='comm-diagnostic-overflows',batch_size=16)
        if result['error'] or result.get('socket_drops')!=0:
            raise RuntimeError('Lecture du compteur comm échouée ou pertes socket')
        checked=audit_probe(folder,host,peer)
        if previous is not None and checked['first_ns']<=previous:
            raise ValueError('Chronologie du compteur incorrecte')
        previous=checked['last_ns']
        (folder/'audit.json').write_text(json.dumps(checked,indent=2)+'\n')
        return int.from_bytes(bytes.fromhex(checked['data_hex']),'big')
    def block(folder,plan,verified,batch):
        nonlocal previous
        folder.mkdir(mode=0o700)
        result=acquire_plan(rx,tx,flow,folder,plan,release_verified=verified,
                           expected=(reference if verified else b'')+bytes(range(0xd0,0xd8)),
                           experimental_rx_batch32=batch==32)
        if not result['complete']:raise RuntimeError(result['error'])
        checked,start,end,counts=inspect_block(folder,host,peer)
        if previous is not None and start<=previous:raise ValueError('Chronologie des blocs incorrecte')
        previous=end
        (folder/'audit.json').write_text(json.dumps(checked,indent=2)+'\n')
        windows=[];rx_seconds=0
        for name in checked['steps']:
            if not name.startswith('rx-data-'):continue
            observed=audit_probe(folder/name,host,peer,expected_batch_size=batch)
            if observed!=checked['steps'][name]:raise ValueError('Lot RX audité différent')
            saved=json.loads((folder/name/'result.json').read_text())
            rx_seconds+=seconds(saved);windows.append(saved['read_length'])
        return {'manifest_sha256':sha((folder/'manifest.json').read_bytes()),
                'audit_sha256':sha((folder/'audit.json').read_bytes()),
                'elapsed_seconds':seconds(result),'rx_read_seconds':rx_seconds,
                'rx_window_lengths':windows,'counts':dict(counts),
                'first_request_ns':start,'last_capture_ns':end}
    save()
    try:
        manifest['release_proof']=block(output/'release-proof',RELEASE_PLAN,False,16);save()
        for number,batch in enumerate(ORDER,1):
            folder=output/f'run-{number:02d}-batch-{batch}';folder.mkdir(mode=0o700)
            row={'number':number,'batch_size':batch,'complete':False}
            manifest['runs'].append(row);save()
            row['overflows_before']=counter(folder/'before');save()
            row.update(block(folder/'block',code_plan(0x8400,12),True,batch));save()
            row['overflows_after']=counter(folder/'after');save()
            if row['overflows_before']!=row['overflows_after']:
                raise ValueError('Débordement diagnostic comm pendant le bloc')
            row['complete']=True;save()
        for key in ('elapsed_seconds','rx_read_seconds'):
            medians={str(batch):statistics.median(row[key]for row in manifest['runs']
                                                  if row['batch_size']==batch)for batch in (16,32)}
            if min(medians.values())<=0:raise ValueError('Durée de mesure non positive')
            manifest['median_'+key]=medians
            manifest['ratio_16_over_32_'+key]=medians['16']/medians['32']
        manifest['complete']=True
    except (OSError,ValueError,RuntimeError,KeyboardInterrupt)as exc:
        manifest['error']=str(exc)or type(exc).__name__
    finally:
        manifest['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send',action='store_true')
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--interface',default='enp0s25')
    parser.add_argument('--mac',type=mac_address,default='00:a0:7e:a0:ad:9c')
    args=parser.parse_args(argv)
    if not args.send:
        print(json.dumps({'network_opened':False,'fader_address':0x8400,'code_bytes':12,
                          'serial_bytes_per_block':465,'order':ORDER,'settle_seconds':0.25},indent=2));return 0
    if os.geteuid()==0 or args.output is None or args.output.exists() or args.reference is None:
        parser.error('Compte utilisateur, référence et nouveau dossier requis')
    reference=reference_bytes(args.reference)
    interface=Path('/sys/class/net')/args.interface
    if (not args.interface or '/' in args.interface or not (interface/'type').exists()
            or (interface/'type').read_text().strip()!='1' or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host=(interface/'address').read_text().strip();peer=mac_bytes(args.mac)
    if not any(peer)or peer[0]&1 or peer==mac_bytes(host):parser.error('MAC console unicast distincte requise')
    status=preflight();args.output.mkdir(parents=True,mode=0o700)
    (args.output/'preflight.json').write_text(json.dumps(status,indent=2)+'\n')
    def interrupted(*_):raise KeyboardInterrupt('SIGTERM')
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:result=run_live(args.interface,host,args.mac,args.output,collector=partial(acquire,reference=reference))
    finally:signal.signal(signal.SIGTERM,previous)
    print(json.dumps({k:v for k,v in result.items()if k!='runs'},indent=2))
    return int(not result['complete'])


if __name__=='__main__':raise SystemExit(main())
