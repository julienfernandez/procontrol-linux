#!/usr/bin/env python3
"""Reconstruit une archive fader depuis les PCAP clôturés de chaque bloc.

Par défaut, une archive incomplète est refusée. --completed-prefix vérifie
uniquement les blocs déjà inscrits dans un instantané du manifeste atomique ;
il ne parcourt jamais le dossier du bloc en cours et ne promet pas sa réussite.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_fader_serial import audit_plan,RELEASES
from inspect_pcap import mac_address

SEGMENTS=((0x8000,0x8008),(0x8064,0x8080),(0x8100,0x8110),(0x8400,0xb0e6))
REFERENCE_SHA256=('0b94948d9565a02762f1a6b7f83c5cf28908ea1bf882cdc5800eb57e0fdd8b2d',
                  'e35d2da6b9a2cab4ad24a40299cbbf8d6028950f3c33d8914dc057e174d8f4ec',
                  '42bfe0154783f4cf48373891ce4bad48f4dac5ff0d54020c61b656473f06222b',
                  '2479230a850da18b33b1dcf7292dbb12af6421aceabc047b2ae07d5582f23e05')


def sha(data):return hashlib.sha256(data).hexdigest()


def load_reference(folder):
    result={}
    for (start,end),digest in zip(SEGMENTS,REFERENCE_SHA256):
        data=(folder/f'CODE-27-{start:08x}.bin').read_bytes()
        if len(data)!=end-start or sha(data)!=digest:raise ValueError('Référence constructeur incorrecte')
        result[start]=data
    return result


def audit_archive(root,reference,host,peer,completed_prefix=False,progress=None,manifest_snapshot=None):
    snapshot=(root/'manifest.json').read_bytes() if manifest_snapshot is None else manifest_snapshot
    manifest=json.loads(snapshot)
    if not manifest['complete'] and not completed_prefix:raise ValueError('Archive incomplète ; aucun résultat complet')
    if manifest['complete'] and manifest.get('error'):raise ValueError('Archive complète mais erreur déclarée')
    planned=manifest['planned_passes']
    if planned not in (1,2) or not 0<=len(manifest['passes'])<=planned:raise ValueError('Nombre de passages incorrect')
    expected_bytes=sum(end-start for start,end in SEGMENTS)
    if manifest['expected_bytes_per_pass']!=expected_bytes:raise ValueError('Périmètre de mémoire incorrect')
    blocks=[(a,min(12,hi-a)) for lo,hi in SEGMENTS for a in range(lo,hi,12)]
    counts=Counter();records=[];rebuilt={};all_match=True;previous_end=None

    def inspect(folder,manifest_sha,audit_sha=None):
        nonlocal previous_end
        if sha((folder/'manifest.json').read_bytes())!=manifest_sha:raise ValueError('Manifeste de bloc altéré')
        cached_bytes=(folder/'audit.json').read_bytes()
        if audit_sha is not None and sha(cached_bytes)!=audit_sha:raise ValueError('Audit enregistré altéré')
        fresh=audit_plan(folder,host,peer)
        if json.loads(json.dumps(fresh))!=json.loads(cached_bytes):raise ValueError('Audit recalculé différent du cache')
        start=fresh['steps']['versions/comm-version']['request']['timestamp_ns']
        end=fresh['steps']['errors-after']['last_ns']
        if start>end or (previous_end is not None and start<=previous_end):
            raise ValueError('Chronologie des blocs incohérente ou capture réutilisée')
        previous_end=end
        for name,step in fresh['steps'].items():
            counts['pcaps']+=1
            counts['frames']+=step.get('frames',step.get('counts',{}).get('frames',0))
            saved=json.loads((folder/name/'result.json').read_text())
            drops=saved.get('socket_drops')
            if drops is None:counts['unknown_socket_drop_counts']+=1
            else:counts['socket_drops']+=drops
        return fresh,start,end

    proof,_,_=inspect(root/'release-proof',manifest['release_proof_manifest_sha256'])
    if proof['kind']!='release-proof' or bytes.fromhex(proof['data_hex'])!=bytes(range(0xd0,0xd8)):
        raise ValueError('Préalable de relâchement absent')
    for index,entry in enumerate(manifest['passes'],1):
        if entry['number']!=index:raise ValueError('Passage manquant ou dupliqué')
        observed=[(c['address'],c['length']) for c in entry['chunks']]
        if len(observed)>len(blocks) or observed!=blocks[:len(observed)]:
            raise ValueError('Adresses de blocs manquantes, répétées ou dans le désordre')
        if entry['complete'] and observed!=blocks:raise ValueError('Passage incomplet annoncé complet')
        if index<len(manifest['passes']) and not entry['complete']:raise ValueError('Passage suivant avant la fin du précédent')
        if manifest['complete'] and not entry['complete']:raise ValueError('Passage non achevé dans une archive complète')
        chunks=[];by_segment={lo:bytearray() for lo,_ in SEGMENTS};pass_root=root/f'pass-{index}'
        for record in entry['chunks']:
            address,length=record['address'],record['length'];folder=pass_root/f'{address:08x}'
            fresh,start,end=inspect(folder,record['manifest_sha256'],record['audit_sha256'])
            expected_plan=((address,length),)+RELEASES
            if fresh['kind']!='code-and-releases' or tuple(map(tuple,fresh['plan']))!=expected_plan:
                raise ValueError('Plan de lecture différent du bloc attendu')
            captured=json.loads((folder/'manifest.json').read_text())
            if captured.get('release_verified_before') is not True:raise ValueError('Préalable non déclaré avant le bloc')
            data=bytes.fromhex(fresh['data_hex'])[:-8]
            if len(data)!=length or data!=(folder/'code.bin').read_bytes() or sha(data)!=record['sha256']:
                raise ValueError('Code enregistré différent des PCAP')
            lo=next(lo for lo,hi in SEGMENTS if lo<=address<hi)
            match=data==reference[lo][address-lo:address-lo+length]
            if record['matches_reference']!=match:raise ValueError('Comparaison de référence incorrecte')
            all_match &= match;by_segment[lo].extend(data)
            counts['code_blocks']+=1;counts['code_bytes']+=len(data)
            chunks.append({**record,'first_request_ns':start,'last_capture_ns':end})
            if progress is not None:progress(counts['code_blocks'])
        segments=[];declared={}
        for segment in entry['segments']:
            if segment['address'] in declared:raise ValueError('Segment déclaré deux fois')
            declared[segment['address']]=segment
        if not set(declared)<={lo for lo,_ in SEGMENTS}:raise ValueError('Segment inconnu')
        for lo,hi in SEGMENTS:
            data=bytes(by_segment[lo])
            if not data:continue
            complete=len(data)==hi-lo
            matches=data==reference[lo][:len(data)]
            row={'address':lo,'length':len(data),'expected_length':hi-lo,'sha256':sha(data),
                 'complete':complete,'matches_reference':matches}
            if lo in declared:
                saved=declared[lo]
                if (not complete or saved['length']!=hi-lo or saved['sha256']!=sha(data)
                        or saved['matches_reference']!=matches):raise ValueError('Segment déclaré incohérent')
                if (pass_root/f'fader-{lo:08x}.bin').read_bytes()!=data:raise ValueError('Segment assemblé différent des PCAP')
            elif entry['complete']:raise ValueError('Segment assemblé absent du manifeste')
            segments.append(row);rebuilt[(index,lo)]=data
        records.append({'number':index,'complete':entry['complete'],'segments':segments,'chunks':chunks})
    full=manifest['complete']
    if full and len(records)!=planned:raise ValueError('Passage complet absent')
    equal=None
    if full and planned==2:
        equal=all(rebuilt[(1,lo)]==rebuilt[(2,lo)] for lo,_ in SEGMENTS)
        if manifest.get('passes_equal')!=equal or not equal:raise ValueError('Les deux passages diffèrent')
    return {'method':'Whole archive rebuilt from closed PCAPs via independent per-plan serial decoding',
            'manifest_snapshot_sha256':sha(snapshot),'manifest_snapshot_updated_utc':manifest.get('updated_utc'),
            'complete_archive':full,'completed_prefix_only':not full,'planned_passes':planned,
            'acquisition_error_at_snapshot':manifest.get('error'),'passes_equal':equal,
            'all_match_reference':all_match,'all_socket_drop_counts_zero':not (
                counts['socket_drops'] or counts['unknown_socket_drop_counts']),
            'counts':dict(counts),'passes':records},rebuilt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reconstruct',type=Path)
    parser.add_argument('--completed-prefix',action='store_true')
    parser.add_argument('--host',type=mac_address,default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',type=mac_address,default='00:a0:7e:a0:ad:9c')
    args=parser.parse_args()
    snapshot_path=args.output.with_name(args.output.stem+'.manifest.json')
    if args.output.exists() or snapshot_path.exists() or (args.reconstruct is not None and args.reconstruct.exists()):
        parser.error('Nouveaux chemins de sortie requis')
    snapshot=(args.archive/'manifest.json').read_bytes()
    with snapshot_path.open('xb') as f:f.write(snapshot)
    report,images=audit_archive(args.archive,load_reference(args.reference),
        bytes.fromhex(args.host.replace(':','')),bytes.fromhex(args.peer.replace(':','')),args.completed_prefix,
        manifest_snapshot=snapshot)
    report['manifest_snapshot_file']=snapshot_path.name
    with args.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    if args.reconstruct is not None:
        args.reconstruct.mkdir(parents=True,mode=0o700)
        for (number,address),data in images.items():
            end=next(hi for lo,hi in SEGMENTS if lo==address)
            suffix='' if len(data)==end-address else '.partial'
            (args.reconstruct/f'pass-{number}-fader-{address:08x}{suffix}.bin').write_bytes(data)
    print(json.dumps({k:v for k,v in report.items() if k!='passes'},indent=2))
    return int(not report['all_match_reference'])


if __name__=='__main__':raise SystemExit(main())
