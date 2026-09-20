#!/usr/bin/env python3
"""Audit PCAP des plans de lecture fader et de leurs relâchements synthétiques.

N'importe aucune fonction de l'outil d'acquisition ou de son parseur série.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from audit_diginet import candidate_header
from audit_firmware_probe import audit_probe
from inspect_pcap import packets,mac_address

SEGMENTS=((0x8000,0x8008),(0x8064,0x8080),(0x8100,0x8110),(0x8400,0xb0e6))
RELEASES=((0x8455,1),(0x9d3a,1),(0x8c64,1),(0x849b,1),(0x8aa0,1),(0xa00f,1),(0x8883,1),(0x8941,1))
PRESERVATION_FIELDS={'fader-boot-vectors':(0,8),
                     'fader-application-checksum':(0xfffe,2),
                     'fader-touch-thresholds':(0x44012,4),
                     'fader-calibration-state':(0x4402a,256)}


def sha(data):return hashlib.sha256(data).hexdigest()


def validate_plan(plan,state=None):
    plan=tuple(map(tuple,plan))
    if state is not None:
        if (state not in PRESERVATION_FIELDS or len(plan)!=9 or plan[1:]!=RELEASES
                or not 1<=plan[0][1]<=12):
            raise ValueError('Champ nommé ou relâchements incorrects')
        kind='preservation-and-releases'
    elif plan==RELEASES:kind='release-proof'
    elif plan==((0x8459,1),(0x8455,1)):kind='touch-pair'
    elif len(plan)==9 and plan[1:]==RELEASES and 1<=plan[0][1]<=12:kind='code-and-releases'
    else:raise ValueError('Plan hors des lectures documentées')
    for index,(address,length) in enumerate(plan):
        ranges=SEGMENTS
        if state is not None and index==0:
            start,size=PRESERVATION_FIELDS[state];ranges=((start,start+size),)
        if not 1<=length<=16 or not any(lo<=address<address+length<=hi for lo,hi in ranges):
            raise ValueError('Plage mémoire fader incorrecte')
    return plan,kind


def audit_request(path,plan,host,peer):
    expected=bytes.fromhex('f0 13 00 70 01')+b''.join(f'U{a:08X}'.encode()+
                 (b'q' if n==1 else b'Q'*n) for a,n in plan)+b'\xf7'
    request=None;ack=None;inputs=[];frames=0
    for number,(stamp,frame,wire) in enumerate(packets(path),1):
        if len(frame)!=wire or len(frame)<30 or frame[12:14]!=b'\x88\x5f':
            raise ValueError('Trame tronquée ou non DigiNet')
        h=candidate_header(frame[14:]);frames+=1
        if not h['body_sum16_match']:raise ValueError('Checksum incorrect')
        body=bytes.fromhex(h['body_hex']);command=h['command_field']
        if frame[6:12]==host and frame[:6]==peer:
            if command==0 and body!=b'\0':
                if request or body!=expected or h['command_count_candidate']!=1:
                    raise ValueError('Requête différente du plan unique')
                request={'frame':number,'timestamp_ns':stamp,'sequence':h['sequence_candidate']}
        elif frame[6:12]==peer and frame[:6]==host:
            if command==0xa0 and request and h['ack_candidate']==request['sequence']:
                ack={'frame':number,'timestamp_ns':stamp}
            elif command==0:inputs.append({'frame':number,'timestamp_ns':stamp,
                                           'body_hex':body.hex(' '),'sequence':h['sequence_candidate']})
        elif frame[6:12]!=peer or frame[:6]!=b'\xff'*6:raise ValueError('Adresses Ethernet inattendues')
    if not request or not ack:raise ValueError('Requête ou ACK absent')
    return {'frames':frames,'request':request,'ack':ack,'inputs':inputs,'pcap_sha256':sha(path.read_bytes())}


def decode_serial(raw,plan):
    size=sum(5+21*n for _,n in plan)
    if len(raw)!=size:raise ValueError('Longueur série incohérente')
    values=bytearray();cursor=0
    for address,length in plan:
        if raw[cursor:cursor+5]!=b'\0\x20\x02\n\r':raise ValueError('Réponse U incorrecte')
        cursor+=5
        for i in range(length):
            packet=raw[cursor:cursor+21];cursor+=21
            match=re.fullmatch(rb"\x00\x20\x12([0-9a-fA-F]{8}): ([0-9a-fA-F]{2}) '(.)'\n\r",packet,re.DOTALL)
            if not match or int(match[1],16)!=address+i or int(match[2],16)!=match[3][0]:
                raise ValueError('Adresse ou représentation série incohérente')
            values.extend(match[3])
    return bytes(values)


def audit_plan(root,host,peer):
    manifest=json.loads((root/'manifest.json').read_text())
    if not manifest['complete'] or manifest.get('error'):raise ValueError('Lecture incomplète')
    state=manifest.get('preservation_field')
    plan,kind=validate_plan(manifest['plan'],state=state)
    names=[s['name'] for s in manifest['steps']]
    required={'versions','request','rx-before','rx-after','rx-final','touch-before','touch-after',
              'mode-before','mode-after','errors-before','errors-after','fader-version-after'}
    if len(set(names))!=len(names) or not required<=set(names):raise ValueError('Étapes absentes ou dupliquées')
    audits={}
    for step in manifest['steps']:
        name=step['name']
        if '/' in name or name in ('.','..'):raise ValueError('Chemin invalide')
        folder=root/name;saved=json.loads((folder/'result.json').read_text())
        if sha((folder/'result.json').read_bytes())!=step['result_sha256']:raise ValueError('Résultat altéré')
        if name=='request':
            audits[name]=audit_request(folder/'traffic.pcap',plan,host,peer)
            if saved['error'] or audits[name]['pcap_sha256']!=saved['pcap_sha256']:raise ValueError('Requête altérée')
        else:
            audits[name]=audit_probe(folder,host,peer)
            if not audits[name]['observed_complete']:raise ValueError('Étape incomplète')
            if name=='versions':
                pre=folder/'comm-version'
                if sha((pre/'result.json').read_bytes())!=saved['comm_prerequisite']['result_sha256']:
                    raise ValueError('Préalable modifié')
                audits['versions/comm-version']=audit_probe(pre,host,peer)
                if not audits['versions/comm-version']['observed_complete']:raise ValueError('Préalable incomplet')
    for name,target in [('versions','fader'),('versions/comm-version','comm'),('fader-version-after','fader')]:
        if audits[name].get('target')!=target:raise ValueError('Cible de version incorrecte')
    def memory(name):return bytes.fromhex(audits[name]['data_hex'])
    for name in required-{'versions','request','fader-version-after'}:
        field={'rx':'fader-rx-ring','touch':'fader-touch-state','mode':'fader-mode','errors':'fader-errors'}[name.split('-')[0]]
        if audits[name].get('state')!=field:raise ValueError('Champ RAM incorrect')
    headers={name:struct.unpack('>6I',memory(name)) for name in ['rx-before','rx-after','rx-final']}
    before,after,final=(headers[name] for name in ['rx-before','rx-after','rx-final'])
    for name,row in headers.items():
        if row[1]!=0x6bf26 or row[3]!=512 or not all(0x6bf26<=v<0x6c10e for v in (row[0],row[2])):
            raise ValueError('Structure RX différente')
        saved=manifest[name.replace('-','_')]
        if row!=tuple(saved[k] for k in ('producer','base','consumer','size','unknown','overflows')):
            raise ValueError('En-tête différent du manifeste')
    count=sum(5+21*n for _,n in plan)
    if count>480 or (before[0]!=before[2] or (after[0]-before[0])%488!=count
                    or final[0]!=after[0] or len({before[5],after[5],final[5]})!=1):
        raise ValueError('Pointeurs RX ou débordement incohérents')
    raw=bytearray();addresses=[]
    for name in sorted((n for n in audits if n.startswith('rx-data-')),key=lambda n:int(n.rsplit('-',1)[1])):
        row=audits[name];data=memory(name);raw.extend(data)
        addresses.extend(range(row['address'],row['address']+len(data)))
    if addresses!=[0x6bf26+(before[0]-0x6bf26+i)%488 for i in range(count)]:raise ValueError('Fenêtres RX incorrectes')
    if raw!=(root/'serial.bin').read_bytes() or sha(raw)!=manifest['serial_sha256']:raise ValueError('Flux série altéré')
    values=decode_serial(raw,plan)
    if (values!=(root/'memory.bin').read_bytes() or values!=bytes.fromhex(manifest['read_bytes_hex'])
            or sha(values)!=manifest['memory_sha256']):raise ValueError('Octets reconstruits différents')
    if kind=='touch-pair':
        if values!=b'\xc0\xd0':raise ValueError('Paire tactile différente')
    elif values[-8:]!=bytes(range(0xd0,0xd8)):raise ValueError('Relâchements différents')
    for side in ('before','after'):
        if memory('touch-'+side)!=bytes(16) or memory('mode-'+side)!=b'\0':raise ValueError('État non neutre')
    errors={side:int.from_bytes(memory('errors-'+side),'big') for side in ('before','after')}
    if any(manifest['parser_errors_'+side]!=v for side,v in errors.items()):raise ValueError('Compteur altéré')
    result={'method':'Independent PCAP RAM reconstruction and separate serial parser','kind':kind,
            'plan':plan,'data_hex':values.hex(' '),'serial_sha256':sha(raw),'memory_sha256':sha(values),
            'manifest_sha256':sha((root/'manifest.json').read_bytes()),'matches_saved_files':True,
            'touch_neutral_before_after':True,'mode_normal_before_after':True,'parser_errors':errors,'steps':audits}
    if state is not None:result['preservation_field']=state
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--host',type=mac_address,default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',type=mac_address,default='00:a0:7e:a0:ad:9c')
    args=parser.parse_args()
    print(json.dumps(audit_plan(args.folder,bytes.fromhex(args.host.replace(':','')),
                               bytes.fromhex(args.peer.replace(':',''))),indent=2))


if __name__=='__main__':main()
