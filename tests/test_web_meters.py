import concurrent.futures,copy,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from web_meters import WebMeters
import test_stereo_settings as fixtures

class MeterSamplingTests(unittest.TestCase):
 def test_concurrent_clients_share_one_rpc_even_on_slow_failure(self):
  meters=WebMeters(Path('/tmp'))
  def fail(*a,**kw):time.sleep(.06);raise OSError('offline')
  with patch('web_meters.rpc',side_effect=fail) as rpc:
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(lambda _:meters.state(),range(8)))
   self.assertEqual(rpc.call_count,1)
   self.assertTrue(all(not v['active'] for v in values))
 def test_success_cache_then_recovery(self):
  m=WebMeters(Path('/tmp'))
  with patch('web_meters.rpc',return_value=dict(ok=True,active=True,strips=[[-3,-9]],large=[])) as rpc:
   self.assertEqual(m.state()['strips'],[[-3,-9]]);self.assertTrue(m.state()['active']);self.assertEqual(rpc.call_count,1)
  m.sampled-=1
  with patch('web_meters.rpc',side_effect=OSError()):self.assertFalse(m.state()['active'])
 def test_raw_stereo_data_staleness_and_no_hardware_side_effect(self):
  f=fixtures.StereoTests();f.setUp();b=f.b
  b.receive('/procontrol/meter',['session',1,1,'a',-10.25,-40.5],1)
  b.receive('/procontrol/meter',['session',1,1,'m',-3.25,-20.5],1)
  before=copy.deepcopy(f.f.queue);frame=b.meter_snapshot(1.1)
  self.assertEqual(frame['strips'][0],[-10.25,-40.5]);self.assertEqual(frame['large'][0]['db'],-3.25)
  self.assertEqual(f.f.queue,before)
  self.assertFalse(b.meter_snapshot(2.01)['active']);self.assertEqual(b.meter_snapshot(2.01)['strips'][0],[-193.,-193.])
  f.r.identity_ready=False;self.assertFalse(b.meter_snapshot(1.2)['active'])
