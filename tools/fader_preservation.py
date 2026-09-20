#!/usr/bin/env python3
"""Deux lectures des vecteurs, checksum, seuils et état de calibration fader.

Aperçu par défaut. --send prend le réseau exclusivement après arrêt de la
passerelle, puis la relance. Aucune calibration ou écriture de réglage exécutée.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal

from audit_fader_preservation import inspect_block,sha
from comm_preservation import preflight,run_live
from fader_serial_probe import acquire_plan,preservation_plan,PRESERVATION_FIELDS,RELEASE_PLAN
from inspect_pcap import mac_address
from session_probe import mac_bytes


def acquire(rx,tx,flow,output,host,peer):
    manifest={'schema':'fader-preservation-v1','started_utc':datetime.now(timezone.utc).isoformat(),
              'complete':False,'error':None,'passes':[],'source_sha256':sha(Path(__file__).read_bytes()),
              'bytes_per_pass':sum(size for _,size in PRESERVATION_FIELDS.values())}
    def save():
        manifest['updated_utc']=datetime.now(timezone.utc).isoformat()
        path=output/'manifest.next.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
        path.replace(output/'manifest.json')
    def read(folder,plan,verified,state=None):
        folder.mkdir(mode=0o700)
        result=acquire_plan(rx,tx,flow,folder,plan,release_verified=verified,state=state,
                            expected=bytes(range(0xd0,0xd8)) if not verified else None)
        if not result['complete']:raise RuntimeError(f'{folder.name}: {result["error"]}')
        audited,_,_,_=inspect_block(folder,host,peer)
        (folder/'audit.json').write_text(json.dumps(audited,indent=2)+'\n')
        return bytes.fromhex(audited['data_hex']),{
            'manifest_sha256':sha((folder/'manifest.json').read_bytes()),
            'audit_sha256':sha((folder/'audit.json').read_bytes())}
    save()
    try:
        values,record=read(output/'release-proof',RELEASE_PLAN,False)
        if values!=bytes(range(0xd0,0xd8)):raise RuntimeError('Relâchements non vérifiés')
        manifest['release_proof']=record;save()
        for number in (1,2):
            root=output/f'pass-{number}';root.mkdir(mode=0o700)
            current={'number':number,'complete':False,'fields':[]};manifest['passes'].append(current)
            for name,(_,size) in PRESERVATION_FIELDS.items():
                folder=root/name;folder.mkdir(mode=0o700);data=bytearray()
                field={'name':name,'blocks':[]};current['fields'].append(field)
                for offset in range(0,size,12):
                    length=min(12,size-offset);plan=preservation_plan(name,offset,length)
                    values,record=read(folder/f'{offset:04x}',plan,True,state=name)
                    values=values[:-8];data.extend(values)
                    field['blocks'].append({'offset':offset,'length':length,'sha256':sha(values),**record})
                    save()
                (folder/'field.bin').write_bytes(data);field['sha256']=sha(data);save()
            current['complete']=True;save()
        manifest['complete']=True
    except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as exc:
        manifest['error']=str(exc) or type(exc).__name__
    finally:
        manifest['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--interface',default='enp0s25')
    parser.add_argument('--mac',type=mac_address,default='00:a0:7e:a0:ad:9c')
    args=parser.parse_args(argv)
    if not args.send:
        print(json.dumps({'network_opened':False,'passes':2,'bytes_per_pass':270,
                          'blocks_per_pass':25,'release_reads_per_block':8,
                          'fields':PRESERVATION_FIELDS},indent=2));return 0
    if os.geteuid()==0 or args.output is None or args.output.exists():
        parser.error('Compte utilisateur et nouveau dossier --output requis')
    interface=Path('/sys/class/net')/args.interface
    if (not args.interface or '/' in args.interface or not (interface/'type').exists()
            or (interface/'type').read_text().strip()!='1' or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host=(interface/'address').read_text().strip();peer=mac_bytes(args.mac)
    if not any(peer) or peer[0]&1 or peer==mac_bytes(host):parser.error('MAC console unicast distincte requise')
    status=preflight();args.output.mkdir(mode=0o700,parents=True)
    (args.output/'preflight.json').write_text(json.dumps(status,indent=2)+'\n')
    def interrupted(*_):raise KeyboardInterrupt('SIGTERM')
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:result=run_live(args.interface,host,args.mac,args.output,collector=acquire)
    finally:signal.signal(signal.SIGTERM,previous)
    print(json.dumps({k:v for k,v in result.items() if k!='passes'},indent=2))
    return int(not result['complete'])


if __name__=='__main__':raise SystemExit(main())
