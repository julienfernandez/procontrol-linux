from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from firmware_probe import (VERSION_REQUEST, PREFIX, EXPECTED_VERSION, diagnostic_payload,
                            exclusive_console, run_probe, requests_for, memory_reply)
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

    def simulate(self, answer, version=EXPECTED_VERSION, address=None, disconnect=False):
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
                    self.assertEqual(request[30:37], VERSION_REQUEST)
                    self.assertEqual(request[29], 1)
                    seq = int.from_bytes(request[18:22], 'big')
                    peer_tx.send(peer.frame(0xa0, ack=seq))
                    if answer:
                        response = peer.frame(0, 1, 101, body=PREFIX + version + b'\xf7')
                        peer_tx.send(response)
                        self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                        if disconnect:
                            peer_tx.send(b'\xff'*6 + peer.frame(0xe0, 1, 100, body=body)[6:])
                        elif version == EXPECTED_VERSION:
                            peer_tx.send(response)  # retry must be ACKed, not double-counted
                            self.assertEqual(peer_rx.recv(65535)[28], 0xa0)
                except Exception as exc:
                    failures.append(exc)

            worker = threading.Thread(target=console)
            worker.start()
            try:
                report = run_probe(rx, tx, ConsoleSession(HOST, PEER), root,
                                   connect_timeout=.5, reply_timeout=.1, address=address)
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

    def test_reads_wait_for_version_and_retry_does_not_skip_address(self):
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
                    expected = requests_for(0x20000, 2)
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
                                   connect_timeout=.5, reply_timeout=.2, address=0x20000, length=2)
                worker.join(2)
                self.assertFalse(worker.is_alive())
                if failures:
                    raise failures[0]
                self.assertIsNone(report['error'])
                self.assertEqual((root/'memory.bin').read_bytes(), b'\xf7\xf7')
                self.assertEqual(len(report['transactions']), 3)
            finally:
                rx.close(); tx.close(); peer_tx.close(); peer_rx.close()


if __name__ == '__main__':
    unittest.main()
