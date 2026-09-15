import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from procontrol_display import clock_command, clock_reference


class ClockTests(unittest.TestCase):
    def test_reference_digits_reverse_and_procontrol_family(self):
        self.assertEqual(clock_command('12345678'),
                         bytes.fromhex('f0 13 00 30 09 00 7f 70 5f 5b 33 79 6d 30 f7'))
        self.assertEqual(clock_command('87654321')[6:14], clock_command('12345678')[6:14][::-1])

    def test_blank_turns_segments_off_without_mode_led_command(self):
        body = clock_command('        ')
        self.assertEqual(len(body), 15)
        self.assertEqual(body[5:14], bytes(9))
        self.assertEqual(body[:5], bytes.fromhex('f0 13 00 30 09'))
        self.assertEqual(clock_reference()['clockbytes'][2], 0)

    def test_rejects_implicit_truncation_and_unsupported_symbols(self):
        for text in ('123', '123456789', '12:34:56', 'ABCDEFGH'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                clock_command(text)


if __name__ == '__main__':
    unittest.main()
