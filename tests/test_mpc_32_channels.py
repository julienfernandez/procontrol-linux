"""Regressions for named 32-channel tracks backed by only 16 real USB channels."""
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from test_studio_control import graph_fixture, REMOTE
import test_studio_control as control_tests
from studio_control import graph_health
from test_mpc_usb_backend import MODULE, fixture
from mpc_channels import channel_count


class ChannelGraphTests(unittest.TestCase):
    def test_32_real_channels_are_counted_in_both_directions(self):
        g = graph_health(graph_fixture(32))
        self.assertTrue(g['usb'])
        self.assertEqual((g['input_channels'], g['output_channels'], g['tracks']), (32, 32, 32))
        self.assertEqual(g['keepalive']['capture']['channels'], 32)

    def test_juju_32_device_counts_every_channel_without_old_brand_name(self):
        objects = graph_fixture(32)
        for obj, direction in zip(objects[:2], ('input', 'output')):
            obj['info']['props']['node.name'] = (
                f'alsa_{direction}.usb-Juju_Juju_Driver_32ch_JUJU-MPCONE-32-00.pro-{direction}-0')
        health = graph_health(objects)
        self.assertEqual((health['input_channels'], health['output_channels'], health['tracks']), (32, 32, 32))
        second = copy.deepcopy(objects[0]); second['id'] = 9999
        objects.append(second)
        self.assertFalse(graph_health(objects)['usb'])

    def test_32_named_tracks_do_not_create_usb_channels(self):
        objects = graph_fixture()
        objects += [o for o in graph_fixture(32) if 516 <= o['id'] < 532]
        g = graph_health(objects)
        self.assertEqual((g['session_channels'], g['input_channels'], g['tracks']), (32, 16, 16))

    def test_lost_channel_32_cannot_be_healthy(self):
        objects = graph_fixture(32)
        objects = [o for o in objects if o['id'] not in (1131, 1231)]
        g = graph_health(objects)
        self.assertEqual(g['keepalive']['capture']['channels'], 31)
        self.assertEqual(g['keepalive']['capture']['expected'], 32)
        self.assertEqual(g['tracks'], 31)

    def test_hole_in_hardware_ports_is_not_a_complete_31_channel_device(self):
        objects = [o for o in graph_fixture(32) if o['id'] != 117]
        self.assertEqual(graph_health(objects)['input_channels'], 0)

    def test_ambiguous_devices_are_not_selected_arbitrarily(self):
        objects = graph_fixture()
        second = copy.deepcopy(objects[0]); second['id'] = 9999
        objects.append(second)
        self.assertFalse(graph_health(objects)['usb'])


class ChannelSnapshotTests(unittest.TestCase):
    setUp = control_tests.SupervisorTests.setUp
    snapshot = control_tests.SupervisorTests.snapshot
    def test_missing_upper_channels_warn_without_recovery_loop(self):
        objects = graph_fixture() + [o for o in graph_fixture(32) if 516 <= o['id'] < 532]
        with patch.object(self.c.backend, 'remote', return_value=REMOTE), patch('studio_control.read_graph', return_value=objects):
            s = self.c.backend.snapshot()
        warning = next(c for c in s['components'] if c['key'] == 'capacity')
        self.assertEqual(warning['state'], 'warning')
        self.assertIn('17–32', warning['detail'])
        self.assertFalse(s['repair_needed'])

    def test_juju_card_is_visible_without_memory_patch(self):
        remote = dict(REMOTE, audio_id='JujuDriver', visibility='')
        s = self.snapshot(remote)
        visible = next(c for c in s['components'] if c['key'] == 'visibility')
        self.assertEqual(visible['state'], 'ok')
        self.assertIn('Juju Driver', visible['detail'])
        self.assertFalse(s['repair_needed'])

    def test_32_configuration_does_not_repeatedly_recreate_live_16_device(self):
        self.c.config['usb_channels'] = 32
        s = self.snapshot()
        self.assertIn('32 canaux', s['recovery_wait'])
        self.assertFalse(s['repair_needed'])


class Backend32Tests(unittest.TestCase):
    def test_keepalive_verifies_upper_channels_in_both_directions(self):
        func = MODULE['keepalive_link_plan']
        with patch.dict(func.__globals__, CHANNELS=32):
            for playback in (True, False):
                objects = fixture(playback, 32)
                self.assertEqual(func(objects, 'keepalive', 'mpc', playback), (set(), set()))
                self.assertEqual(func(objects[:-1], 'keepalive', 'mpc', playback), ({(131, 231)}, set()))
                with self.assertRaises(RuntimeError):
                    func(fixture(playback, 16), 'keepalive', 'mpc', playback)

    def test_unsupported_mpc_is_rejected_before_prepare_writes(self):
        func = MODULE['prepare']
        remote = Mock(return_value='')
        command = Mock()
        with patch.dict(func.__globals__, CHANNELS=32, remote=remote, command=command), patch.object(Path, 'is_file', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'Liaison existante conservée'):
                func()
        command.assert_not_called()
        self.assertEqual(remote.call_count, 1)
        self.assertIn('p_channels', remote.call_args[0][0])

    def test_32_request_rejects_actual_16_ports(self):
        func = MODULE['verify_usb_width']
        with patch.dict(func.__globals__, CHANNELS=32):
            with self.assertRaisesRegex(RuntimeError, '16 canaux réels, 32 demandés'):
                func(graph_fixture())
            func(graph_fixture(32))

    def test_routing_checks_all_ports_before_first_connection(self):
        func = MODULE['route']
        jack = Mock()
        jack.ports.return_value = [p for i in range(16) for p in
            (f'MPC One USB Audio 32ch Pro:capture_AUX{i}',
             'ardour:MPC %02d-%02d/audio_in %d' % (i//2*2+1, i//2*2+2, i%2+1))]
        with patch.dict(func.__globals__, CHANNELS=32, Jack=lambda: jack):
            with self.assertRaisesRegex(RuntimeError, 'aucune liaison modifiée'):
                func()
        jack.connect.assert_not_called()
        jack.close.assert_called_once()

    def test_routing_connects_channel_32(self):
        func = MODULE['route']
        jack = Mock()
        jack.ports.return_value = [p for i in range(32) for p in
            (f'MPC One USB Audio 32ch Pro:capture_AUX{i}',
             'ardour:MPC %02d-%02d/audio_in %d' % (i//2*2+1, i//2*2+2, i%2+1))]
        jack.ports.return_value.append('MPC One USB MIDI (capture_1)')
        jack.connections.return_value = []
        with patch.dict(func.__globals__, CHANNELS=32, Jack=lambda: jack):
            func()
        audio_links = [c for c in jack.connect.call_args_list if ':capture_AUX' in c.args[0]]
        self.assertEqual(len(audio_links), 32)
        jack.connect.assert_any_call('MPC One USB Audio 32ch Pro:capture_AUX31', 'ardour:MPC 31-32/audio_in 2')

    def test_configuration_is_restricted(self):
        for value in (True, 0, 17, 64, '32; reboot'):
            with self.assertRaises(ValueError):
                channel_count(value)


if __name__ == '__main__':
    unittest.main()
