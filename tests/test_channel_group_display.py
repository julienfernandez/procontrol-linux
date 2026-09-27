# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from channel_group_display import ChannelGroupDisplay, KEY, channel_group_text, context_frames
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback
from surface_routing import SurfaceRouting
from eq_editor import EQEditor
from console_indicators import ConsoleIndicators
from console_mapping import MappingRuntime


class ChannelGroupTests(unittest.TestCase):
    def setUp(self):
        self.surface = SurfaceMap()
        self.feedback = SurfaceFeedback(self.surface)
        self.routing = SurfaceRouting(self.surface, self.feedback)
        self.eq = EQEditor(self.routing, self.feedback)
        self.display = ChannelGroupDisplay(self.feedback, self.surface, self.eq)

    def test_selection_changes_use_current_feedback_and_disconnect_hides_stale_name(self):
        self.surface.feedback('/select/name', ['MPC 01-02'])
        self.display.tick(10, True)
        self.assertEqual(self.feedback.desired[KEY][6:-1], b'MPC01-02')
        self.surface.feedback('/select/name', ['MPC 15-16'])
        self.display.tick(11, True)
        self.assertEqual(self.display.text, 'MPC15-16')
        self.display.tick(12, False)
        self.assertEqual(self.display.text, 'ARD WAIT')
        self.assertEqual(self.eq.outgoing, [])

    def test_mode_and_page_change_immediately_reset_name_alternation(self):
        self.eq.active = True
        self.eq.route_name = 'VOIX A'
        self.eq.usable = lambda: True
        self.eq.mode = 'params'
        self.eq.family = 'comp'
        self.eq.parameter_list = lambda: list(range(19))
        self.display.tick(10, True)
        self.assertEqual(self.display.text, 'DYN 1/3')
        self.display.tick(13, True)
        self.assertEqual(self.display.text, 'VOIX A')
        self.eq.page = 1
        self.display.tick(13.2, True)
        self.assertEqual(self.display.text, 'DYN 2/3')
        self.eq.mode = 'eq'
        self.eq.filter = 7
        self.display.tick(14, True)
        self.assertEqual(self.display.text, 'EQ B8/8')

    def test_browser_library_and_pending_are_not_confirmation(self):
        self.eq.active = True
        self.eq.route_name = 'VOIX A'
        self.eq.usable = lambda: True
        self.eq.mode = 'library'
        self.eq.plugin_page = 1
        self.assertEqual(context_frames(self.surface, self.eq, True)[0], 'LIB 2/2')
        self.eq.create_pending = {'request': 'pending'}
        self.assertEqual(context_frames(self.surface, self.eq, True), ('AJOUT...',))
        self.eq.create_pending = None
        self.eq.create_error = 'Ajout non confirme'
        self.assertEqual(context_frames(self.surface, self.eq, True), ('ERREUR',))
        self.assertEqual(self.eq.outgoing, [])

    def test_sends_are_status_only_and_ascii_is_eight_bytes(self):
        self.surface.encoder_mode = 'send'
        self.surface.send_index = 5
        self.surface.feedback('/select/name', ['Réverb longue'])
        self.display.tick(10, True)
        self.assertEqual(self.display.text, 'SEND E')
        self.display.tick(13, True)
        self.assertEqual(self.feedback.desired[KEY], bytes.fromhex('f0 13 00 40 35 00') + b'Reverb l\xf7')
        self.assertEqual(self.eq.outgoing, [])

    def test_probe_overrides_live_render_then_restores_latest_context(self):
        with tempfile.TemporaryDirectory() as root:
            mapping = MappingRuntime(root, self.surface, self.feedback, self.routing,
                                     ConsoleIndicators(self.surface, self.feedback))
            mapping.online = True
            self.surface.feedback('/select/name', ['VOIX A'])
            self.display.tick(10, True)
            mapping.start_probe({'element': 'dsp.channel'})
            self.surface.feedback('/select/name', ['VOIX B'])
            self.display.tick(11, True)
            self.assertEqual(self.feedback.queue[KEY][6:-1], b'TEST cha')
            mapping.cancel_probe()
            self.assertEqual(self.feedback.queue[KEY], channel_group_text('VOIX B'))

    def test_identical_feedback_is_not_requeued_and_learning_has_context(self):
        self.display.tick(10, True)
        self.feedback.sent[KEY] = self.feedback.queue.pop(KEY)
        self.display.tick(11, True)
        self.assertNotIn(KEY, self.feedback.queue)
        self.display.tick(12, True, learning=True)
        self.assertEqual(self.display.text, 'CAPTURE')


if __name__ == '__main__':
    unittest.main()
