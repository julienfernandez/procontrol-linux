#!/usr/bin/env python3
"""Reconstruction indépendante des petits champs fader et instantanés de RAM.

Le rapport contient des données propres à l'unité. Aucun collecteur importé.
Les différences entre instantanés volatils ne sont pas remplacées ni corrigées.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_fader_serial import audit_plan, RELEASES
from inspect_pcap import mac_address

FIELDS={'fader-boot-vectors':(0,8),'fader-application-checksum':(0xfffe,2),
        'fader-touch-thresholds':(0x44012,4),'fader-calibration-state':(0x4402a,256)}


def sha(data):return hashlib.sha256(data).hexdigest()


def inspect_block(folder,host,peer):
    fresh=audit_plan(folder,host,peer)
    start=fresh['steps']['versions/comm-version']['request']['timestamp_ns']
    end=fresh['steps']['errors-after']['last_ns']
    if start>end:raise ValueError('Chronologie du bloc incohérente')
    counts=Counter()
    for name,step in fresh['steps'].items():
        saved=json.loads((folder/name/'result.json').read_text())
        if saved.get('socket_drops')!=0:raise ValueError('Pertes socket non nulles ou inconnues')
        counts['pcaps']+=1
        counts['frames']+=step.get('frames',step.get('counts',{}).get('frames',0))
    return fresh,start,end,counts


def interpret(fields):
    if set(fields)!=set(FIELDS) or any(len(fields[k])!=n for k,(_,n) in FIELDS.items()):
        raise ValueError('Champs fader incomplets')
    vectors=fields['fader-boot-vectors'];thresholds=fields['fader-touch-thresholds']
    data=fields['fader-calibration-state'];channels=[]
    for index in range(8):
        raw=data[index*32:(index+1)*32]
        channels.append({'channel':index+1,'address':0x4402a+index*32,
                         'scale_word_raw':int.from_bytes(raw[:4],'big'),
                         'extent_signed':int.from_bytes(raw[0x10:0x12],'big',signed=True),
                         'validity_flag_raw':raw[0x1b], 'record_sha256':sha(raw)})
    return {'boot_vectors':{'initial_stack_pointer':int.from_bytes(vectors[:4],'big'),
                            'reset_program_counter':int.from_bytes(vectors[4:],'big')},
            'application_checksum':{'stored_word':int.from_bytes(fields['fader-application-checksum'],'big'),
                                    'full_application_sum_verified':False},
            'touch_thresholds':{'0x44012_raw_s16':int.from_bytes(thresholds[:2],'big',signed=True),
                                '0x44014_raw_s16':int.from_bytes(thresholds[2:],'big',signed=True),
                                'raw_words_are_percentages':False},
            'calibration_state':{'snapshot_atomic':False,'calibration_triggered':False,
                                 'physical_calibration_validated':False,'channels':channels}}


def audit(root,host,peer):
    raw_manifest=(root/'manifest.json').read_bytes();manifest=json.loads(raw_manifest)
    if (manifest.get('schema')!='fader-preservation-v1' or not manifest.get('complete')
            or manifest.get('error') or manifest.get('bytes_per_pass')!=270
            or [p.get('number') for p in manifest.get('passes',[])]!=[1,2]):
        raise ValueError('Acquisition fader incomplète ou plan différent')
    counts=Counter();previous_end=None

    def inspect(folder,record):
        nonlocal previous_end
        if sha((folder/'manifest.json').read_bytes())!=record['manifest_sha256']:
            raise ValueError('Manifeste de bloc modifié')
        cached=(folder/'audit.json').read_bytes()
        if sha(cached)!=record['audit_sha256']:raise ValueError('Audit enregistré modifié')
        fresh,start,end,totals=inspect_block(folder,host,peer)
        if json.loads(json.dumps(fresh))!=json.loads(cached):raise ValueError('Audit recalculé différent')
        if previous_end is not None and start<=previous_end:
            raise ValueError('Blocs réutilisés ou chronologie incohérente')
        previous_end=end;counts.update(totals)
        return fresh,start,end

    proof,_,_=inspect(root/'release-proof',manifest['release_proof'])
    if proof['kind']!='release-proof' or bytes.fromhex(proof['data_hex'])!=bytes(range(0xd0,0xd8)):
        raise ValueError('Preuve de relâchement incorrecte')
    report={'archive_manifest_sha256':sha(raw_manifest),'complete':True,'passes':[],
            'full_device_backup':False,'ram_snapshot_atomic':False,'socket_drops':0,
            'method':'Independent per-block PCAP and serial reconstruction, followed by field assembly'}
    data_passes=[]
    for entry in manifest['passes']:
        if not entry.get('complete') or [r.get('name') for r in entry['fields']]!=list(FIELDS):
            raise ValueError('Champs absents, répétés ou réordonnés')
        field_data={};checked_fields=[]
        for record in entry['fields']:
            name=record['name'];address,length=FIELDS[name]
            expected=[(offset,min(12,length-offset)) for offset in range(0,length,12)]
            if [(b['offset'],b['length']) for b in record['blocks']]!=expected:
                raise ValueError('Couverture incorrecte du champ')
            folder=root/f'pass-{entry["number"]}'/name;data=bytearray();times=[]
            for block in record['blocks']:
                where=folder/f'{block["offset"]:04x}'
                fresh,start,end=inspect(where,block)
                plan=((address+block['offset'],block['length']),)+RELEASES
                source=json.loads((where/'manifest.json').read_text())
                if (fresh['kind']!='preservation-and-releases' or fresh.get('preservation_field')!=name
                        or tuple(map(tuple,fresh['plan']))!=plan or source.get('release_verified_before') is not True):
                    raise ValueError('Champ ou préalable de lecture incorrect')
                values=bytes.fromhex(fresh['data_hex'])[:-8]
                if len(values)!=block['length'] or sha(values)!=block['sha256']:
                    raise ValueError('Bloc de champ différent')
                data.extend(values);times.append((start,end));counts['data_blocks']+=1
            if data!=(folder/'field.bin').read_bytes() or sha(data)!=record['sha256']:
                raise ValueError('Champ assemblé différent des captures')
            field_data[name]=bytes(data);counts['data_bytes']+=len(data)
            checked_fields.append({'name':name,'address':address,'length':length,'sha256':sha(data),
                                   'first_request_ns':times[0][0],'last_capture_ns':times[-1][1],
                                   'blocks':record['blocks']})
        data_passes.append(field_data)
        report['passes'].append({'number':entry['number'],'fields':checked_fields,
                                 'interpretation':interpret(field_data)})
    report['field_passes_equal']={name:data_passes[0][name]==data_passes[1][name] for name in FIELDS}
    report['persistent_fields_equal']=all(report['field_passes_equal'][name]
        for name in ('fader-boot-vectors','fader-application-checksum'))
    report['counts']=dict(counts)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--host',type=mac_address,default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',type=mac_address,default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('Nouveau fichier de sortie requis')
    result=audit(args.archive,bytes.fromhex(args.host.replace(':','')),bytes.fromhex(args.peer.replace(':','')))
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='passes'},indent=2))
    return int(not result['persistent_fields_equal'])


if __name__=='__main__':raise SystemExit(main())
