#!/usr/bin/env python3
"""Reconstruction indépendante d'une lecture fader depuis les PCAP RAM clôturés."""
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


def sha(data):return hashlib.sha256(data).hexdigest()


def audit_request(path,address,length,host,peer):
    expected=bytes.fromhex('f0 13 00 70 01')+f'U{address:08X}'.encode()+(
        b'q' if length==1 else b'Q'*length)+b'\xf7'
    request=None;ack=None;frames=0;inputs=[]
    for number,(stamp,frame,wire) in enumerate(packets(path),1):
        if len(frame)!=wire or len(frame)<30 or frame[12:14]!=b'\x88\x5f':
            raise ValueError('Trame de requête tronquée ou non DigiNet')
        h=candidate_header(frame[14:]);frames+=1
        if not h['body_sum16_match']:raise ValueError('Checksum de requête/réponse incorrect')
        body=bytes.fromhex(h['body_hex']);command=h['command_field']
        if frame[6:12]==host and frame[:6]==peer:
            if command==0 and body!=b'\0':
                if request or body!=expected or h['command_count_candidate']!=1:
                    raise ValueError('Requête fader différente du plan unique')
                request={'frame':number,'timestamp_ns':stamp,'sequence':h['sequence_candidate']}
        elif frame[6:12]==peer and frame[:6]==host:
            if command==0xa0 and request and h['ack_candidate']==request['sequence']:
                ack={'frame':number,'timestamp_ns':stamp}
            elif command==0:inputs.append({'frame':number,'body_hex':body.hex(' '),'sequence':h['sequence_candidate']})
        elif frame[6:12]!=peer or frame[:6]!=b'\xff'*6:
            raise ValueError('Adresses Ethernet inattendues')
    if not request or not ack:raise ValueError('Requête fader ou ACK absent')
    return {'frames':frames,'request':request,'ack':ack,'inputs':inputs,'pcap_sha256':sha(path.read_bytes())}


def decode_serial(raw,address,length):
    if len(raw)!=5+21*length or raw[:5]!=b'\0\x20\x02\n\r':
        raise ValueError('Flux série incomplet ou réponse U incorrecte')
    result=bytearray()
    for i in range(length):
        packet=raw[5+i*21:5+(i+1)*21]
        match=re.fullmatch(rb"\x00\x20\x12([0-9a-fA-F]{8}): ([0-9a-fA-F]{2}) '(.)'\n\r",packet,re.DOTALL)
        if not match or int(match[1],16)!=address+i or int(match[2],16)!=match[3][0]:
            raise ValueError('Adresse/hexadécimal/caractère série incohérent')
        result.extend(match[3])
    return bytes(result)


