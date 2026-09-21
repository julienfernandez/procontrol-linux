import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_comm_application as audit
import comm_application_gaps as collect
import comm_preservation as common
import firmware_probe as probe
import test_preservation_fields as fixture
from inspect_pcap import packets
from pcap_writer import write_header,write_packet


class ApplicationTests(unittest.TestCase):
    def test_preview_is_offline_and_names_exactly_the_missing_ranges(self):
        with patch.object(common,'run_live') as live,contextlib.redirect_stdout(io.StringIO())as output:
            self.assertEqual(collect.main([]),0)
        preview=json.loads(output.getvalue());live.assert_not_called()
        self.assertFalse(preview['network_opened']);self.assertEqual(preview['bytes_per_pass'],1770)
        self.assertEqual(preview['fields'],{n:list(v)for n,v in audit.FIELDS.items()})
        for name,(start,size)in audit.FIELDS.items():
            plan=probe.requests_for(state=name,batch_size=16)
            self.assertEqual(sum(len(body)-15 for _,body in plan[1:]),size)
            self.assertEqual(plan[-1][0]+len(plan[-1][1])-15,start+size)
            for overrides in ({'address':start},{'length':size},{'target':'fader'},
                              {'batch_size':32},{'ring_offset':0}):
                with self.assertRaises(ValueError):probe.requests_for(state=name,**overrides)

    def fixture(self,root,changed=False,drops=0):
        calls=[]
        def read(rx,tx,flow,folder,state,batch_size):
            calls.append(state);self.assertEqual(batch_size,16)
            data=bytes([255 if changed and len(calls)>5 else 0])*audit.FIELDS[state][1]
            _,result=fixture.PreservationFieldsTests().fixture(folder,state,data)
            path=folder/'traffic.pcap';frames=list(packets(path))
            with path.open('wb')as stream:
                write_header(stream)
                for stamp,frame,wire in frames:write_packet(stream,stamp+len(calls)*1000000000,frame)
            result.update(socket_drops=drops,pcap_sha256=common.sha(path.read_bytes()))
            (folder/'result.json').write_text(json.dumps(result));return result
        with patch.dict(fixture.RANGES,audit.FIELDS),patch.object(common,'run_probe',side_effect=read):
            manifest=collect.acquire(None,None,None,root,bytes.fromhex(fixture.HOST.replace(':','')),
                                     bytes.fromhex(fixture.PEER.replace(':','')))
        return manifest,calls

    def check(self,root):
        return audit.audit_fields(root,bytes.fromhex(fixture.HOST.replace(':','')),
            bytes.fromhex(fixture.PEER.replace(':','')),fields=audit.FIELDS,
            schema='comm-application-gaps-v1',interpreter=None)

    def test_independent_gap_capture_audit_and_changed_pass_are_preserved(self):
        for changed in (False,True):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);manifest,calls=self.fixture(root,changed=changed)
                self.assertTrue(manifest['complete']);self.assertEqual(calls,list(audit.FIELDS)*2)
                checked=self.check(root);self.assertEqual(checked['pcap_files'],10)
                self.assertEqual(checked['persistent_fields_equal'],not changed)

    def test_socket_loss_stops_without_retry(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);manifest,calls=self.fixture(root,drops=1)
            self.assertFalse(manifest['complete']);self.assertEqual(len(calls),1)
            with self.assertRaises(ValueError):self.check(root)

    def test_full_assembly_never_fills_a_missing_byte_or_overwrites_overlap(self):
        pieces=[(0x20000,b'\xff'*8),(0x20008,b'\0'*(65536-8))]
        image=audit.assemble(list(reversed(pieces)))
        self.assertEqual(len(image),65536);self.assertEqual(sum(image)&0xffff,2040)
        for malformed in ([pieces[0]],[(0x20000,b'\0'*65535)],
                          [pieces[0],(0x20007,b'\0'*(65536-7))],
                          [pieces[0],(0x20009,b'\0'*(65536-9))],
                          [(0x20000,b'\0'*65537)],pieces+[(0x30000,b'\0')]):
            with self.assertRaises(ValueError):audit.assemble(malformed)


if __name__=='__main__':unittest.main()
