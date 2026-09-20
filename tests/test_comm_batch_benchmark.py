import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import comm_batch_benchmark as collect
import firmware_probe as probe
from pcap_writer import write_header, write_packet
from session_probe import Session

HOST = '02:00:00:00:00:01'
PEER = '00:a0:7e:a0:ad:9c'


class BatchBenchmarkTests(unittest.TestCase):
    def acquire_fixture(self, root, fault=None):
        calls = []
        reference = bytes(range(256))

        def reader(rx, tx, flow, folder, **kwargs):
            calls.append(kwargs)
            state = kwargs.get('state')
            start, data = ((0x6b51e, (1 if fault == 'overflow' and len(calls) == 3 else 0).to_bytes(4, 'big'))
                           if state else (collect.START, reference))
            if not state and fault == 'reference': data = b'\xff'+data[1:]
            batch = kwargs['batch_size']
            host, peer = Session(HOST, PEER), Session(PEER, HOST)
            prefix = bytes.fromhex('f0 13 00 70 00')
            frames = [host.frame(0, 1, 2, body=prefix+b'V\xf7'), peer.frame(0xa0, ack=2),
                      peer.frame(0, 1, 10, body=prefix+b'COMv1.37\n\r\xf7')]
            for i, offset in enumerate(range(0, len(data), batch), 3):
                part = data[offset:offset+batch]; address = start+offset
                frames.extend([host.frame(0, 1, i, body=prefix+f'A{address:08X}'.encode()+b'M'*len(part)+b'\xf7'),
                               peer.frame(0xa0, ack=i)])
                reply = prefix+b'\n\r\xf7'+b''.join(
                    prefix+f"{address+j:08X}: {v:02X} '".encode()+bytes([v])+b"'\n\r\xf7"
                    for j, v in enumerate(part))
                frames.append(peer.frame(0, 1+len(part), 100+i, body=reply))
            path = folder/'traffic.pcap'
            with path.open('wb') as stream:
                write_header(stream)
                for i, frame in enumerate(frames):
                    write_packet(stream, 1700000000000000000+len(calls)*1000000000+i*1000000, frame)
            (folder/'memory.bin').write_bytes(data)
            result = {'error': None, 'target': 'comm', 'read_state': state,
                      'read_address': start, 'read_length': len(data), 'read_bytes_hex': data.hex(),
                      'memory_sha256': collect.sha(data), 'pcap_sha256': collect.sha(path.read_bytes()),
                      'socket_drops': 1 if fault == 'drops' else 0,
                      'started_utc': '2026-09-20T23:00:00+00:00',
                      'finished_utc': '2026-09-20T23:00:00.500000+00:00'}
            (folder/'result.json').write_text(json.dumps(result))
            return result

        with patch.object(collect, 'run_probe', side_effect=reader):
            result = collect.acquire(None, None, None, root,
                bytes.fromhex(HOST.replace(':', '')), bytes.fromhex(PEER.replace(':', '')), reference)
        return result, calls

    def test_fixed_pilot_audits_24_captures_and_all_reference_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result, calls = self.acquire_fixture(root)
            self.assertTrue(result['complete']); self.assertEqual(len(calls), 24)
            self.assertEqual([r['batch_size'] for r in result['runs']], list(collect.ORDER))
            self.assertEqual(result['median_ratio_16_over_32'], 1)
            self.assertEqual(len(list(root.glob('run-*/*/audit.json'))), 24)
            for run in result['runs']:
                self.assertEqual(run['counts']['memory_requests'], 256//run['batch_size'])
                self.assertEqual(run['overflows_before'], run['overflows_after'])

    def test_overflow_bad_reference_and_drops_stop_without_retry_and_preserve_failure(self):
        for fault, expected_calls in [('overflow', 3), ('reference', 2), ('drops', 1)]:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); result, calls = self.acquire_fixture(root, fault)
                self.assertFalse(result['complete']); self.assertIsNotNone(result['error'])
                self.assertEqual(len(calls), expected_calls)
                self.assertFalse(json.loads((root/'manifest.json').read_text())['complete'])
                self.assertEqual(len(list(root.glob('run-*/*/traffic.pcap'))), expected_calls)

    def test_counter_address_exact_and_no_arbitrary_ram(self):
        requests = probe.requests_for(state=collect.COUNTER, batch_size=16)
        self.assertEqual(requests[1][1], probe.PREFIX+b'A0006B51E'+b'M'*4+b'\xf7')
        with self.assertRaises(ValueError): probe.requests_for(address=0x6b51e, length=4)

    def test_preview_opens_no_network_and_reference_hash_is_required(self):
        with patch.object(collect, 'run_live') as live, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(collect.main([]), 0)
        self.assertFalse(json.loads(out.getvalue())['network_opened']); live.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'reference.bin'; path.write_bytes(bytes(63716))
            with self.assertRaises(ValueError): collect.reference_bytes(path)


if __name__ == '__main__': unittest.main()
