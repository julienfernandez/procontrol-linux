from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fader_serial_probe as probe


def serial(plan,data):
    result=bytearray();cursor=0
    for address,length in plan:
        result.extend(b'\0\x20\x02\n\r')
        for i in range(length):
            v=data[cursor];cursor+=1
            result.extend(b'\0\x20\x12'+f"{address+i:08X}: {v:02X} '".encode()+bytes([v])+b"'\n\r")
    return bytes(result)


class FaderSerialProbeTests(unittest.TestCase):
    def test_release_and_pair_requests_are_reads_only(self):
        body,size=probe.request_for(probe.RELEASE_PLAN)
        self.assertEqual(size,208)
        self.assertEqual(body.count(b'q'),8)
        self.assertNotIn(b'W',body)
        body,size=probe.request_for(probe.PAIR_PLAN)
        self.assertEqual(size,52)
        self.assertEqual(body,bytes.fromhex('f0 13 00 70 01')+b'U00008459qU00008455q\xf7')

    def test_full_block_always_ends_with_all_releases_and_fits_rx(self):
        plan=probe.code_plan(0x8400,12)
        self.assertEqual(plan[-8:],probe.RELEASE_PLAN)
        self.assertEqual(probe.request_for(plan)[1],465)
        for addr,length in [(0x8400,13),(0x807f,2),(0x8008,1),(0x8000071b,1)]:
            with self.assertRaises(ValueError):probe.code_plan(addr,length)

    def test_serial_parser_preserves_and_checks_both_byte_forms(self):
        plan=probe.code_plan(0x8400,8)
        values=bytes([0,0x80,0xf7,10,13,39,0xc0,0xff])+bytes(range(0xd0,0xd8))
        raw=serial(plan,values)
        self.assertEqual(probe.parse_serial(raw,plan),values)
        for bad in [raw[:-1],b'x'+raw[1:],raw[:22]+b'x'+raw[23:]]:
            with self.assertRaises(ValueError):probe.parse_serial(bad,plan)

    def test_unknown_code_requires_verified_release_prerequisite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for plan in [probe.code_plan(0x8400,12),probe.PAIR_PLAN,((0x8459,1),)]:
                with self.assertRaises(ValueError):probe.acquire_plan(None,None,None,root,plan)
            self.assertEqual(list(root.iterdir()),[])

    def simulate(self,touched=False,overwritten=False,state=None,length=12):
        base=0x6bf26;offset=450
        plan=probe.code_plan(0x8400,length) if state is None else probe.preservation_plan(state,0,length)
        values=bytes([0xc0,0x80,0,0xf7]*3)[:length]+bytes(range(0xd0,0xd8))
        raw=serial(plan,values);ring=bytearray(488)
        for i,v in enumerate(raw):ring[(offset+i)%488]=v
        before=base+offset;after=base+(offset+len(raw))%488
        requests=[]
        def save(folder,data=None):
            result={'error':None};(folder/'result.json').write_text(json.dumps(result))
            if data is not None:(folder/'memory.bin').write_bytes(data)
            return result
        def read(rx,tx,flow,folder,**kwargs):
            state=kwargs.get('state');data=None
            if state=='fader-mode':data=b'\0'
            elif state=='fader-touch-state':data=b'\0\1'+bytes(14) if touched and folder.name=='touch-before' else bytes(16)
            elif state=='fader-errors':data=bytes(4)
            elif state=='fader-rx-ring':
                pointer=before if folder.name=='rx-before' else after
                if overwritten and folder.name=='rx-final':pointer+=1
                data=struct.pack('>6I',pointer,base,pointer,512,0,0)
            elif kwargs.get('ring_offset') is not None:
                start=kwargs['ring_offset'];data=ring[start:start+kwargs['length']]
            return save(folder,data)
        def capture(rx,tx,flow,folder,plan,**kwargs):
            if folder.name=='request':self.assertEqual(kwargs.get('state'),state)
            else:self.assertNotIn('state',kwargs)
            requests.append(plan);return save(folder)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(probe,'run_probe',side_effect=read),\
                 patch.object(probe,'run_fader_version',side_effect=lambda a,b,c,d:save(d)),\
                 patch.object(probe,'capture_plan',side_effect=capture):
                result=probe.acquire_plan(None,None,None,root,plan,release_verified=True,state=state)
            if touched:self.assertFalse(result['request_attempted']);self.assertEqual(requests,[])
            elif overwritten:
                self.assertFalse(result['complete']);self.assertTrue(result['recovery_touch_neutral'])
                self.assertEqual(requests[-1],probe.RELEASE_PLAN)
            else:
                self.assertTrue(result['complete']);self.assertEqual((root/'memory.bin').read_bytes(),values)

    def test_wrapped_plan_reconstructs_data_and_all_release_bytes(self):self.simulate()
    def test_real_touch_prevents_reading(self):self.simulate(touched=True)
    def test_overwritten_data_aborts_and_checks_recovery(self):self.simulate(overwritten=True)


if __name__=='__main__':unittest.main()
