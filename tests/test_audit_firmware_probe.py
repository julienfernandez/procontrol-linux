from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_firmware_probe import audit_version
from pcap_writer import write_header,write_packet
from session_probe import Session


class VersionAuditTests(unittest.TestCase):
    def capture(self, response=True, corrupt=False, wrong_target=False):
        host='02:00:00:00:00:01';peer='00:a0:7e:a0:ad:9c'
        outgoing=Session(host,peer);incoming=Session(peer,host)
        prefix=bytes.fromhex('f0 13 00 70 01')
        frames=[outgoing.frame(0,1,2,body=prefix+b'V\xf7'),incoming.frame(0xa0,ack=2)]
        if response:
            if wrong_target:prefix=bytes.fromhex('f0 13 00 70 00')
            reply=incoming.frame(0,1,100,body=prefix+b'FDRv1.37\n\r\xf7')
            if corrupt:
                damaged=bytearray(reply);damaged[36]^=1;reply=bytes(damaged)
            frames += [reply,reply]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'traffic.pcap'
            with path.open('wb') as file:
                write_header(file)
                for i,frame in enumerate(frames):write_packet(file,1_000_000_000+i*1_000_000,frame)
            return audit_version(path,'fader',bytes.fromhex(host.replace(':','')),
                                 bytes.fromhex(peer.replace(':','')))

    def test_complete_response_is_deduplicated_and_timed_from_capture(self):
        result=self.capture()
        self.assertTrue(result['observed_complete'])
        self.assertEqual(result['counts']['duplicates'],1)
        self.assertEqual(result['responses'][0]['request_to_response_ms'],2)

    def test_ack_only_and_wrong_channel_remain_incomplete(self):
        self.assertFalse(self.capture(response=False)['observed_complete'])
        self.assertFalse(self.capture(wrong_target=True)['observed_complete'])

    def test_corrupted_body_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Somme'):
            self.capture(corrupt=True)


if __name__ == '__main__':unittest.main()
