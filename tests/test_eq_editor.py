import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from eq_editor import EQEditor
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback, scribble, button_led
from surface_routing import SurfaceRouting

FIXTURE=json.loads((Path(__file__).parent/'fixtures/lsp-live-descriptors.json').read_text())


class EQTests(unittest.TestCase):
    def setUp(self):
        self.now=100.; self.m=SurfaceMap(); self.f=SurfaceFeedback(self.m)
        self.r=SurfaceRouting(self.m,self.f)
        self.r.rows={i:dict(sid=i,name=f'Track {i}',kind='AT',channels=2) for i in range(1,10)}
        self.r.ready=True
        self.r.cache[('/strip/select',1)]=[1,1]
        self.eq=EQEditor(self.r,self.f,lambda:self.now)

    def action(self,c):
        return self.r.actions(self.m.route(int(self.now*1000),bytes.fromhex(c),self.now))

    def load(self,plugin=1):
        self.eq.tick()
        self.r.feed(*copy.deepcopy(FIXTURE[0]))
        requests=self.eq.tick()
        for a,v in copy.deepcopy(FIXTURE[1:]):
            if v[1]==plugin:self.r.feed(a,v)
        return requests

    def start(self):
        self.action('90 02 40'); self.load(); self.assertTrue(self.eq.usable())

    def test_live_descriptors_bind_correct_control_ids(self):
        self.start()
        old=self.eq.value('frequency')
        result=self.action('b0 40 41')
        self.assertEqual(result[0][0:2],('osc','/strip/plugin/parameter'))
        self.assertEqual(result[0][2][:3],[1,1,27])
        self.assertAlmostEqual(result[0][2][3],old*2**(1/24))
        self.assertEqual(self.f.desired[('value',1)],scribble(1,self.eq.knob_text(0),False))

    def test_unknown_parameters_and_retry_do_not_write(self):
        self.action('90 02 40')
        self.assertEqual(self.action('b0 41 41'),[])
        self.assertEqual(self.action('90 02 40'),[])  # exact Ethernet retry
        self.load()
        first=self.action('b0 41 42');self.assertEqual(len(first),1)
        self.assertEqual(self.action('b0 41 42'),[])

    def test_filter_selection_enable_bypass_preserves_values(self):
        self.start();self.action('90 00 50')
        self.assertEqual(self.eq.filter,3)
        self.assertEqual(self.action('90 00 10'),[])
        self.action('90 01 50')  # Off -> Bell, preserve frequency and gain
        self.assertEqual(self.eq.value('type'),1)
        old=self.eq.value('frequency');self.now+=.01
        self.action('90 02 50');self.assertEqual(self.eq.value('mute'),1)
        self.now+=.01;self.action('90 02 50');self.assertEqual(self.eq.value('mute'),0)
        self.assertEqual(self.eq.value('frequency'),old)

    def test_fine_gain_bounds_and_faders_unaffected(self):
        self.start();self.m.modifiers.add('Shift_L')
        old=self.eq.value('gain');self.action('b0 41 41')
        self.assertAlmostEqual(self.eq.value('gain'),old*10**(.05/20))
        self.eq.params['Frequency 0']['value']=24000
        self.action('b0 40 7f');self.assertEqual(self.eq.value('frequency'),24000)
        self.assertEqual(self.action('b0 00 7f 20 70'),[('osc','/strip/fader',[1,1.])])
        self.action('90 09 40');self.assertIn(1,self.m.touched)

    def test_inflight_snapshot_cannot_rewind_a_turn(self):
        self.start();self.now+=.6;self.eq.tick();self.r.feed(*copy.deepcopy(FIXTURE[0]));self.eq.tick()
        self.now+=.001;self.action('b0 41 42');value=self.eq.value('gain')
        for a,v in copy.deepcopy(FIXTURE[1:]):
            if v[1]==1:self.r.feed(a,v)
        self.assertEqual(self.eq.value('gain'),value)
        self.now+=.6;self.load()
        self.assertEqual(self.eq.value('gain'),1.) # newer DAW snapshot authoritative

    def test_missing_eq_and_partial_snapshot_disable_writes(self):
        self.action('90 02 40');self.eq.tick()
        self.r.feed('/strip/plugin/list',[1,1,'Other',1]);self.assertFalse(self.eq.usable())
        self.assertEqual(self.action('b0 41 42'),[])
        self.now+=1.1;self.eq.tick();self.r.feed(*copy.deepcopy(FIXTURE[0]));self.eq.tick()
        self.r.feed('/strip/plugin/descriptor_end',[1,1]);self.assertFalse(self.eq.usable())

    def test_exit_restores_latest_gain_and_pan_mode(self):
        self.f.feed('/strip/gain',[1,-7.])
        self.start();self.f.feed('/strip/gain',[1,-9.])
        self.assertNotEqual(self.f.desired[('value',1)],scribble(1,'-9.0 dB',False))
        self.action('90 30 57')
        self.assertFalse(self.eq.active);self.assertEqual(self.m.encoder_mode,'pan')
        self.assertEqual(self.f.desired[('value',1)],scribble(1,'-9.0 dB',False))
        self.assertEqual(self.f.desired[('dsp',1)][6:14],b'        ')

    def test_catalog_disconnect_and_bank_change_end_editing(self):
        self.start();self.r.feed('/strip/list',[]);self.assertTrue(self.eq.active)
        self.assertFalse(self.eq.usable());self.assertEqual(self.eq.tick(),[])
        self.r.ready=True;self.load();self.assertTrue(self.eq.usable())
        self.r.disconnect();self.assertFalse(self.eq.active)

    def test_real_catalog_identity_change_closes_mode(self):
        self.start();self.r.feed('/strip/list',[])
        self.r.ready=True;self.r.revision+=1
        self.eq.tick();self.assertFalse(self.eq.active)

    def test_stale_and_foreign_feedback_cannot_write(self):
        self.start();self.r.feed('/strip/plugin/descriptor_end',[2,1])
        self.now+=2;self.assertEqual(self.action('b0 41 41'),[])
        self.eq.tick();self.assertFalse(self.eq.usable())
        self.r.feed('/strip/select',[2,1]);self.assertFalse(self.eq.active)

    def test_browser_open_compressor_and_pages(self):
        self.action('90 02 55');self.load()
        self.assertEqual(self.eq.mode,'browse');self.assertTrue(self.eq.usable())
        self.assertEqual(self.f.desired[('dsp',1)][6:14],b'LSP EQ8 ')
        self.action('90 00 4e');self.load(2)
        self.assertEqual(self.eq.mode,'params');self.assertTrue(self.eq.usable())
        self.assertEqual([n for n,p in self.eq.parameter_list()][:4],['Attack threshold','Ratio','Attack time','Release time'])
        result=self.action('b0 41 41')
        self.assertEqual(result[0][2][:3],[1,2,24]);self.assertAlmostEqual(result[0][2][3],1.1)
        self.action('90 2a 57');self.assertEqual(self.eq.page,1)
        self.m.modifiers.add('Shift_L');self.now+=.01
        self.action('90 2a 57');self.assertEqual(self.eq.page,0)
        self.now+=.01;self.action('90 02 55');self.assertEqual(self.eq.mode,'browse')

    def test_browse_track_navigation_and_no_raw_id_rerouting(self):
        self.r.start=8
        out=self.action('90 02 55')
        self.assertEqual(out,[('osc','/strip/select',[9,0])])
        self.assertEqual(self.eq.tick(),[('osc','/strip/plugin/list',[9])])
        self.r.start=0;self.eq.exit();self.now+=1
        self.action('90 02 55');self.load();self.action('90 06 41')
        self.assertEqual(self.eq.sid,2);self.assertEqual(self.eq.mode,'browse')

    def test_blink_only_target_and_filter(self):
        self.start();self.eq.render(100)
        self.assertEqual(self.f.desired[('led',0,2)],button_led(0,2,True))
        self.assertEqual(self.f.desired[('led',1,2)],button_led(1,2,False))
        self.eq.render(100.25)
        self.assertEqual(self.f.desired[('led',0,2)],button_led(0,2,False))

    def test_no_legacy_refresh_or_periodic_catalog_requests(self):
        self.start();self.now+=.6
        out=self.eq.tick()
        self.assertEqual(out,[('osc','/strip/plugin/list',[1])])
        self.assertEqual(self.eq.tick(),[])

    def test_direct_dyn_entry_and_same_button_exit(self):
        self.start();self.action('90 03 40');self.load(2)
        self.assertEqual(self.eq.mode,'params');self.assertEqual(self.eq.plugin,2)
        self.assertTrue(self.eq.usable());self.now+=.01
        self.action('90 03 40');self.assertFalse(self.eq.active)

    def test_compressor_can_be_first_action_after_startup(self):
        self.action('90 03 40');self.load(2)
        self.assertTrue(self.eq.usable());self.assertEqual(self.eq.plugin,2)

    def test_high_frequency_keeps_unit_in_eight_characters(self):
        self.start();self.eq.params['Frequency 0']['value']=24000
        self.assertEqual(self.eq.knob_text(0),'F1 24.0k')

    def test_matrix_and_bank_navigation_keep_eq_family(self):
        self.start();out=self.action('90 09 57')
        self.assertEqual(self.eq.sid,9);self.assertEqual(self.eq.mode,'eq')
        self.assertEqual(out,[('osc','/strip/select',[9,0])])
        self.action('90 0a 5b');self.assertEqual(self.eq.sid,1)
        self.assertEqual(self.eq.mode,'eq')

    def test_compressor_follows_track_selection(self):
        self.action('90 03 40'); self.load(2)
        out = self.action('90 06 41')
        self.assertEqual(out, [('osc','/strip/select',[2,0])])
        self.assertEqual((self.eq.sid,self.eq.family,self.eq.mode), (2,'comp','params'))
        self.assertFalse(self.eq.ready)

    def test_ambiguous_direct_eq_requires_browser_choice(self):
        self.action('90 02 40');self.eq.tick()
        self.r.feed('/strip/plugin/list',[1,1,'LSP Parametric Equalizer x8 Stereo',1,2,'LSP Parametric Equalizer x8 Stereo',1])
        self.assertFalse(self.eq.usable());self.assertEqual(self.action('b0 40 41'),[])

if __name__=='__main__':unittest.main()
