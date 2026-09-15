import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from automation_modes import PATH, mode_value, lamp_command
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback
from surface_routing import SurfaceRouting


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.r=SurfaceRouting(self.m,self.f)
        self.r.rows={i:dict(sid=i,name=f'Track {i}',kind='AT',channels=2) for i in range(1,10)}
        self.r.rows[10]=dict(sid=10,name='Master',kind='MA',channels=2)
        self.r.ready=True;self.seq=0

    def press(self,slot=1):
        self.seq+=1
        result=self.r.actions(self.m.route(self.seq,bytes([0x90,5,slot-1+0x40]),100+self.seq))
        self.seq+=1
        self.assertEqual(self.r.actions(self.m.route(self.seq,bytes([0x90,5,slot-1]),100+self.seq)),[])
        return result

    def feed(self,sid,mode):
        self.r.feed('/strip/fader/automation',[sid,mode])

    def test_reference_led_bits_and_zero_based_channel(self):
        for mode,bits in enumerate((0,4,64,32,16)):
            self.assertEqual(lamp_command(1,mode),bytes([240,19,0,32,0,bits,247]))
            self.assertEqual(lamp_command(8,mode)[4],7)
            self.assertEqual(lamp_command(1,mode)[5]&8,0) # TM is not Manual

    def test_gainmode_two_alias_is_canonical(self):
        self.feed(1,3.)
        self.assertEqual(self.r.cache[(PATH,1)],[1,3])
        self.assertEqual(self.m.state[(PATH,1)],3)
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,3))
        self.assertEqual(self.press(),[('osc',PATH,[1,4])])

    def test_whole_cycle_uses_feedback_without_selecting_or_record_arming(self):
        self.feed(1,0)
        for mode in (1,2,3,4,0):
            out=self.press()
            self.assertEqual(out,[('osc',PATH,[1,mode])])
            self.feed(1,float(mode))
            self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,mode))

    def test_shift_cycles_backwards(self):
        self.feed(3,0);self.m.modifiers.add('Shift_L')
        self.assertEqual(self.press(3),[('osc',PATH,[3,4])])
        self.feed(3,4)
        self.assertEqual(self.press(3),[('osc',PATH,[3,3])])

    def test_quick_presses_do_not_repeat_unacknowledged_mode(self):
        self.feed(1,0)
        self.assertEqual([self.press()[0][2][1] for _ in range(3)],[1,2,3])
        self.feed(1,1) # delayed first acknowledgement
        self.assertEqual(self.press(),[('osc',PATH,[1,4])])
        self.feed(1,4)
        self.assertNotIn(1,self.r.automation_pending)

    def test_lamps_wait_for_ardour_not_command_prediction(self):
        self.feed(1,0);self.press()
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,0))
        self.feed(1,1)
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,1))

    def test_external_gui_mode_overrides_pending(self):
        self.feed(1,0);self.press();self.press()
        self.feed(1,4)
        self.assertNotIn(1,self.r.automation_pending)
        self.assertEqual(self.press(),[('osc',PATH,[1,0])])

    def test_timed_out_command_uses_confirmed_mode(self):
        self.feed(1,0)
        with patch('surface_routing.time.monotonic',return_value=100):self.press()
        with patch('surface_routing.time.monotonic',return_value=102):
            self.assertEqual(self.press(),[('osc',PATH,[1,1])])

    def test_bank_restores_known_state_and_clears_empty_strips(self):
        self.feed(1,2);self.feed(9,3);self.r.change_bank(8)
        self.assertEqual(self.m.state[(PATH,1)],3)
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,3))
        self.assertEqual(self.f.desired[('automation',2)],lamp_command(2,None))
        self.assertEqual(self.press(),[('osc',PATH,[9,4])])
        self.assertEqual(self.press(2),[])
        self.r.change_bank(0)
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,2))

    def test_unknown_target_and_disconnection_never_guess_a_mode(self):
        self.assertEqual(self.press(),[])
        self.feed(1,1);self.r.ready=False
        self.r.render();self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,1))
        self.assertEqual(self.press(),[])
        self.r.disconnect()
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,None))
        self.assertEqual(self.press(),[])

    def test_master_bank_routes_absolute_id(self):
        self.feed(10,4)
        self.r.actions([('bank','master',[True])])
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,4))
        self.assertEqual(self.press(),[('osc',PATH,[10,0])])

    def test_held_button_and_ethernet_retry_change_once(self):
        self.feed(1,0);b=bytes.fromhex('90 05 40')
        self.assertEqual(self.r.actions(self.m.route(1,b,100)),[('osc',PATH,[1,1])])
        self.assertEqual(self.m.route(1,b,100),[])
        self.assertEqual(self.m.route(2,b,100.1),[])
        self.m.command(bytes.fromhex('90 05 00'),101)
        self.assertEqual(self.r.actions(self.m.route(3,b,102)),[('osc',PATH,[1,2])])
        self.m.reset_inputs();self.assertFalse(self.m.auto_held)

    def test_invalid_feedback_does_not_change_lights_or_command(self):
        self.feed(1,3)
        for v in (None,-1,5,3.5,float('nan'),float('inf'),True,'Write'):
            self.assertIsNone(mode_value(v));self.feed(1,v)
        self.assertEqual(self.f.desired[('automation',1)],lamp_command(1,3))
        self.assertEqual(self.press(),[('osc',PATH,[1,4])])

    def test_reconnect_resends_current_lamps(self):
        self.feed(1,4);self.f.sent=dict(self.f.desired);self.f.queue.clear()
        self.f.resync()
        self.assertEqual(self.f.queue[('automation',1)],lamp_command(1,4))

    def test_auto_in_eq_does_not_exit_plugin_or_modify_its_parameters(self):
        from eq_editor import EQEditor
        eq=EQEditor(self.r,self.f);eq.handle('enter',[1]);self.feed(1,0)
        self.assertEqual(self.press(),[('osc',PATH,[1,1])])
        self.assertTrue(eq.active)

if __name__=='__main__':unittest.main()
