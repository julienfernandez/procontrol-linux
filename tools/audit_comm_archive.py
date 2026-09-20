#!/usr/bin/env python3
"""Reconstruit hors ligne les acquisitions comm depuis les PCAP clôturés."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from audit_diginet import candidate_header
from inspect_pcap import packets

SEGMENTS = ((0x20000,0x20008),(0x20064,0x20080),(0x20100,0x20110),(0x20400,0x2fce4))
PREFIX = bytes.fromhex('f0 13 00 70 00')
REPLY = re.compile(re.escape(PREFIX) +
    rb"(?:\n\r|COMv1\.37\n\r|(?P<address>[0-9A-Fa-f]{8}): (?P<hex>[0-9A-Fa-f]{2}) '(?P<byte>.)'\n\r)\xf7", re.DOTALL)
REQUEST = re.compile(re.escape(PREFIX) + rb'A([0-9A-F]{8})(m|M{1,16})\xf7')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit_chunk(path, start, length, host, peer):
    expected=set(range(start,start+length))
    requested=set(); values={}; requests={}; acks=set(); sequences={}
    counts=Counter(); first=None; last=None
    for number,(stamp,frame,wirelen) in enumerate(packets(path),1):
        if len(frame)!=wirelen or len(frame)<30 or frame[12:14]!=b'\x88\x5f':
            raise ValueError(f'{path}, trame {number}: trame tronquée ou non DigiNet')
        header=candidate_header(frame[14:])
        if not header['body_sum16_match']:
            raise ValueError(f'{path}, trame {number}: somme du corps incorrecte')
        counts['frames']+=1
        first=stamp if first is None else first;last=stamp
        body=bytes.fromhex(header['body_hex'])
        command=header['command_field']
        if frame[6:12]==host and frame[:6]==peer:
            if command!=0 or body==b'\0':continue
            if header['command_count_candidate']!=1:
                raise ValueError('Requête contenant plusieurs enveloppes inattendues')
            sequence=header['sequence_candidate']
            if sequence in requests:raise ValueError('Requête hôte réémise dans le PCAP')
            requests[sequence]=number
            if body==PREFIX+b'V\xf7':
                counts['version_requests']+=1
                continue
            match=REQUEST.fullmatch(body)
            if not match:raise ValueError('Commande diagnostic hors plan de lecture')
            address=int(match[1],16);size=len(match[2])
            addresses=set(range(address,address+size))
            if not addresses<=expected or addresses & requested:
                raise ValueError('Adresses hors bloc ou requêtes de lecture chevauchantes')
            requested.update(addresses)
            counts['memory_requests']+=1
        elif frame[6:12]==peer and frame[:6]==host:
            if command==0xa0:
                acks.add(header['ack_candidate']);continue
            if command!=0:continue
            if not body.startswith(PREFIX):
                counts['non_diagnostic_input_frames']+=1;continue
            sequence=header['sequence_candidate']
            if sequence in sequences:
                if sequences[sequence]!=body:raise ValueError('Même séquence avec deux corps différents')
                counts['duplicate_response_frames']+=1;continue
            sequences[sequence]=body
            offset=0;envelopes=0
            while offset<len(body):
                match=REPLY.match(body,offset)
                if not match:raise ValueError(f'Réponse non reconnue en trame {number}, offset {offset}')
                offset=match.end();envelopes+=1
                if match['address'] is None:
                    counts['version_responses' if b'COM' in match[0] else 'address_set_responses']+=1
                    continue
                address=int(match['address'],16);value=int(match['hex'],16)
                if address not in requested or value!=match['byte'][0]:
                    raise ValueError('Adresse non demandée ou représentations différentes de l’octet')
                if address in values:
                    raise ValueError('Adresse répétée avec une nouvelle séquence')
                values[address]=value
            if envelopes!=header['command_count_candidate']:
                raise ValueError('Nombre d’enveloppes différent du compteur DigiNet')
            counts['response_envelopes']+=envelopes
        elif frame[6:12]!=peer or frame[:6]!=b'\xff'*6:
            raise ValueError('Émetteur ou destinataire inattendu')
    if (requested!=expected or set(values)!=expected or set(requests)-acks or
            counts['version_requests']!=1 or counts['version_responses']!=1):
        raise ValueError('Acquisition incomplète : adresses, version ou ACK manquants')
    data=bytes(values[a] for a in range(start,start+length))
    return data, {'pcap_sha256':sha(path.read_bytes()),'memory_sha256':sha(data),
                  'first_ns':first,'last_ns':last,'counts':dict(counts)}


def audit_archive(root, reference, host, peer):
    manifest=json.loads((root/'manifest.json').read_text())
    if not manifest.get('complete'):raise ValueError('Archive annoncée incomplète')
    result={'archive_manifest_sha256':sha((root/'manifest.json').read_bytes()),
            'method':'Independent PCAP parsing and byte reconstruction, including DigiNet envelope counts',
            'passes':[],'counts':{},'all_match_saved_files':True,'all_match_reference':True}
    totals=Counter()
    for number in (1,2):
        entry={'number':number,'segments':[],'chunks':[]}
        recorded={row['address']:row for row in manifest['passes'][number-1]['chunks']}
        for lo,hi in SEGMENTS:
            full=bytearray()
            for address in range(lo,hi,256):
                length=min(256,hi-address)
                folder=root/f'pass-{number}/{address:08x}'
                data,report=audit_chunk(folder/'traffic.pcap',address,length,host,peer)
                record=recorded[address]
                if (report['pcap_sha256']!=record['pcap_sha256'] or sha(data)!=record['sha256'] or
                        sha((folder/'result.json').read_bytes())!=record['result_sha256']):
                    raise ValueError('Empreinte différente du manifeste d’acquisition')
                if data!=(folder/'memory.bin').read_bytes():raise ValueError('PCAP et fichier de bloc divergent')
                report.update(address=address,length=length)
                entry['chunks'].append(report);totals.update(report['counts']);full.extend(data)
            name=f'comm-{lo:08x}.bin'
            if full!=(root/f'pass-{number}'/name).read_bytes():raise ValueError('PCAP et segment assemblé divergent')
            official=(reference/f'CODE-26-{lo:08x}.bin').read_bytes()
            match=full==official
            result['all_match_reference'] &= match
            entry['segments'].append({'address':lo,'length':len(full),'sha256':sha(full),
                                      'reference_sha256':sha(official),'matches_reference':match})
        result['passes'].append(entry)
    result['counts']=dict(totals)
    result['passes_equal']=[s['sha256'] for s in result['passes'][0]['segments']]==[s['sha256'] for s in result['passes'][1]['segments']]
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--host',default='3c:97:0e:1b:3a:00')
    parser.add_argument('--peer',default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Nouveau fichier de sortie requis')
    report=audit_archive(args.archive,args.reference,bytes.fromhex(args.host.replace(':','')),bytes.fromhex(args.peer.replace(':','')))
    with args.output.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='passes'},indent=2))
    return int(not report['all_match_reference'] or not report['passes_equal'])


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as exc:raise SystemExit(str(exc))
