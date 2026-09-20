from pathlib import Path
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import firmware_probe as probe
from audit_firmware_probe import audit_probe
from pcap_writer import write_header,write_packet
from session_probe import Session
import test_firmware_probe as existing

HOST='02:00:00:00:00:01';PEER='00:a0:7e:a0:ad:9c'
RANGES={'comm-boot-vectors':(0,8),'comm-application-checksum':(0x30000,2),
        'comm-network-settings':(0x34000,10),'comm-utility-settings':(0x3c000,88),
        'comm-utility-mirror':(0x40000,88)}


class PreservationFieldsTests(unittest.TestCase):
    def test_named_fields_have_exact_bounds_and_no_free_address_extension(self):
        for name,(address,length) in RANGES.items():
            with self.subTest(name=name):
                plan=probe.requests_for(state=name,batch_size=16)
                self.assertEqual(plan[0][1],probe.VERSION_REQUEST)
                expected=[(a,min(16,address+length-a)) for a in range(address,address+length,16)]
                self.assertEqual(plan[1:],[(a,probe.PREFIX+f'A{a:08X}'.encode()+b'M'*n+b'\xf7')for a,n in expected])
                for args in ({'address':address},{'length':length},{'target':'fader'},
                             {'ring_offset':0},{'batch_size':17}):
                    with self.assertRaises(ValueError):probe.requests_for(state=name,**args)
                with self.assertRaises(ValueError):probe.requests_for(address=address,length=length)

    def test_zero_address_and_utility_block_work_over_simulated_link(self):
        for name in ('comm-boot-vectors','comm-utility-settings'):
            with self.subTest(name=name):existing.FirmwareProbeTests().exercise_reads(state=name)

    def test_preview_never_opens_sockets(self):
        for name in RANGES:
            with patch.object(probe,'packet_sockets',side_effect=AssertionError('network')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(probe.main(['--read-state',name,'--batch-size','16']),0)
            self.assertFalse(json.loads(output.getvalue())['network_opened'])

    def fixture(self,folder,name,data=None):
        address,length=RANGES[name]
        if data is None:data=bytes((i*71+247)%256 for i in range(length))
        assert len(data)==length
        host=Session(HOST,PEER);peer=Session(PEER,HOST);prefix=bytes.fromhex('f0 13 00 70 00')
        frames=[host.frame(0,1,2,body=prefix+b'V\xf7'),peer.frame(0xa0,ack=2),
                peer.frame(0,1,10,body=prefix+b'COMv1.37\n\r\xf7')]
        for i,offset in enumerate(range(0,length,16),3):
            loc=address+offset;part=data[offset:offset+16]
            frames.extend([host.frame(0,1,i,body=prefix+f'A{loc:08X}'.encode()+b'M'*len(part)+b'\xf7'),peer.frame(0xa0,ack=i)])
            reply=prefix+b'\n\r\xf7'+b''.join(prefix+f"{loc+j:08X}: {v:02X} '".encode()+bytes([v])+b"'\n\r\xf7"for j,v in enumerate(part))
            frames.append(peer.frame(0,1+len(part),100+i,body=reply))
        path=folder/'traffic.pcap'
        with path.open('wb') as f:
            write_header(f)
            for i,frame in enumerate(frames):write_packet(f,1700000000000000000+i*1000000,frame)
        sha=lambda b:hashlib.sha256(b).hexdigest()
        (folder/'memory.bin').write_bytes(data)
        report={'target':'comm','read_state':name,'read_address':address,'read_length':length,
                'read_bytes_hex':data.hex(),'memory_sha256':sha(data),'pcap_sha256':sha(path.read_bytes()),'error':None}
        (folder/'result.json').write_text(json.dumps(report))
        return data,report

    def audit(self,folder):
        return audit_probe(folder,bytes.fromhex(HOST.replace(':','')),bytes.fromhex(PEER.replace(':','')))

    def test_independent_audit_reconstructs_each_named_field(self):
        for name in RANGES:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);data,_=self.fixture(folder,name);result=self.audit(folder)
                self.assertTrue(result['observed_complete'])
                self.assertEqual(bytes.fromhex(result['data_hex']),data)

    def test_false_bounds_and_tampered_bytes_are_rejected(self):
        for tamper in ('bounds','bytes'):
            with self.subTest(tamper=tamper),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);data,report=self.fixture(folder,'comm-utility-settings')
                if tamper=='bounds':
                    report['read_address']+=1;(folder/'result.json').write_text(json.dumps(report))
                else:(folder/'memory.bin').write_bytes(bytes(len(data)))
                with self.assertRaises(ValueError):self.audit(folder)


if __name__=='__main__':unittest.main()
