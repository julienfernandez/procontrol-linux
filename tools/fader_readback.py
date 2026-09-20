#!/usr/bin/env python3
"""Lecture expérimentale des huit vecteurs fader via le tampon RX de comm.

Aperçu par défaut. Limité à 0x8000..0x8007, sans firmware écrit ni réglage
moteur. La passerelle doit être arrêtée, puis relancée après --send.
Les pointeurs de diagnostic U/A sont volatils. Un ACK ne valide pas les octets.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import struct
import time

from firmware_probe import (ROOT, FADER_PREFIX, RX_BUFFER_START, RX_BUFFER_SIZE,
                            exclusive_console, run_probe, run_fader_version, memory_reply)
from inspect_pcap import mac_address
from pcap_writer import write_header, write_packet
from procontrold import ConsoleSession, packet_sockets
from session_probe import mac_bytes


def digest(data):
    return hashlib.sha256(data).hexdigest()


def request_for(address, length):
    if not 1 <= length <= 8 or not 0x8000 <= address < address+length <= 0x8008:
        raise ValueError('Pilote limité aux huit vecteurs fader 0x8000..0x8007')
    reads = b'q' if length == 1 else b'Q'*length
    return FADER_PREFIX+f'U{address:08X}'.encode()+reads+b'\xf7'


def ring_header(data):
    if len(data) != 24:
        raise ValueError('En-tête RX incomplet')
    producer,base,consumer,size,unknown,overflows = struct.unpack('>6I',data)
    if (base != RX_BUFFER_START or size != 512 or not
            all(base <= p < base+RX_BUFFER_SIZE for p in (producer,consumer))):
        raise ValueError('Disposition du tampon RX différente du firmware étudié')
    return {'producer':producer,'consumer':consumer,'base':base,'size':size,
            'unknown':unknown,'overflows':overflows}


def ring_windows(producer, length):
    if not RX_BUFFER_START <= producer < RX_BUFFER_START+RX_BUFFER_SIZE or not 1 <= length < RX_BUFFER_SIZE:
        raise ValueError('Fenêtre circulaire hors limites')
    offset = producer-RX_BUFFER_START
    result = []
    while length:
        size = min(length,256,RX_BUFFER_SIZE-offset)
        result.append((offset,size))
        length -= size
        offset = (offset+size) % RX_BUFFER_SIZE
    return result


def parse_serial(data, address, length):
    request_for(address,length)
    if len(data) != 5+21*length or data[:5] != b'\x00\x20\x02\n\r':
        raise ValueError('Réponse série U/mémoire incomplète ou différente')
    values = bytearray()
    for index in range(length):
        frame = data[5+index*21:5+(index+1)*21]
        if frame[:3] != b'\x00\x20\x12':
            raise ValueError('En-tête de lecture série différent')
        value = memory_reply(frame[3:],address+index)
        if value is None:
            raise ValueError('Adresse de lecture série différente')
        values.append(value)
    return bytes(values)


def capture_request(rx, tx, flow, output, address, length, settle=.5):
    body = request_for(address,length)
    if flow.phase != 'online':
        raise RuntimeError('Session non préparée ; requête fader refusée')
    if not .001 <= settle <= 1:
        raise ValueError('Fenêtre de réception hors limites')
    report = {'started_utc':datetime.now(timezone.utc).isoformat(),
              'request_hex':body.hex(' '),'ack_received':False,
              'scope':'Only request delivery; memory validity requires RX reconstruction',
              'settle_seconds':settle,'frames_tx':0,'frames_rx':0,'error':None}
    flow.session.sequence += 1
    sequence = flow.session.sequence
    report['sequence'] = sequence
    path = output/'traffic.pcap'
    with path.open('xb') as file:
        write_header(file)

        def send(frames):
            for frame in frames:
                if frame[28] == 0xa0:time.sleep(.0008)
                if tx.send(frame) != len(frame):raise OSError('Émission incomplète')
                write_packet(file,time.time_ns(),frame)
                report['frames_tx'] += 1

        try:
            send([flow.session.frame(0,count=1,sequence=sequence,body=body)])
            deadline = time.monotonic()+2
            while time.monotonic() < deadline:
                send(flow.tick(time.monotonic()))
                if flow.phase != 'online':raise RuntimeError('Session perdue')
                if not select.select([rx],[],[],min(.02,max(0,deadline-time.monotonic())))[0]:continue
                frame = rx.recv(65535)
                if len(frame)<30 or frame[6:12] != flow.session.peer:continue
                write_packet(file,time.time_ns(),frame);report['frames_rx'] += 1
                outgoing,header = flow.receive(frame,time.monotonic());send(outgoing)
                if flow.phase != 'online' or (header and header['command_field']==0xe0):
                    raise RuntimeError('Console déconnectée après la requête')
                if (header and frame[:6]==flow.session.host and header['command_field']==0xa0
                        and header['ack_candidate']==sequence and not report['ack_received']):
                    report['ack_received'] = True
                    deadline = time.monotonic()+settle
            if not report['ack_received']:raise RuntimeError('ACK de requête absent ; aucun retry')
        except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as exc:
            report['error'] = str(exc) or type(exc).__name__
        finally:
            if rx.family == socket.AF_PACKET:
                try:report['socket_packets'],report['socket_drops'] = struct.unpack('II',rx.getsockopt(263,6,8))
                except OSError as exc:report['socket_statistics_error'] = str(exc)
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    report['pcap_sha256'] = digest(path.read_bytes())
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def acquire(rx, tx, flow, output, address, length):
    request_for(address,length)
    report = {'started_utc':datetime.now(timezone.utc).isoformat(),'address':address,'length':length,
              'source_sha256':digest(Path(__file__).read_bytes()),'complete':False,'error':None,
              'method':'Read retained comm RX bytes after bounded fader U/q or U/Q request',
              'request_attempted':False,'steps':[]}

    def step(name, **kwargs):
        folder = output/name;folder.mkdir(mode=0o700)
        result = run_probe(rx,tx,flow,folder,**kwargs)
        report['steps'].append({'name':name,'result_sha256':digest((folder/'result.json').read_bytes())})
        if result['error']:raise RuntimeError(f'{name}: {result["error"]}')
        return (folder/'memory.bin').read_bytes() if (folder/'memory.bin').exists() else None

    try:
        gate = output/'versions';gate.mkdir(mode=0o700)
        version = run_fader_version(rx,tx,flow,gate)
        report['steps'].append({'name':'versions','result_sha256':digest((gate/'result.json').read_bytes())})
        if version['error']:raise RuntimeError(version['error'])
        touch = step('touch-before',state='fader-touch-state')
        mode = step('mode-before',state='fader-mode')
        if any(touch) or mode != b'\0':raise RuntimeError('Faders touchés ou mode non normal ; lecture refusée')
        report['parser_errors_before'] = int.from_bytes(step('errors-before',state='fader-errors'),'big')
        before = ring_header(step('rx-before',state='fader-rx-ring'))
        report['rx_before'] = before
        if before['producer'] != before['consumer']:raise RuntimeError('File RX non vide avant lecture')
        folder = output/'request';folder.mkdir(mode=0o700)
        report['request_attempted'] = True
        request = capture_request(rx,tx,flow,folder,address,length)
        report['steps'].append({'name':'request','result_sha256':digest((folder/'result.json').read_bytes())})
        if request['error']:raise RuntimeError(request['error'])
        after = ring_header(step('rx-after',state='fader-rx-ring'))
        report['rx_after'] = after
        expected = 5+21*length
        if ((after['producer']-before['producer']) % RX_BUFFER_SIZE != expected or
                after['overflows'] != before['overflows']):
            raise RuntimeError('Production RX inattendue ou débordement ; snapshot non attribuable')
        raw = bytearray()
        for index,(offset,size) in enumerate(ring_windows(before['producer'],expected)):
            raw.extend(step(f'rx-data-{index}',ring_offset=offset,length=size,batch_size=16))
        (output/'serial.bin').write_bytes(raw)
        report['serial_sha256'] = digest(raw)
        final = ring_header(step('rx-final',state='fader-rx-ring'))
        report['rx_final'] = final
        if final['producer'] != after['producer'] or final['overflows'] != after['overflows']:
            raise RuntimeError('Tampon RX modifié pendant sa lecture')
        data = parse_serial(raw,address,length)
        report['read_bytes_hex'] = data.hex(' ')
        report['memory_sha256'] = digest(data)
        (output/'memory.bin').write_bytes(data)
        # Version also flushes any partial trailing response in the comm parser.
        step('fader-version-after',target='fader')
        if step('touch-after',state='fader-touch-state') != touch:
            raise RuntimeError('État tactile du relais modifié ; ne pas poursuivre les lectures')
        if step('mode-after',state='fader-mode') != mode:
            raise RuntimeError('Mode du relais modifié')
        report['parser_errors_after'] = int.from_bytes(step('errors-after',state='fader-errors'),'big')
        report['complete'] = True
    except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as exc:
        report['error'] = str(exc) or type(exc).__name__
        if report['request_attempted']:
            try:
                step('recovery-version',target='fader')
                report['recovery'] = {
                    'version_confirmed':True,
                    'touch_unchanged':step('recovery-touch',state='fader-touch-state')==touch,
                    'mode_unchanged':step('recovery-mode',state='fader-mode')==mode}
            except (OSError,ValueError,RuntimeError,KeyboardInterrupt) as recovery:
                report['recovery_error'] = str(recovery) or type(recovery).__name__
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address',type=lambda x:int(x,0),default=0x8000)
    parser.add_argument('--length',type=int,default=1)
    parser.add_argument('--interface',default='enp0s25')
    parser.add_argument('--mac',type=mac_address,default='00:a0:7e:a0:ad:9c')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--send',action='store_true')
    args = parser.parse_args()
    try:body = request_for(args.address,args.length)
    except ValueError as exc:parser.error(str(exc))
    if not args.send:
        print(json.dumps({'network_opened':False,'fader_read_hex':body.hex(' '),
                          'prerequisites':['COMv1.37','FDRv1.37','normal mode','no touch','RX empty'],
                          'expected_serial_bytes':5+21*args.length}));return 0
    if os.geteuid()==0:parser.error('Utiliser le compte utilisateur et le helper installé')
    if args.output is None or args.output.exists():parser.error('Nouveau dossier --output requis')
    interface = Path('/sys/class/net')/args.interface
    if (not args.interface or '/' in args.interface or not (interface/'type').exists()
            or (interface/'type').read_text().strip()!='1' or (interface/'wireless').exists()):
        parser.error('Interface Ethernet filaire requise')
    host = (interface/'address').read_text().strip();peer = mac_bytes(args.mac)
    if not any(peer) or peer[0]&1 or peer==mac_bytes(host):parser.error('MAC console unicast distincte requise')
    with exclusive_console(ROOT/'run'):
        rx,tx = packet_sockets(args.interface)
        with rx,tx:
            rx.bind((args.interface,0));tx.bind((args.interface,0))
            rx.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
            args.output.mkdir(parents=True,mode=0o700)
            result = acquire(rx,tx,ConsoleSession(host,args.mac),args.output,args.address,args.length)
    print(json.dumps(result,indent=2,ensure_ascii=False));return int(not result['complete'])


if __name__=='__main__':raise SystemExit(main())
