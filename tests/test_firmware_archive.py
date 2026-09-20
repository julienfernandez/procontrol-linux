import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import archive_comm_firmware as archive


class ArchiveTests(unittest.TestCase):
    def test_real_plan_covers_only_the_four_known_segments_once(self):
        addresses = [a for start,size in archive.chunk_plan() for a in range(start,start+size)]
        expected = [a for lo,hi in archive.CODE_SEGMENTS for a in range(lo,hi)]
        self.assertEqual(addresses,expected)
        self.assertEqual(len(addresses),63768)
        self.assertEqual(len(archive.chunk_plan()),252)
        self.assertEqual(archive.chunk_plan()[-1],(0x2fc00,228))

    def test_incomplete_acquisition_retains_progress_without_claiming_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            reference={lo:bytes(hi-lo) for lo,hi in archive.CODE_SEGMENTS}
            calls=[]
            def reader(rx,tx,flow,folder,**args):
                calls.append(args)
                if len(calls)==2:return {'error':'réponse manquante'}
                (folder/'memory.bin').write_bytes(bytes(args['length']))
                result={'error':None,'pcap_sha256':'synthetic','socket_drops':0}
                (folder/'result.json').write_text(json.dumps(result))
                return result
            result=archive.acquire(None,None,None,out,reference,reader,lambda _:None)
            self.assertFalse(result['complete'])
            self.assertIn('réponse manquante',result['error'])
            self.assertEqual(result['passes'][0]['bytes_read'],8)
            self.assertEqual((out/'pass-1/comm-00020000.bin').read_bytes(),bytes(8))
            self.assertEqual(json.loads((out/'manifest.json').read_text())['complete'],False)

    def exercise_complete(self, mismatch=False):
        # Small disjoint regions exercise both passes and file assembly without
        # mirroring the 63kB fixture or requiring manufacturer's proprietary data.
        segments=((0x20000,0x20008),(0x20064,0x20080),(0x20100,0x20110),(0x20400,0x20414))
        reference={lo:bytes(range(hi-lo)) for lo,hi in segments}
        with tempfile.TemporaryDirectory() as temp, patch.object(archive,'CODE_SEGMENTS',segments):
            out=Path(temp)
            def reader(rx,tx,flow,folder,**args):
                data=reference[args['address']]
                if mismatch and 'pass-2' in folder.parts:data=bytes([1])+data[1:]
                (folder/'memory.bin').write_bytes(data)
                result={'error':None,'pcap_sha256':'synthetic','socket_drops':0}
                (folder/'result.json').write_text(json.dumps(result))
                return result
            result=archive.acquire(None,None,None,out,reference,reader,lambda _:None)
            self.assertTrue(result['complete'])
            self.assertEqual(result['passes_equal'],not mismatch)
            self.assertEqual(result['matches_reference'],not mismatch)
            self.assertEqual([p['bytes_read'] for p in result['passes']],[72,72])
            self.assertEqual(len(result['passes'][0]['segments']),4)

    def test_two_matching_passes_publish_each_segment_separately(self):
        self.exercise_complete()

    def test_mismatched_real_data_is_preserved_and_not_validated(self):
        self.exercise_complete(mismatch=True)

    def test_reference_must_match_pinned_manufacturer_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            (out/'CODE-26-00020000.bin').write_bytes(bytes(8))
            with self.assertRaises(ValueError):archive.references(out)


if __name__=='__main__':unittest.main()
