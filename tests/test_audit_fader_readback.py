from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_fader_readback as audit
from pcap_writer import write_header,write_packet
from session_probe import Session

HOST='02:00:00:00:00:01'
PEER='00:a0:7e:a0:ad:9c'
HOST_BYTES=bytes.fromhex(HOST.replace(':',''))
PEER_BYTES=bytes.fromhex(PEER.replace(':',''))
COMM=bytes.fromhex('f0 13 00 70 00')
FADER=bytes.fromhex('f0 13 00 70 01')


def serial(data,address=0x8000):
    return b'\0\x20\x02\n\r'+b''.join(b'\0\x20\x12'+
        f"{address+i:08X}: {v:02X} '".encode()+bytes([v])+b"'\n\r" for i,v in enumerate(data))


def fixture(root,plan=None,values=None,epoch_ns=1700000000000000000,socket_drops=None,rx_batch=1):
    """Synthetic PCAP evidence; no hardware dump or live parser used."""
    host=Session(HOST,PEER);peer=Session(PEER,HOST)
    def write_capture(folder,transactions):
        frames=[]
        for index,(body,response) in enumerate(transactions,1):
            frames.extend([host.frame(0,1,index,body=body),peer.frame(0xa0,ack=index)])
            if response is not None:
                count,body=response if isinstance(response,tuple) else (1,response)
                frames.append(peer.frame(0,count,1000+index,body=body))
        path=folder/'traffic.pcap'
        with path.open('wb') as f:
            write_header(f)
            for i,frame in enumerate(frames):write_packet(f,epoch_ns+i*1000000,frame)
        return audit.sha(path.read_bytes())
    def save(folder,result):
        if socket_drops is not None:result['socket_drops']=socket_drops
        (folder/'result.json').write_text(json.dumps(result))
        return audit.sha((folder/'result.json').read_bytes())
    def version(folder,target):
        folder.mkdir(parents=True)
        prefix,value=(COMM,b'COMv1.37\n\r') if target=='comm' else (FADER,b'FDRv1.37\n\r')
        result={'target':target,'error':None,
                'pcap_sha256':write_capture(folder,[(prefix+b'V\xf7',prefix+value+b'\xf7')])}
        return result
    manifest={'complete':True,'error':None,'address':0x8000,'length':8,'steps':[]}
    if plan is not None:manifest['plan']=plan
    def record(name,result):
        manifest['steps'].append({'name':name,'result_sha256':save(root/name,result)})
    gate=version(root/'versions','fader')
    prerequisite=version(root/'versions/comm-version','comm')
    gate['comm_prerequisite']={'result_sha256':save(root/'versions/comm-version',prerequisite)}
    record('versions',gate)
    def memory(name,address,data,state=None,offset=None):
        folder=root/name;folder.mkdir()
        transactions=[(COMM+b'V\xf7',COMM+b'COMv1.37\n\r\xf7')]
        batch=rx_batch if offset is not None else 1
        for i in range(0,len(data),batch):
            loc=address+i;part=data[i:i+batch]
            response=b''.join(COMM+f"{loc+j:08X}: {v:02X} '".encode()+bytes([v])+b"'\n\r\xf7"
                              for j,v in enumerate(part))
            reads=b'm' if batch==1 else b'M'*len(part)
            if batch!=1:response=(1+len(part),COMM+b'\n\r\xf7'+response)
            transactions.append((COMM+f'A{loc:08X}'.encode()+reads+b'\xf7',response))
        (folder/'memory.bin').write_bytes(data)
        record(name,{'target':'comm','read_state':state,'read_ring_offset':offset,
                     'read_address':address,'read_length':len(data),'read_bytes_hex':data.hex(),
                     'memory_sha256':audit.sha(data),'error':None,
                     'pcap_sha256':write_capture(folder,transactions)})
    data=bytes([0,4,0x53,0x84,0,0,0xa4,0x70]) if values is None else values
    if plan is None:raw=serial(data)
    else:
        raw=b'';cursor=0
        for address,length in plan:
            raw+=serial(data[cursor:cursor+length],address);cursor+=length
    for side in ('before','after'):
        memory('touch-'+side,0x508ea,bytes(16),'fader-touch-state')
        memory('mode-'+side,0x5095c,b'\0','fader-mode')
        count=0 if side=='before' else 25
        memory('errors-'+side,0x509ba,count.to_bytes(4,'big'),'fader-errors')
        manifest['parser_errors_'+side]=count
    base=0x6bf26;before=base+480;after=base+(480+len(raw))%488
    for name,pointer in [('rx-before',before),('rx-after',after),('rx-final',after)]:
        fields={'producer':pointer,'base':base,'consumer':pointer,'size':512,'unknown':0,'overflows':0}
        manifest[name.replace('-','_')]=fields
        memory(name,0x6bf0e,struct.pack('>6I',*fields.values()),'fader-rx-ring')
    cursor=0;offset=480;index=0
    while cursor<len(raw):
        count=min(256,488-offset,len(raw)-cursor)
        memory(f'rx-data-{index}',base+offset,raw[cursor:cursor+count],offset=offset)
        cursor+=count;offset=(offset+count)%488;index+=1
    folder=root/'request';folder.mkdir()
    command=(b'U00008000'+b'Q'*8 if plan is None else
             b''.join(f'U{a:08X}'.encode()+(b'q' if n==1 else b'Q'*n) for a,n in plan))
    record('request',{'error':None,'pcap_sha256':write_capture(folder,[(FADER+command+b'\xf7',None)])})
    record('fader-version-after',version(root/'fader-version-after','fader'))
    for filename,content in [('serial.bin',raw),('memory.bin',data)]:(root/filename).write_bytes(content)
    manifest.update(serial_sha256=audit.sha(raw),memory_sha256=audit.sha(data),read_bytes_hex=data.hex())
    (root/'manifest.json').write_text(json.dumps(manifest))
    return manifest