def audit_readback(root,host,peer,reference=None):
    manifest=json.loads((root/'manifest.json').read_text())
    address,length=manifest['address'],manifest['length']
    if (not manifest['complete'] or manifest.get('error') or not 1<=length<=8
            or not 0x8000<=address<address+length<=0x8008):
        raise ValueError('Lecture incomplète ou hors pilote autorisé')
    names=[step['name'] for step in manifest['steps']]
    required={'versions','request','rx-before','rx-after','rx-final',
              'touch-before','touch-after','mode-before','mode-after','fader-version-after'}
    if len(set(names))!=len(names) or not required<=set(names):
        raise ValueError('Étape obligatoire absente ou dupliquée')
    errors_present={'errors-before','errors-after'} & set(names)
    if errors_present and len(errors_present)!=2:
        raise ValueError('Compteur d’erreurs avant/après incomplet')
    if any(key in manifest for key in ('parser_errors_before','parser_errors_after')) and not errors_present:
        raise ValueError('Compteur d’erreurs déclaré sans captures')
    audits={}
    for step in manifest['steps']:
        name=step['name'];folder=root/name
        if '/' in name or name in ('.','..'):raise ValueError('Chemin d’étape invalide')
        if sha((folder/'result.json').read_bytes())!=step['result_sha256']:
            raise ValueError('Résultat différent du manifeste')
        if name=='request':
            audits[name]=audit_request(folder/'traffic.pcap',address,length,host,peer)
            saved=json.loads((folder/'result.json').read_text())
            if saved['pcap_sha256']!=audits[name]['pcap_sha256'] or saved['error']:
                raise ValueError('Capture de requête différente du résultat')
        else:
            audits[name]=audit_probe(folder,host,peer)
            if not audits[name]['observed_complete']:raise ValueError('Étape incomplète')
            if name=='versions':
                prerequisite=folder/'comm-version'
                saved=json.loads((folder/'result.json').read_text())
                if sha((prerequisite/'result.json').read_bytes())!=saved['comm_prerequisite']['result_sha256']:
                    raise ValueError('Préalable comm différent')
                audits['versions/comm-version']=audit_probe(prerequisite,host,peer)
                if not audits['versions/comm-version']['observed_complete']:
                    raise ValueError('Préalable comm incomplet')

    if any(audits[name].get('target')!=target for name,target in
           [('versions','fader'),('versions/comm-version','comm'),('fader-version-after','fader')]):
        raise ValueError('Cible de version incorrecte')
    for name in ('rx-before','rx-after','rx-final','touch-before','touch-after',
                 'mode-before','mode-after',*sorted(errors_present)):
        field=name.split('-')[0]
        expected={'rx':'fader-rx-ring','touch':'fader-touch-state',
                  'mode':'fader-mode','errors':'fader-errors'}[field]
        if audits[name].get('state')!=expected:raise ValueError('Champ RAM incorrect pour l’étape')
    def memory(name):return bytes.fromhex(audits[name]['data_hex'])
    headers={name:struct.unpack('>6I',memory(name)) for name in ['rx-before','rx-after','rx-final']}
    before,after,final=(headers[x] for x in ['rx-before','rx-after','rx-final'])
    for row in headers.values():
        if row[1]!=0x6bf26 or row[3]!=512 or not all(0x6bf26<=v<0x6c10e for v in (row[0],row[2])):
            raise ValueError('Structure RX différente')
    for name,row in headers.items():
        saved=manifest[name.replace('-','_')]
        if tuple(saved[key] for key in ('producer','base','consumer','size','unknown','overflows'))!=row:
            raise ValueError('En-tête RX différent du manifeste')
    count=5+21*length
    if (before[0]!=before[2] or (after[0]-before[0])%488!=count or
            final[0]!=after[0] or len({before[5],after[5],final[5]})!=1):
        raise ValueError('Pointeurs/compteurs RX incohérents')
    raw=bytearray();addresses=[]
    names=sorted((name for name in audits if name.startswith('rx-data-')),key=lambda n:int(n.rsplit('-',1)[1]))
    for name in names:
        row=audits[name];data=memory(name)
        raw.extend(data);addresses.extend(range(row['address'],row['address']+len(data)))
    expected=[0x6bf26+(before[0]-0x6bf26+i)%488 for i in range(count)]
    if addresses!=expected:raise ValueError('Fenêtres RX manquantes, superposées ou dans le mauvais ordre')
    if raw!=(root/'serial.bin').read_bytes() or sha(raw)!=manifest['serial_sha256']:
        raise ValueError('Flux série reconstruit différent')
    data=decode_serial(raw,address,length)
    if (data!=(root/'memory.bin').read_bytes() or data!=bytes.fromhex(manifest['read_bytes_hex'])
            or sha(data)!=manifest['memory_sha256']):raise ValueError('Octets fader reconstruits différents')
    if memory('touch-before')!=bytes(16) or memory('touch-after')!=bytes(16):
        raise ValueError('État tactile non neutre')
    if memory('mode-before')!=b'\0' or memory('mode-after')!=b'\0':
        raise ValueError('Mode fader non normal')
    error_counts=None
    if errors_present:
        error_counts={side:int.from_bytes(memory('errors-'+side),'big') for side in ('before','after')}
        if any(manifest.get('parser_errors_'+side)!=value for side,value in error_counts.items()):
            raise ValueError('Compteur d’erreurs différent du manifeste')
    match=None
    if reference is not None:
        known=reference.read_bytes()
        if sha(known)!='0b94948d9565a02762f1a6b7f83c5cf28908ea1bf882cdc5800eb57e0fdd8b2d':
            raise ValueError('Vecteurs constructeur différents de la référence figée')
        match=data==known[address-0x8000:address-0x8000+length]
    return {'method':'Independent PCAP RAM reconstruction and separate binary serial parser',
            'address':address,'length':length,'data_hex':data.hex(' '),'memory_sha256':sha(data),
            'serial_sha256':sha(raw),'matches_saved_files':True,'matches_reference':match,
            'touch_unchanged':True,'mode_unchanged':True,'snapshots_non_atomic':True,
            'parser_errors':error_counts,
            'manifest_sha256':sha((root/'manifest.json').read_bytes()),'steps':audits}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--host',type=mac_address,default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',type=mac_address,default='00:a0:7e:a0:ad:9c')
    args=parser.parse_args()
    result=audit_readback(args.folder,bytes.fromhex(args.host.replace(':','')),
                          bytes.fromhex(args.peer.replace(':','')),args.reference)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
