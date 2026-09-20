from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fader_serial_probe as probe
import audit_fader_serial as audit
import test_fader_serial_probe as simulation
from test_audit_fader_readback import fixture,HOST_BYTES,PEER_BYTES

RANGES={'fader-boot-vectors':(0,8),'fader-application-checksum':(0xfffe,2),
        'fader-touch-thresholds':(0x44012,4),'fader-calibration-state':(0x4402a,256)}


class FaderPreservationFieldsTests(unittest.TestCase):
    def test_named_blocks_cover_only_the_documented_fields(self):
        for name,(start,size) in RANGES.items():
            with self.subTest(name=name):
                addresses=[]
                for offset in range(0,size,12):
                    length=min(12,size-offset);plan=probe.preservation_plan(name,offset,length)
                    self.assertEqual(plan,((start+offset,length),)+probe.RELEASE_PLAN)
                    _,serial_size=probe.request_for(plan,state=name)
                    self.assertLessEqual(serial_size,465)
                    addresses.extend(range(plan[0][0],plan[0][0]+length))
                    self.assertEqual(audit.validate_plan(plan,state=name)[1],'preservation-and-releases')
                    with self.assertRaises(ValueError):probe.code_plan(start+offset,length)
                    with self.assertRaises(ValueError):audit.validate_plan(plan)
                self.assertEqual(addresses,list(range(start,start+size)))

    def test_unknown_name_overrun_large_block_and_missing_releases_are_rejected(self):
        for name,(start,size) in RANGES.items():
            for offset,length in [(-1,1),(size,1),(size-1,2),(0,0),(0,13)]:
                with self.subTest(name=name,offset=offset,length=length):
                    with self.assertRaises(ValueError):probe.preservation_plan(name,offset,length)
                    with self.assertRaises(ValueError):audit.validate_plan(((start+offset,length),)+audit.RELEASES,state=name)
            for plan in [((start,1),),probe.RELEASE_PLAN,((0x8000071b,1),)+probe.RELEASE_PLAN]:
                with self.assertRaises(ValueError):probe.request_for(plan,state=name)
                with self.assertRaises(ValueError):audit.validate_plan(plan,state=name)
        with self.assertRaises(ValueError):probe.preservation_plan('arbitrary-ram',0,1)

    def test_new_fields_still_require_a_live_release_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,(_,size) in RANGES.items():
                plan=probe.preservation_plan(name,0,min(size,12))
                with self.assertRaises(ValueError):probe.acquire_plan(None,None,None,root,plan,state=name)
            self.assertEqual(list(root.iterdir()),[])

    def test_named_reads_use_the_same_ring_checks_and_recovery(self):
        for name,(_,size) in RANGES.items():
            with self.subTest(name=name):
                simulation.FaderSerialProbeTests().simulate(state=name,length=min(size,12))
        simulation.FaderSerialProbeTests().simulate(state='fader-calibration-state',overwritten=True)
        simulation.FaderSerialProbeTests().simulate(state='fader-calibration-state',touched=True)

    def test_independent_pcap_audit_preserves_control_and_high_bytes(self):
        for name,(address,size) in RANGES.items():
            length=min(size,12);plan=((address,length),)+audit.RELEASES
            values=bytes([0,0xf7,0xc0,0xd0,0x80,39,10,13,0xff,1,2,3])[:length]+bytes(range(0xd0,0xd8))
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);manifest=fixture(root,plan,values)
                manifest['preservation_field']=name;(root/'manifest.json').write_text(json.dumps(manifest))
                result=audit.audit_plan(root,HOST_BYTES,PEER_BYTES)
                self.assertEqual(bytes.fromhex(result['data_hex']),values)
                self.assertEqual(result['preservation_field'],name)
                self.assertEqual(probe.parse_serial(simulation.serial(plan,values),plan,state=name),values)

    def test_wrong_field_name_cannot_authorize_a_different_capture(self):
        plan=((0x44012,4),)+audit.RELEASES;values=bytes(4)+bytes(range(0xd0,0xd8))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=fixture(root,plan,values)
            for state in ('fader-boot-vectors',None,'arbitrary-ram'):
                manifest['preservation_field']=state;(root/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):audit.audit_plan(root,HOST_BYTES,PEER_BYTES)


if __name__=='__main__':unittest.main()