class FaderAuditTests(unittest.TestCase):
    def test_binary_parser_does_not_split_on_null_f7_or_newline(self):
        data=bytes([0,0x80,0xf7,10,13,39,0xff,4])
        self.assertEqual(audit.decode_serial(serial(data),0x8000,8),data)
        with self.assertRaises(ValueError):audit.decode_serial(serial(data,0x8001),0x8000,8)
        bad=bytearray(serial(data));bad[22]=1
        with self.assertRaises(ValueError):audit.decode_serial(bad,0x8000,8)

    def test_complete_pcap_reconstruction_including_circular_wrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            result=audit.audit_readback(root,HOST_BYTES,PEER_BYTES)
            self.assertTrue(result['matches_saved_files'])
            self.assertEqual(result['data_hex'],'00 04 53 84 00 00 a4 70')
            self.assertEqual(result['parser_errors'],{'before':0,'after':25})

    def test_serial_file_tampering_is_detected_from_pcaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            raw=bytearray((root/'serial.bin').read_bytes());raw[-4]^=1
            (root/'serial.bin').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'Flux série'):audit.audit_readback(root,HOST_BYTES,PEER_BYTES)

    def test_omitted_request_or_duplicate_steps_are_rejected(self):
        for duplicate in (False,True):
            with self.subTest(duplicate=duplicate),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);manifest=fixture(root)
                if duplicate:manifest['steps'].append(manifest['steps'][0])
                else:manifest['steps']=[s for s in manifest['steps'] if s['name']!='request']
                (root/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,'obligatoire'):audit.audit_readback(root,HOST_BYTES,PEER_BYTES)

    def test_manifest_cannot_replace_observed_pointers_or_error_counts(self):
        for field in ('pointer','errors'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);manifest=fixture(root)
                if field=='pointer':manifest['rx_before']['producer']+=1
                else:manifest['parser_errors_after']=0
                (root/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,'manifeste'):audit.audit_readback(root,HOST_BYTES,PEER_BYTES)

    def test_memory_file_and_claimed_hash_cannot_override_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=fixture(root)
            changed=bytes(8);(root/'memory.bin').write_bytes(changed)
            manifest.update(memory_sha256=audit.sha(changed),read_bytes_hex=changed.hex())
            (root/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Octets fader'):audit.audit_readback(root,HOST_BYTES,PEER_BYTES)

    def test_missing_ack_is_not_a_valid_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'traffic.pcap'
            with path.open('wb') as f:
                write_header(f)
                write_packet(f,0,Session(HOST,PEER).frame(0,1,1,body=FADER+b'U00008000q\xf7'))
            with self.assertRaisesRegex(ValueError,'ACK absent'):audit.audit_request(path,0x8000,1,HOST_BYTES,PEER_BYTES)


if __name__=='__main__':unittest.main()
