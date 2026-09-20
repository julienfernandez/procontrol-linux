from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_audit_fader_readback import fixture,HOST_BYTES,PEER_BYTES
import audit_fader_serial as audit


class FaderSerialAuditTests(unittest.TestCase):
    def test_reconstruct_release_proof_from_synthetic_pcaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root,audit.RELEASES,bytes(range(0xd0,0xd8)))
            result=audit.audit_plan(root,HOST_BYTES,PEER_BYTES)
            self.assertEqual(result['kind'],'release-proof')
            self.assertTrue(result['touch_neutral_before_after'])

    def test_code_and_release_plan_across_three_ram_windows(self):
        plan=((0x8400,12),)+audit.RELEASES
        values=bytes([0xc0,0,0xf7,0xe7]*3)+bytes(range(0xd0,0xd8))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root,plan,values)
            result=audit.audit_plan(root,HOST_BYTES,PEER_BYTES)
            self.assertEqual(bytes.fromhex(result['data_hex']),values)
            self.assertIn('rx-data-2',result['steps'])

    def test_wrong_release_character_is_rejected_even_with_consistent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root,audit.RELEASES,b'\xc0'+bytes(range(0xd1,0xd8)))
            with self.assertRaisesRegex(ValueError,'Relâchements'):audit.audit_plan(root,HOST_BYTES,PEER_BYTES)

    def test_touch_pair_requires_c0_then_d0(self):
        for values in [b'\xc0\xd0',b'\xd0\xc0']:
            with self.subTest(values=values),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);fixture(root,((0x8459,1),(0x8455,1)),values)
                if values==b'\xc0\xd0':self.assertEqual(audit.audit_plan(root,HOST_BYTES,PEER_BYTES)['kind'],'touch-pair')
                else:
                    with self.assertRaises(ValueError):audit.audit_plan(root,HOST_BYTES,PEER_BYTES)

    def test_no_release_tail_or_hole_can_be_authorized_by_manifest(self):
        for plan in [((0x8459,1),),((0x8008,1),)+audit.RELEASES,((0x8400,13),)+audit.RELEASES]:
            with self.assertRaises(ValueError):audit.validate_plan(plan)

    def test_manifest_cannot_hide_changed_rx_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m=fixture(root,audit.RELEASES,bytes(range(0xd0,0xd8)))
            m['rx_final']['producer']+=1;(root/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'En-tête'):audit.audit_plan(root,HOST_BYTES,PEER_BYTES)


if __name__=='__main__':unittest.main()
