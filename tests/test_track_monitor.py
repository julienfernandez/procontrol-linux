import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from surface_map import SurfaceMap, osc
from surface_feedback import SurfaceFeedback, scribble, button_led
from surface_routing import SurfaceRouting
from track_monitor import TrackMonitor, INPUT, DISK
from eq_editor import EQEditor


class TrackMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.; self.seq = 0
        self.mapper = SurfaceMap(); self.feedback = SurfaceFeedback(self.mapper)
        self.routing = SurfaceRouting(self.mapper, self.feedback)
        self.routing.rows = {i: dict(sid=i, name=f'Track {i}', kind='AT', channels=2) for i in range(1, 10)}
        self.routing.rows[10] = dict(sid=10, name='Bus', kind='B', channels=2)
        self.routing.ready = True
        self.eq = EQEditor(self.routing, self.feedback, lambda: self.now)
        self.monitor = TrackMonitor(self.routing, self.feedback, lambda: self.now)
        for sid in range(1, 10):
            self.state(sid, (0, 1))
            self.routing.feed('/strip/recenable', [sid, 0])
            self.routing.feed('/strip/select', [sid, int(sid == 1)])

    def state(self, sid, state):
        for path, bit in zip((INPUT, DISK), state): self.routing.feed(path, [sid, bit])

    def command(self, data):
        self.seq += 1
        return self.routing.actions(self.mapper.route(self.seq, data, self.now))

    def press(self, zone, key):
        actions = self.command(bytes([0x90, key, zone | 0x40]))
        self.assertEqual(self.command(bytes([0x90, key, zone])), [])
        return actions

    def text(self, ch, text):
        self.assertEqual(self.feedback.desired['value', ch], scribble(ch, text, False))

    def test_in_disk_transition_is_serialized_and_never_arms_record(self):
        self.press(8, 9)
        self.assertEqual(self.press(0, 4), [osc(DISK, 1, 0)])
        self.assertEqual(self.monitor.tick(), [])  # still waiting for the first bit
        self.text(1, 'Attente')
        self.state(1, (0, 0))
        self.assertEqual(self.monitor.tick(), [osc(INPUT, 1, 1)])
        self.state(1, (1, 0)); self.assertEqual(self.monitor.tick(), [])
        self.text(1, 'IN')
        self.assertEqual(self.routing.cache['/strip/recenable', 1], [1, 0])
        self.assertEqual(self.press(0, 4), [osc(INPUT, 1, 0)])
        self.state(1, (0, 0)); self.assertEqual(self.monitor.tick(), [osc(DISK, 1, 1)])
        self.state(1, (0, 1)); self.monitor.tick(); self.text(1, 'DISK')

    def test_selected_shortcuts_and_default_resolve_to_exclusive_targets(self):
        self.state(1, (1, 1))  # valid external mixed monitoring state
        self.assertEqual(self.press(8, 10), [osc(DISK, 1, 0)])
        self.state(1, (1, 0)); self.monitor.tick()
        self.assertEqual(self.press(8, 11), [osc(INPUT, 1, 0)])
        self.state(1, (0, 0)); self.assertEqual(self.monitor.tick(), [osc(DISK, 1, 1)])
        self.state(1, (0, 1)); self.monitor.tick()
        self.assertEqual(self.press(8, 7), [osc(DISK, 1, 0)])
        self.state(1, (0, 0)); self.monitor.tick(); self.text(1, 'AUTO')

    def test_rapid_double_toggle_finishes_the_latest_request(self):
        self.monitor.enter()
        self.assertEqual(self.press(0, 4), [osc(DISK, 1, 0)])
        self.assertEqual(self.press(0, 4), [])  # second press requests DISK again
        self.state(1, (0, 0))
        self.assertEqual(self.monitor.tick(), [osc(DISK, 1, 1)])
        self.state(1, (0, 1)); self.monitor.tick(); self.assertFalse(self.monitor.pending)

    def test_unknown_state_queries_identified_replies_before_toggling(self):
        for path in (INPUT, DISK): self.routing.cache.pop((path, 2))
        self.monitor.enter()
        self.assertEqual(self.press(1, 4), [osc(INPUT+'/2'), osc(DISK+'/2')])
        self.assertEqual(self.monitor.tick(), [])  # no query flood
        self.routing.feed(INPUT+'/2', [1]); self.routing.feed(DISK+'/2', [0])
        self.assertEqual(self.monitor.tick(), [osc(INPUT, 2, 0)])

    def test_bank_change_keeps_pending_absolute_target_and_clears_empty_slots(self):
        self.monitor.enter(); self.press(0, 4)
        self.routing.change_bank(8)
        self.text(1, 'DISK'); self.text(2, '--'); self.text(3, '--')
        self.assertEqual(self.press(1, 4), [])  # bus
        self.assertEqual(self.press(2, 4), [])  # no track
        self.state(1, (0, 0))
        self.assertEqual(self.monitor.tick(), [osc(INPUT, 1, 1)])
        self.assertEqual(self.press(0, 4), [osc(DISK, 9, 0)])

    def test_select_then_input_without_feedback_targets_the_new_track(self):
        actions = self.command(bytes.fromhex('90 06 42 90 0a 48'))
        self.assertEqual(actions, [osc('/strip/select', 3, 0), osc(DISK, 3, 0)])
        self.assertNotIn(1, self.monitor.pending)
        self.routing.feed('/strip/select', [1, 0]); self.routing.feed('/strip/select', [3, 1])
        self.assertIsNone(self.monitor.selection_pending)

    def test_matrix_select_then_input_targets_absolute_track(self):
        self.assertEqual(self.routing.actions([('matrix', 'select', [9]), ('monitor', 'selected', ['input'])]),
                         [osc('/strip/select', 9, 0), osc(DISK, 9, 0)])

    def test_unknown_relative_selection_or_expired_selection_never_uses_old_track(self):
        self.routing.actions([osc('/select/next', 1.)])
        self.assertEqual(self.press(8, 10), []); self.text(1, 'SELECT?')
        self.assertFalse(self.monitor.pending)
        self.monitor.select_requested(3); self.now += 3
        self.assertEqual(self.press(8, 10), [])
        self.routing.feed('/strip/select', [1, 0]); self.routing.feed('/strip/select', [3, 1])
        self.assertEqual(self.press(8, 10), [osc(DISK, 3, 0)])

    def test_ambiguous_selection_does_not_write(self):
        self.routing.feed('/strip/select', [2, 1])
        self.assertEqual(self.press(8, 11), []); self.assertFalse(self.monitor.pending)

    def test_reselecting_current_track_needs_no_redundant_feedback(self):
        self.assertEqual(self.press(0, 6), [osc('/strip/select', 1, 0)])
        self.now += 5  # Ardour may emit no change when selection stays the same
        self.assertEqual(self.press(8, 10), [osc(DISK, 1, 0)])

    def test_lamps_and_external_mix_show_confirmed_state(self):
        self.monitor.enter()
        for state, text, on in (((1, 0), 'IN', True), ((0, 1), 'DISK', False), ((1, 1), 'IN+DISK', True)):
            self.state(1, state); self.text(1, text)
            self.assertEqual(self.feedback.desired['led', 0, 4], button_led(0, 4, on))
            for key, value in zip((10, 11), state):
                self.assertEqual(self.feedback.desired['led', 8, key], button_led(8, key, value))
        self.state(1, (0, 0)); self.monitor.tick()
        self.assertEqual(self.feedback.desired['led', 0, 4], button_led(0, 4, True))
        self.now += 1; self.monitor.tick()
        self.assertEqual(self.feedback.desired['led', 0, 4], button_led(0, 4, False))

    def test_pending_fast_blink_does_not_pretend_source_is_confirmed(self):
        self.monitor.enter(); self.press(0, 4)
        self.monitor.tick(); self.text(1, 'Attente')
        self.assertEqual(self.feedback.desired['led', 8, 10], button_led(8, 10, False))
        self.assertEqual(self.feedback.desired['led', 0, 4], button_led(0, 4, True))
        self.now += .125; self.monitor.tick()
        self.assertEqual(self.feedback.desired['led', 0, 4], button_led(0, 4, False))

    def test_timeout_queries_actual_state_and_does_not_replay_write(self):
        self.monitor.enter(); self.press(0, 4); self.now += 2
        self.assertEqual(self.monitor.tick(), [osc(INPUT+'/1'), osc(DISK+'/1')])
        self.assertFalse(self.monitor.pending); self.text(1, 'ERREUR')
        self.now += 3; self.assertEqual(self.monitor.tick(), []); self.text(1, 'DISK')
        self.assertFalse(self.monitor.status()['tracks'][0]['error'])

    def test_catalog_replacement_and_disconnect_cancel_old_intent(self):
        self.monitor.enter(); self.press(0, 4); self.monitor.catalog_changed()
        self.assertFalse(self.monitor.pending); self.assertIsNone(self.monitor.state(1))
        self.routing.disconnect(); self.assertFalse(self.monitor.active)
        self.assertFalse(self.monitor.pending); self.assertEqual(self.monitor.tick(), [])

    def test_held_button_and_ethernet_retry_act_once(self):
        self.monitor.enter(); data = bytes.fromhex('90 04 40')
        self.assertEqual(self.command(data), [osc(DISK, 1, 0)])
        self.assertEqual(self.mapper.route(self.seq, data, self.now), [])
        self.assertEqual(self.command(data), [])
        self.assertEqual(self.monitor.pending[1]['target'], (1, 0))
        self.mapper.reset_inputs(); self.assertFalse(self.monitor.held)
        self.assertFalse(self.monitor.active); self.assertFalse(self.monitor.pending)

    def test_eq_and_monitor_views_are_exclusive_and_mix_updates_are_preserved(self):
        self.press(0, 2); self.assertTrue(self.eq.active)
        self.press(8, 9); self.assertFalse(self.eq.active); self.assertTrue(self.monitor.active)
        self.routing.feed('/strip/gain', [1, -6.]); self.text(1, 'DISK')
        self.assertEqual(self.command(bytes.fromhex('b0 40 41')), [])
        self.assertEqual(self.command(bytes.fromhex('b0 4d 41')), [])
        self.press(8, 8); self.assertFalse(self.monitor.active)
        self.assertEqual(self.feedback.desired['value', 1], self.feedback.mix_values[1])
        self.press(8, 9); self.press(0, 2)
        self.assertTrue(self.eq.active); self.assertFalse(self.monitor.active)

    def test_monitor_exit_does_not_cancel_valid_inflight_track_command(self):
        self.monitor.enter(); self.press(0, 4); self.press(0x17, 0x30)
        self.assertFalse(self.monitor.active)
        self.state(1, (0, 0)); self.assertEqual(self.monitor.tick(), [osc(INPUT, 1, 1)])

    def test_shift_mon_keeps_polarity_shortcut(self):
        self.mapper.modifiers.add('Shift_L'); self.mapper.state['/select/polarity', None] = 0
        self.assertEqual(self.press(8, 9), [osc('/select/polarity', 1)])
        self.assertFalse(self.monitor.active)

    def test_malformed_monitor_feedback_is_ignored(self):
        self.monitor.enter()
        for value in (None, True, '1', -1, 2, .5, float('nan'), float('inf')):
            self.routing.feed(INPUT, [1, value]); self.routing.feed(DISK+'/1', [value])
        self.assertEqual(self.monitor.state(1), (0, 1)); self.text(1, 'DISK')


if __name__ == '__main__': unittest.main()
