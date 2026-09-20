import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fader_preservation as collect
import audit_fader_preservation as audit
import comm_preservation as shared
from test_audit_fader_readback import fixture,HOST_BYTES,PEER_BYTES


class FaderPreservationTests(unittest.TestCase):
    def test_shared_runner_dispatches_the_selected_collector_and_restarts(self):
        class Socket:
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def bind(self,*_):pass
            def setsockopt(self,*_):pass
        rx,tx=Socket(),Socket()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(shared,'exclusive_console',return_value=contextlib.nullcontext()),\
                 patch.object(shared,'packet_sockets',return_value=(rx,tx)),\
                 patch.object(shared,'acquire',side_effect=AssertionError('wrong collector')),\
                 patch.object(shared.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'started','')) as process,\
                 patch.object(collect,'acquire',return_value={'complete':True}) as reader:
                result=shared.run_live('fake0','02:00:00:00:00:01','00:a0:7e:a0:ad:9c',root,collector=reader)
            self.assertTrue(result['complete']);reader.assert_called_once()
            self.assertEqual(reader.call_args.args[:2],(rx,tx))
            self.assertEqual(reader.call_args.args[3:],(root,HOST_BYTES,PEER_BYTES))
            self.assertEqual([c.args[0][-1] for c in process.call_args_list],['stop','start'])

    def synthetic(self,root,fail_at=None,changed_field=None,drops=0):
        calls=[]
        def reader(rx,tx,flow,folder,plan,release_verified,state,expected):
            calls.append((state,release_verified))
            if len(calls)==fail_at:
                result={'complete':False,'error':'simulated failure'}
                (folder/'manifest.json').write_text(json.dumps(result));return result
            if not release_verified:
                self.assertEqual(expected,bytes(range(0xd0,0xd8)))
                values=expected
            else:
                self.assertIsNone(expected)
                address,length=plan[0];values=bytes((address+i)*71%256 for i in range(length))
                if changed_field==state and 'pass-2' in folder.parts:values=bytes([values[0]^1])+values[1:]
                values+=bytes(range(0xd0,0xd8))
            result=fixture(folder,plan,values,1700000000000000000+len(calls)*10000000000,socket_drops=drops)
            result['release_verified_before']=release_verified
            if state is not None:result['preservation_field']=state
            (folder/'manifest.json').write_text(json.dumps(result))
            return result
        with patch.object(collect,'acquire_plan',side_effect=reader):
            result=collect.acquire(None,None,None,root,HOST_BYTES,PEER_BYTES)
        return result,calls

    def test_preview_uses_no_network_and_reports_the_full_scope(self):
        with patch.object(collect,'run_live') as live,patch.object(collect,'preflight') as gate,\
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(collect.main([]),0)
        result=json.loads(output.getvalue())
        self.assertFalse(result['network_opened']);self.assertEqual(result['bytes_per_pass'],270)
        self.assertEqual(result['blocks_per_pass'],25);live.assert_not_called();gate.assert_not_called()

    def test_two_complete_passes_are_rebuilt_from_independent_pcaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result,calls=self.synthetic(root)
            self.assertTrue(result['complete']);self.assertEqual(len(calls),51)
            self.assertEqual(calls[0],(None,False))
            self.assertTrue(all(verified for _,verified in calls[1:]))
            checked=audit.audit(root,HOST_BYTES,PEER_BYTES)
            self.assertEqual(checked['counts']['data_bytes'],540)
            self.assertEqual(checked['counts']['data_blocks'],50)
            self.assertTrue(checked['persistent_fields_equal'])
            self.assertTrue(all(checked['field_passes_equal'].values()))
            self.assertEqual(len(checked['passes'][0]['interpretation']['calibration_state']['channels']),8)

    def test_failed_release_proof_prevents_unknown_memory_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result,calls=self.synthetic(root,fail_at=1)
            self.assertFalse(result['complete']);self.assertEqual(calls,[(None,False)])
            self.assertEqual(result['passes'],[])

    def test_failure_keeps_completed_blocks_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result,calls=self.synthetic(root,fail_at=7)
            self.assertFalse(result['complete']);self.assertEqual(len(calls),7)
            self.assertEqual(len(result['passes'][0]['fields'][-1]['blocks']),2)
            with self.assertRaisesRegex(ValueError,'incomplète'):audit.audit(root,HOST_BYTES,PEER_BYTES)

    def test_drop_counters_are_required_before_accepting_release_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result,calls=self.synthetic(root,drops=1)
            self.assertFalse(result['complete']);self.assertEqual(len(calls),1)
            self.assertIn('Pertes',result['error'])

    def test_changed_ram_is_preserved_separately_from_persistent_differences(self):
        for name,stable in [('fader-calibration-state',True),('fader-application-checksum',False)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);result,_=self.synthetic(root,changed_field=name)
                self.assertTrue(result['complete'])
                checked=audit.audit(root,HOST_BYTES,PEER_BYTES)
                self.assertFalse(checked['field_passes_equal'][name])
                self.assertEqual(checked['persistent_fields_equal'],stable)
                self.assertNotEqual((root/'pass-1'/name/'field.bin').read_bytes(),
                                    (root/'pass-2'/name/'field.bin').read_bytes())

    def test_duplicate_capture_missing_block_and_false_assembly_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest,_=self.synthetic(root)
            field=root/'pass-2/fader-boot-vectors/field.bin';original=field.read_bytes();field.write_bytes(bytes(8))
            with self.assertRaisesRegex(ValueError,'assemblé'):audit.audit(root,HOST_BYTES,PEER_BYTES)
            field.write_bytes(original)
            saved=json.dumps(manifest);manifest['passes'][1]['fields'][-1]['blocks'].pop()
            (root/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Couverture'):audit.audit(root,HOST_BYTES,PEER_BYTES)
            manifest=json.loads(saved)
            shutil.copytree(root/'pass-1/fader-boot-vectors',root/'pass-2/fader-boot-vectors',dirs_exist_ok=True)
            manifest['passes'][1]['fields'][0]=manifest['passes'][0]['fields'][0]
            (root/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'chronologie'):audit.audit(root,HOST_BYTES,PEER_BYTES)

    def test_calibration_offsets_and_raw_units_are_not_physical_validation(self):
        fields={name:bytes(n) for name,(_,n) in audit.FIELDS.items()}
        fields['fader-touch-thresholds']=bytes.fromhex('0059 0073')
        data=bytearray(256)
        for i in range(8):
            base=i*32;data[base:base+4]=(1000+i).to_bytes(4,'big')
            data[base+16:base+18]=(-3+i).to_bytes(2,'big',signed=True);data[base+27]=i
        fields['fader-calibration-state']=bytes(data)
        result=audit.interpret(fields)
        self.assertEqual(result['touch_thresholds']['0x44012_raw_s16'],89)
        self.assertEqual(result['touch_thresholds']['0x44014_raw_s16'],115)
        self.assertFalse(result['touch_thresholds']['raw_words_are_percentages'])
        state=result['calibration_state'];self.assertFalse(state['physical_calibration_validated'])
        self.assertFalse(state['snapshot_atomic']);self.assertFalse(state['calibration_triggered'])
        for i,row in enumerate(state['channels']):
            self.assertEqual(row['scale_word_raw'],1000+i);self.assertEqual(row['extent_signed'],-3+i)
            self.assertEqual(row['validity_flag_raw'],i);self.assertEqual(row['address'],0x4402a+i*32)


if __name__=='__main__':unittest.main()
