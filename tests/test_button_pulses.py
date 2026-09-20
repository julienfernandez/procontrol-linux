import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback,button_led,scribble
from session_probe import Session


class ButtonPulseTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap(); self.f=SurfaceFeedback(self.m)
        self.s=Session('00:00:00:00:00:01','00:00:00:00:00:02'); self.s.online_acked=True
        self.key=('led',0x19,6)

    def ack(self,now):
        self.f.acknowledge({'command_field':160,'ack_candidate':self.s.sequence},now)

    def test_forwarded_press_lights_then_restores_without_release(self):
        actions=self.m.route(1,bytes.fromhex('90 06 59'),1)
        self.assertEqual(actions,[('osc','/access_action',['EditorEditing/undo'])])
        self.f.pulse_buttons(self.m.last_button_presses,1)
        self.assertEqual(self.f.desired[self.key],button_led(0x19,6,False))
        self.assertIn(button_led(0x19,6,True),self.f.next_frame(self.s,1.05))
        self.ack(1.06)
        self.assertIsNone(self.f.next_frame(self.s,1.39))
        self.assertAlmostEqual(self.f.wait_timeout(1.39),.01)
        self.assertIn(button_led(0x19,6,False),self.f.next_frame(self.s,1.41))
        self.ack(1.42); self.assertFalse(self.f.pulses)

    def test_retry_hold_release_and_unknown_do_not_trigger_more_pulses(self):
        c=bytes.fromhex('90 06 59')
        self.m.route(1,c); self.assertEqual(self.m.last_button_presses,[(25,6)])
        for seq,data in ((1,c),(2,c),(3,bytes.fromhex('90 06 19')),(4,bytes.fromhex('90 1f 58'))):
            self.m.route(seq,data); self.assertEqual(self.m.last_button_presses,[])
        self.m.route(5,c); self.assertEqual(self.m.last_button_presses,[(25,6)])
        self.m.reset_inputs(); self.assertEqual(self.m.last_button_presses,[])

    def test_real_state_update_and_reconnect_cannot_replay_old_flash(self):
        self.f.pulse_buttons([(25,6)],1);self.f.next_frame(self.s,1);self.ack(1.01)
        self.f.put(self.key,button_led(25,6,True))
        self.assertFalse(self.f.pulses)
        self.assertIsNone(self.f.next_frame(self.s,2))
        self.f.put(self.key,button_led(25,6,False));self.f.next_frame(self.s,2.01);self.ack(2.02)
        self.f.pulse_buttons([(25,6)],3);self.f.next_frame(self.s,3)
        self.f.resync();self.assertFalse(self.f.pulses)
        self.assertEqual(self.f.queue[self.key],button_led(25,6,False))

    def test_lost_ack_retries_current_pulse_then_restores_off(self):
        self.f.pulse_buttons([(25,6)],1);self.f.next_frame(self.s,1)
        self.assertIsNone(self.f.next_frame(self.s,1.101))
        self.assertIn(button_led(25,6,True),self.f.next_frame(self.s,1.102))
        self.ack(1.11)
        self.assertIn(button_led(25,6,False),self.f.next_frame(self.s,1.36))
        self.ack(1.37)
        self.assertFalse(self.f.pulses);self.assertEqual(self.f.counts['timeouts'],1)

    def test_pulse_waits_for_actual_send_but_stale_unsent_pulse_expires(self):
        self.f.pulse_buttons([(25,6)],1)
        self.f.put(('clock',),b'clock')
        self.assertIn(b'clock',self.f.next_frame(self.s,1)); self.ack(1.01)
        self.assertIn(button_led(25,6,True),self.f.next_frame(self.s,1.8));self.ack(1.81)
        self.assertIsNone(self.f.next_frame(self.s,2.14))
        self.assertIn(button_led(25,6,False),self.f.next_frame(self.s,2.16));self.ack(2.17)
        self.f.pulse_buttons([(25,6)],3)
        self.assertIsNone(self.f.next_frame(self.s,4.1))
        self.assertFalse(self.f.pulses)

    def test_repeated_press_coalesces_and_stateful_buttons_are_untouched(self):
        stateful=[(0,0),(0,6),(0,7),(0,8),(8,9),(8,10),(8,11),(21,2),(28,9),(28,16),(27,11)]
        self.f.pulse_buttons(stateful,1);self.assertFalse(self.f.queue)
        self.f.pulse_buttons([(25,6)],1);self.f.next_frame(self.s,1);self.ack(1.01)
        for n in range(10):self.f.pulse_buttons([(25,6)],1.1+n*.01)
        self.assertEqual(len(self.f.pulses),1);self.assertFalse(self.f.queue)
        self.assertIsNone(self.f.next_frame(self.s,1.53))
        self.assertIn(button_led(25,6,False),self.f.next_frame(self.s,1.55))


if __name__=='__main__':unittest.main()
