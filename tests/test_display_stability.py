import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback, scribble, meter, button_led
from surface_routing import SurfaceRouting
from stereo_bridge import StereoBridge
from surface_settings import DEFAULTS

class DisplayStabilityTests(unittest.TestCase):
 def setUp(self):
  self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.r=SurfaceRouting(self.m,self.f)
  self.r.begin_catalog();self.r.feed('/strip',[1,'AT','Audio',2,2,0,0,0]);self.r.feed('/set_surface',[0]*9)
  self.r.set_lua_catalog('s',[dict(id='a',kind='AT',name='Audio',order=1,hidden=False,channels=2)])
  self.b=StereoBridge(self.r,self.f,copy.deepcopy(DEFAULTS),bind=False)
  self.b.levels={'a':(100,[-10,-20])}
 def test_snapshot_does_not_blackout_strip_meters_or_matrix(self):
  self.r.feed('/strip/select',[1,1]);self.b.render(100)
  left=self.f.desired[('meter',0)]
  self.r.feed('/strip/list',[]);self.r.begin_catalog();self.r.match_identities()
  self.assertEqual(self.r.slots(),[]) # controls remain guarded
  self.assertEqual(self.r.display_slots(),[1])
  self.b.render(100.005);self.r.render_matrix()
  self.assertEqual(self.f.desired[('meter',0)],left)
  self.assertEqual(self.f.desired[('led',23,1)],button_led(23,1,True))
  self.r.feed('/strip',[1,'AT','Audio',2,2,0,0,0]);self.r.feed('/set_surface',[0]*9)
  self.b.render(100.01);self.assertEqual(self.f.desired[('meter',0)],left)
 def test_disconnect_still_blanks_and_stale_audio_still_expires(self):
  self.b.render(100);self.r.feed('/strip/list',[]);self.b.render(102)
  self.assertEqual(self.f.desired[('meter',0)],meter(0,-193))
  self.b.levels['a']=(102,[-10,-20]);self.r.disconnect();self.b.render(102)
  self.assertEqual(self.f.desired[('meter',0)],meter(0,-193))
 def test_db_never_replaced_by_percent_on_fader_or_render(self):
  self.r.feed('/strip/gain',[1,-6.]);self.r.feed('/strip/fader',[1,.7])
  self.assertEqual(self.f.desired[('value',1)],scribble(1,'-6.0 dB',False))
  self.r.render()
  self.assertEqual(self.f.desired[('value',1)],scribble(1,'-6.0 dB',False))
 def test_unsupported_record_state_is_not_lit(self):
  self.r.begin_catalog();self.r.feed('/strip',[1,'MA','Master',2,2,0,0,-1]);self.r.feed('/set_surface',[0]*9)
  self.assertEqual(self.r.cache[('/strip/recenable',1)],[1,0])

if __name__=='__main__':unittest.main()
