from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_comm_archive import audit_chunk
from pcap_writer import write_header, write_packet
from session_probe import Session

HOST='02:00:00:00:00:01';PEER='00:a0:7e:a0:ad:9c'


class OfflineAuditTests(unittest.TestCase):
    def fixture(self,path,mode='valid'):
        host=Session(HOST,PEER);peer=Session(PEER,HOST)
        frames=[host.frame(0,1,2,body=bytes.fromhex('f0 13 00 70 00 56 f7')),
                peer.frame(0xa0,ack=2),
                peer.frame(0,1,10,body=bytes.fromhex('f0 13 00 70 00')+b'COMv1.37\n\r\xf7'),
                host.frame(0xa0,ack=10)]
        prefix=bytes.fromhex('f0 13 00 70 00')
        request=prefix+b'A00020000MM\xf7' if mode!='write' else prefix+b'WFF\xf7'
        frames.append(host.frame(0,1,3,body=request))
        if mode!='missing_ack':frames.append(peer.frame(0xa0,ack=3))
        body=prefix+b'\n\r\xf7'+prefix+b"00020000: F7 '\xf7'\n\r\xf7"
        count=2
        if mode!='missing_byte':
            body+=prefix+b"00020001: 90 '\x90'\n\r\xf7";count+=1
        if mode=='inconsistent':body=body.replace(b"F7 '\xf7'",b"F7 '\xf0'")
        frames.extend([peer.frame(0,count,11,body=body),host.frame(0xa0,ack=11),
                       peer.frame(0,count,11,body=body),host.frame(0xa0,ack=11)])
        if mode=='checksum':
            bad=bytearray(frames[-2]);bad[16]^=1;frames[-2]=bytes(bad)
        with path.open('wb') as f:
            write_header(f)
            for i,frame in enumerate(frames):write_packet(f,1700000000000000000+i*1000000,frame)

    def test_reconstructs_raw_bytes_from_concatenated_frames_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'traffic.pcap';self.fixture(p)
            data,r=audit_chunk(p,0x20000,2,bytes.fromhex(HOST.replace(':','')),bytes.fromhex(PEER.replace(':','')))
            self.assertEqual(data,b'\xf7\x90')
            self.assertEqual(r['counts']['duplicate_response_frames'],1)
            self.assertEqual(r['counts']['response_envelopes'],4)

    def test_corrupt_or_incomplete_capture_cannot_validate_an_archive(self):
        for mode in ['write','missing_ack','missing_byte','inconsistent','checksum']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'traffic.pcap';self.fixture(p,mode)
                with self.assertRaises(ValueError):
                    audit_chunk(p,0x20000,2,bytes.fromhex(HOST.replace(':','')),bytes.fromhex(PEER.replace(':','')))


if __name__=='__main__':unittest.main()
