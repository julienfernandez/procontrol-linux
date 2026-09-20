from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_fader_archive as archive
from audit_fader_serial import audit_plan,RELEASES
from test_audit_fader_readback import fixture,HOST_BYTES,PEER_BYTES


def make_archive(root,partial=False,reuse=False):
    value=bytes([0xc0,0,0x80,4,0xf7,10,13,39])
    def plan(folder,requests,values,epoch,verified):
        folder.mkdir(parents=True)
        m=fixture(folder,requests,values,epoch)
        m['release_verified_before']=verified
        (folder/'manifest.json').write_text(json.dumps(m))
        audit=audit_plan(folder,HOST_BYTES,PEER_BYTES)
        (folder/'audit.json').write_text(json.dumps(audit))
        return archive.sha((folder/'manifest.json').read_bytes()),archive.sha((folder/'audit.json').read_bytes())
    proof,_=plan(root/'release-proof',RELEASES,bytes(range(0xd0,0xd8)),1700000000000000000,False)
    report={'complete':not partial,'error':None,'planned_passes':2,'expected_bytes_per_pass':8,
            'release_proof_manifest_sha256':proof,'passes':[],'passes_equal':True}
    for number in range(1,2 if partial else 3):
        folder=root/f'pass-{number}/00008000'
        epoch=1700000010000000000 if reuse else 1700000000000000000+number*10000000000
        m,a=plan(folder,((0x8000,8),)+RELEASES,value+bytes(range(0xd0,0xd8)),epoch,True)
        (folder/'code.bin').write_bytes(value)
        (folder.parent/'fader-00008000.bin').write_bytes(value)
        report['passes'].append({'number':number,'complete':True,
            'segments':[{'address':0x8000,'length':8,'sha256':archive.sha(value),'matches_reference':True}],
            'chunks':[{'address':0x8000,'length':8,'sha256':archive.sha(value),
                       'manifest_sha256':m,'audit_sha256':a,'matches_reference':True}]})
    (root/'manifest.json').write_text(json.dumps(report))
    return report,{0x8000:value}


class FaderArchiveAuditTests(unittest.TestCase):
    def inspect(self,root,reference,prefix=False):
        with patch.object(archive,'SEGMENTS',((0x8000,0x8008),)):
            return archive.audit_archive(root,reference,HOST_BYTES,PEER_BYTES,prefix)

    def test_complete_two_pass_archive_rebuilds_from_real_synthetic_pcaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,reference=make_archive(root)
            result,images=self.inspect(root,reference)
            self.assertTrue(result['complete_archive']);self.assertTrue(result['passes_equal'])
            self.assertEqual(result['counts']['code_bytes'],16)
            self.assertEqual(images[(1,0x8000)],images[(2,0x8000)])

    def test_incomplete_archive_requires_explicit_prefix_and_stays_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,reference=make_archive(root,partial=True)
            with self.assertRaisesRegex(ValueError,'incomplète'):self.inspect(root,reference)
            result,_=self.inspect(root,reference,True)
            self.assertFalse(result['complete_archive']);self.assertTrue(result['completed_prefix_only'])
            self.assertIsNone(result['passes_equal']);self.assertEqual(result['counts']['code_blocks'],1)

    def test_prefix_ignores_uncommitted_in_progress_block_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,reference=make_archive(root,partial=True)
            active=root/'pass-2/00008000/request';active.mkdir(parents=True)
            (active/'traffic.pcap').write_bytes(b'not a closed capture')
            result,_=self.inspect(root,reference,True)
            self.assertEqual(result['counts']['code_blocks'],1)

    def test_copied_first_pass_cannot_count_as_an_independent_second_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,reference=make_archive(root,reuse=True)
            with self.assertRaisesRegex(ValueError,'Chronologie'):self.inspect(root,reference)

    def test_missing_duplicate_or_reordered_blocks_are_rejected(self):
        for mode in ('missing','duplicate','wrong-address'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);m,reference=make_archive(root)
                chunks=m['passes'][0]['chunks']
                if mode=='missing':chunks.clear()
                elif mode=='duplicate':chunks.append(chunks[0])
                else:chunks[0]['address']+=1
                (root/'manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):self.inspect(root,reference)

    def test_rebuilt_segment_cannot_be_replaced_by_a_matching_report_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m,reference=make_archive(root)
            data=b'changed!';(root/'pass-1/fader-00008000.bin').write_bytes(data)
            m['passes'][0]['segments'][0]['sha256']=archive.sha(data)
            (root/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'Segment déclaré'):self.inspect(root,reference)

    def test_cached_audit_tampering_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,reference=make_archive(root)
            path=root/'pass-1/00008000/audit.json';value=json.loads(path.read_text());value['data_hex']='00'
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'Audit enregistré'):self.inspect(root,reference)

    def test_cli_preserves_exact_manifest_snapshot_beside_its_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'archive';root.mkdir();_,reference=make_archive(root,partial=True)
            original=(root/'manifest.json').read_bytes();output=Path(tmp)/'audit.json'
            argv=['audit_fader_archive.py',str(root),'--reference','unused','--output',str(output),
                  '--completed-prefix','--host','02:00:00:00:00:01','--peer','00:a0:7e:a0:ad:9c']
            with patch.object(sys,'argv',argv),patch.object(archive,'load_reference',return_value=reference),\
                 patch.object(archive,'SEGMENTS',((0x8000,0x8008),)),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(archive.main(),0)
            saved=(Path(tmp)/'audit.manifest.json').read_bytes()
            result=json.loads(output.read_text())
            self.assertEqual(saved,original)
            self.assertEqual(result['manifest_snapshot_sha256'],archive.sha(saved))
            self.assertTrue(result['completed_prefix_only'])


if __name__=='__main__':unittest.main()
