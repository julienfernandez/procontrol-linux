# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic fixtures only; no manufacturer firmware is redistributed."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_firmware import FirmwareError, inspect, intel_hex, resources


def record(kind, address=0, payload=b''):
    raw = bytes([len(payload)]) + address.to_bytes(2, 'big') + bytes([kind]) + payload
    return b':' + (raw + bytes([-sum(raw) & 255])).hex().encode() + b'\r\n'


def fork(body):
    # One named CODE resource. Resource references are relative to the type list.
    area = struct.pack('>I', len(body)) + body
    header = struct.pack('>IIII', 256, 256 + len(area), len(area), 58)
    table = header + bytes(8) + struct.pack('>HH', 28, 50)
    table += struct.pack('>H4sHH', 0, b'CODE', 0, 10)
    table += struct.pack('>hHII', 26, 0, 0, 0)
    table += b'\x07example'
    return header + bytes(240) + area + table


class FirmwareTests(unittest.TestCase):
    def test_published_hex_record_and_segment_address(self):
        # Keil's Intel HEX documentation example, independent of our record builder.
        data = (b':020000021200EA\n:10246200464C5549442050524F46494C4500464C33\n'
                b':00000001FF\n')
        summary, segments = intel_hex(data)
        self.assertEqual(segments, [(0x14462, b'FLUID PROFILE\0FL')])
        self.assertEqual(summary['checksums_valid'], 3)

    def test_sparse_segments_linear_base_and_start_not_data(self):
        source = (record(4, payload=b'\x00\x01') + record(5, payload=b'\0\x01\0\x20')
                  + record(0, 0, b'ab') + record(0, 32, b'cd') + record(1))
        summary, segments = intel_hex(source)
        self.assertEqual(segments, [(0x10000, b'ab'), (0x10020, b'cd')])
        self.assertEqual(summary['addressed_bytes'], 4)

    def test_invalid_hex_never_silently_recovers(self):
        good = record(0, 0, b'ab')
        cases = [good, good + record(1) + good, good + good + record(1),
                 good[:-4] + b'00\r\n' + record(1), b':01000000ff\n',
                 record(6) + record(1), record(2, payload=b'x') + record(1),
                 record(0, 0xffff, b'ab') + record(1), b':00 zz\n']
        for data in cases:
            with self.subTest(data=data), self.assertRaises(FirmwareError):
                intel_hex(data)

    def test_named_resource_boundaries(self):
        data = fork(b'data')
        result = resources(data)
        self.assertEqual((result[0]['id'], result[0]['name'], result[0]['data']),
                         (26, 'example', b'data'))
        self.assertEqual(result[0]['offset'], 260)
        for broken in [data[:15], data[:-1], data[:256] + b'\xff\xff\xff\xff' + data[260:]]:
            with self.assertRaises((FirmwareError, struct.error)):
                resources(broken)

    def test_bad_name_or_reference_offsets(self):
        data = fork(b'data')
        map_at = 264
        for field, value in [(map_at + 36, 0xffff), (map_at + 40, 0xfffe)]:
            broken = bytearray(data)
            struct.pack_into('>H', broken, field, value)
            with self.assertRaises(FirmwareError):
                resources(bytes(broken))

    def test_extraction_preserves_source_and_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'example.rsr'
            raw = fork(record(0, 0x100, b'example') + record(1))
            source.write_bytes(raw)
            out = root / 'extract'
            report = inspect(source, out)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual((out / 'CODE-26-00000100.bin').read_bytes(), b'example')
            self.assertEqual(json.loads((out / 'manifest.json').read_text()), report)
            with self.assertRaises(FileExistsError):
                inspect(source, out)

    def test_failed_validation_produces_no_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'bad.rsr'
            source.write_bytes(fork(record(0, 0x100, b'example')))
            out = root / 'extract'
            with self.assertRaises(FirmwareError):
                inspect(source, out)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
