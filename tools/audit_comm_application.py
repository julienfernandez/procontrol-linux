#!/usr/bin/env python3
"""Reconstruit les 64 Kio comm depuis les segments et les trous réellement capturés.

Les deux campagnes restent datées séparément : couverture cumulative,
aucun remplissage supposé et aucune affirmation de snapshot atomique.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_comm_archive import audit_archive as audit_code, SEGMENTS
from audit_comm_preservation import audit as audit_fields, sha
from inspect_pcap import mac_address

FIELDS = {'comm-app-gap-20008': (0x20008,92), 'comm-app-gap-20080': (0x20080,128),
          'comm-app-gap-20110': (0x20110,752), 'comm-app-gap-2fce4': (0x2fce4,796),
          'comm-application-checksum': (0x30000,2)}


def assemble(pieces):
    cursor=0x20000; result=bytearray()
    for address,data in sorted(pieces):
        if address!=cursor or not data or address+len(data)>0x30000:
            raise ValueError('Couverture avec trou, recouvrement ou débordement')
        result.extend(data); cursor+=len(data)
    if cursor!=0x30000:
        raise ValueError('Plage du programme incomplète')
    return bytes(result)


def audit(gaps, code, reference, host, peer):
    legacy=audit_code(code,reference,host,peer)
    if not legacy['all_match_reference'] or not legacy['passes_equal']:
        raise ValueError('Segments de base différents entre passes ou du constructeur')
    extra=audit_fields(gaps,host,peer,fields=FIELDS,schema='comm-application-gaps-v1',interpreter=None)
    report={'method':'Cumulative complete application reconstruction from independently audited PCAPs',
            'code_archive_manifest_sha256':legacy['archive_manifest_sha256'],
            'gap_archive_manifest_sha256':extra['archive_manifest_sha256'],
            'bytes_per_pass':65536,'complete_application_coverage':True,
            'cumulative_acquisition':True,'snapshot_atomic':False,'full_device_backup':False,
            'all_known_segments_match_reference':True,'gap_fields_equal':extra['field_passes_equal'],
            'passes':[],'counts':{'code_pcaps':0,'gap_pcaps':extra['pcap_files'],
                                'frames':legacy['counts']['frames']+extra['frames'],'socket_drops':0}}
    seen=set();previous=None
    for old in legacy['passes']:
        for chunk in old['chunks']:
            path=code/f'pass-{old["number"]}/{chunk["address"]:08x}/result.json'
            saved=json.loads(path.read_text())
            if saved.get('socket_drops')!=0:
                raise ValueError('Pertes de la campagne de base non nulles ou inconnues')
            if (chunk['pcap_sha256'] in seen or chunk['first_ns']>chunk['last_ns']
                    or (previous is not None and chunk['first_ns']<=previous)):
                raise ValueError('Captures de base réutilisées ou non chronologiques')
            previous=chunk['last_ns'];seen.add(chunk['pcap_sha256']);report['counts']['code_pcaps']+=1
    images=[]
    for number in (1,2):
        old=legacy['passes'][number-1];new=extra['passes'][number-1];pieces=[];parts=[]
        for row,(lo,hi) in zip(old['segments'],SEGMENTS):
            data=(code/f'pass-{number}/comm-{lo:08x}.bin').read_bytes()
            if row['address']!=lo or len(data)!=hi-lo or sha(data)!=row['sha256']:
                raise ValueError('Segment assemblé différent du code audité')
            pieces.append((lo,data));parts.append({'address':lo,'length':len(data),'sha256':sha(data),'source':'earlier-code-pass'})
        for name,field in new['fields'].items():
            if field['first_ns']<=previous or field['pcap_sha256'] in seen:
                raise ValueError('Les captures complémentaires doivent être distinctes et postérieures')
            previous=field['last_ns'];seen.add(field['pcap_sha256'])
            if name=='comm-application-checksum':continue
            data=bytes.fromhex(field['data_hex']);pieces.append((field['address'],data))
            parts.append({'address':field['address'],'length':len(data),'sha256':sha(data),'source':'new-gap-pass'})
        image=assemble(pieces);images.append(image)
        stored=int.from_bytes(bytes.fromhex(new['fields']['comm-application-checksum']['data_hex']),'big')
        actual=sum(image)&0xffff
        gap_counts=Counter(v for name,row in new['fields'].items() if name!='comm-application-checksum'
                           for v in bytes.fromhex(row['data_hex']))
        report['passes'].append({'number':number,'sha256':sha(image),'parts':sorted(parts,key=lambda r:r['address']),
            'computed_sum16':actual,'stored_sum16':stored,'checksum_matches':actual==stored,
            'gap_byte_histogram':{f'{key:02x}':value for key,value in sorted(gap_counts.items())},
            'first_code_capture_ns':old['chunks'][0]['first_ns'],
            'last_code_capture_ns':old['chunks'][-1]['last_ns'],
            'first_gap_capture_ns':next(iter(new['fields'].values()))['first_ns'],
            'last_gap_capture_ns':new['fields']['comm-application-checksum']['last_ns']})
    report['passes_equal']=images[0]==images[1]
    report['all_checksums_match']=all(p['checksum_matches'] for p in report['passes'])
    return report,images


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gaps',type=Path)
    parser.add_argument('--code-archive',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--host',type=mac_address,default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',type=mac_address,default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reconstruct',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists() or args.reconstruct.exists():parser.error('Nouveaux chemins requis')
    report,images=audit(args.gaps,args.code_archive,args.reference,
        bytes.fromhex(args.host.replace(':','')),bytes.fromhex(args.peer.replace(':','')))
    with args.output.open('x')as stream:json.dump(report,stream,indent=2);stream.write('\n')
    args.reconstruct.mkdir(mode=0o700)
    for number,image in enumerate(images,1):(args.reconstruct/f'pass-{number}-comm-00020000.bin').write_bytes(image)
    print(json.dumps({k:v for k,v in report.items()if k!='passes'},indent=2))
    return int(not report['passes_equal'] or not report['all_checksums_match'])


if __name__=='__main__':raise SystemExit(main())
