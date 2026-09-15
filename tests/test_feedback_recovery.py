import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback,motor,scribble
from session_probe import Session
class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.m=SurfaceMap();self.f=SurfaceFeedback(self.m)
  self.s=Session('00:00:00:00:00:01','00:00:00:00:00:02');self.s.online_acked=True
 def test_missing_ack_recovers_with_latest_value_only(self):
  self.f.put(('name',2),scribble(2,'Unaffected'));self.f.next_frame(self.s,1)
  self.f.acknowledge({'command_field':160,'ack_candidate':self.s.sequence},1.002)
  self.f.put(('name',1),scribble(1,'Old'));self.f.next_frame(self.s,1.010)
  oldseq=self.s.sequence
  self.f.put(('name',1),scribble(1,'New'))
  self.assertIsNone(self.f.next_frame(self.s,1.111))
  self.assertFalse(self.f.needs_refresh);self.assertIsNotNone(self.f.error)
  frame=self.f.next_frame(self.s,1.112);self.assertIn(b'New',frame)
  self.assertNotIn(('name',2),self.f.queue)
  self.assertEqual(self.f.confirmed[('name',2)],scribble(2,'Unaffected'))
  self.f.acknowledge({'command_field':160,'ack_candidate':oldseq},1.113)
  self.assertIsNotNone(self.f.pending)
  self.f.acknowledge({'command_field':160,'ack_candidate':self.s.sequence},1.114)
  self.assertIsNone(self.f.error);self.assertEqual(self.f.counts['recoveries'],1)
  self.assertEqual(self.f.confirmed[('name',1)],scribble(1,'New'))
 def test_recovery_still_respects_touched_motor(self):
  self.f.active[1]=True;self.f.put(('motor',1),motor(1,.2));self.f.next_frame(self.s,1)
  self.m.touched.add(1);self.f.put(('motor',1),motor(1,.8));self.f.next_frame(self.s,1.101)
  self.assertIsNone(self.f.next_frame(self.s,1.102))
  self.m.touched.clear();frame=self.f.next_frame(self.s,1.103)
  self.assertEqual(frame[30:35],motor(1,.8))
 def test_repeated_loss_backs_off_and_is_bounded(self):
  self.f.put(('name',1),scribble(1,'Track'));now=1
  for expected in (0,0,.1,.2,.4,.8,1.6,2,2):
   self.assertIsNotNone(self.f.next_frame(self.s,now))
   self.f.next_frame(self.s,now+.101)
   self.assertAlmostEqual(self.f.retry_after-(now+.101),expected)
   now=self.f.retry_after+.001
  self.assertEqual(self.f.counts['timeouts'],9)
  self.assertTrue(self.f.needs_refresh)
 def test_timeout_deadline_wakes_promptly_without_spin(self):
  self.f.put(('name',1),scribble(1,'Track'));self.f.next_frame(self.s,1)
  self.assertAlmostEqual(self.f.wait_timeout(1.090),.010)
  self.assertGreater(self.f.wait_timeout(1.090),0)
  self.f.next_frame(self.s,1.101)
  self.assertEqual(self.f.wait_timeout(1.101),0)

class ReopenOwnSessionTests(unittest.TestCase):
 def test_reopen_only_when_announcement_names_our_host(self):
  from procontrold import ConsoleSession
  from session_probe import mac_bytes
  host='02:00:00:00:00:01';peer='00:a0:7e:a0:ad:9c'
  console=Session(peer,host)
  for owner,expected in [(host,True),('02:00:00:00:00:03',False)]:
   body=mac_bytes(owner)+bytes(9)+b'1.37'.ljust(9,b'\0')+b'MAINUNIT\0'+b'\0'
   frame=b'\xff'*6+console.frame(0xe1,1,400,body=body)[6:]
   flow=ConsoleSession(host,peer);result,h=flow.receive(frame,100)
   self.assertEqual(bool(result),expected)
   if expected:
    self.assertEqual(result[0][28],0xe2)
    flow.receive(console.frame(0xa0,ack=1),101)
    self.assertEqual(flow.phase,'online')
