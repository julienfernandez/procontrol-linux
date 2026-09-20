# SPDX-License-Identifier: GPL-3.0-or-later
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from console_indicators import ConsoleIndicators, PATH
from surface_feedback import SurfaceFeedback, button_led
from surface_map import SurfaceMap

class ConsoleIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.now=0.
        self.i=ConsoleIndicators(self.m,self.f,clock=lambda:self.now)
    def on(self,n):return self.f.desired.get(('led',28,n))==button_led(28,n,True)
    def accept(self,*names):self.i.accepted([('osc','/access_action',[n]) for n in names])
    def test_range_builder_zero_length_and_reverse_range(self):
        self.i.feed('/position/samples',['100'])
        self.accept('Common/finish-range-from-playhead','Common/start-range-from-playhead')
        self.assertEqual(self.i.range_phase,'in')
        self.now=.6;self.i.tick();self.assertTrue(self.on(2));self.assertFalse(self.on(3))
        self.accept('Common/finish-range-from-playhead');self.assertEqual(self.i.range_phase,'in')
        self.i.feed('/position/samples',['50']);self.accept('Common/finish-range-from-playhead')
        self.assertTrue(self.on(2));self.assertTrue(self.on(3))
        self.accept('EditorEditing/editor-copy');self.assertEqual(self.i.range_phase,'ready')
        self.accept('EditorEditing/editor-delete');self.assertEqual(self.i.range_phase,'idle')
    def test_paused_position_remains_valid_and_disconnect_clears_it(self):
        self.i.feed('/position/samples',['100']);self.now=20
        self.accept('Common/start-range-from-playhead');self.assertEqual(self.i.range_start,100)
        self.i.disconnect();self.assertIsNone(self.i.position);self.assertFalse(self.on(2))
    def test_external_punch_and_record_follow_ardour_not_button_guess(self):
        self.i.feed(PATH,[1,1,1,0,0,1,1]);self.assertTrue(self.on(8));self.assertTrue(self.on(5))
        self.assertFalse(self.on(11));self.assertFalse(self.on(17))
        self.now=.6;self.i.tick();self.assertTrue(self.on(11));self.assertTrue(self.on(17))
        self.i.feed(PATH,[1,0,1,1,0,2,1]);self.now=1.2;self.i.tick()
        self.assertTrue(self.on(11));self.assertTrue(self.on(17));self.assertFalse(self.on(8))
        self.accept('Transport/ToggleExternalSync');self.assertFalse(self.on(8))
        self.f.feed('/rec_enable_toggle',[1.]);self.assertTrue(self.on(17))
    def test_bounded_polling_invalid_packets_and_stale_state(self):
        self.assertEqual(self.i.tick(),[('osc',PATH,[])])
        for _ in range(100):self.assertEqual(self.i.tick(),[])
        for v in ([1,1], [1,1,1,1,0,9,1], [1.,1,1,1,0,1,1]):self.i.feed(PATH,v)
        self.assertIsNone(self.i.transport)
        self.i.feed(PATH,[1,1,1,1,0,1,1]);self.now=.3
        self.assertEqual(self.i.tick(),[('osc',PATH,[])])
        self.now=5.;self.i.tick();self.assertIsNone(self.i.transport)
        self.assertFalse(self.on(8));self.assertFalse(self.on(11));self.assertFalse(self.on(17))
    def test_state_toggles_do_not_repeat_on_held_press(self):
        for n in (5,8,11):
            c=bytes([0x90,n,0x5c]);self.assertTrue(self.m.command(c,0))
            self.assertEqual(self.m.command(c,.1),[])
            self.m.command(bytes([0x90,n,0x1c]),.2)
            self.assertTrue(self.m.command(c,.3));self.m.reset_inputs()
    def test_grab_reenters_range_mode_before_selection(self):
        a=self.m.command(bytes.fromhex('90 0f 5b'),0)
        names=[v[0] for k,p,v in a if p=='/access_action']
        self.assertLess(names.index('EditorEditing/set-mouse-mode-range'),names.index('Editor/select-all-between-cursors'))

if __name__=='__main__':unittest.main()
