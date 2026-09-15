import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback, motor, scribble
from session_probe import Session
from audit_diginet import candidate_header
from procontrol_mapping import split_commands


class MotorTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m)
        self.s=Session('00:00:00:00:00:01','00:00:00:00:00:02');self.s.online_acked=True
        self.f.active={i:True for i in range(1,9)}
    def targets(self,v):
        for i in range(1,9):self.f.put(('motor',i),motor(i,v))
    def ack(self,now):
        self.f.acknowledge({'command_field':160,'ack_candidate':self.s.sequence},now)
    def test_eight_latest_targets_share_a_valid_frame_and_ack(self):
        self.targets(.1);self.targets(.7)
        frame=self.f.next_frame(self.s,100);h=candidate_header(frame[14:])
        self.assertEqual(frame[29],8);self.assertTrue(h['body_sum16_match'])
        self.assertEqual(list(split_commands(bytes.fromhex(h['body_hex']))),[motor(i,.7) for i in range(1,9)])
        self.assertEqual(self.f.confirmed,{})
        self.ack(100.002)
        self.assertEqual(len(self.f.confirmed),8);self.assertFalse(self.f.queue)
    def test_motor_rate_leaves_clock_free_and_latest_target_wins(self):
        self.targets(.1);self.f.next_frame(self.s,100);self.ack(100.002)
        self.targets(.3);self.targets(.9)
        self.assertIsNone(self.f.next_frame(self.s,100.005))
        self.assertAlmostEqual(self.f.wait_timeout(100.005),.015)
        self.f.clock('smpte','00:00:01:00')
        clock=self.f.next_frame(self.s,100.006)
        self.assertIn(self.f.desired[('clock',)],clock);self.ack(100.008)
        frame=self.f.next_frame(self.s,100.021)
        self.assertEqual(frame[29],8)
        for i in range(1,9):self.assertIn(motor(i,.9),frame)
    def test_touch_blocks_only_its_motor_and_echo_bypasses_rate(self):
        self.targets(.2);self.f.next_frame(self.s,100);self.ack(100.002)
        self.targets(.8);self.m.touched.add(3)
        self.f.local(('osc','/strip/fader',[3,.4]))
        echo=self.f.next_frame(self.s,100.004)
        self.assertEqual(echo[29],1);self.assertEqual(echo[30:35],motor(3,.4));self.ack(100.006)
        frame=self.f.next_frame(self.s,100.021)
        self.assertEqual(frame[29],7);self.assertNotIn(motor(3,.8),frame)
    def test_loss_under_continuous_automation_converges_without_history(self):
        sent=[];dropped=False
        for tick in range(1201):
            now=100+tick*.001
            if tick<=1000:
                self.targets((tick%173)/173)
                self.f.put(('value',1),scribble(1,str(tick),False))
                if tick%20==0:self.f.clock('smpte',str(tick))
            if self.f.pending and now-self.f.pending[1]>=.002:
                if dropped or tick<300:self.ack(now)
                elif now-self.f.pending[1]>.100:dropped=True
            frame=self.f.next_frame(self.s,now)
            if frame:sent.append((now,frame))
        self.assertEqual(self.f.counts['timeouts'],1)
        self.assertEqual(self.f.counts['recoveries'],1)
        self.assertFalse(self.f.queue);self.assertIsNone(self.f.pending)
        for i in range(1,9):self.assertEqual(self.f.confirmed[('motor',i)],motor(i,(1000%173)/173))
        self.assertLess(max(b[0]-a[0] for a,b in zip(sent,sent[1:])),.105)
        self.assertLessEqual(self.f.motor_batches,51)
