import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback
from surface_routing import SurfaceRouting
class SendMappingTests(unittest.TestCase):
 def setUp(self):
  self.m=SurfaceMap();self.r=SurfaceRouting(self.m,SurfaceFeedback(self.m))
  self.r.begin_catalog()
  for i in range(1,10):self.r.feed('#reply',['AT',str(i),2,2,0,0,i,0])
  self.r.feed('#reply',['end_route_list',48000,0,0])
 def test_real_gain_and_coalesced_relative_moves(self):
  self.m.encoder_mode='send';a=self.m.command(bytes.fromhex('b0 40 41'),0)
  self.assertEqual(self.r.actions(a),[('osc','/strip/sends',[1])])
  self.assertEqual(self.r.actions(a),[])
  self.r.feed('/strip/sends',[1,9,'Reverb',1,.75,1])
  self.assertEqual(self.r.drain(),[('osc','/strip/send/fader',[1,1,.77])])
  self.assertEqual(self.r.drain(),[])
 def test_late_missing_or_invalid_reply_does_not_write(self):
  a=[('send_delta','',[1,1,.1])]
  for reply in ([1],[1,9,'Reverb',1,float('nan'),1],[1,9,'Reverb']):
   self.r.actions(a);self.r.feed('/strip/sends',reply);self.assertEqual(self.r.drain(),[])
  self.r.actions(a);self.r.send_pending[1]['at']-=2
  self.r.feed('/strip/sends',[1,9,'Reverb',1,.5,1]);self.assertEqual(self.r.drain(),[])
 def test_bank_change_drops_inflight_delta(self):
  self.r.actions([('send_delta','',[1,1,.1])]);self.r.change_bank(8)
  self.r.feed('/strip/sends',[1,9,'Reverb',1,.5,1]);self.assertEqual(self.r.drain(),[])
  self.assertEqual(self.r.actions([('send_delta','',[1,1,.1])]),[('osc','/strip/sends',[9])])
 def test_send_mute_requires_feedback(self):
  c=bytes.fromhex('90 0d 48')
  self.assertEqual(self.m.command(c,0),[('osc','/refresh',[1.0])])
  self.m.feedback('/select/send_enable',[1,1])
  self.assertEqual(self.m.command(c,0),[('osc','/select/send_enable',[1,0])])

 def test_selected_cache_is_not_reused_after_track_or_plugin_change(self):
  self.m.encoder_mode='plugin'
  c=bytes.fromhex('b0 40 41')
  self.m.feedback('/select/plugin/parameter',[1,.6])
  self.assertAlmostEqual(self.m.command(c,0)[0][2][1],.61)
  self.m.feedback('/select/plugin/name',['Other'])
  self.assertEqual(self.m.command(c,0),[('osc','/refresh',[1.0])])
  self.m.feedback('/select/send_enable',[1,1]);self.m.feedback('/select/name',['New track'])
  self.assertNotIn(('/select/send_enable',1),self.m.state)
