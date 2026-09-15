"""Checks of candidate parsing, not validation of a device protocol."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_diginet import candidate_header
from inspect_pcap import CaptureError


class CandidateHeaderTests(unittest.TestCase):
    def packet(self, body, checksum=None, padding=b''):
        checksum = sum(body) & 0xffff if checksum is None else checksum
        return struct.pack('>HHIIHBB', 16 + len(body), checksum, 42, 0, 0, 0, 1) + body + padding

    def test_padding_excluded(self):
        body = bytes.fromhex('f0 13 00 70 00 55 f7')
        result = candidate_header(self.packet(body, padding=b'\xff' * 23))
        self.assertTrue(result['body_sum16_match'])
        self.assertEqual(result['body_sum'], 0x2bf)
        self.assertEqual(result['trailing_bytes'], 23)
        self.assertEqual(result['text_after_70_candidate'], 'U')

    def test_mismatch_visible(self):
        self.assertFalse(candidate_header(self.packet(b'abc', checksum=0))['body_sum16_match'])

    def test_online_announcement_identifies_host_and_console(self):
        body = bytes.fromhex('3c 97 0e 1b 3a 00') + bytes(9) + b'1.37'.ljust(9, b'\0') + b'MAINUNIT\0'
        payload = bytearray(self.packet(body))
        payload[14] = 0xe1
        result = candidate_header(payload)
        self.assertEqual(result['announced_host_candidate'], '3c:97:0e:1b:3a:00')
        self.assertEqual(result['device_candidate'], 'MAINUNIT')
        self.assertEqual(result['version_candidate'], '1.37')

    def test_arithmetic_wrap_is_explicit(self):
        result = candidate_header(self.packet(b'\xff' * 514))
        self.assertEqual(result['body_sum'], 131070)
        self.assertTrue(result['body_sum16_match'])

    def test_invalid_lengths_rejected(self):
        for payload in (b'short', bytes(16), struct.pack('>H', 60) + bytes(14)):
            with self.subTest(payload=payload), self.assertRaises(CaptureError):
                candidate_header(payload)


if __name__ == '__main__':
    unittest.main()
