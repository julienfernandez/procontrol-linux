import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_feedback import SurfaceFeedback,motor
from surface_map import SurfaceMap
from session_probe import Session

class FaderEchoTests(unittest.TestCase):
 def setUp(self):
  self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.f.active[5]=True
  self.s=Session('00:00:00:00:00:01','00:00:00:00:00:02');self.s.online_acked=True
 def ack(self):self.f.acknowledge({'command_field':160,'ack_candidate':self.s.sequence})
 def test_only_exact_physical_position_is_allowed_while_touched(self):
  self.m.touched.add(5)
  self.f.local(('osc','/strip/gain/touch',[5,1]))
  self.f.feed('/strip/fader',[5,.1]);self.assertIsNone(self.f.next_frame(self.s,100))
  self.f.local(('osc','/strip/fader',[5,.8690127077223851]))
  self.f.feed('/strip/fader',[5,.2])
  frame=self.f.next_frame(self.s,100)
  self.assertEqual(frame[30:35],bytes.fromhex('b0 04 6f 24 10'))
 def test_release_echo_bypasses_300ms_holdoff(self):
  self.m.touched.add(5);self.m.fader_moved[5]=100
  self.f.local(('osc','/strip/fader',[5,.8]));self.f.next_frame(self.s,100);self.ack()
  self.m.touched.clear();self.f.local(('osc','/strip/gain/touch',[5,0]))
  frame=self.f.next_frame(self.s,100.003)
  self.assertIsNotNone(frame);self.assertEqual(frame[30:35],motor(5,.8))
 def test_late_daw_echo_cannot_replace_last_physical_target(self):
  self.m.fader_moved[5]=time.monotonic()
  self.f.local(('osc','/strip/fader',[5,.8]))
  self.f.local(('osc','/strip/gain/touch',[5,0]))
  self.f.feed('/strip/fader',[5,.3])
  self.assertEqual(self.f.queue[('motor',5)],motor(5,.8))
 def test_remote_control_resumes_and_reconnect_clears_echo_authority(self):
  self.f.local(('osc','/strip/fader',[5,.8]))
  self.f.feed('/strip/fader',[5,.3])
  self.assertFalse(self.f.is_local_echo(('motor',5)))
  self.assertEqual(self.f.next_frame(self.s,100)[30:35],motor(5,.3))
  self.f.local(('osc','/strip/fader',[5,.7]));self.f.resync()
  self.assertFalse(self.f.is_local_echo(('motor',5)))

if __name__=='__main__':unittest.main()
