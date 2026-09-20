import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_comm_preservation as audit
import comm_preservation as collect
import test_preservation_fields as fixture
from inspect_pcap import packets
from pcap_writer import write_header, write_packet

HOST = bytes.fromhex(fixture.HOST.replace(':', ''))
PEER = bytes.fromhex(fixture.PEER.replace(':', ''))


class CommPreservationTests(unittest.TestCase):
    def acquire_fixture(self, root, fail_at=None, drops=0, changed_field=None):
        calls = []

        def reader(rx, tx, flow, folder, state, batch_size):
            calls.append(state)
            self.assertEqual(batch_size, 16)
            if len(calls) == fail_at:
                (folder/'result.json').write_text(json.dumps({'error': 'simulated timeout'}))
                return {'error': 'simulated timeout'}
            changed = (bytes(audit.FIELDS[state][1])
                       if changed_field == state and len(calls) > 5 else None)
            _, result = fixture.PreservationFieldsTests().fixture(folder, state, changed)
            path = folder/'traffic.pcap'
            frames = list(packets(path))
            with path.open('wb') as stream:
                write_header(stream)
                for stamp, frame, wire in frames:
                    write_packet(stream, stamp+len(calls)*1000000000, frame)
            result.update(pcap_sha256=collect.sha(path.read_bytes()), socket_drops=drops)
            (folder/'result.json').write_text(json.dumps(result))
            return result

        with patch.object(collect, 'run_probe', side_effect=reader):
            result = collect.acquire(None, None, None, root, HOST, PEER)
        return result, calls

    def test_preview_never_stops_gateway_or_opens_network(self):
        with patch.object(collect, 'packet_sockets') as sockets, patch.object(collect, 'run_live') as live, \
             patch.object(collect.subprocess, 'run') as process, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(collect.main([]), 0)
        self.assertFalse(json.loads(out.getvalue())['network_opened'])
        self.assertEqual(json.loads(out.getvalue())['bytes_per_pass'], 196)
        sockets.assert_not_called(); live.assert_not_called(); process.assert_not_called()

    def test_two_distinct_passes_are_reconstructed_from_ten_pcaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result, calls = self.acquire_fixture(root)
            self.assertTrue(result['complete']); self.assertEqual(calls, list(audit.FIELDS)*2)
            checked = audit.audit(root, HOST, PEER)
            self.assertEqual(checked['pcap_files'], 10)
            self.assertTrue(checked['persistent_fields_equal'])
            self.assertTrue(all(checked['field_passes_equal'].values()))
            self.assertFalse(checked['full_device_backup'])

    def test_read_failure_is_preserved_and_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result, calls = self.acquire_fixture(root, fail_at=3)
            self.assertFalse(result['complete']); self.assertIn('timeout', result['error'])
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(result['passes'][0]['fields']), 2)
            self.assertTrue((root/'pass-1/comm-network-settings/result.json').exists())
            with self.assertRaisesRegex(ValueError, 'incomplète'): audit.audit(root, HOST, PEER)

    def test_different_ram_and_persistent_reads_are_preserved_and_distinguished(self):
        for field, stable in [('comm-utility-mirror', True), ('comm-network-settings', False)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); result, calls = self.acquire_fixture(root, changed_field=field)
                self.assertTrue(result['complete']); self.assertEqual(len(calls), 10)
                checked = audit.audit(root, HOST, PEER)
                self.assertFalse(checked['field_passes_equal'][field])
                self.assertEqual(checked['persistent_fields_equal'], stable)
                self.assertNotEqual((root/'pass-1'/field/'memory.bin').read_bytes(),
                                    (root/'pass-2'/field/'memory.bin').read_bytes())

    def test_drops_abort_after_preserving_the_actual_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result, calls = self.acquire_fixture(root, drops=1)
            self.assertFalse(result['complete']); self.assertEqual(len(calls), 1)
            self.assertIn('pertes', result['error'])
            self.assertTrue((root/'pass-1/comm-boot-vectors/memory.bin').exists())

    def test_gateway_restart_attempted_after_socket_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            restart = subprocess.CompletedProcess([], 0, 'restarted\n', '')
            with patch.object(collect, 'exclusive_console', return_value=contextlib.nullcontext()), \
                 patch.object(collect, 'packet_sockets', side_effect=OSError('socket unavailable')), \
                 patch.object(collect.subprocess, 'run', return_value=restart) as process:
                with self.assertRaisesRegex(OSError, 'socket unavailable'):
                    collect.run_live('fake0', fixture.HOST, fixture.PEER, root)
            self.assertEqual([call.args[0][-1] for call in process.call_args_list], ['stop', 'start'])
            self.assertEqual(json.loads((root/'restart-result.json').read_text())['exit_code'], 0)

    def test_failed_restart_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failed = subprocess.CompletedProcess([], 2, '', 'restart failed\n')
            with patch.object(collect, 'exclusive_console', return_value=contextlib.nullcontext()), \
                 patch.object(collect, 'packet_sockets', side_effect=OSError('socket unavailable')), \
                 patch.object(collect.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0), failed]):
                with self.assertRaises(subprocess.CalledProcessError):
                    collect.run_live('fake0', fixture.HOST, fixture.PEER, root)
            self.assertEqual(json.loads((root/'restart-result.json').read_text())['exit_code'], 2)

    def test_stale_gateway_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'run').mkdir()
            status = {'pid': 123, 'console': 'online', 'ardour': 'waiting',
                      'mapping': {'learning': False}, 'last_action': None}
            path = root/'run/status.json'; path.write_text(json.dumps(status))
            with patch.object(collect, 'ROOT', root), patch.object(collect.os, 'kill'), \
                 patch.object(collect.time, 'time', return_value=path.stat().st_mtime+30):
                with self.assertRaisesRegex(ValueError, 'fraîche'): collect.preflight()

    def test_pcap_reuse_and_missing_fields_are_rejected(self):
        import shutil
        for tamper in ('reuse', 'omit', 'bytes'):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); manifest, _ = self.acquire_fixture(root)
                if tamper == 'reuse':
                    for name in audit.FIELDS:
                        shutil.copytree(root/'pass-1'/name, root/'pass-2'/name, dirs_exist_ok=True)
                    manifest['passes'][1]['fields'] = manifest['passes'][0]['fields']
                elif tamper == 'omit':
                    manifest['passes'][1]['fields'].pop()
                else:
                    (root/'pass-2/comm-network-settings/memory.bin').write_bytes(bytes(10))
                (root/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError): audit.audit(root, HOST, PEER)

    def test_network_checksum_requires_nonzero_sum_and_never_replaces_invalid_bytes(self):
        fields = {name: bytes(length) for name, (_, length) in audit.FIELDS.items()}
        self.assertFalse(audit.interpret(fields)['network']['record_valid'])
        network = bytes.fromhex('02 00 00 00 00 01 88 5f')
        fields['comm-network-settings'] = network+sum(network).to_bytes(2, 'big')
        self.assertTrue(audit.interpret(fields)['network']['record_valid'])
        fields['comm-network-settings'] = network+b'\xff\xff'
        result = audit.interpret(fields)
        self.assertFalse(result['network']['record_valid'])
        self.assertEqual(result['network']['stored_mac'], '02:00:00:00:00:01')
        self.assertEqual(result['network']['stored_checksum'], 65535)
        self.assertFalse(result['network']['effective_driver_configuration_verified'])

    def test_marker_and_ram_difference_are_not_treated_as_invalid_backup(self):
        fields = {name: bytes(length) for name, (_, length) in audit.FIELDS.items()}
        fields['comm-utility-settings'] = b'v1.37\0\0\0'+bytes(80)
        mirror = bytearray(fields['comm-utility-settings']); mirror[34] = 7
        fields['comm-utility-mirror'] = bytes(mirror)
        result = audit.interpret(fields)['utility']
        self.assertTrue(result['stored_marker_matches_v1_37'])
        self.assertTrue(result['mirror_marker_matches_v1_37'])
        self.assertFalse(result['flash_equals_ram']); self.assertEqual(result['different_offsets'], [34])
        self.assertFalse(result['snapshot_atomic'])
        fields['comm-utility-settings'] = b'v1.36\0\0\0'+bytes(80)
        self.assertFalse(audit.interpret(fields)['utility']['stored_marker_matches_v1_37'])


if __name__ == '__main__':
    unittest.main()
