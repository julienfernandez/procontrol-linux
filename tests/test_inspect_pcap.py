"""Synthetic file-format tests; these do not emulate or validate a ProControl."""
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('inspect_pcap', Path(__file__).resolve().parents[1] / 'tools/inspect_pcap.py')
pcap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pcap)

FRAME = bytes.fromhex('ffffffffffff020000000001885f') + b'SYNTHETIC ONLY'


def make_pcap(frame=FRAME, endian='<', nano=False, linktype=1, wirelen=None):
    magic = 0xa1b23c4d if nano else 0xa1b2c3d4
    header = struct.pack(endian + 'IHHIIII', magic, 2, 4, 0, 0, 262144, linktype)
    return header + struct.pack(endian + 'IIII', 1_700_000_000, 123456, len(frame), wirelen or len(frame)) + frame


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'synthetic.pcap'

    def read(self, content):
        self.path.write_bytes(content)
        return list(pcap.packets(self.path))

    def test_endianness_and_precision(self):
        for endian in '<>':
            for nano in (False, True):
                with self.subTest(endian=endian, nano=nano):
                    result = self.read(make_pcap(endian=endian, nano=nano))
                    expected = 1_700_000_000_000_000_000 + 123456 * (1 if nano else 1000)
                    self.assertEqual(result, [(expected, FRAME, len(FRAME))])

    def test_ethernet_directions_and_type(self):
        src, dst, kind, tags, payload = pcap.ethernet(FRAME)
        self.assertEqual((src, dst, kind, tags, payload),
                         ('02:00:00:00:00:01', 'ff:ff:ff:ff:ff:ff', '0x885f', (), b'SYNTHETIC ONLY'))

    def test_double_vlan(self):
        frame = FRAME[:12] + bytes.fromhex('88a80064810000c8885f') + FRAME[14:]
        self.assertEqual(pcap.ethernet(frame)[2:], ('0x885f', (100, 200), b'SYNTHETIC ONLY'))

    def test_ieee8023_length_is_not_ethertype(self):
        frame = FRAME[:12] + bytes.fromhex('000d') + FRAME[14:]
        self.assertEqual(pcap.ethernet(frame)[2], 'length:13')

    def test_reject_other_capture_formats(self):
        for content in (b'\x0a\x0d\x0d\x0a' + bytes(20), make_pcap(linktype=113), b''):
            with self.subTest(content=content[:4]), self.assertRaises(pcap.CaptureError):
                self.read(content)

    def test_incomplete_record_is_error(self):
        for content in (make_pcap()[:-1], make_pcap()[:30]):
            with self.subTest(size=len(content)), self.assertRaises(pcap.CaptureError):
                self.read(content)

    def test_snaplen_truncation_remains_distinguishable(self):
        result = self.read(make_pcap(wirelen=len(FRAME) + 100))
        self.assertEqual(result[0][2] - len(result[0][1]), 100)

    def test_corrupt_record_length_is_error(self):
        content = bytearray(make_pcap())
        content[32:36] = struct.pack('<I', 0x7fffffff)
        with self.assertRaises(pcap.CaptureError):
            self.read(content)

    def test_incomplete_ethernet_and_vlan(self):
        for frame in (b'short', FRAME[:12] + bytes.fromhex('810000')):
            with self.subTest(frame=frame), self.assertRaises(pcap.CaptureError):
                pcap.ethernet(frame)

    def test_empty_valid_capture(self):
        self.assertEqual(self.read(make_pcap()[:24]), [])

    def test_cli_filters_and_summary(self):
        self.path.write_bytes(make_pcap())
        for mac, expected in [('02:00:00:00:00:01', 1), ('ff:ff:ff:ff:ff:ff', 1), ('02:00:00:00:00:02', 0)]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = pcap.main([str(self.path), '--show', '0', '--mac', mac])
            self.assertEqual(code, 0)
            self.assertIn(f'sélectionnées : {expected}', output.getvalue())


if __name__ == '__main__':
    unittest.main()
