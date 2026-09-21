import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fader_rx_benchmark as collect
import fader_serial_probe as fader
import firmware_probe as comm
import audit_fader_serial as audit
import test_fader_serial_probe as simulation
import test_firmware_batches as socket_test
import test_preservation_fields as counter_fixture
from test_audit_fader_readback import fixture,HOST_BYTES,PEER_BYTES
from inspect_pcap import packets
from pcap_writer import write_header,write_packet


class RxBenchmarkTests(unittest.TestCase):
    def test_rx_flag_requires_bounded_rx_window_and_never_authorizes_code_or_fields(self):
        allowed=dict(ring_offset=450,length=38,batch_size=32,experimental_rx_batch32=True)
        self.assertEqual(len(comm.requests_for(**allowed)),3)
        for change in ({'length':39},{'ring_offset':-1},{'ring_offset':488},
                       {'address':0x20400},{'state':'fader-rx-ring'},{'target':'fader'},
                       {'batch_size':16},{'experimental_batch32':True},
                       {'experimental_rx_batch32':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                comm.requests_for(**{**allowed,**change})
        with tempfile.TemporaryDirectory()as tmp:
            for plan,state in [(fader.RELEASE_PLAN,None),(fader.code_plan(0x8401,12),None),
                               (fader.preservation_plan('fader-calibration-state',0,12),'fader-calibration-state')]:
                with self.assertRaises(ValueError):
                    fader.acquire_plan(None,None,None,Path(tmp),plan,release_verified=True,state=state,
                                       experimental_rx_batch32=True)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_rx_32_real_socket_and_wrapped_serial_checks_and_recovery(self):
        socket_test.BatchTests().exchange(experimental_rx=True)
        socket_test.BatchTests().exchange(experimental_rx=True,incomplete=True)
        simulation.FaderSerialProbeTests().simulate(experimental=True)
        simulation.FaderSerialProbeTests().simulate(experimental=True,overwritten=True)

    def test_independent_audit_checks_actual_rx_batch_size_not_manifest_label(self):
        plan=fader.code_plan(0x8400,12);values=bytes([0,0x80,0xf7,10,13,39]*2)+bytes(range(0xd0,0xd8))
        for batch,valid in [(32,True),(16,False)]:
            with self.subTest(batch=batch),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);manifest=fixture(root,plan,values,rx_batch=batch)
                manifest['experimental_rx_batch32']=True
                (root/'manifest.json').write_text(json.dumps(manifest))
                if valid:
                    checked=audit.audit_plan(root,HOST_BYTES,PEER_BYTES)
                    self.assertEqual(checked['rx_batch_size'],32)
                    self.assertEqual(bytes.fromhex(checked['data_hex']),values)
                else:
                    with self.assertRaisesRegex(ValueError,'lot'):audit.audit_plan(root,HOST_BYTES,PEER_BYTES)

    def synthetic(self,root,overflow=False):
        calls=[];reference=bytes(range(12))
        def stamp():
            calls.append(1);return 1700000000000000000+len(calls)*10000000000
        def read(rx,tx,flow,folder,plan,release_verified,expected,experimental_rx_batch32):
            epoch=stamp();data=(reference if release_verified else b'')+bytes(range(0xd0,0xd8))
            self.assertEqual(expected,data)
            result=fixture(folder,plan,data,epoch_ns=epoch,socket_drops=0,
                           rx_batch=32 if experimental_rx_batch32 else 16)
            result.update(started_utc='2026-09-21T00:00:00+00:00',finished_utc='2026-09-21T00:00:02+00:00')
            if experimental_rx_batch32:result['experimental_rx_batch32']=True
            for row in result['steps']:
                p=folder/row['name']/'result.json';saved=json.loads(p.read_text())
                saved.update(started_utc=result['started_utc'],finished_utc='2026-09-21T00:00:00.1+00:00')
                if row['name'].startswith('rx-data-'):saved['read_length']=len((p.parent/'memory.bin').read_bytes())
                p.write_text(json.dumps(saved));row['result_sha256']=collect.sha(p.read_bytes())
            (folder/'manifest.json').write_text(json.dumps(result));return result
        def counter(rx,tx,flow,folder,**kwargs):
            epoch=stamp();value=int(overflow and len(calls)==4)
            _,result=counter_fixture.PreservationFieldsTests().fixture(folder,'comm-diagnostic-overflows',value.to_bytes(4,'big'))
            p=folder/'traffic.pcap';frames=list(packets(p))
            with p.open('wb')as stream:
                write_header(stream)
                for i,(_,frame,_)in enumerate(frames):write_packet(stream,epoch+i*1000000,frame)
            result.update(socket_drops=0,pcap_sha256=collect.sha(p.read_bytes()))
            (folder/'result.json').write_text(json.dumps(result));return result
        with patch.object(collect,'acquire_plan',side_effect=read),patch.object(collect,'run_probe',side_effect=counter),\
             patch.dict(counter_fixture.RANGES,{'comm-diagnostic-overflows':(0x6b51e,4)}):
            result=collect.acquire(None,None,None,root,HOST_BYTES,PEER_BYTES,reference)
        return result,calls

    def test_eight_audited_blocks_after_release_proof_and_stop_on_overflow(self):
        for overflow,count in [(False,25),(True,4)]:
            with self.subTest(overflow=overflow),tempfile.TemporaryDirectory()as tmp:
                result,calls=self.synthetic(Path(tmp),overflow)
                self.assertEqual(result['complete'],not overflow);self.assertEqual(len(calls),count)
                self.assertTrue((Path(tmp)/'manifest.json').exists())

    def test_preview_never_opens_network(self):
        with patch.object(collect,'run_live')as live,contextlib.redirect_stdout(io.StringIO())as out:
            self.assertEqual(collect.main([]),0)
        self.assertFalse(json.loads(out.getvalue())['network_opened']);live.assert_not_called()


if __name__=='__main__':unittest.main()
