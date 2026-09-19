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
        self.r.feed('/procontrol/plugin/version', [1])

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

    def test_library_has_five_choices_without_discovery(self):
        self.connected(); self.action('90 0a 40'); self.load()
        self.action('90 00 4f')  # third row = + Effet
        self.assertEqual(self.eq.mode, 'library')
        self.assertEqual(len(self.eq.browser_rows()), 5)
        self.assertEqual([r[0] for r in CATALOG], ['eq','comp','reverb','delay','phaser'])
        self.action('b0 54 3f')
        self.assertEqual(self.eq.cursor, 4)
        actions = self.action('90 11 5a')  # ENTER confirms the rotary cursor.
        self.assertEqual(actions[0][2][2], 'phaser')

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

    def test_real_mono_and_stereo_descriptors_bind_all_five_profiles(self):
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
