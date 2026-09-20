import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fader_archive as archive


class FaderArchiveTests(unittest.TestCase):
    def test_plan_covers_every_known_byte_exactly_once_without_holes(self):
        wanted=[a for lo,hi in archive.SEGMENTS for a in range(lo,hi)]
        actual=[a for start,length in archive.blocks() for a in range(start,start+length)]
        self.assertEqual(actual,wanted)
        self.assertEqual(len(actual),11546)
        self.assertEqual(len(archive.blocks()),964)

    def test_preview_does_not_open_socket_or_stop_gateway(self):
        with patch.object(sys,'argv',['fader_archive.py']),patch.object(archive,'packet_sockets') as network,\
             patch.object(archive.subprocess,'run') as process,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(archive.main(),0)
        self.assertFalse(json.loads(out.getvalue())['network_opened'])
        network.assert_not_called();process.assert_not_called()

    def test_wrong_reference_is_rejected_before_network_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'CODE-27-00008000.bin').write_bytes(bytes(8))
            with self.assertRaises(ValueError):archive.references(root)

    def exercise(self,wrong=False,gate_fails=False):
        data=b'abcdefgh';calls=[];seen={}
        def read(rx,tx,flow,folder,plan,expected,verified):
            calls.append((folder.name,verified))
            value=bytes(range(0xd0,0xd8)) if folder.name=='release-proof' else (b'X'+data[1:] if wrong else data)+bytes(range(0xd0,0xd8))
            seen[folder]=value
            result={'complete':not (gate_fails and folder.name=='release-proof'),'error':'gate failed' if gate_fails else None}
            (folder/'manifest.json').write_text(json.dumps(result))
            return result
        def audit(folder,host,peer):return {'data_hex':seen[folder].hex()}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(archive,'SEGMENTS',((0x8000,0x8008),)),\
                 patch.object(archive,'acquire_plan',side_effect=read),patch.object(archive,'audit_plan',side_effect=audit):
                result=archive.acquire_archive(None,None,None,root,{0x8000:data},b'',b'')
            if gate_fails:
                self.assertFalse(result['complete']);self.assertEqual(calls,[('release-proof',False)])
            elif wrong:
                self.assertFalse(result['complete']);self.assertIn('différents',result['error'])
                self.assertFalse(result['passes'][0]['chunks'][0]['matches_reference'])
                self.assertEqual(len(calls),2)
            else:
                self.assertTrue(result['complete']);self.assertTrue(result['passes_equal'])
                self.assertEqual((root/'pass-1/fader-00008000.bin').read_bytes(),data)
                self.assertEqual((root/'pass-2/fader-00008000.bin').read_bytes(),data)
                self.assertEqual(calls,[('release-proof',False),('00008000',True),('00008000',True)])
            self.assertEqual(json.loads((root/'manifest.json').read_text())['complete'],result['complete'])

    def test_two_audited_passes_are_assembled_without_release_bytes(self):self.exercise()
    def test_reference_mismatch_is_preserved_and_aborts(self):self.exercise(wrong=True)
    def test_failed_release_gate_prevents_any_code_read(self):self.exercise(gate_fails=True)


if __name__=='__main__':unittest.main()
