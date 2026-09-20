#!/usr/bin/env python3
"""Lectures fader bornées, récupération série et neutralisation des faux touchers.

Les relâchements utilisent uniquement des lectures de caractères D0..D7 connus.
Pas de commande mémoire W, de réglage moteur, de flash ou de calibration.
La passerelle doit être arrêtée sous son verrou puis relancée par l'appelant.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime,timezone
import json
from pathlib import Path
import select
import socket
import struct
import time

from fader_readback import digest,ring_header,ring_windows
from firmware_probe import FADER_PREFIX,run_probe,run_fader_version,memory_reply,RX_BUFFER_SIZE
from pcap_writer import write_header,write_packet

SEGMENTS=((0x8000,0x8008),(0x8064,0x8080),(0x8100,0x8110),(0x8400,0xb0e6))
# Addresses in the original CODE 27 image. A live release-only probe must verify
# these eight bytes and neutral state before using them with unknown contents.
RELEASE_ADDRESSES=(0x8455,0x9d3a,0x8c64,0x849b,0x8aa0,0xa00f,0x8883,0x8941)
RELEASE_PLAN=tuple((address,1) for address in RELEASE_ADDRESSES)
PAIR_PLAN=((0x8459,1),(0x8455,1))
# Separate named opt-in: never expand the original code reader's address ranges.
# Provenance: docs/preservation-layout-2026-09-21.md (static analysis only).
PRESERVATION_FIELDS={'fader-boot-vectors':(0,8),
                     'fader-application-checksum':(0xfffe,2),
                     'fader-touch-thresholds':(0x44012,4),
                     'fader-calibration-state':(0x4402a,256)}


def request_for(plan,state=None):
    if not plan:raise ValueError('Plan vide')
    if state is not None:
        if (state not in PRESERVATION_FIELDS or len(plan)!=9 or tuple(map(tuple,plan[1:]))!=RELEASE_PLAN
                or not 1<=plan[0][1]<=12):
            raise ValueError('Champ fader nommé avec huit relâchements requis')
    body=bytearray(FADER_PREFIX);serial_length=0
    for index,(address,length) in enumerate(plan):
        ranges=SEGMENTS
        if state is not None and index==0:
            start,size=PRESERVATION_FIELDS[state];ranges=((start,start+size),)
        if not 1<=length<=16 or not any(lo<=address<address+length<=hi for lo,hi in ranges):
            raise ValueError('Lecture hors segment fader connu ou longueur excessive')
        body.extend(f'U{address:08X}'.encode())
        body.extend(b'q' if length==1 else b'Q'*length)
        serial_length+=5+21*length
    if serial_length>480:raise ValueError('Réponse trop longue pour le tampon RX')
    return bytes(body)+b'\xf7',serial_length


def code_plan(address,length):
    if not 1<=length<=12:raise ValueError('Bloc de code limité à 12 octets')
    plan=((address,length),)+RELEASE_PLAN
    request_for(plan)
    return plan


def preservation_plan(state,offset,length):
    if state not in PRESERVATION_FIELDS or offset<0:
        raise ValueError('Champ ou offset fader incorrect')
    plan=((PRESERVATION_FIELDS[state][0]+offset,length),)+RELEASE_PLAN
    request_for(plan,state=state)
    return plan


def parse_serial(raw,plan,state=None):
    _,size=request_for(plan,state=state)
    if len(raw)!=size:raise ValueError('Longueur série différente du plan')
    cursor=0;values=bytearray()
    for address,length in plan:
        if raw[cursor:cursor+5]!=b'\0\x20\x02\n\r':raise ValueError('Réponse U incorrecte')
        cursor+=5
        for index in range(length):
            packet=raw[cursor:cursor+21];cursor+=21
            if packet[:3]!=b'\0\x20\x12':raise ValueError('En-tête série mémoire incorrect')
            value=memory_reply(packet[3:],address+index)
            if value is None:raise ValueError('Adresse mémoire série incorrecte')
            values.append(value)
    return bytes(values)


def capture_plan(rx,tx,flow,output,plan,settle=.25,state=None):
    body,size=request_for(plan,state=state)
    if flow.phase!='online':raise RuntimeError('Session non Online')
    if not .01<=settle<=1:raise ValueError('Délai de réception hors limites')
    result={'started_utc':datetime.now(timezone.utc).isoformat(),'request_hex':body.hex(' '),
            'plan':plan,'expected_serial_bytes':size,'ack_received':False,'error':None,
            'frames_tx':0,'frames_rx':0,'settle_seconds':settle}
    flow.session.sequence+=1;sequence=flow.session.sequence;result['sequence']=sequence
    path=output/'traffic.pcap'
    with path.open('xb') as file:
        write_header(file)
        def send(frames):
            for frame in frames:
                if frame[28]==0xa0:time.sleep(.0008)
                if tx.send(frame)!=len(frame):raise OSError('Émission incomplète')
                write_packet(file,time.time_ns(),frame);result['frames_tx']+=1
        try:
            send([flow.session.frame(0,count=1,sequence=sequence,body=body)])
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                send(flow.tick(time.monotonic()))
                if flow.phase!='online':raise RuntimeError('Session perdue')
                if not select.select([rx],[],[],min(.02,max(0,deadline-time.monotonic())))[0]:continue
                frame=rx.recv(65535)
                if len(frame)<30 or frame[6:12]!=flow.session.peer:continue
                write_packet(file,time.time_ns(),frame);result['frames_rx']+=1
                outgoing,header=flow.receive(frame,time.monotonic());send(outgoing)
                if flow.phase!='online' or (header and header['command_field']==0xe0):
                    raise RuntimeError('Console déconnectée')
                if (header and frame[:6]==flow.session.host and header['command_field']==0xa0
                        and header['ack_candidate']==sequence and not result['ack_received']):
                    result['ack_received']=True;deadline=time.monotonic()+settle
            if not result['ack_received']:raise RuntimeError('ACK absent ; aucun retry')
        except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as exc:
            result['error']=str(exc) or type(exc).__name__
        finally:
            if rx.family==socket.AF_PACKET:
                try:result['socket_packets'],result['socket_drops']=struct.unpack('II',rx.getsockopt(263,6,8))
                except OSError as exc:result['socket_statistics_error']=str(exc)
    result.update(finished_utc=datetime.now(timezone.utc).isoformat(),pcap_sha256=digest(path.read_bytes()))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def acquire_plan(rx,tx,flow,output,plan,expected=None,release_verified=False,state=None):
    _,serial_size=request_for(plan,state=state)
    normalized=tuple(map(tuple,plan))
    if normalized not in (RELEASE_PLAN,PAIR_PLAN) and not (
            len(plan)==9 and normalized[1:]==RELEASE_PLAN and 1<=plan[0][1]<=12):
        raise ValueError('Plan non suivi des huit relâchements connus')
    if normalized not in (RELEASE_PLAN,PAIR_PLAN) and not release_verified:
        raise ValueError('Preuve préalable des octets de relâchement requise')
    if tuple(map(tuple,plan))==PAIR_PLAN and not release_verified:
        raise ValueError('Paire tactile interdite avant la preuve des relâchements')
    report={'started_utc':datetime.now(timezone.utc).isoformat(),'plan':plan,
            'source_sha256':digest(Path(__file__).read_bytes()),'complete':False,'error':None,
            'request_attempted':False,'release_verified_before':release_verified,'steps':[]}
    if state is not None:report['preservation_field']=state
    def record(name,result):
        report['steps'].append({'name':name,'result_sha256':digest((output/name/'result.json').read_bytes())})
        if result['error']:raise RuntimeError(f'{name}: {result["error"]}')
    def probe(name,**kwargs):
        folder=output/name;folder.mkdir(mode=0o700)
        if kwargs.get('state'):kwargs['batch_size']=16
        result=run_probe(rx,tx,flow,folder,**kwargs);record(name,result)
        return (folder/'memory.bin').read_bytes() if (folder/'memory.bin').exists() else None
    def recovery():
        if probe('recovery-mode',state='fader-mode')!=b'\0':raise RuntimeError('Mode changé ; relâchements refusés')
        if release_verified:
            folder=output/'recovery-release';folder.mkdir(mode=0o700)
            result=capture_plan(rx,tx,flow,folder,RELEASE_PLAN);record('recovery-release',result)
        probe('recovery-version',target='fader')
        report['recovery_touch_neutral']=probe('recovery-touch',state='fader-touch-state')==bytes(16)
    try:
        folder=output/'versions';folder.mkdir(mode=0o700)
        record('versions',run_fader_version(rx,tx,flow,folder))
        touch=probe('touch-before',state='fader-touch-state');mode=probe('mode-before',state='fader-mode')
        if touch!=bytes(16) or mode!=b'\0':raise RuntimeError('Toucher actif ou mode non normal')
        report['parser_errors_before']=int.from_bytes(probe('errors-before',state='fader-errors'),'big')
        before=ring_header(probe('rx-before',state='fader-rx-ring'));report['rx_before']=before
        if before['producer']!=before['consumer']:raise RuntimeError('File RX non vide avant lecture')
        folder=output/'request';folder.mkdir(mode=0o700);report['request_attempted']=True
        options={} if state is None else {'state':state}
        record('request',capture_plan(rx,tx,flow,folder,plan,**options))
        after=ring_header(probe('rx-after',state='fader-rx-ring'));report['rx_after']=after
        if ((after['producer']-before['producer'])%RX_BUFFER_SIZE!=serial_size
                or after['overflows']!=before['overflows']):raise RuntimeError('Production RX non attribuable')
        raw=bytearray()
        for i,(offset,length) in enumerate(ring_windows(before['producer'],serial_size)):
            raw.extend(probe(f'rx-data-{i}',ring_offset=offset,length=length,batch_size=16))
        (output/'serial.bin').write_bytes(raw);report['serial_sha256']=digest(raw)
        final=ring_header(probe('rx-final',state='fader-rx-ring'));report['rx_final']=final
        if final['producer']!=after['producer'] or final['overflows']!=after['overflows']:
            raise RuntimeError('Tampon modifié pendant la lecture')
        values=parse_serial(raw,plan,state=state)
        (output/'memory.bin').write_bytes(values)
        report.update(read_bytes_hex=values.hex(' '),memory_sha256=digest(values))
        probe('fader-version-after',target='fader')
        if probe('touch-after',state='fader-touch-state')!=touch:raise RuntimeError('État tactile modifié')
        if probe('mode-after',state='fader-mode')!=mode:raise RuntimeError('Mode modifié')
        report['parser_errors_after']=int.from_bytes(probe('errors-after',state='fader-errors'),'big')
        if expected is not None and values!=expected:raise RuntimeError('Octets différents de la référence attendue')
        if release_verified and tuple(map(tuple,plan[-8:]))==RELEASE_PLAN and values[-8:]!=bytes(range(0xd0,0xd8)):
            raise RuntimeError('Octets de relâchement différents')
        report['complete']=True
    except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as exc:
        report['error']=str(exc) or type(exc).__name__
        if report['request_attempted']:
            try:recovery()
            except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as error:
                report['recovery_error']=str(error) or type(error).__name__
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
