import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from procontrol_display import bbt_clock_command, clock_command, clock_reference
from surface_feedback import SurfaceFeedback
from surface_map import SurfaceMap


def decoded(command):
    digits = {v: k for k, v in clock_reference()['sevenseg'].items() if k in '0123456789 -'}
    return ''.join(digits[b] for b in command[6:14][::-1])


class MusicalClockTests(unittest.TestCase):
    def test_tick_boundary_never_moves_bar_or_beat_digits(self):
        for tick, expected in [(0, '000'), (998, '499'), (999, '499'),
                               (1000, '500'), (1001, '500'), (1918, '959'), (1919, '959')]:
            with self.subTest(tick=tick):
                command = bbt_clock_command(f'123|04|{tick:04d}')
                self.assertEqual(decoded(command), '12304' + expected)
                self.assertEqual(command[:6], bytes.fromhex('f0 13 00 30 09 14'))
                self.assertEqual(len(command), 15)
                self.assertEqual(command[-1], 0xf7)

    def test_complete_beat_has_only_three_ticks_cells_and_fixed_dots(self):
        previous = -1
        for tick in range(1920):
            command = bbt_clock_command(f'009|12|{tick:04d}')
            text = decoded(command)
            self.assertEqual(text[:5], '00912')
            self.assertEqual(command[5], 0x14)
            self.assertLessEqual(previous, int(text[5:]))
            self.assertLessEqual(int(text[5:]), 959)
            previous = int(text[5:])

    def test_bar_boundaries_and_overflow_are_explicit(self):
        for raw, expected in [('009|04|1919', '00904959'), ('010|01|0000', '01001000'),
                              ('999|01|0000', '99901000'), ('1000|01|0000', '---01000'),
                              ('-1|01|0000', '-0101000'), ('-100|01|0000', '---01000'),
                              ('001|100|0000', '001--000'), ('001|01|1920', '00101---')]:
            with self.subTest(raw=raw): self.assertEqual(decoded(bbt_clock_command(raw)), expected)

    def test_invalid_or_cleared_osc_value_blanks_digits_and_dots(self):
        for text in (' ', '', 'bad 001|02|0000', '001|02', '001|02|-1'):
            with self.subTest(text=text):
                self.assertEqual(bbt_clock_command(text), clock_command('        '))

    def test_switch_uses_latest_matching_clock_without_changing_transport(self):
        mapper = SurfaceMap(); feedback = SurfaceFeedback(mapper)
        feedback.feed('/position/smpte', ['01:23:45:12'])
        original = feedback.desired[('clock',)]
        feedback.feed('/position/bbt', ['123|04|1500'])
        self.assertEqual(feedback.desired[('clock',)], original)
        feedback.local(('mode', 'clock', ['bbt']))
        self.assertEqual(decoded(feedback.desired[('clock',)]), '12304750')
        self.assertEqual(feedback.desired[('clock_mode',)], bytes.fromhex('f0 13 00 20 09 08 f7'))
        feedback.feed('/position/smpte', ['01:23:46:00'])
        self.assertEqual(decoded(feedback.desired[('clock',)]), '12304750')
        feedback.local(('mode', 'clock', ['smpte']))
        self.assertEqual(decoded(feedback.desired[('clock',)]), '01234600')
        self.assertEqual(feedback.desired[('clock',)][5], 0x2a)
        self.assertEqual(feedback.desired[('clock_mode',)], bytes.fromhex('f0 13 00 20 09 20 f7'))


if __name__ == '__main__': unittest.main()
