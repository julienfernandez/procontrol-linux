from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from firmware_probe import (VERSION_REQUEST, PREFIX, EXPECTED_VERSION, diagnostic_payload,
                            exclusive_console, run_probe, requests_for, memory_reply,
                            FADER_PREFIX, FADER_VERSION, PROFILES, diagnostic_payloads,
                            STATE_FIELDS, run_fader_version)
from procontrold import ConsoleSession
from session_probe import Session
from inspect_pcap import packets

HOST = '02:00:00:00:00:01'
PEER = '00:a0:7e:a0:ad:9c'


class FirmwareProbeTests(unittest.TestCase):
    def test_daemon_lock_excludes_probe_and_releases_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with exclusive_console(root):
                with self.assertRaises(RuntimeError):
                    with exclusive_console(root):
                        self.fail('Deux émetteurs autorisés')
            with self.assertRaises(ValueError):
                with exclusive_console(root):
                    raise ValueError('échec simulé')
            with exclusive_console(root):
                pass

    def simulate(self, answer, version=EXPECTED_VERSION, address=None, disconnect=False,
                 target='comm', reply_target=None):
        prefix, expected_version = PROFILES[target]
        reply_prefix = PROFILES[reply_target or target][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rx, peer_tx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            tx, peer_rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            peer_rx.settimeout(1)
            peer = Session(PEER, HOST)
            failures = []

            def console():
                try:
                    # Real e1 layout includes the incumbent host MAC.
                    body = bytes.fromhex(HOST.replace(':', '')) + bytes(9) + b'1.37'.ljust(9, b'\0') + b'MAINUNIT\0\0'
                    peer_tx.send(b'\xff'*6 + peer.frame(0xe1, 1, 100, body=body)[6:])
                    self.assertEqual(peer_rx.recv(65535)[28], 0xe2)
                    peer_tx.send(peer.frame(0xa0, ack=1))
                    request = peer_rx.recv(65535)
                    self.assertEqual(request[30:37], prefix+b'V\xf7')
                    self.assertEqual(request[29], 1)
                    seq = int.from_bytes(request[18:22], 'big')
                    peer_tx.send(peer.frame(0xa0, ack=seq))
                    if answer:
                        response = peer.frame(0, 1, 101, body=reply_prefix + version + b'\xf7')
                        peer_tx.send(response)
                        self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                        if disconnect:
                            peer_tx.send(b'\xff'*6 + peer.frame(0xe0, 1, 100, body=body)[6:])
                        elif version == expected_version:
                            peer_tx.send(response)  # retry must be ACKed, not double-counted
                            self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                except Exception as exc:
                    failures.append(exc)

            worker = threading.Thread(target=console)
            worker.start()
            try:
                report = run_probe(rx, tx, ConsoleSession(HOST, PEER), root,
                                   connect_timeout=.5, reply_timeout=.1, address=address, target=target)
                worker.join(2)
                self.assertFalse(worker.is_alive())
                if failures:
                    raise failures[0]
                self.assertTrue(report['ack_received'])
                self.assertTrue(list(packets(root/'traffic.pcap')))
                if report['error']:
                    self.assertFalse((root/'memory.bin').exists())
                return report
            finally:
                rx.close(); tx.close(); peer_tx.close(); peer_rx.close()

    def test_version_response_and_retry_have_raw_evidence(self):
        report = self.simulate(True)
        self.assertIsNone(report['error'])
        self.assertEqual([row['duplicate'] for row in report['responses']], [False, True])
        self.assertEqual(report['responses'][0]['payload_hex'], EXPECTED_VERSION.hex(' '))

    def test_ack_without_response_is_not_success(self):
        report = self.simulate(False)
        self.assertIn('ACK insuffisant', report['error'])
        self.assertEqual(report['responses'], [])

    def test_fader_version_is_captured_without_any_memory_request(self):
        report = self.simulate(True, version=FADER_VERSION, target='fader')
        self.assertIsNone(report['error'])
        self.assertEqual(report['probe'], 'fader_version')
        self.assertEqual(report['request_hex'], 'f0 13 00 70 01 56 f7')
        self.assertEqual(len(report['transactions']), 1)
        self.assertEqual([r['duplicate'] for r in report['responses']], [False, True])
        self.assertEqual(report['read_length'], 0)
        self.assertEqual(report['read_bytes_hex'], '')

    def test_fader_ack_without_payload_does_not_validate_access(self):
        report = self.simulate(False, target='fader')
        self.assertIn('ACK insuffisant', report['error'])
        self.assertEqual(report['responses'], [])

    def test_fader_probe_ignores_version_on_comm_channel(self):
        report = self.simulate(True, version=FADER_VERSION, target='fader', reply_target='comm')
        self.assertIn('ACK insuffisant', report['error'])
        self.assertEqual(report['responses'], [])

    def test_different_fader_version_is_reported_and_stops(self):
        report = self.simulate(True, version=b'FDRv1.38\n\r', target='fader')
        self.assertIn('Version fader différente', report['error'])
        self.assertEqual(len(report['transactions']), 1)
        self.assertEqual(report['responses'][0]['payload_ascii'], 'FDRv1.38\n\r')

    def test_fader_cannot_enable_memory_reads_or_batches(self):
        self.assertEqual(requests_for(target='fader'), [(None, FADER_PREFIX+b'V\xf7')])
        for args in ({'address': 0x8000}, {'length': 2}, {'batch_size': 16}):
            with self.assertRaisesRegex(ValueError, 'version'):
                requests_for(target='fader', **args)
        with self.assertRaisesRegex(ValueError, 'inconnue'):
            requests_for(target='other')

    def test_fader_envelopes_keep_their_selector(self):
        body = FADER_PREFIX+FADER_VERSION+b'\xf7'
        self.assertEqual(diagnostic_payloads(body+body, 'fader'), [FADER_VERSION]*2)
        self.assertEqual(diagnostic_payloads(body), [])
        with self.assertRaises(ValueError):
            diagnostic_payloads(body+PREFIX+EXPECTED_VERSION+b'\xf7', 'fader')

    def test_named_ram_fields_cannot_become_arbitrary_memory_access(self):
        for state, (address, length) in STATE_FIELDS.items():
            plan = requests_for(state=state)
            self.assertEqual(plan[0], (None, VERSION_REQUEST))
            self.assertEqual([a for a, _ in plan[1:]], list(range(address, address+length)))
            self.assertTrue(all(body.endswith(b'm\xf7') for _, body in plan[1:]))
        for args in ({'target': 'fader'}, {'address': 0x8000071b}, {'length': 10},
                     {'batch_size': 2}):
            with self.assertRaises(ValueError):
                requests_for(state='fader-version', **args)
        with self.assertRaises(ValueError):
            requests_for(state='anything')
        with self.assertRaises(ValueError):
            requests_for(address=0x5094a, length=10)

    def test_rx_windows_cannot_cross_buffer_or_select_another_processor(self):
        plan = requests_for(ring_offset=480,length=8,batch_size=16)
        self.assertEqual(plan[1],(0x6c106,PREFIX+b'A0006C106'+b'M'*8+b'\xf7'))
        for options in [{'ring_offset': -1}, {'ring_offset': 488},
                        {'ring_offset': 480,'length': 9}, {'ring_offset': 0,'length': 257},
                        {'ring_offset': 0,'target': 'fader'},
                        {'ring_offset': 0,'state': 'fader-version'},
                        {'ring_offset': 0,'address': 0x8000071b}]:
            with self.assertRaises(ValueError):requests_for(**options)

    def test_different_firmware_version_prevents_any_memory_command(self):
        report = self.simulate(True, version=b'COMv1.38\n\r', address=0x20000)
        self.assertIn('Version comm différente', report['error'])
        self.assertEqual(len(report['transactions']), 1)
        self.assertEqual(report['read_bytes_hex'], '')

    def test_offline_announcement_between_version_and_read_aborts(self):
        report = self.simulate(True, address=0x20000, disconnect=True)
        self.assertIn('Session perdue', report['error'])
        self.assertEqual(len(report['transactions']), 1)
        self.assertEqual(report['read_bytes_hex'], '')

    def test_envelope_keeps_high_bit_bytes_and_rejects_other_channels(self):
        self.assertEqual(diagnostic_payload(bytes.fromhex('f0 13 00 70 00 80 f7')), b'\x80')
        for body in ('f0 13 00 70 01 56 f7', 'f0 13 00 70 00 56', '90 00 5c'):
            self.assertIsNone(diagnostic_payload(bytes.fromhex(body)))

    def test_read_addresses_cannot_leave_known_code_or_cross_holes(self):
        for address, length in [(0, 1), (0x8000071b, 1), (0x5007a, 1),
                                (0x20007, 2), (0x2fce3, 2), (0x20400, 257), (0x20400, 0)]:
            with self.assertRaises(ValueError):
                requests_for(address, length)
        self.assertEqual(requests_for(0x20000, 2), [(None, VERSION_REQUEST),
            (0x20000, PREFIX+b'A00020000m\xf7'), (0x20001, PREFIX+b'A00020001m\xf7')])

    def test_memory_parser_checks_address_and_both_byte_encodings(self):
        for byte in (0, 10, 13, 39, 128, 240, 247, 255):
            payload = f'00020000: {byte:02X} \''.encode() + bytes([byte]) + b"'\n\r"
            self.assertEqual(memory_reply(payload, 0x20000), byte)
            self.assertIsNone(memory_reply(payload, 0x20001))
        with self.assertRaises(ValueError):
            memory_reply(b"00020000: 00 'x'\n\r", 0x20000)

    def exercise_reads(self, state=None):
        start, length = STATE_FIELDS[state] if state else (0x20000, 2)
        read_args = {'state': state} if state else {'address': start, 'length': length}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rx, peer_tx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            tx, peer_rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            peer_rx.settimeout(1)
            peer = Session(PEER, HOST)
            failures = []

            def console():
                try:
                    body = bytes(15) + b'1.37'.ljust(9, b'\0') + b'MAINUNIT\0\0'
                    peer_tx.send(b'\xff'*6 + peer.frame(0xe0, 1, 100, body=body)[6:])
                    self.assertEqual(peer_rx.recv(65535)[28], 0xe2)
                    peer_tx.send(peer.frame(0xa0, ack=1))
                    peer_tx.send(b'\xff'*6 + peer.frame(0xe1, 1, 100, body=body)[6:])
                    expected = requests_for(**read_args)
                    for index, (address, request_body) in enumerate(expected):
                        request = peer_rx.recv(65535)
                        self.assertEqual(request[30:30+len(request_body)], request_body)
                        seq = int.from_bytes(request[18:22], 'big')
                        peer_tx.send(peer.frame(0xa0, ack=seq))
                        if address is not None:
                            # A acknowledges its pointer update with LF CR;
                            # only m supplies the addressed byte afterwards.
                            peer_tx.send(peer.frame(0, 1, 201+2*index, body=PREFIX+b'\n\r\xf7'))
                            self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                        payload = EXPECTED_VERSION if address is None else (
                            f"{address:08X}: F7 '".encode()+b"\xf7'\n\r")
                        reply = peer.frame(0, 1, 202+2*index, body=PREFIX+payload+b'\xf7')
                        peer_tx.send(reply)
                        self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                        if index == 0:
                            peer_tx.send(reply)
                            self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                except Exception as exc:
                    failures.append(exc)

            worker = threading.Thread(target=console)
            worker.start()
            try:
                report = run_probe(rx, tx, ConsoleSession(HOST, PEER), root,
                                   connect_timeout=.5, reply_timeout=.2, **read_args)
                worker.join(2)
                self.assertFalse(worker.is_alive())
                if failures:
                    raise failures[0]
                self.assertIsNone(report['error'])
                self.assertEqual((root/'memory.bin').read_bytes(), b'\xf7'*length)
                self.assertEqual(len(report['transactions']), length+1)
                self.assertEqual(report['read_address'], start)
                self.assertEqual(report['read_length'], length)
                self.assertEqual(report['read_state'], state)
            finally:
                rx.close(); tx.close(); peer_tx.close(); peer_rx.close()

    def test_reads_wait_for_version_and_retry_does_not_skip_address(self):
        self.exercise_reads()

    def test_named_state_is_read_through_comm_and_preserves_raw_bytes(self):
        self.exercise_reads(state='fader-version')

    def exercise_fader_prerequisite(self, valid):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rx, remote_tx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            tx, remote_rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            remote_rx.settimeout(1)
            peer = Session(PEER, HOST)
            failures = []
            requests = []

            def console():
                try:
                    ident = bytes.fromhex(HOST.replace(':',''))+bytes(9)+b'1.37'.ljust(9,b'\0')+b'MAINUNIT\0\0'
                    remote_tx.send(b'\xff'*6+peer.frame(0xe1,1,100,body=ident)[6:])
                    self.assertEqual(remote_rx.recv(65535)[28], 0xe2)
                    remote_tx.send(peer.frame(0xa0,ack=1))
                    stages = [(PREFIX, EXPECTED_VERSION if valid else b'COMv1.38\n\r')]
                    if valid: stages.append((FADER_PREFIX,FADER_VERSION))
                    for index,(prefix,version) in enumerate(stages):
                        request = remote_rx.recv(65535)
                        requests.append(request[30:37])
                        self.assertEqual(request[30:37],prefix+b'V\xf7')
                        remote_tx.send(peer.frame(0xa0,ack=int.from_bytes(request[18:22],'big')))
                        remote_tx.send(peer.frame(0,1,101+index,body=prefix+version+b'\xf7'))
                        self.assertEqual(remote_rx.recv(65535)[28],0xa0)
                    remote_rx.settimeout(.1)
                    with self.assertRaises(socket.timeout): remote_rx.recv(65535)
                except Exception as exc: failures.append(exc)

            worker = threading.Thread(target=console); worker.start()
            try:
                result = run_fader_version(rx,tx,ConsoleSession(HOST,PEER),out,
                                           connect_timeout=.5,reply_timeout=.2)
                worker.join(2)
                self.assertFalse(worker.is_alive())
                if failures: raise failures[0]
                self.assertTrue((out/'comm-version/traffic.pcap').exists())
                self.assertEqual(len(requests),2 if valid else 1)
                self.assertEqual(result['fader_request_sent'],valid)
                self.assertEqual((out/'traffic.pcap').exists(),valid)
                if valid: self.assertIsNone(result['error'])
                else: self.assertIn('aucune requête fader',result['error'])
            finally:
                rx.close();tx.close();remote_tx.close();remote_rx.close()

    def test_fader_cli_flow_confirms_comm_on_same_socket_session(self):
        self.exercise_fader_prerequisite(True)

    def test_fader_cli_flow_never_sends_fader_after_wrong_comm_version(self):
        self.exercise_fader_prerequisite(False)


if __name__ == '__main__':
    unittest.main()
