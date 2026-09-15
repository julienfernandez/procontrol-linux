"""Vecteurs de référence et gestes PLAY/STOP observés ; aucun firmware simulé."""
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from procontrol_mapping import decode_command, decode_body, TABLE_PATH


class ProControlMappingTests(unittest.TestCase):
    def decode(self, hextext):
        return decode_command(bytes.fromhex(hextext))

    def test_vendor_table_is_unmodified(self):
        self.assertEqual(hashlib.sha256(TABLE_PATH.read_bytes()).hexdigest(),
                         '5e54cb39368f0e2a09692c2293a11981be08418e6f85de088a447c26bd8ff253')

    def test_observed_transport_pairs(self):
        for key, name in (('10', 'Play'), ('0f', 'Stop')):
            for state, value in (('5c', 1), ('1c', 0)):
                row = self.decode(f'90 {key} {state}')
                self.assertEqual(row['address'], '/button/command/Transport/' + name)
                self.assertEqual(row['value'], value)

    def test_track_touch_and_solo_use_same_channel_convention(self):
        for channel in range(8):
            touch = self.decode(f'90 09 {0x40 + channel:02x}')
            solo = self.decode(f'90 07 {channel:02x}')
            self.assertEqual(touch['address'], f'/button/track/{channel+1}/Touch')
            self.assertEqual(solo['address'], f'/button/track/{channel+1}/Solo')
            self.assertEqual((touch['value'], solo['value']), (1, 0))

    def test_fader_raw_endpoints_and_signature(self):
        self.assertEqual(self.decode('b0 00 00 20 00')['fader_raw_10bit'], 0)
        row = self.decode('b0 07 7f 27 70')
        self.assertEqual((row['track'], row['fader_raw_10bit']), (8, 1023))
        for bad in ('b0 00 00', 'b0 01 00 20 00', 'b0 00 00 20 01'):
            self.assertEqual(self.decode(bad)['status'], 'malformed')

    def test_multiplexed_body_and_unknown_are_preserved(self):
        rows = decode_body(bytes.fromhex('90 10 5c 90 10 1c f0 13 00 60 01 00 00 01 f7'))
        self.assertEqual([r['status'] for r in rows], ['mapped_reference', 'mapped_reference', 'unmapped'])
        self.assertEqual(rows[-1]['hex'], 'f0 13 00 60 01 00 00 01 f7')
        for bad in ('90 10', 'f0 13 00 40 01', ''):
            self.assertEqual(self.decode(bad)['status'], 'malformed')


if __name__ == '__main__':
    unittest.main()
