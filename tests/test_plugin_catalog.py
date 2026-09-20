import copy
import json
from pathlib import Path
import unittest
import test_eq_editor as eq_tests
from plugin_catalog import CATALOG, profile_for_name


class PluginCatalogTests(unittest.TestCase):
    setUp = eq_tests.EQTests.setUp
    action = eq_tests.EQTests.action
    load = eq_tests.EQTests.load

    def connected(self):
        self.r.session = '/session'
        self.r.identities = {i: str(100+i) for i in self.r.rows}
        self.r.identity_ready = True
        self.r.feed('/procontrol/plugin/version', [2])

    def missing(self, command='90 02 40'):
        self.connected(); self.action(command); self.eq.tick()
        self.r.feed('/strip/plugin/list', [1])
        return self.eq.tick()

    def test_explicit_eq_creates_once_with_persistent_identity(self):
        actions = self.missing()
        self.assertEqual(len(actions), 1)
        kind, path, values = actions[0]
        self.assertEqual((kind,path), ('osc','/procontrol/plugin/ensure'))
        self.assertEqual(values[:3], ['/session','101','eq'])
        self.assertEqual(self.eq.tick(), [])
        self.assertEqual(self.action('b0 40 41'), [])
        self.assertEqual(self.action('90 02 40'), [])  # Ethernet retry
        self.r.feed('/procontrol/plugin/result', values+[2,1,'LSP Parametric Equalizer x8 Stereo'])
        self.load()
        self.assertTrue(self.eq.usable())
        self.assertFalse(self.eq.create_armed)

    def test_compressor_creates_and_opens_parameters(self):
        actions = self.missing('90 03 40')
        self.assertEqual(actions[0][2][2], 'comp')
        self.r.feed('/procontrol/plugin/result', actions[0][2]+[2,2,'LSP Compressor Stereo'])
        self.load(2)
        self.assertTrue(self.eq.usable())
        self.assertEqual(self.eq.mode, 'params')

    def test_existing_eq_does_not_insert_even_when_removed_later(self):
        self.connected(); self.action('90 02 40'); self.load()
        self.assertFalse(self.eq.create_armed)
        self.now += .6; self.eq.tick(); self.r.feed('/strip/plugin/list', [1])
        self.assertFalse(any(a[1].endswith('/ensure') for a in self.eq.tick()))

    def test_following_track_does_not_create(self):
        self.connected(); self.action('90 02 40'); self.load()
        self.now += .01; self.action('90 06 41'); self.eq.tick()
        self.r.feed('/strip/plugin/list', [2])
        self.assertEqual(self.eq.tick(), [])
        self.assertFalse(self.eq.create_armed)

    def test_absent_extension_or_identity_blocks_creation(self):
        self.action('90 02 40'); self.eq.tick(); self.r.feed('/strip/plugin/list', [1])
        self.assertEqual(self.eq.tick(), [])
        self.assertEqual(self.eq.error, 'MAJ Ardour')
        self.eq.exit(); self.r.feed('/procontrol/plugin/version', [1])
        self.now += .01; self.action('90 02 40'); self.eq.tick(); self.r.feed('/strip/plugin/list', [1])
        self.assertEqual(self.eq.tick(), [])
        self.assertEqual(self.eq.error, 'Identite')

    def test_missing_extension_explains_restart_in_eq_and_dyn_displays(self):
        from surface_feedback import scribble
        for command in ('90 02 40', '90 03 40'):
            with self.subTest(command=command):
                self.setUp(); self.action(command); self.eq.tick()
                self.r.feed('/strip/plugin/list', [1]); self.eq.tick()
                self.now += 2; self.eq.tick(); self.r.feed('/strip/plugin/list', [1]); self.eq.render()
                self.assertEqual(self.f.desired[('dsp',1)][6:14], b'RELANCER')
                self.assertEqual(self.f.desired[('dsp',2)][6:14], b'ARDOUR  ')
                self.assertEqual(self.f.desired[('value',1)], scribble(1,'RELANCER',False))
                self.assertEqual(self.f.desired[('dsp',8)][6:14], b'        ')
                self.assertEqual(self.action('b0 4d 41'), [])

    def test_wrong_response_and_changed_route_never_open_or_write(self):
        actions = self.missing(); request = actions[0][2]
        self.r.feed('/procontrol/plugin/result', request[:3]+['wrong',2,1,'LSP Parametric Equalizer x8 Stereo'])
        self.assertTrue(self.eq.create_pending)
        self.r.identities[1] = '999'
        self.assertEqual(self.eq.tick(), [])
        self.assertFalse(self.eq.active)
        self.r.feed('/procontrol/plugin/result', request+[2,1,'LSP Parametric Equalizer x8 Stereo'])
        self.assertFalse(self.eq.active)

    def test_insertion_timeout_never_retries_automatically(self):
        self.missing(); self.now += 6
        self.assertEqual(self.eq.tick(), [])
        self.assertFalse(self.eq.create_pending)
        self.now += 2; self.eq.tick(); self.r.feed('/strip/plugin/list', [1])
        self.assertEqual(self.eq.tick(), [])

    def test_creation_reply_waits_for_catalog_without_resending(self):
        actions = self.missing(); request = actions[0][2]
        self.r.feed('/strip/list', [])
        self.r.feed('/procontrol/plugin/result', request+[2,1,'LSP Parametric Equalizer x8 Stereo'])
        self.assertTrue(self.eq.create_pending)
        self.assertEqual(self.eq.tick(), [])
        self.r.ready = True
        self.assertEqual(self.eq.tick(), [('osc','/strip/plugin/list',[1])])
        self.assertFalse(self.eq.create_pending)

    def test_insertion_failure_is_visible_and_cannot_create_in_a_loop(self):
        actions = self.missing(); request = actions[0][2]
        self.r.feed('/procontrol/plugin/result', request+[-4,0,''])
        self.now += 2; self.eq.tick(); self.r.feed('/strip/plugin/list', [1])
        self.assertEqual(self.eq.tick(), [])
        self.assertEqual(self.eq.create_error, 'Non installe')
        self.assertFalse(self.eq.create_pending)

    def test_inserts_button_targets_physical_track_in_current_bank(self):
        self.connected(); self.r.start = 8
        self.assertEqual(self.action('90 0a 40'), [('osc','/strip/select',[9,0])])
        self.eq.tick(); self.r.feed('/strip/plugin/list', [9])
        self.assertEqual(self.eq.mode, 'library')
        self.assertFalse(self.eq.create_armed)
        self.assertEqual(self.eq.tick(), [])
        self.action('b0 4d 41')
        self.assertEqual(self.eq.cursor, 1)
        actions = self.action('90 00 4e')
        self.assertEqual(actions[0][2][:3], ['/session','109','comp'])

    def test_ins_send_opens_dsp_browser_for_its_track_in_current_bank(self):
        from surface_feedback import button_led
        self.connected(); self.r.start = 8
        # The observed main-unit INS/SEND code is 01, rather than the older
        # reference INSERTS code 0a. Track 9 is physical strip 1 in bank 2.
        self.assertEqual(self.action('90 01 40'), [('osc','/strip/select',[9,0])])
        self.assertEqual(self.eq.mode, 'browse')
        self.assertFalse(self.eq.create_armed)
        self.assertEqual(self.action('90 01 00'), [])
        self.assertEqual(self.eq.tick(), [('osc','/strip/plugin/list',[9])])
        self.r.feed('/strip/plugin/list', [9,1,'LSP Compressor Stereo',1])
        self.assertTrue(self.eq.usable())
        self.assertEqual(self.f.desired['led',0,1], button_led(0,1,True))
        self.assertEqual(self.f.desired['led',1,1], button_led(1,1,False))
        self.assertEqual(self.f.desired['led',0x15,2], button_led(0x15,2,True))
        self.assertEqual(self.action('90 01 40'), [])  # exact Ethernet retry
        self.assertEqual(self.eq.mode, 'browse')
        self.now += .01
        self.action('90 01 40')  # next real press behaves like INSERTS/PARAM
        self.assertEqual(self.eq.mode, 'library')
        self.assertFalse(self.eq.create_pending)
        self.eq.exit()
        self.assertEqual(self.f.desired['led',0,1], button_led(0,1,False))

    def test_ins_send_from_monitoring_opens_empty_tracks_library_without_inserting(self):
        from track_monitor import TrackMonitor
        from surface_feedback import button_led
        self.connected(); monitor = TrackMonitor(self.r, self.f, lambda:self.now)
        monitor.enter()
        self.assertEqual(self.action('90 01 41'), [('osc','/strip/select',[2,0])])
        self.assertFalse(monitor.active); self.assertTrue(self.eq.active)
        self.eq.tick(); self.r.feed('/strip/plugin/list', [2])
        self.assertEqual(self.eq.mode, 'library')
        self.assertEqual(self.eq.tick(), [])
        self.assertFalse(self.eq.create_armed); self.assertFalse(self.eq.create_pending)
        self.assertEqual(self.f.desired['led',1,1], button_led(1,1,True))
        self.now += .01; self.action('90 02 41')
        self.assertEqual(self.f.desired['led',1,1], button_led(1,1,False))

    def test_ins_send_switches_to_another_tracks_browser_and_clears_previous_lamp(self):
        from surface_feedback import button_led
        self.connected(); self.action('90 01 40'); self.load()
        self.assertEqual(self.f.desired['led',0,1], button_led(0,1,True))
        self.action('90 01 42')
        self.assertEqual(self.eq.sid, 3); self.assertEqual(self.eq.mode, 'browse')
        self.assertEqual(self.f.desired['led',0,1], button_led(0,1,False))
        self.assertEqual(self.f.desired['led',2,1], button_led(2,1,True))

    def test_library_has_eight_choices_without_discovery(self):
        self.connected(); self.action('90 0a 40'); self.load()
        self.action('90 00 4f')  # third row = + Effet
        self.assertEqual(self.eq.mode, 'library')
        self.assertEqual(len(self.eq.browser_rows()), 8)
        self.assertEqual([r[0] for r in CATALOG], ['eq','comp','reverb','delay','phaser','warm','tube','tape'])
        self.action('b0 54 3f')
        self.assertEqual(self.eq.cursor, 7)
        actions = self.action('90 11 5a')  # ENTER confirms the rotary cursor.
        self.assertEqual(actions[0][2][2], 'tape')

    def test_dsp_knob_controls_compressor_and_stale_catalog_blocks(self):
        self.action('90 03 40'); self.load(2)
        actions = self.action('b0 4e 41')
        self.assertEqual(actions[0][2][:3], [1,2,24])
        self.assertAlmostEqual(actions[0][2][3], 1.1)
        self.r.ready = False; self.now += .01
        self.assertEqual(self.action('b0 4e 41'), [])

    def test_browser_page_and_rotary_share_cursor(self):
        self.connected(); self.action('90 0a 40'); self.eq.tick()
        values = [1]
        for i in range(1,10): values += [i,'Existing '+str(i),1]
        self.r.feed('/strip/plugin/list', values)
        self.action('90 2a 57')
        self.assertEqual((self.eq.plugin_page,self.eq.cursor), (1,8))
        self.action('b0 4d 41')
        self.assertEqual((self.eq.plugin_page,self.eq.cursor), (1,9))
        self.action('90 11 5a')
        self.assertEqual(self.eq.mode, 'library')

    def test_effect_profile_units_order_and_missing_descriptor(self):
        self.connected(); self.action('90 0a 40'); self.eq.tick()
        self.r.feed('/strip/plugin/list', [1,1,'ZamDelay',1]); self.action('90 00 4d')
        self.eq.tick(); self.r.feed('/strip/plugin/list', [1,1,'ZamDelay',1]); self.eq.tick()
        for i,(label,caption,unit,step) in enumerate(profile_for_name('ZamDelay'), 1):
            self.r.feed('/strip/plugin/descriptor', [1,1,i,label,128,0.,0.,8000.,'',0,0.])
        self.r.feed('/strip/plugin/descriptor_end', [1,1])
        self.assertTrue(self.eq.usable())
        actions = self.action('b0 4d 41')
        self.assertEqual(actions[0][2], [1,1,1,5.])
        self.assertEqual(self.eq.parameter_text('Dry/Wet',dict(value=.25,flags=128)), '25%')
        self.now += 1; self.eq.tick(); self.r.feed('/strip/plugin/list', [1,1,'ZamDelay',1])
        self.r.feed('/strip/plugin/descriptor_end', [1,1])
        self.assertFalse(self.eq.usable())

    def test_old_native_module_only_blocks_new_effects(self):
        self.connected(); self.r.feed('/procontrol/plugin/version', [1])
        self.action('90 0a 40'); self.eq.tick(); self.r.feed('/strip/plugin/list', [1])
        self.eq.handle('open', [7])
        self.assertEqual(self.eq.create_error, 'MAJ Ardour')
        self.assertFalse(self.eq.create_pending)
        self.assertEqual(self.eq.tick(), [])
        self.r.feed('/procontrol/plugin/version', [2])
        request = self.eq.handle('open', [7])
        self.assertEqual(request[0][2][2], 'tape')

    def test_native_version_reconnect_and_unknown_protocol(self):
        self.connected(); self.assertEqual(self.eq.creation_version, 2)
        self.r.disconnect()
        self.assertEqual(self.eq.creation_version, 0)
        self.assertFalse(self.eq.creation_supported)
        for bad in ([], [True], [3], ['2']):
            self.eq.feed('/procontrol/plugin/version', bad)
            self.assertFalse(self.eq.creation_supported)

    def test_tape_normalized_units_and_compact_labels(self):
        self.eq.plugin_name = 'CHOWTapeModel'
        self.assertEqual(self.eq.parameter_text('Input Gain', dict(value=30/36, flags=128)), '+0.0dB')
        self.assertEqual(self.eq.parameter_text('Output Gain', dict(value=.5, flags=128)), '+0.0dB')
        self.assertEqual(self.eq.parameter_text('Wow Depth', dict(value=.18, flags=128)), '18%')
        self.assertEqual(self.eq.parameter_text('Wow/Flutter On/Off', dict(value=0., flags=128)), 'OFF')
        for name in ('Valve saturation', 'ZamTube', 'CHOWTapeModel'):
            for _, caption, _, _ in profile_for_name(name):self.assertLessEqual(len(caption), 8)

    def test_normalized_tape_switch_ignores_fine_increment(self):
        self.eq.plugin_name = 'CHOWTapeModel'
        self.eq.params = {'Tape On/Off': dict(id=1, flags=128, low=0., high=1., value=1.)}
        self.r.mapper.modifiers = {1}
        writes = []
        self.eq.write_label = lambda label, value: writes.append((label, value))
        self.eq.turn_parameter(0, -1)
        self.eq.params['Tape On/Off']['value'] = 0.
        self.eq.turn_parameter(0, 1)
        self.assertEqual(writes, [('Tape On/Off', 0), ('Tape On/Off', 1)])

    def test_real_mono_and_stereo_descriptors_bind_all_catalog_profiles(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/curated-live-descriptors.json').read_text())
        for key, entry in fixture.items():
            with self.subTest(plugin=key):
                self.setUp(); self.connected()
                self.action('90 0a 40'); self.eq.tick()
                pid = entry['descriptors'][0][1][1]
                self.r.feed('/strip/plugin/list', [1,pid,entry['name'],1])
                self.action('90 00 4d'); self.eq.tick()
                self.r.feed('/strip/plugin/list', [1,pid,entry['name'],1]); self.eq.tick()
                for path, values in entry['descriptors']:
                    self.r.feed(path, [1]+values[1:])
                self.r.feed('/strip/plugin/descriptor_end',[1,pid])
                self.assertTrue(self.eq.usable(), self.eq.error)
                if self.eq.mode == 'params':
                    for page in range((len(self.eq.parameter_list())+7)//8):
                        self.eq.page = page
                        for knob in range(8):
                            self.now += .001
                            for action in self.action(f'b0 {0x4d+knob:02x} 41'):
                                self.assertEqual(action[1], '/strip/plugin/parameter')
                                self.assertEqual(action[2][:2], [1,pid])


if __name__ == '__main__': unittest.main()
