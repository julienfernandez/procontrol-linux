# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from procontrol_pointer import decode_pointer
from pointer_x11 import FreshPointer


class PointerTests(unittest.TestCase):
    def test_controlled_hardware_axes(self):
        # Small real-frame extracts keep the test portable without the ignored PCAPs.
        fixtures = json.loads((ROOT / 'tests/fixtures/pointer-gestures.json').read_text())
        directions = {'right': ('dx', 1), 'left': ('dx', -1), 'up': ('dy', -1), 'down': ('dy', 1)}
        self.assertEqual({f['user_confirmed_direction'] for f in fixtures}, set(directions))
        for fixture in fixtures:
            axis, sign = directions[fixture['user_confirmed_direction']]
            for sample in fixture['samples']:
                event = decode_pointer(bytes.fromhex(sample['body_hex']))
                self.assertIsNotNone(event)
                self.assertGreater(sign * event[axis], 0, sample)
                self.assertEqual(event['button_bits'], 0)

    def test_strict_format_and_signed_extremes(self):
        self.assertEqual(decode_pointer(bytes.fromhex('f0 13 00 60 01 0a 00 00 f7')),
                         {'dx': -128, 'dy': -128, 'button_bits': 0})
        self.assertEqual(decode_pointer(bytes.fromhex('f0 13 00 60 01 05 3f 3f f7')),
                         {'dx': 127, 'dy': 127, 'button_bits': 0})
        for body in ('b0 5c 41', 'f0 13 01 60 01 00 01 00 f7',
                     'f0 13 00 60 01 00 01 00', 'f0 13 00 60 01 00 40 00 f7',
                     'f0 13 00 60 02 00 01 00 f7', 'f0 13 00 60 01 40 01 00 f7',
                     'f0 13 00 60 01 00 01 00 f7 90 10 5c'):
            self.assertIsNone(decode_pointer(bytes.fromhex(body)))

    def test_live_freshness_unicast_confirmation_and_duplicates(self):
        parser = FreshPointer(1)
        now = 1000.0
        def header(seq, age=0.01, **changes):
            return {'event': 'ethernet_rx', 'utc': datetime.fromtimestamp(now-age, timezone.utc).isoformat(),
                    'command_field': 0, 'body_sum16_match': True, 'sequence_candidate': seq,
                    'body_hex': 'f0 13 00 60 01 00 01 00 f7', **changes}
        # RX alone is never injected: require following unicast controls record.
        self.assertIsNone(parser.feed(header(1), now))
        self.assertEqual(parser.feed({'event': 'controls'}, now), (1, 0))
        self.assertIsNone(parser.feed({'event': 'controls'}, now))
        for row in (header(1), header(2, age=1), header(3, body_sum16_match=False),
                    header(4, command_field=225), header(5, body_hex='b0 5c 41')):
            parser.feed(row, now)
            self.assertIsNone(parser.feed({'event': 'controls'}, now))
        parser.feed(header(8), now)
        parser.feed({'event': 'console_state', 'state': 'waiting_console'}, now)
        self.assertIsNone(parser.feed({'event': 'controls'}, now))

    def test_fractional_motion_is_preserved(self):
        parser = FreshPointer(0.25); total = 0
        for seq in range(4):
            parser.feed({'event': 'ethernet_rx', 'utc': '1970-01-01T00:16:40+00:00',
                         'command_field': 0, 'body_sum16_match': True, 'sequence_candidate': seq,
                         'body_hex': 'f0 13 00 60 01 03 3f 00 f7'}, 1000.01)
            total += parser.feed({'event': 'controls'}, 1000.01)[0]
        self.assertEqual(total, -1)


if __name__ == '__main__':
    unittest.main()
