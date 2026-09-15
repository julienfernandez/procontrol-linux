import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback, meter, scribble, motor
from session_probe import Session

class FeedbackLatencyTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m)
        self.s=Session('00:00:00:00:00:01','00:00:00:00:00:02');self.s.online_acked=True
    def ack(self):self.f.acknowledge({'command_field':160,'ack_candidate':self.s.sequence})
    def test_clock_overtakes_meter_backlog(self):
        for i in range(18):self.f.meter_address(i,-12)
        self.f.clock('smpte','00:00:01:02')
        expected=self.f.queue[('clock',)]
        frame=self.f.next_frame(self.s,100)
        self.assertEqual(frame[30:30+len(expected)],expected)
        self.assertIsNone(self.f.next_frame(self.s,100.003)) # still awaiting ACK
    def test_deadline_uses_spacing_not_fixed_sleep(self):
        self.f.meter_address(1,-12);self.f.meter_address(2,-12)
        self.f.next_frame(self.s,100);self.ack()
        self.assertAlmostEqual(self.f.wait_timeout(100.001),.001)
        self.assertIsNotNone(self.f.next_frame(self.s,100.0021))
        self.ack();self.assertEqual(self.f.wait_timeout(101),.05)
    def test_touched_motor_queue_never_busy_spins(self):
        self.f.active[1]=True;self.m.touched.add(1);self.f.put(('motor',1),motor(1,.5))
        self.assertIsNone(self.f.next_frame(self.s,100))
        self.assertEqual(self.f.wait_timeout(100),.05)
    def test_bulk_not_starved_by_continuous_clock(self):
        self.f.put(('name',1),scribble(1,'Track'))
        bodies=[]
        for i in range(5):
            self.f.clock('smpte',f'00:00:01:{i:02d}')
            bodies.append(self.f.next_frame(self.s,100+i*.01));self.ack()
        self.assertTrue(any(scribble(1,'Track') in b for b in bodies))
    def test_return_to_sent_value_cancels_redundant_output(self):
        self.f.meter_address(1,-12);self.f.next_frame(self.s,100);self.ack()
        self.f.meter_address(1,-3);self.f.meter_address(1,-12)
        self.assertNotIn(('meter',1),self.f.queue)
    def test_simulated_ten_hz_stereo_load_and_clock(self):
        # 18 meters + clock changing every 100ms, real measured ACK ~1.4ms.
        sent=0
        for tick in range(1000):
            now=100+tick*.001
            if tick%100==0:
                for i in range(18):self.f.meter_address(i,-12 if tick%200 else -3)
                self.f.clock('smpte',f'00:00:00:{tick//100:02d}')
            if self.f.pending and now-self.f.pending[1]>=.0014:self.ack()
            if self.f.next_frame(self.s,now):sent+=1
        self.assertGreaterEqual(sent,180)
        self.assertEqual(len(self.f.queue),0)

if __name__=='__main__':unittest.main()
