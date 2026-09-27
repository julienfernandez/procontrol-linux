import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback
from surface_routing import SurfaceRouting
from control_audit import context, relevant, mix_change


class MatrixNavigationAuditTests(unittest.TestCase):
    def setUp(self):
        self.m = SurfaceMap()
        self.f = SurfaceFeedback(self.m)
        self.r = SurfaceRouting(self.m, self.f)
        self.r.begin_catalog()
        for sid in range(1, 33):
            self.r.feed('#reply', ['AT', f'Track {sid}', 2, 2, 0, 0, sid, 0])
        self.r.feed('#reply', ['end_route_list'])
        self.sequence = 0

    def press(self, key):
        self.sequence += 1
        before = context(self.m, self.r)
        actions = self.m.route(self.sequence, bytes([0x90, key, 0x57]))
        routed = self.r.actions(actions)
        after = context(self.m, self.r)
        return routed, relevant(actions, before, after), before, after

    def test_select_navigation_cannot_send_solo_mute_or_record(self):
        initial = copy.deepcopy(self.r.cache)
        for sid in [1, 9, 17, 25, 17, 9, 1] * 8:
            routed, logged, before, after = self.press(sid)
            self.assertEqual(routed, [('osc', '/strip/select', [sid, 0])])
            self.assertTrue(logged)
            self.assertEqual(after['slots'][0]['sid'], sid)
            self.assertEqual(after['matrix_mode'], 'select')
        self.assertEqual(self.r.cache, initial)

    def test_latched_matrix_mode_explains_first_channel_mix_writes(self):
        for key, mode in [(0x25, 'mute'), (0x26, 'solo'), (0x27, 'recenable')]:
            routed, logged, before, after = self.press(key)
            self.assertEqual(routed, [])
            self.assertTrue(logged)
            self.assertEqual(after['matrix_mode'], mode)
            for sid in (1, 9, 17, 25):
                routed, logged, before, after = self.press(sid)
                self.assertEqual(routed, [('osc', '/strip/' + mode, [sid, 1])])
                self.assertTrue(logged)
            self.press(0x24)
            self.assertEqual(self.press(1)[0], [('osc', '/strip/select', [1, 0])])

    def test_feedback_records_changes_without_mutating_mix_or_logging_meters(self):
        before = copy.deepcopy(self.r.cache)
        change = mix_change(self.r, '/strip/solo', [9, 1])
        self.assertEqual((change['sid'], change['previous'], change['value']), (9, 0, 1))
        self.assertEqual(self.r.cache, before)
        self.r.feed('/strip/solo', [9, 1])
        self.assertIsNone(mix_change(self.r, '/strip/solo', [9, 1]))
        self.assertEqual(mix_change(self.r, '/strip/solo', [9, 0])['previous'], 1)
        for path, values in [('/strip/meter', [9, -12.0]), ('/select/solo', [1]),
                             ('/strip/solo', [0, 1]), ('/strip/mute', [9, float('nan')])]:
            self.assertIsNone(mix_change(self.r, path, values))


if __name__ == '__main__':
    unittest.main()
