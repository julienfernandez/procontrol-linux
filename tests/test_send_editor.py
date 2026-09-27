import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback,scribble
from surface_routing import SurfaceRouting
from eq_editor import EQEditor
from send_editor import SendEditor

class SendsTests(unittest.TestCase):
 def setUp(self):
  self.now=100.;self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.r=SurfaceRouting(self.m,self.f)
  self.r.rows={i:dict(sid=i,name='Track '+str(i),kind='AT',channels=2) for i in range(1,20)}
  self.r.ready=True;self.r.session='session';self.r.identities={i:'route'+str(i) for i in range(1,20)}
  self.r.start=8;self.r.cache[('/strip/select',9)]=[9,1]
  self.eq=EQEditor(self.r,self.f,lambda:self.now);self.e=SendEditor(self.r,self.f,lambda:self.now)
 def enter(self):
  self.e.handle('toggle',[]);self.assertTrue(self.e.active)
  self.assertEqual(self.e.tick(),[('osc','/strip/sends',[9])])
  self.e.feed('/strip/sends',[9,17,'Reverb',2,.5,1,18,'Delay',5,.25,0])
 def test_absolute_target_and_sparse_send_indexes(self):
  self.enter();self.assertTrue(self.e.usable())
  action=self.e.command(bytes.fromhex('b0 4e 41'))
  self.assertEqual(self.r.actions(action),[('osc','/strip/send/fader',[9,5,.26])])
  self.assertEqual(self.e.handle('enable',[1]),[('osc','/strip/send/enable',[9,5,1.])])
  self.assertEqual(self.e.handle('mute',[0]),[('osc','/strip/send/enable',[9,2,0.])])
 def test_missing_stale_changed_target_prevent_writes(self):
  self.enter();self.now+=2
  self.assertEqual(self.e.handle('turn',[0,3]),[])
  self.now=100;self.r.identities[9]='replacement'
  self.assertEqual(self.e.handle('mute',[0]),[]);self.e.tick();self.assertFalse(self.e.active)
 def test_malformed_and_wrong_reply_ignored(self):
  self.e.enter();self.e.tick()
  for reply in ([10,17,'Bus',1,.5,1],[9,17,'Bus',1,float('nan'),1],[9,17,'Bus',1,.5,1,17,'Bus',1,.2,1]):
   self.e.feed('/strip/sends',reply);self.assertFalse(self.e.ready)
 def test_inflight_reply_does_not_rewind_edit(self):
  self.enter();self.now+=.21;self.e.tick();self.now+=.01
  self.e.handle('turn',[0,10]);self.e.feed('/strip/sends',[9,17,'Reverb',2,.5,1])
  self.assertAlmostEqual(self.e.rows[0]['gain'],.6)
  self.now+=.21;self.e.tick();self.e.feed('/strip/sends',[9,17,'Reverb',2,.45,1])
  self.assertEqual(self.e.rows[0]['gain'],.45)
 def test_modes_and_selection_restore_mix_display(self):
  self.enter();self.f.feed('/strip/gain',[1,-9.])
  self.assertNotEqual(self.f.desired[('value',1)],scribble(1,'-9.0 dB',False))
  self.e.command(bytes.fromhex('90 02 40'));self.assertFalse(self.e.active)
  self.assertEqual(self.f.desired[('value',1)],scribble(1,'-9.0 dB',False))
 def test_page_bounds_empty_sends_and_disconnect(self):
  self.enter();self.e.handle('page',[1]);self.assertEqual(self.e.page,0)
  self.now+=.21;self.e.tick();self.e.feed('/strip/sends',[9]);self.assertTrue(self.e.usable())
  self.assertEqual(self.e.handle('turn',[0,127]),[])
  self.r.disconnect();self.assertFalse(self.e.active)
 def test_retry_deduplication(self):
  self.enter();body=bytes.fromhex('b0 4d 41')
  self.assertTrue(self.r.actions(self.m.route(1,body)))
  self.assertEqual(self.r.actions(self.m.route(1,body)),[])
 def test_no_selected_track_is_noop(self):
  self.r.cache.clear();self.e.enter();self.assertFalse(self.e.active)
